"""Remove unchanged Elefante-emitted integration files; dry-run by default."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lifecycle.daemon_service import uninstall as uninstall_daemon_service
from scripts.setup.install_manifest import remove_unchanged_files, remove_unchanged_host_commands


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="remove unchanged emitted files")
    args = parser.parse_args()
    # A daemon service must be stopped before its owned unit file is removed.
    # The service helper declines to touch modified or untracked unit files.
    uninstall_daemon_service(Path.home(), args.apply)
    removed_commands, preserved_commands = remove_unchanged_host_commands(apply=args.apply)
    for key in removed_commands:
        print(f"{'remove' if args.apply else 'would_remove'} host registration {key}")
    for key in preserved_commands:
        print(f"preserve host registration {key} (missing, modified, or unavailable)")
    removed, preserved = remove_unchanged_files(apply=args.apply)
    for path in removed:
        print(f"{'remove' if args.apply else 'would_remove'} {path}")
    for path in preserved:
        print(f"preserve {path} (missing or modified)")
    if not args.apply:
        print("dry_run; re-run with --apply to remove only unchanged files")


if __name__ == "__main__":
    main()
