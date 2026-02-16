#!/usr/bin/env python3
"""
Migration: v1.9 -> v1.10.0 (Behavioral Relevance)
==================================================

Maps legacy metadata fields to v1.10.0 schema:
  - importance (1-10) -> score (0-100)
  - Preserves layer/sublayer as category prefix if category is generic

Does NOT change processing_status. Memories stay 'raw' so ETL can
re-classify them under the current topology.

Uses the proven direct-ChromaDB pattern from migrate_cognitive_fields_v161.py.

Usage:
    .venv/bin/python scripts/migrate_v19_to_v110.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import get_config


def migrate_memory(memory_id: str, metadata: dict, dry_run: bool = False) -> dict:
    """Apply v1.10.0 schema migration to a single memory's metadata."""
    changes = {}

    # 1. SCORE: importance (1-10) -> score (0-100)
    importance = metadata.get("importance")
    current_score = metadata.get("score")

    if importance is not None and current_score is None:
        try:
            imp = int(importance)
            new_score = min(100, max(0, imp * 10))
            changes["score"] = {"old": f"importance={imp}", "new": f"score={new_score}"}
            if not dry_run:
                metadata["score"] = new_score
        except (TypeError, ValueError):
            pass

    # 2. CATEGORY: If category is generic and layer/sublayer exist, enrich it
    layer = metadata.get("layer")
    sublayer = metadata.get("sublayer")
    category = metadata.get("category", "")

    if layer and category in ("general", "", None):
        enriched = f"{layer}_{sublayer}" if sublayer else layer
        changes["category"] = {"old": category, "new": enriched}
        if not dry_run:
            metadata["category"] = enriched

    # 3. STAMP: Mark migration version
    if not dry_run and changes:
        metadata["migration_v110"] = datetime.utcnow().isoformat()

    return changes


def main():
    parser = argparse.ArgumentParser(description="Migrate memories from v1.9 to v1.10.0 schema")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    args = parser.parse_args()

    mode = "(DRY RUN)" if args.dry_run else ""
    print(f"=== v1.9 -> v1.10.0 Migration {mode} ===\n")

    config = get_config()
    persist_dir = config.elefante.vector_store.persist_directory
    collection_name = config.elefante.vector_store.collection_name

    print(f"ChromaDB path: {persist_dir}")
    print(f"Collection: {collection_name}\n")

    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        collection = client.get_collection(collection_name)
    except Exception as e:
        print(f"ERROR: Failed to connect to ChromaDB: {e}")
        sys.exit(1)

    total = collection.count()
    print(f"Total memories: {total}\n")

    if total == 0:
        print("No memories to migrate.")
        return

    batch_size = 100
    migrated = 0
    skipped = 0
    errors = 0

    for offset in range(0, total, batch_size):
        result = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas", "documents"]
        )

        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])
        documents = result.get("documents", [])

        for i, memory_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else ""

            try:
                changes = migrate_memory(memory_id, metadata, dry_run=args.dry_run)

                if changes:
                    migrated += 1
                    content_preview = (doc or "")[:60].replace("\n", " ")
                    print(f"[{migrated}] {memory_id[:12]}  \"{content_preview}...\"")
                    for field, diff in changes.items():
                        print(f"      {field}: {diff['old']} -> {diff['new']}")

                    if not args.dry_run:
                        collection.update(
                            ids=[memory_id],
                            metadatas=[metadata],
                        )
                else:
                    skipped += 1

            except Exception as e:
                errors += 1
                print(f"ERROR [{memory_id[:12]}]: {e}")

    print(f"\n=== Migration Summary ===")
    print(f"Total:    {total}")
    print(f"Migrated: {migrated}")
    print(f"Skipped:  {skipped} (already had score or no importance)")
    print(f"Errors:   {errors}")

    if args.dry_run:
        print("\n(Dry run - no changes applied. Run without --dry-run to apply.)")
    else:
        print(f"\nDone. All memories now use score (0-100).")


if __name__ == "__main__":
    main()
