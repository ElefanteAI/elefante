#!/usr/bin/env python3
"""Backfill curated title/summary into stored memories (Chroma + optional Kuzu).

This script is intended to make stored memory metadata "production-grade":
- Ensures `title` and `summary` exist and are reasonable
- Persists them into Chroma metadata (via VectorStore.update_memory)
- Optionally updates the corresponding Kuzu Entity's `name`/`description`

Requires DB access (Elefante Mode ON recommended to avoid lock surprises).

Usage:
  python scripts/backfill_curated_fields.py --dry-run
  python scripts/backfill_curated_fields.py --limit 200
  python scripts/backfill_curated_fields.py --force --update-graph
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running as a standalone script: add repo root to sys.path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.utils.curation import generate_summary, generate_title


def _now() -> datetime:
    return datetime.utcnow()


def _get_cm(memory) -> Dict[str, Any]:
    cm = getattr(memory.metadata, "custom_metadata", None)
    return cm if isinstance(cm, dict) else {}


async def _update_graph_title_summary(
    graph: GraphStore,
    *,
    memory_id: str,
    title: str,
    summary: str,
) -> bool:
    # Avoid DELETE/DROP/REMOVE per validate_cypher_query.
    q = """
    MATCH (n:Entity)
    WHERE n.id = $id
    SET n.name = $name,
        n.description = $description
    RETURN n
    """
    try:
        rows = await graph.execute_query(
            q,
            params={"id": memory_id, "name": title, "description": summary},
        )
        return bool(rows)
    except Exception:
        return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill curated title/summary into DB")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Rewrite title/summary even if present")
    parser.add_argument(
        "--update-graph",
        action="store_true",
        help="Also update Kuzu Entity name/description for memory nodes",
    )

    args = parser.parse_args()

    vector = VectorStore()
    graph = GraphStore() if args.update_graph else None

    total_seen = 0
    total_changed = 0
    total_graph_updated = 0

    offset = int(args.offset)
    limit = int(args.limit)
    batch = int(args.batch_size)

    while total_seen < limit:
        take = min(batch, limit - total_seen)
        memories = await vector.get_all(limit=take, offset=offset)
        if not memories:
            break

        for m in memories:
            total_seen += 1

            layer = getattr(m.metadata, "layer", "world")
            sublayer = getattr(m.metadata, "sublayer", "fact")
            cm = dict(_get_cm(m))

            existing_title = str(cm.get("title") or "").strip()
            existing_summary = str(cm.get("summary") or "").strip()

            new_title = existing_title
            new_summary = existing_summary

            if args.force or not existing_title:
                new_title = generate_title(content=m.content, layer=str(layer), sublayer=str(sublayer), max_len=120)

            if args.force or not existing_summary:
                new_summary = generate_summary(content=m.content, max_len=220)

            changed = (new_title != existing_title) or (new_summary != existing_summary)
            if not changed:
                continue

            total_changed += 1

            cm["title"] = new_title
            cm["summary"] = new_summary
            cm["curation_version"] = "ingestion-curation-v1"
            cm["curated_at"] = _now().isoformat() + "Z"

            if args.dry_run:
                continue

            await vector.update_memory(
                m.id,
                {
                    "custom_metadata": cm,
                    "last_modified": _now(),
                },
            )

            if graph is not None:
                ok = await _update_graph_title_summary(
                    graph,
                    memory_id=str(m.id),
                    title=new_title,
                    summary=new_summary,
                )
                if ok:
                    total_graph_updated += 1

        offset += len(memories)

    print(
        f"[ok] seen={total_seen} changed={total_changed} graph_updated={total_graph_updated} dry_run={bool(args.dry_run)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
