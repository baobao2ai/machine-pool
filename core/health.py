"""Health checker — collect real-time stats from machines."""
from dataclasses import dataclass, field
from typing import Optional
from .connector import Connector


@dataclass
class MachineHealth:
    machine_id: str
    reachable: bool
    cpu_pct: Optional[float] = None
    ram_used_gb: Optional[float] = None
    ram_total_gb: Optional[float] = None
    gpu_name: Optional[str] = None
    gpu_vram_used_mb: Optional[int] = None
    gpu_vram_total_mb: Optional[int] = None
    gpu_util_pct: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    load_avg: Optional[str] = None
    uptime: Optional[str] = None
    errors: list = field(default_factory=list)

    @property
    def ram_pct(self):
        if self.ram_used_gb and self.ram_total_gb:
            return round(self.ram_used_gb / self.ram_total_gb * 100, 1)
        return None

    @property
    def gpu_vram_pct(self):
        if self.gpu_vram_used_mb and self.gpu_vram_total_mb:
            return round(self.gpu_vram_used_mb / self.gpu_vram_total_mb * 100, 1)
        return None

    def summary(self) -> str:
        if not self.reachable:
            return f"[{self.machine_id}] ❌ unreachable"
        parts = [f"[{self.machine_id}] ✅"]
        if self.cpu_pct is not None:
            parts.append(f"CPU {self.cpu_pct:.0f}%")
        if self.ram_pct is not None:
            parts.append(f"RAM {self.ram_pct}% ({self.ram_used_gb:.1f}/{self.ram_total_gb:.0f}GB)")
        if self.gpu_name:
            parts.append(f"GPU {self.gpu_name}")
            if self.gpu_util_pct is not None:
                parts.append(f"util {self.gpu_util_pct:.0f}%")
            if self.gpu_vram_pct is not None:
                parts.append(f"VRAM {self.gpu_vram_pct}% ({self.gpu_vram_used_mb}/{self.gpu_vram_total_mb}MB)")
        if self.load_avg:
            parts.append(f"load {self.load_avg}")
        return " | ".join(parts)


class HealthChecker:
    def __init__(self, machine):
        self.machine = machine
        self.conn = Connector(machine)

    def check(self) -> MachineHealth:
        h = MachineHealth(machine_id=self.machine.id, reachable=False)

        # Reachability
        if not self.conn.ping():
            return h
        h.reachable = True

        # CPU + RAM + load + uptime (single command)
        r = self.conn.run(
            "cat /proc/loadavg && free -m && uptime -p 2>/dev/null || uptime"
        )
        if r.ok:
            lines = r.stdout.strip().splitlines()
            if lines:
                h.load_avg = lines[0].split()[:3]
                h.load_avg = " ".join(h.load_avg)
            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    total, used = int(parts[1]), int(parts[2])
                    h.ram_total_gb = round(total / 1024, 1)
                    h.ram_used_gb  = round(used / 1024, 1)
                if "up " in line and ("min" in line or "hour" in line or "day" in line):
                    h.uptime = line.strip()
        else:
            h.errors.append(f"sys stats: {r.stderr[:80]}")

        # CPU % (1-second sample)
        r = self.conn.run(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d. -f1"
        )
        if r.ok and r.stdout.strip().isdigit():
            h.cpu_pct = float(r.stdout.strip())

        # GPU (nvidia-smi)
        r = self.conn.run(
            "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total "
            "--format=csv,noheader,nounits 2>/dev/null"
        )
        if r.ok and r.stdout.strip():
            for line in r.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    h.gpu_name          = parts[0]
                    h.gpu_util_pct      = float(parts[1]) if parts[1].isdigit() else None
                    h.gpu_vram_used_mb  = int(parts[2]) if parts[2].isdigit() else None
                    h.gpu_vram_total_mb = int(parts[3]) if parts[3].isdigit() else None
                    break  # first GPU only for now

        # Disk
        r = self.conn.run("df -BG / | tail -1 | awk '{print $2, $3}'")
        if r.ok and r.stdout.strip():
            parts = r.stdout.strip().split()
            if len(parts) == 2:
                h.disk_total_gb = float(parts[0].rstrip("G"))
                h.disk_used_gb  = float(parts[1].rstrip("G"))

        return h
