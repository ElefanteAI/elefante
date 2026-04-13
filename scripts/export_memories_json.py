#!/usr/bin/env python3
"""Export all memories from ChromaDB to a JSON file.

This is a direct export (no filtering) intended for before/after validation.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import get_config


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export all memories to JSON")
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional output path (defaults under data/)",
    )
    args = parser.parse_args()

    config = get_config()
    chroma_dir = Path(config.elefante.vector_store.persist_directory)

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_collection(config.elefante.vector_store.collection_name)

    results = collection.get(include=["metadatas", "documents"])

    ids = results.get("ids") or []
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []

    exported = []
    for i, memory_id in enumerate(ids):
        exported.append(
            {
                "id": memory_id,
                "content": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            }
        )

    output_path = Path(args.output) if args.output else Path("data") / f"memory_export_{_timestamp()}_all.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "exported_at": datetime.now().isoformat(),
        "count": len(exported),
        "chroma_dir": str(chroma_dir),
        "collection": config.elefante.vector_store.collection_name,
        "memories": exported,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    print(f"Exported {len(exported)} memories to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
