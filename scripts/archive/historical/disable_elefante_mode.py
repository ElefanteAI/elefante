#!/usr/bin/env python3
"""Disable Elefante Mode and report lock status.

Purpose:
- Ensure Elefante Mode is disabled (releases Elefante DB locks)
- Print lock status for troubleshooting

Examples:
  .venv/bin/python scripts/disable_elefante_mode.py
  .venv/bin/python scripts/disable_elefante_mode.py --status-only

Exit codes:
  0 = Elefante Mode is OFF
  1 = Still enabled (unexpected)
"""

from __future__ import annotations

import argparse
import json

from src.utils.elefante_mode import ElefanteModeManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Disable Elefante Mode and show lock status")
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only print status/locks; do not attempt to change state.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    args = parser.parse_args()

    manager = ElefanteModeManager()

    status_before = manager.status
    locks_before = manager.check_locks()

    disable_result = None
    if not args.status_only:
        disable_result = manager.disable()

    status_after = manager.status
    locks_after = manager.check_locks()

    payload = {
        "status_before": status_before,
        "locks_before": locks_before,
        "disable_result": disable_result,
        "status_after": status_after,
        "locks_after": locks_after,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status_before: {status_before}")
        print(f"locks_before: {locks_before}")
        if disable_result is not None:
            print(f"disable_result: {disable_result}")
        print(f"status_after:  {status_after}")
        print(f"locks_after:  {locks_after}")

    enabled = bool(status_after.get("enabled"))
    return 0 if not enabled else 1


if __name__ == "__main__":
    raise SystemExit(main())
