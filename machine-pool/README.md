# machine-pool

Manage a pool of Linux machines. Distribute tasks based on specs, tags, and location.

## Quick Start

```bash
cd ~/machine-pool

# List machines
python cli/mp.py list

# Health check all
python cli/mp.py status

# Health check specific machine
python cli/mp.py status home-4090

# Run command on best GPU machine
python cli/mp.py run "nvidia-smi" --tags gpu

# Run on specific machine
python cli/mp.py run "df -h" --on home-4090

# Run on all machines
python cli/mp.py broadcast "uptime"

# Find machines with GPU + 16GB+ VRAM
python cli/mp.py find --tags gpu --min-vram 16
```

## Adding a Machine

Edit `machines/registry.yaml`:

```yaml
- id: my-server
  label: "Description"
  host: 192.168.x.x
  user: ubuntu
  ssh_key: ~/.ssh/id_rsa
  sudo: true
  enabled: true
  tags: [gpu, cloud, training]
  specs:
    gpu: "A100"
    vram_gb: 80
    cpu_cores: 32
    ram_gb: 256
    storage_gb: 500
    os: linux
  location:
    region: us-east
    country: US
```

## Architecture

```
core/registry.py     — load/query machine registry
core/connector.py    — SSH + local command execution
core/health.py       — collect CPU/RAM/GPU/disk stats
core/dispatcher.py   — route tasks to best machine
cli/mp.py            — command-line interface
machines/registry.yaml — machine definitions
```

## Task Routing (Dispatcher)

The dispatcher selects machines by:
1. **Tags** — `gpu`, `high-vram`, `home`, `cloud`, `training`, etc.
2. **Min specs** — `vram_gb >= 24`, `ram_gb >= 64`, etc.
3. **Location** — `home`, `us-east`, `EU`, etc.
4. **Load** — prefers machines with lower CPU/GPU utilization

## Roadmap

- [ ] Task queue (async job submission)
- [ ] Persistent job history + logs
- [ ] Auto-discover new machines on local network
- [ ] Slack/Discord notifications on job complete
- [ ] Cost-aware routing (prefer free/cheap machines first)
- [ ] Health dashboard (web UI)
