#!/usr/bin/env python3
"""
Migration: v1.6.1 Cognitive Field Standardization

Applies cognitive field canonicalization to ALL existing memories:
- concepts: parsed to list[str], canonicalized, re-encoded
- surfaces_when: parsed to list[str], canonicalized, re-encoded
- authority_score: clamped to [0.0, 1.0]

This ensures all memories benefit from V4 concept-overlap scoring.

Usage:
    .venv/bin/python scripts/migrate_cognitive_fields_v161.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import get_config
from src.utils.curation import canonicalize_concepts


def parse_list_field(value) -> list[str]:
    """Parse a stored list field back into list[str] with back-compat."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # JSON array
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x]
            except json.JSONDecodeError:
                pass
            # Python repr fallback
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x]
            except (ValueError, SyntaxError):
                pass
        # Comma-joined fallback
        return [x.strip() for x in s.split(",") if x.strip()]
    return []


def migrate_memory(memory_id: str, metadata: dict, dry_run: bool = False) -> dict:
    """Apply cognitive field standardization to a single memory's metadata."""
    changes = {}
    
    # Parse and canonicalize concepts
    raw_concepts = metadata.get("concepts")
    parsed_concepts = parse_list_field(raw_concepts)
    if parsed_concepts:
        canonical = canonicalize_concepts(parsed_concepts, max_concepts=10)
        new_value = json.dumps(canonical)
        if new_value != raw_concepts:
            changes["concepts"] = {"old": raw_concepts, "new": new_value}
            if not dry_run:
                metadata["concepts"] = new_value
    
    # Parse and canonicalize surfaces_when
    raw_surfaces = metadata.get("surfaces_when")
    parsed_surfaces = parse_list_field(raw_surfaces)
    if parsed_surfaces:
        canonical = canonicalize_concepts(parsed_surfaces, max_concepts=15)
        new_value = json.dumps(canonical)
        if new_value != raw_surfaces:
            changes["surfaces_when"] = {"old": raw_surfaces, "new": new_value}
            if not dry_run:
                metadata["surfaces_when"] = new_value
    
    # Clamp authority_score
    raw_authority = metadata.get("authority_score")
    if raw_authority is not None:
        try:
            clamped = max(0.0, min(1.0, float(raw_authority)))
            if clamped != raw_authority:
                changes["authority_score"] = {"old": raw_authority, "new": clamped}
                if not dry_run:
                    metadata["authority_score"] = clamped
        except (TypeError, ValueError):
            pass
    
    # Mark as processed
    if not dry_run and changes:
        metadata["processing_status"] = "processed"
        metadata["migration_v161"] = datetime.utcnow().isoformat()
    
    return changes


def main():
    parser = argparse.ArgumentParser(description="Migrate all memories to v1.6.1 cognitive field standard")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    args = parser.parse_args()
    
    print(f"=== v1.6.1 Cognitive Field Migration {'(DRY RUN)' if args.dry_run else ''} ===\n")
    
    # Initialize ChromaDB
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
    
    # Get all memories
    total = collection.count()
    print(f"Total memories: {total}\n")
    
    if total == 0:
        print("No memories to migrate.")
        return
    
    # Fetch all in batches
    batch_size = 100
    migrated = 0
    unchanged = 0
    errors = 0
    
    for offset in range(0, total, batch_size):
        result = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas", "documents", "embeddings"]
        )
        
        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])
        documents = result.get("documents", [])
        embeddings = result.get("embeddings", [])
        
        for i, memory_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) else {}
            
            try:
                changes = migrate_memory(memory_id, metadata, dry_run=args.dry_run)
                
                if changes:
                    migrated += 1
                    print(f"[{migrated}] {memory_id[:8]}...")
                    for field, diff in changes.items():
                        old_display = str(diff["old"])[:50] if diff["old"] else "(empty)"
                        new_display = str(diff["new"])[:50]
                        print(f"    {field}: {old_display} -> {new_display}")
                    
                    # Apply update to ChromaDB (metadata only - don't touch embeddings)
                    if not args.dry_run:
                        collection.update(
                            ids=[memory_id],
                            metadatas=[metadata],
                        )
                else:
                    unchanged += 1
                    
            except Exception as e:
                errors += 1
                print(f"ERROR [{memory_id[:8]}]: {e}")
    
    # Summary
    print(f"\n=== Migration Summary ===")
    print(f"Total memories: {total}")
    print(f"Migrated: {migrated}")
    print(f"Unchanged: {unchanged}")
    print(f"Errors: {errors}")
    
    if args.dry_run:
        print("\n(Dry run - no changes applied. Run without --dry-run to apply.)")
    else:
        print(f"\nMigration complete.")


if __name__ == "__main__":
    main()
