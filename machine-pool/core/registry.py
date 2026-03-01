"""Machine registry — load and query machines from registry.yaml."""
from pathlib import Path
from typing import List, Optional
import yaml

REGISTRY_FILE = Path(__file__).parent.parent / "machines" / "registry.yaml"


class Machine:
    def __init__(self, data: dict):
        self.id       = data["id"]
        self.label    = data.get("label", self.id)
        self.host     = data["host"]
        self.user     = data.get("user", "root")
        self.ssh_key  = data.get("ssh_key")
        self.sudo     = data.get("sudo", False)
        self.enabled  = data.get("enabled", True)
        self.tags     = set(data.get("tags", []))
        self.specs    = data.get("specs", {})
        self.location = data.get("location", {})
        self.notes    = data.get("notes", "")
        self.is_local = (self.host in ("localhost", "127.0.0.1") or self.ssh_key is None and self.host == "localhost")

    def matches(self, require_tags: List[str] = None, min_specs: dict = None, location: str = None) -> bool:
        """Check if machine satisfies requirements."""
        if not self.enabled:
            return False
        if require_tags:
            if not all(t in self.tags for t in require_tags):
                return False
        if min_specs:
            for key, val in min_specs.items():
                if self.specs.get(key, 0) < val:
                    return False
        if location:
            if self.location.get("region") != location and self.location.get("country") != location:
                return False
        return True

    def __repr__(self):
        return f"<Machine {self.id} host={self.host} tags={sorted(self.tags)}>"


class Registry:
    def __init__(self, path: Path = REGISTRY_FILE):
        self._path = path
        self._machines: List[Machine] = []
        self.reload()

    def reload(self):
        data = yaml.safe_load(self._path.read_text())
        self._machines = [Machine(m) for m in data.get("machines", [])]

    @property
    def all(self) -> List[Machine]:
        return list(self._machines)

    @property
    def enabled(self) -> List[Machine]:
        return [m for m in self._machines if m.enabled]

    def get(self, machine_id: str) -> Optional[Machine]:
        for m in self._machines:
            if m.id == machine_id:
                return m
        return None

    def find(self, require_tags=None, min_specs=None, location=None) -> List[Machine]:
        """Return all enabled machines matching the given requirements."""
        return [m for m in self.enabled if m.matches(require_tags, min_specs, location)]

    def best(self, require_tags=None, min_specs=None, location=None) -> Optional[Machine]:
        """Return the best single machine for a task (currently: first match; extend with load-balancing)."""
        candidates = self.find(require_tags, min_specs, location)
        return candidates[0] if candidates else None
