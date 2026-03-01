"""
Task dispatcher — select the best machine for a task and run it.

Routing strategy (extensible):
1. Filter by requirements (tags, min specs, location)
2. Among candidates, prefer machines with lower load
3. If tie, prefer local over remote
"""
from typing import Optional, List
from .registry import Registry, Machine
from .connector import Connector, ExecResult
from .health import HealthChecker, MachineHealth


class Dispatcher:
    def __init__(self, registry: Registry):
        self.registry = registry

    def select(
        self,
        require_tags: List[str] = None,
        min_specs: dict = None,
        location: str = None,
        prefer_low_load: bool = True,
    ) -> Optional[Machine]:
        """Select best machine for a task based on requirements."""
        candidates = self.registry.find(require_tags, min_specs, location)
        if not candidates:
            return None

        if not prefer_low_load or len(candidates) == 1:
            return candidates[0]

        # Score by load (lower is better). Skip health check if only one candidate.
        scored = []
        for m in candidates:
            try:
                h = HealthChecker(m).check()
                if not h.reachable:
                    continue
                # Score: weight CPU + GPU util + RAM usage
                score = (
                    (h.cpu_pct or 50) * 0.4 +
                    (h.gpu_util_pct or 0) * 0.4 +
                    (h.ram_pct or 50) * 0.2
                )
                # Prefer local
                if m.is_local:
                    score -= 10
                scored.append((score, m))
            except Exception:
                scored.append((999, m))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0])
        return scored[0][1]

    def run(
        self,
        command: str,
        require_tags: List[str] = None,
        min_specs: dict = None,
        location: str = None,
        machine_id: str = None,
        sudo: bool = False,
        timeout: int = 60,
    ) -> ExecResult:
        """Select a machine and run a command on it."""
        if machine_id:
            machine = self.registry.get(machine_id)
            if not machine:
                raise ValueError(f"Machine '{machine_id}' not found")
        else:
            machine = self.select(require_tags, min_specs, location)
            if not machine:
                raise RuntimeError(
                    f"No machine available for tags={require_tags} "
                    f"min_specs={min_specs} location={location}"
                )

        print(f"[Dispatch] → {machine.id} ({machine.host}): {command[:80]}")
        conn = Connector(machine)
        return conn.run(command, timeout=timeout, sudo=sudo)

    def broadcast(
        self,
        command: str,
        require_tags: List[str] = None,
        sudo: bool = False,
        timeout: int = 60,
    ) -> List[ExecResult]:
        """Run command on ALL matching machines simultaneously."""
        import concurrent.futures
        machines = self.registry.find(require_tags)
        if not machines:
            return []

        def _run(m):
            return Connector(m).run(command, timeout=timeout, sudo=sudo)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(machines)) as ex:
            futures = {ex.submit(_run, m): m for m in machines}
            return [f.result() for f in concurrent.futures.as_completed(futures)]
