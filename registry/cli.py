"""
Pheonix Component Registry CLI
Command-line tool for inspecting components and validating updates.
"""

import argparse
import json
import sys
from pathlib import Path

from registry import (
    ComponentRegistry,
    ComponentManifest,
    IncompatibleUpdateError,
)

MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"


def load_default_registry() -> ComponentRegistry:
    reg = ComponentRegistry()
    for f in sorted(MANIFESTS_DIR.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            reg.register_component(ComponentManifest(**data), force=True)
    return reg


def main():
    parser = argparse.ArgumentParser(description="Pheonix Component Registry CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List
    subparsers.add_parser("list", help="List registered components and versions")

    # Check
    check_parser = subparsers.add_parser("check", help="Check compatibility of an update manifest")
    check_parser.add_argument("manifest_path", type=Path, help="Path to manifest JSON file")

    # Update
    update_parser = subparsers.add_parser("update", help="Apply component update (blocks if incompatible)")
    update_parser.add_argument("manifest_path", type=Path, help="Path to manifest JSON file")

    # Export
    subparsers.add_parser("export", help="Export full system manifest")

    args = parser.parse_args()
    reg = load_default_registry()

    if args.command == "list":
        comps = reg.list_components()
        print(f"{'Component':<20} {'Version':<10} {'Dependencies':<35} {'Description'}")
        print("-" * 85)
        for c in comps:
            deps_str = ", ".join(f"{d.component_name} {d.version_constraint}" for d in c.dependencies) or "None"
            print(f"{c.name:<20} {c.version:<10} {deps_str:<35} {c.description[:30]}")

    elif args.command == "check":
        with open(args.manifest_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        cand = ComponentManifest(**data)
        plan = reg.propose_update(cand)
        if plan.can_apply:
            print(f"[OK] Candidate update for '{cand.name}' to v{cand.version} is compatible!")
        else:
            print(f"[BLOCKED] Update for '{cand.name}' to v{cand.version} CANNOT be applied:")
            for reason in plan.block_reasons:
                print(f" - {reason}")
            sys.exit(1)

    elif args.command == "update":
        with open(args.manifest_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        cand = ComponentManifest(**data)
        try:
            reg.apply_update(cand)
            print(f"[SUCCESS] Successfully updated '{cand.name}' to v{cand.version}.")
        except IncompatibleUpdateError as e:
            print(f"[BLOCKED] {e}")
            sys.exit(1)

    elif args.command == "export":
        print(json.dumps(reg.export_system_manifest(), indent=2))


if __name__ == "__main__":
    main()
