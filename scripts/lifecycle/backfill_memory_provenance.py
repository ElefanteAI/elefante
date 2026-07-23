"""Backfill explicit legacy provenance into memories created before the daemon."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.graph_store import get_graph_store
from src.core.vector_store import get_vector_store


def _legacy_source() -> dict[str, str]:
    return {
        "tool": "legacy",
        "instance_id": "pre-daemon",
        "session_id": "pre-daemon",
        "cwd": "",
        "transport": "legacy-stdio",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


async def backfill(*, apply: bool) -> tuple[int, int, int]:
    store = get_vector_store()
    graph_store = get_graph_store()
    memories = await store.get_all(limit=100_000, offset=0)
    candidates = [memory for memory in memories if "elefante_source" not in (memory.metadata.custom_metadata or {})]
    if not apply:
        return len(candidates), 0, len(memories)

    updated = 0
    for memory in candidates:
        custom_metadata = dict(memory.metadata.custom_metadata or {})
        custom_metadata["elefante_source"] = _legacy_source()
        if await store.update_memory(memory.id, {"custom_metadata": custom_metadata}):
            updated += 1
    linked = 0
    for memory in memories:
        source = (memory.metadata.custom_metadata or {}).get("elefante_source") or _legacy_source()
        await graph_store.record_memory_source(memory.id, source)
        linked += 1
    return len(candidates), updated, linked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="persist the backfill; default is dry-run")
    args = parser.parse_args()
    candidates, updated, linked = asyncio.run(backfill(apply=args.apply))
    if args.apply:
        print(f"backfilled={updated} candidates={candidates} source_links={linked}")
    else:
        print(f"dry_run candidates={candidates} source_links_pending={linked}; re-run with --apply to persist")


if __name__ == "__main__":
    main()
