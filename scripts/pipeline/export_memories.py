#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : export_memories.py
# PURPOSE : Read-only export of the memory corpus for offline analysis.
#           Merged from export_memories_json.py + export_memories_csv.py.
# WHEN    : Before a surgical delete (--format json for before/after comparison).
#           When you need to analyze memory quality offline or in a spreadsheet.
#           Use --format csv for categorical analysis, --format json for precise
#           content review or scripted processing.
# USAGE   : python scripts/pipeline/export_memories.py --format json|csv|all
# NOTES   : This is NOT a backup or restore format: it excludes embeddings and
#           has no import path. Use backup_elefante_data.py for recovery. Content
#           is truncated at 500 chars in CSV. --output is only valid for single-
#           format runs; use --format all to emit both files simultaneously.
# ─────────────────────────────────────────────────────────────────────────────
"""Export all Elefante memories to JSON and/or CSV for analysis only.

Reads the configured local vector store without filtering — intended for
before/after validation, offline analysis, and spreadsheet review.

This output is not a backup: it does not contain the stored embeddings and has
no restore command. Use ``scripts/lifecycle/backup_elefante_data.py`` before a
destructive operation.

Outputs land under the configured data directory unless --output is provided.

Usage:
  python scripts/pipeline/export_memories.py --format json
  python scripts/pipeline/export_memories.py --format csv
  python scripts/pipeline/export_memories.py --format all
  python scripts/pipeline/export_memories.py --format json --output ~/my_export.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import get_config  # noqa: E402


# ── Shared fetch ─────────────────────────────────────────────────────────────

def _fetch(config) -> tuple[list, list, list]:
    """Return raw export fields from the configured embedded vector store."""
    vector_config = config.elefante.vector_store
    if vector_config.type == "sqlite":
        from src.core.sqlite_vector_store import SQLiteVectorStore

        async def read_sqlite():
            store = SQLiteVectorStore(
                collection_name=vector_config.collection_name,
                persist_directory=vector_config.persist_directory,
            )
            try:
                return await store.get_all(limit=1_000_000)
            finally:
                store.close()

        memories = __import__("asyncio").run(read_sqlite())
        records = [memory.to_dict() for memory in memories]
        return (
            [record["id"] for record in records],
            [record["metadata"] for record in records],
            [record["content"] for record in records],
        )
    if vector_config.type != "chromadb":
        raise ValueError(f"Unsupported vector store for export: {vector_config.type}")

    import chromadb

    client = chromadb.PersistentClient(path=str(Path(vector_config.persist_directory)))
    collection = client.get_collection(vector_config.collection_name)
    results = collection.get(include=["metadatas", "documents"])
    return (
        results.get("ids") or [],
        results.get("metadatas") or [],
        results.get("documents") or [],
    )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── JSON export ───────────────────────────────────────────────────────────────

def export_json(config, output_path: Path | None) -> Path:
    ids, metadatas, documents = _fetch(config)
    exported = [
        {"id": ids[i], "content": documents[i] if i < len(documents) else "", "metadata": metadatas[i] if i < len(metadatas) else {}}
        for i in range(len(ids))
    ]
    path = output_path or (Path("data") / f"memory_export_{_timestamp()}_all.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "exported_at": datetime.now().isoformat(),
        "count": len(exported),
        "vector_store_type": config.elefante.vector_store.type,
        "vector_store_path": str(Path(config.elefante.vector_store.persist_directory)),
        "collection": config.elefante.vector_store.collection_name,
        "memories": exported,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"JSON export: {len(exported)} memories → {path}")
    return path


# ── CSV export ────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "id", "content", "memory_type", "score", "tags", "status", "created_at",
    "domain", "category", "confidence", "relationship_type", "related_memory_ids",
    "conflict_ids", "supersedes_id", "superseded_by_id", "source", "source_detail",
    "verified", "author", "project", "last_accessed", "access_count", "decay_rate",
    "reinforcement_factor", "version", "deprecated", "archived", "title",
    "emotional_valence", "emotional_arousal", "emotional_mood",
]


def export_csv(config, output_path: Path | None) -> Path:
    ids, metadatas, documents = _fetch(config)
    path = output_path or (Path("data") / f"memory_export_{_timestamp()}.csv")
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for i, memory_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            content = documents[i] if i < len(documents) else ""

            custom_meta = meta.get("custom_metadata", {})
            if isinstance(custom_meta, str):
                try:
                    custom_meta = json.loads(custom_meta)
                except json.JSONDecodeError:
                    custom_meta = {}
            emotional = custom_meta.get("emotional_context", {})

            writer.writerow({
                "id": memory_id,
                "content": content[:500] + ("..." if len(content) > 500 else ""),
                "memory_type": meta.get("memory_type", ""),
                "score": meta.get("score", ""),
                "tags": meta.get("tags", ""),
                "status": meta.get("status", ""),
                "created_at": meta.get("created_at", ""),
                "domain": meta.get("domain", ""),
                "category": meta.get("category", ""),
                "confidence": meta.get("confidence", ""),
                "relationship_type": meta.get("relationship_type", ""),
                "related_memory_ids": json.dumps(meta.get("related_memory_ids", [])),
                "conflict_ids": json.dumps(meta.get("conflict_ids", [])),
                "supersedes_id": meta.get("supersedes_id", ""),
                "superseded_by_id": meta.get("superseded_by_id", ""),
                "source": meta.get("source", ""),
                "source_detail": meta.get("source_detail", ""),
                "verified": meta.get("verified", ""),
                "author": meta.get("author", ""),
                "project": meta.get("project", ""),
                "last_accessed": meta.get("last_accessed", ""),
                "access_count": meta.get("access_count", ""),
                "decay_rate": meta.get("decay_rate", ""),
                "reinforcement_factor": meta.get("reinforcement_factor", ""),
                "version": meta.get("version", ""),
                "deprecated": meta.get("deprecated", ""),
                "archived": meta.get("archived", ""),
                "title": custom_meta.get("title", ""),
                "emotional_valence": emotional.get("valence", ""),
                "emotional_arousal": emotional.get("arousal", ""),
                "emotional_mood": emotional.get("mood", ""),
            })

    print(f"CSV export: {len(ids)} memories → {path}")
    return path


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Export Elefante memories to JSON and/or CSV")
    parser.add_argument(
        "--format",
        choices=["json", "csv", "all"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional output path override (only valid for single-format run)",
    )
    args = parser.parse_args()

    out = Path(args.output) if args.output else None
    if out and args.format == "all":
        print("--output cannot be used with --format all (two files would be written)")
        return 1

    config = get_config()

    if args.format in ("json", "all"):
        export_json(config, out if args.format == "json" else None)
    if args.format in ("csv", "all"):
        export_csv(config, out if args.format == "csv" else None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
