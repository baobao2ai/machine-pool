#!/usr/bin/env bash
# =============================================================================
# init.sh — Initialize a machine-pool node
# Safe to run multiple times (idempotent).
# =============================================================================
set -euo pipefail

MACHINE_POOL_PUBKEY="${MACHINE_POOL_PUBKEY:-}"
LOG_PREFIX="[init.sh]"

info()  { echo "$LOG_PREFIX ✅ $*"; }
warn()  { echo "$LOG_PREFIX ⚠️  $*"; }
step()  { echo ""; echo "$LOG_PREFIX ── $* ──"; }

# ── 0. Basic checks ───────────────────────────────────────────────────────────
step "System info"
echo "  Host:    $(hostname)"
echo "  OS:      $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY | cut -d= -f2 | tr -d '\"')"
echo "  Kernel:  $(uname -r)"
echo "  User:    $(whoami)"
echo "  Date:    $(date)"

# ── 1. System updates ─────────────────────────────────────────────────────────
step "Package update"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
info "System packages up to date"

# ── 2. Common packages ────────────────────────────────────────────────────────
step "Installing common packages"
PACKAGES=(
    # Essentials
    curl wget git vim htop tmux
    # System tools
    lsof net-tools dnsutils iotop sysstat
    # Network
    iperf3 nmap openssh-server
    # Hardware info
    pciutils usbutils dmidecode lshw
    # Python
    python3 python3-pip python3-venv python3.12-venv
    # Build tools
    build-essential pkg-config
    nvtop
)

for pkg in "${PACKAGES[@]}"; do
    if dpkg -l "$pkg" &>/dev/null; then
        : # already installed, skip silently
    else
        sudo apt-get install -y -qq "$pkg" 2>/dev/null && echo "  + $pkg" || warn "Could not install $pkg (skipping)"
    fi
done
info "Common packages ready"

# ── 3. SSH hardening: prefer key auth, keep passwd as fallback ────────────────
step "SSH configuration"
SSHD_CONFIG="/etc/ssh/sshd_config"

# Check current auth method
PUBKEY_AUTH=$(grep -i "^PubkeyAuthentication" $SSHD_CONFIG 2>/dev/null | awk '{print $2}' || echo "not set")
PASSWD_AUTH=$(grep -i "^PasswordAuthentication" $SSHD_CONFIG 2>/dev/null | awk '{print $2}' || echo "not set")

echo "  Current: PubkeyAuthentication=$PUBKEY_AUTH, PasswordAuthentication=$PASSWD_AUTH"

# Enable key auth (idempotent sed)
sudo sed -i 's/^#*\s*PubkeyAuthentication.*/PubkeyAuthentication yes/' $SSHD_CONFIG
# Disable password auth (only if a key is already present for this user)
if [ -s ~/.ssh/authorized_keys ]; then
    sudo sed -i 's/^#*\s*PasswordAuthentication.*/PasswordAuthentication no/' $SSHD_CONFIG
    info "SSH: key auth enabled, password auth disabled (key found)"
else
    warn "SSH: no authorized_keys found — keeping password auth enabled for safety"
    sudo sed -i 's/^#*\s*PasswordAuthentication.*/PasswordAuthentication yes/' $SSHD_CONFIG
fi

# Inject machine-pool public key if provided
if [ -n "$MACHINE_POOL_PUBKEY" ]; then
    mkdir -p ~/.ssh && chmod 700 ~/.ssh
    if ! grep -qF "$MACHINE_POOL_PUBKEY" ~/.ssh/authorized_keys 2>/dev/null; then
        echo "$MACHINE_POOL_PUBKEY" >> ~/.ssh/authorized_keys
        chmod 600 ~/.ssh/authorized_keys
        info "SSH: machine-pool public key injected"
    else
        info "SSH: machine-pool public key already present"
    fi
fi

# Reload SSH without kicking current session
sudo systemctl reload sshd 2>/dev/null || sudo systemctl reload ssh 2>/dev/null || sudo service ssh reload 2>/dev/null || true
info "SSH service reloaded"

# ── 4. Firewall (ufw) — allow SSH ─────────────────────────────────────────────
step "Firewall"
if command -v ufw &>/dev/null; then
    sudo ufw allow OpenSSH >/dev/null
    if ! sudo ufw status | grep -q "Status: active"; then
        sudo ufw --force enable >/dev/null
    fi
    info "UFW: SSH allowed"
else
    warn "ufw not found — skipping firewall config"
fi

# ── 5. Python venv for machine-pool agent scripts ─────────────────────────────
step "Python environment"
VENV_DIR="$HOME/.machine-pool-venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    info "Created venv at $VENV_DIR"
else
    info "Venv already exists at $VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet pyyaml psutil requests
info "Python packages ready"

# ── 6. Sudo access check ──────────────────────────────────────────────────────
step "Sudo access"
if sudo -n true 2>/dev/null; then
    info "Passwordless sudo available"
else
    warn "Sudo requires password — consider adding to sudoers for automation"
fi

# ── 7. Hostname ───────────────────────────────────────────────────────────────
step "Hostname"
echo "  Current hostname: $(hostname)"
if [ -n "${SET_HOSTNAME:-}" ]; then
    sudo hostnamectl set-hostname "$SET_HOSTNAME"
    info "Hostname set to $SET_HOSTNAME"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "$LOG_PREFIX ════════════════════════════════"
echo "$LOG_PREFIX  Init complete on $(hostname)"
echo "$LOG_PREFIX  $(date)"
echo "$LOG_PREFIX ════════════════════════════════"
