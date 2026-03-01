#!/usr/bin/env bash
# =============================================================================
# profile_machine.sh — Hardware + network profiling for machine-pool
# Outputs JSON to stdout; redirect to a file for storage.
# Safe to run multiple times.
# =============================================================================
set -uo pipefail

OUTPUT_FILE="${1:-}"   # Optional: path to write JSON output

# Helper: JSON-safe string
jsons() { echo "$*" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\n'; }

# ── Collect ───────────────────────────────────────────────────────────────────

HOSTNAME=$(hostname)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OS=$(lsb_release -ds 2>/dev/null || grep PRETTY /etc/os-release | cut -d= -f2 | tr -d '"')
KERNEL=$(uname -r)
ARCH=$(uname -m)

# CPU
CPU_MODEL=$(grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | xargs 2>/dev/null || echo "unknown")
CPU_CORES=$(nproc)
CPU_THREADS=$(grep -c ^processor /proc/cpuinfo)
CPU_MHZ=$(grep -m1 "cpu MHz" /proc/cpuinfo | cut -d: -f2 | xargs | cut -d. -f1 2>/dev/null || echo "?")

# RAM
RAM_TOTAL_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
RAM_TOTAL_GB=$(echo "scale=1; $RAM_TOTAL_KB / 1048576" | bc)
SWAP_TOTAL_KB=$(grep SwapTotal /proc/meminfo | awk '{print $2}')
SWAP_TOTAL_GB=$(echo "scale=1; $SWAP_TOTAL_KB / 1048576" | bc)

# Disk
DISK_INFO=$(df -BG / | tail -1)
DISK_TOTAL=$(echo $DISK_INFO | awk '{print $2}' | tr -d G)
DISK_USED=$(echo $DISK_INFO | awk '{print $3}' | tr -d G)
DISK_FREE=$(echo $DISK_INFO | awk '{print $4}' | tr -d G)

# All block devices
BLOCK_DEVICES=$(lsblk -dno NAME,SIZE,TYPE,MODEL 2>/dev/null | grep -v loop | head -10 || echo "unavailable")

# GPU
GPU_INFO=""
GPU_COUNT=0
if command -v nvidia-smi &>/dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total,driver_version,power.limit \
        --format=csv,noheader,nounits 2>/dev/null || echo "")
    GPU_COUNT=$(echo "$GPU_INFO" | grep -c . 2>/dev/null || echo 0)
fi
if [ -z "$GPU_INFO" ]; then
    GPU_INFO=$(lspci 2>/dev/null | grep -i "vga\|display\|3d\|gpu" || echo "none detected")
fi

# Network interfaces
NET_INTERFACES=$(ip -o link show | awk -F': ' '{print $2}' | grep -v lo | tr '\n' ',')
NET_IPS=$(ip -o -4 addr show | grep -v "127\." | awk '{print $2"="$4}' | tr '\n' ',')

# Network bandwidth test (iperf3 to Google DNS — just latency; real iperf needs server)
PING_LAN=""
PING_WAN=""
PING_LAN=$(ping -c 3 -W 2 8.8.8.8 2>/dev/null | tail -1 | awk -F'/' '{print $5}' || echo "?")
# DNS latency
DNS_LATENCY=$(dig +stats google.com 2>/dev/null | grep "Query time" | awk '{print $4}' || echo "?")

# Internet speed via curl (rough estimate: download 10MB)
DOWNLOAD_MBPS="?"
DL_START=$(date +%s%N)
curl -s -o /dev/null --max-time 10 \
    "https://speed.cloudflare.com/__down?bytes=10000000" 2>/dev/null && \
DL_END=$(date +%s%N) && \
DL_ELAPSED=$(echo "scale=3; ($DL_END - $DL_START) / 1000000000" | bc) && \
DOWNLOAD_MBPS=$(echo "scale=1; 10 / $DL_ELAPSED * 8" | bc) || true

# Uptime
UPTIME=$(uptime -p 2>/dev/null || uptime)
LOAD=$(cat /proc/loadavg | awk '{print $1, $2, $3}')

# SSH auth method
SSH_PUBKEY=$(grep -i "^PubkeyAuthentication" /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo "yes")
SSH_PASSWD=$(grep -i "^PasswordAuthentication" /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo "yes")

# ── Output JSON ───────────────────────────────────────────────────────────────

JSON=$(cat <<EOF
{
  "profiled_at": "$TIMESTAMP",
  "hostname": "$(jsons $HOSTNAME)",
  "os": "$(jsons $OS)",
  "kernel": "$(jsons $KERNEL)",
  "arch": "$ARCH",
  "cpu": {
    "model": "$(jsons $CPU_MODEL)",
    "cores": $CPU_CORES,
    "threads": $CPU_THREADS,
    "mhz": "$CPU_MHZ"
  },
  "memory": {
    "ram_gb": $RAM_TOTAL_GB,
    "swap_gb": $SWAP_TOTAL_GB
  },
  "storage": {
    "root_total_gb": $DISK_TOTAL,
    "root_used_gb": $DISK_USED,
    "root_free_gb": $DISK_FREE,
    "block_devices": "$(jsons $BLOCK_DEVICES)"
  },
  "gpu": {
    "count": $GPU_COUNT,
    "info": "$(jsons $GPU_INFO)"
  },
  "network": {
    "interfaces": "$(jsons $NET_INTERFACES)",
    "ips": "$(jsons $NET_IPS)",
    "ping_wan_ms": "$PING_LAN",
    "dns_latency_ms": "$DNS_LATENCY",
    "download_mbps": "$DOWNLOAD_MBPS"
  },
  "ssh": {
    "pubkey_auth": "$SSH_PUBKEY",
    "password_auth": "$SSH_PASSWD"
  },
  "system": {
    "uptime": "$(jsons $UPTIME)",
    "load_avg": "$LOAD"
  }
}
EOF
)

echo "$JSON"

if [ -n "$OUTPUT_FILE" ]; then
    echo "$JSON" > "$OUTPUT_FILE"
    echo "[profile] Written to $OUTPUT_FILE" >&2
fi
