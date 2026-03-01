# machine-pool TODOs

## In Progress
- [x] Register home-4090 (localhost, RTX 4090)
- [x] Register minipc (172.28.195.237, Ryzen 9 7940HS)
- [x] init.sh — idempotent machine initialization script
- [x] profile_machine.sh — hardware + network profiler → JSON
- [x] SSH key-based auth (id_machine_pool shared key)

## Next Up

### Core
- [ ] **Task queue** — async job submission with status tracking (pending/running/done/failed)
- [ ] **Job history** — persist all runs to SQLite: machine, command, duration, exit code, output
- [ ] **Auto-profile on register** — run profile_machine.sh automatically when adding a machine to registry
- [ ] **Health cron** — run `mp status` every 30min, store time-series, alert on unreachable

### Dispatcher
- [ ] **Real load-aware routing** — use live CPU/GPU stats from health check before dispatch
- [ ] **GPU task routing** — route image-gen and training to home-4090 automatically
- [ ] **CPU task routing** — route crawling and data processing to minipc
- [ ] **Retry logic** — if a machine fails mid-task, retry on next available

### Machines
- [ ] **Auto-discover** — scan local subnet for new machines running SSH
- [ ] **ZeroTier integration** — manage ZeroTier membership for remote machines
- [ ] **Add cloud machines** — set up at least one cloud GPU (Lambda Labs / Vast.ai / RunPod)

### Network / Profiling
- [ ] **iperf3 bandwidth test** — need iperf3 server on home-4090 to test real LAN throughput to minipc
- [ ] **Latency matrix** — measure ping between all machines and store in profiles
- [ ] **Periodic re-profile** — run profile_machine.sh weekly, detect hardware/config changes

### Interface
- [ ] **Discord status command** — `!pool status` → posts machine health table to Discord
- [ ] **Web dashboard** — simple Flask/FastAPI page showing machine pool health (future)
- [ ] **Notifications** — Discord alert when machine goes offline or task fails

### Integration
- [ ] **flux-girl integration** — dispatcher routes image gen to home-4090, data crawling to minipc
- [ ] **idle-runner integration** — idle-runner picks machine automatically based on task type
- [ ] **Cost tracking** — if cloud machines added, track estimated cost per task

## Ideas / Research
- Could ZeroTier be used as the private LAN for all pool machines? (already using it)
- Consider Fabric (Python SSH library) as connector backend for richer remote execution
- Ansible for more complex multi-machine provisioning? (init.sh covers basics for now)
- Netdata or Prometheus for time-series machine monitoring
