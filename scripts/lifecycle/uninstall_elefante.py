"""Detach unchanged Elefante-owned integrations; dry-run by default.

The matching official package owns complete product uninstall because it runs
outside the installed app root and can verify backup, data preservation, code
removal, and the final receipt. This module remains the single ownership-safe
detachment implementation used by that package transaction.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lifecycle.daemon_service import uninstall as uninstall_daemon_service  # noqa: E402
from scripts.setup.install_manifest import (  # noqa: E402
    clear_runtime_installation,
    remove_unchanged_files,
    remove_unchanged_host_commands,
)


def detach_owned_surfaces(
    *,
    home: Path,
    apply: bool,
    clear_runtime: bool = False,
) -> dict[str, object]:
    """Detach only unchanged owned surfaces and return a content-free result."""
    # A daemon service must be stopped before its owned unit file is removed.
    # The service helper declines to touch modified or untracked unit files.
    uninstall_daemon_service(home, apply)
    removed_commands, preserved_commands = remove_unchanged_host_commands(
        home=home,
        apply=apply,
    )
    removed, preserved = remove_unchanged_files(home=home, apply=apply)
    runtime_removed = False
    if apply and clear_runtime:
        clear_runtime_installation(home)
        runtime_removed = True
    return {
        "schema_version": 1,
        "operation": "detach_owned_surfaces",
        "applied": apply,
        "removed_command_count": len(removed_commands),
        "preserved_command_count": len(preserved_commands),
        "removed_file_count": len(removed),
        "preserved_file_count": len(preserved),
        "runtime_identity_removed": runtime_removed,
        "removed_commands": removed_commands,
        "preserved_commands": preserved_commands,
        "removed_files": [str(path) for path in removed],
        "preserved_files": [str(path) for path in preserved],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="remove unchanged emitted files")
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Exact user home whose installer manifest owns the integrations",
    )
    parser.add_argument(
        "--clear-runtime",
        action="store_true",
        help="Package transaction only: clear runtime identity after app removal",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one machine-readable result",
    )
    args = parser.parse_args()
    if args.clear_runtime and not args.apply:
        parser.error("--clear-runtime requires --apply")
    home = args.home.expanduser().resolve()
    result = detach_owned_surfaces(
        home=home,
        apply=args.apply,
        clear_runtime=args.clear_runtime,
    )
    if args.json:
        safe_result = {
            key: value
            for key, value in result.items()
            if key not in {
                "removed_commands",
                "preserved_commands",
                "removed_files",
                "preserved_files",
            }
        }
        print(json.dumps(safe_result, sort_keys=True))
        return
    for key in result["removed_commands"]:
        print(f"{'remove' if args.apply else 'would_remove'} host registration {key}")
    for key in result["preserved_commands"]:
        print(f"preserve host registration {key} (missing, modified, or unavailable)")
    for path in result["removed_files"]:
        print(f"{'remove' if args.apply else 'would_remove'} {path}")
    for path in result["preserved_files"]:
        print(f"preserve {path} (missing or modified)")
    if result["runtime_identity_removed"]:
        print("remove customer runtime registration")
    if not args.apply:
        print("dry_run; re-run with --apply to remove only unchanged files")
    elif not args.clear_runtime:
        print("app_and_data_preserved; use the matching official package for complete uninstall")


if __name__ == "__main__":
    main()
