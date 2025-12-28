#!/usr/bin/env python3
"""Run deterministic memory cleanup via the existing orchestrator entry point.

- Dry-run by default
- Apply with --force

Writes a JSON record of the run under data/.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.orchestrator import get_orchestrator


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Elefante deterministic memory cleanup")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Alias for --force (apply cleanup changes)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional JSON output path (defaults under data/)",
    )
    args = parser.parse_args()

    orchestrator = get_orchestrator()
    apply_changes = bool(args.force or args.apply)
    result = await orchestrator.consolidate_memories(force=apply_changes)

    refinery = result.get("refinery", {})
    stats = refinery.get("stats", {})

    print("\n=== Memory Consolidate (Deterministic Refinery) ===\n")
    print(f"Mode: {'APPLY' if apply_changes else 'DRY-RUN'}")
    if stats:
        print("\nStats:")
        for key in [
            "total_memories",
            "groups",
            "duplicate_groups",
            "redundant_marked",
            "canonical_key_set",
            "namespace_set",
            "planned_updates",
        ]:
            if key in stats:
                print(f"  {key}: {stats[key]}")
    if refinery.get("applied"):
        print(f"\nApplied changed: {refinery.get('changed', 0)}")

    output_path = Path(args.output) if args.output else Path("data") / f"refinery_run_{_timestamp()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nWrote run record: {output_path}")
    print("\n=== Done ===\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
