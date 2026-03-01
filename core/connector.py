"""SSH connector — run commands on local or remote machines."""
import subprocess
import shlex
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    machine_id: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def __str__(self):
        out = self.stdout.strip()
        err = self.stderr.strip()
        return out if out else err


class Connector:
    def __init__(self, machine):
        self.machine = machine

    def run(self, command: str, timeout: int = 60, sudo: bool = False) -> ExecResult:
        """Run command on the machine. Returns ExecResult."""
        if sudo and self.machine.sudo:
            command = f"sudo {command}"

        if self.machine.is_local:
            return self._run_local(command, timeout)
        else:
            return self._run_ssh(command, timeout)

    def _run_local(self, command: str, timeout: int) -> ExecResult:
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return ExecResult(proc.returncode, proc.stdout, proc.stderr, self.machine.id)
        except subprocess.TimeoutExpired:
            return ExecResult(-1, "", "Timeout", self.machine.id)
        except Exception as e:
            return ExecResult(-1, "", str(e), self.machine.id)

    def _run_ssh(self, command: str, timeout: int) -> ExecResult:
        ssh_args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
        if self.machine.ssh_key:
            key = str(self.machine.ssh_key).replace("~", __import__("os").path.expanduser("~"))
            ssh_args += ["-i", key]
        ssh_args += [f"{self.machine.user}@{self.machine.host}", command]

        try:
            proc = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
            return ExecResult(proc.returncode, proc.stdout, proc.stderr, self.machine.id)
        except subprocess.TimeoutExpired:
            return ExecResult(-1, "", "SSH timeout", self.machine.id)
        except Exception as e:
            return ExecResult(-1, "", str(e), self.machine.id)

    def ping(self, timeout: int = 5) -> bool:
        """Quick connectivity check."""
        result = self._run_local(f"ping -c 1 -W {timeout} {self.machine.host}", timeout + 2)
        return result.ok or self.machine.is_local

    def copy_to(self, local_path: str, remote_path: str) -> ExecResult:
        """Copy a file to the machine (scp). No-op for local."""
        if self.machine.is_local:
            if local_path != remote_path:
                return self._run_local(f"cp -r {shlex.quote(local_path)} {shlex.quote(remote_path)}", 30)
            return ExecResult(0, "same machine, skipped", "", self.machine.id)

        scp_args = ["scp", "-o", "StrictHostKeyChecking=no"]
        if self.machine.ssh_key:
            key = str(self.machine.ssh_key).replace("~", __import__("os").path.expanduser("~"))
            scp_args += ["-i", key]
        scp_args += [local_path, f"{self.machine.user}@{self.machine.host}:{remote_path}"]

        try:
            proc = subprocess.run(scp_args, capture_output=True, text=True, timeout=120)
            return ExecResult(proc.returncode, proc.stdout, proc.stderr, self.machine.id)
        except Exception as e:
            return ExecResult(-1, "", str(e), self.machine.id)
