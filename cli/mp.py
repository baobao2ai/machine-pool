#!/usr/bin/env python3
"""
mp — machine-pool CLI

Commands:
  mp list                          List all registered machines
  mp status [machine_id]           Health check one or all machines
  mp run <cmd> [--tags t1,t2]     Run command on best-matched machine
  mp run <cmd> --on <machine_id>  Run command on specific machine
  mp broadcast <cmd> [--tags ...]  Run command on all matching machines
  mp find --tags t1,t2            Show machines matching requirements
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import Registry, HealthChecker, Dispatcher


def cmd_list(registry, args):
    machines = registry.all
    if not machines:
        print("No machines registered.")
        return
    print(f"{'ID':<20} {'HOST':<20} {'TAGS':<40} {'STATUS'}")
    print("-" * 90)
    for m in machines:
        status = "✅ enabled" if m.enabled else "⏸ disabled"
        tags = ", ".join(sorted(m.tags))
        print(f"{m.id:<20} {m.host:<20} {tags:<40} {status}")


def cmd_status(registry, args):
    machines = [registry.get(args.machine_id)] if args.machine_id else registry.enabled
    machines = [m for m in machines if m]
    if not machines:
        print("No machines found.")
        return

    for m in machines:
        print(f"\nChecking {m.id} ({m.label})...")
        h = HealthChecker(m).check()
        print(f"  {h.summary()}")
        if h.uptime:
            print(f"  Uptime: {h.uptime}")
        if h.disk_total_gb:
            disk_pct = round(h.disk_used_gb / h.disk_total_gb * 100, 1)
            print(f"  Disk: {h.disk_used_gb:.0f}/{h.disk_total_gb:.0f}GB ({disk_pct}%)")
        if h.errors:
            print(f"  Warnings: {'; '.join(h.errors)}")


def cmd_run(registry, args):
    dispatcher = Dispatcher(registry)
    tags = args.tags.split(",") if args.tags else None
    specs = {}
    if args.min_vram:
        specs["vram_gb"] = int(args.min_vram)
    if args.min_ram:
        specs["ram_gb"] = int(args.min_ram)

    result = dispatcher.run(
        args.command,
        require_tags=tags,
        min_specs=specs or None,
        location=args.location,
        machine_id=args.on,
        sudo=args.sudo,
        timeout=args.timeout,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    sys.exit(result.returncode)


def cmd_broadcast(registry, args):
    dispatcher = Dispatcher(registry)
    tags = args.tags.split(",") if args.tags else None
    results = dispatcher.broadcast(args.command, require_tags=tags, sudo=args.sudo)
    for r in results:
        print(f"\n[{r.machine_id}] (exit {r.returncode})")
        if r.stdout:
            print(r.stdout)
        if r.stderr:
            print(r.stderr)


def cmd_find(registry, args):
    tags = args.tags.split(",") if args.tags else None
    specs = {}
    if args.min_vram:
        specs["vram_gb"] = int(args.min_vram)
    machines = registry.find(require_tags=tags, min_specs=specs or None, location=args.location)
    if not machines:
        print("No machines match.")
        return
    for m in machines:
        print(f"  {m.id} — {m.label} [{', '.join(sorted(m.tags))}]")


def main():
    parser = argparse.ArgumentParser(prog="mp", description="machine-pool CLI")
    sub = parser.add_subparsers(dest="cmd")

    # list
    sub.add_parser("list", help="List all machines")

    # status
    p = sub.add_parser("status", help="Health check machines")
    p.add_argument("machine_id", nargs="?", help="Specific machine id (default: all)")

    # run
    p = sub.add_parser("run", help="Run command on best-matched machine")
    p.add_argument("command")
    p.add_argument("--tags", help="Comma-separated required tags")
    p.add_argument("--on", help="Target specific machine id")
    p.add_argument("--location", help="Required location/region")
    p.add_argument("--min-vram", help="Minimum VRAM GB")
    p.add_argument("--min-ram", help="Minimum RAM GB")
    p.add_argument("--sudo", action="store_true")
    p.add_argument("--timeout", type=int, default=60)

    # broadcast
    p = sub.add_parser("broadcast", help="Run command on all matching machines")
    p.add_argument("command")
    p.add_argument("--tags", help="Comma-separated tag filter")
    p.add_argument("--sudo", action="store_true")

    # find
    p = sub.add_parser("find", help="Find machines matching requirements")
    p.add_argument("--tags", help="Comma-separated required tags")
    p.add_argument("--min-vram", help="Minimum VRAM GB")
    p.add_argument("--location", help="Region/country filter")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    registry = Registry()

    dispatch = {
        "list":      cmd_list,
        "status":    cmd_status,
        "run":       cmd_run,
        "broadcast": cmd_broadcast,
        "find":      cmd_find,
    }
    dispatch[args.cmd](registry, args)


if __name__ == "__main__":
    main()
