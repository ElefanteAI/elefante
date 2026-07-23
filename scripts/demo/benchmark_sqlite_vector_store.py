"""Benchmark isolated SQLite exact-vector retrieval without touching user data.

The benchmark writes deterministic synthetic memories to an automatically
removed temporary directory, then measures the public SQLite retrieval path.
It is evidence for the ChromaDB-exit decision, not a migration command.

Run: .venv/bin/python scripts/demo/benchmark_sqlite_vector_store.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.sqlite_vector_store import SQLiteVectorStore
from src.models.memory import Memory, MemoryMetadata


class SyntheticEmbeddingService:
    """Return one deterministic query vector without loading a model."""

    def __init__(self, vector: np.ndarray):
        self._vector = vector.astype(np.float32).tolist()

    async def generate_embedding(self, _text: str) -> list[float]:
        return self._vector

    def get_embedding_dimension(self) -> int:
        return len(self._vector)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile of no latency samples")
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[index]


def _validate_count(name: str, value: int, maximum: int) -> None:
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")


async def run_benchmark(
    *,
    records: int = 5_000,
    queries: int = 20,
    dimension: int = 768,
    limit: int = 10,
    seed: int = 20260722,
    temporary_parent: Path | None = None,
) -> dict[str, Any]:
    """Return deterministic insert and exact-search timings from a disposable store."""
    _validate_count("records", records, 100_000)
    _validate_count("queries", queries, 10_000)
    _validate_count("dimension", dimension, 4_096)
    _validate_count("limit", limit, records)

    random = np.random.default_rng(seed)
    vectors = random.standard_normal((records, dimension)).astype(np.float32)
    populate_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="elefante-sqlite-benchmark-", dir=temporary_parent) as directory:
        store = SQLiteVectorStore(collection_name="benchmark", persist_directory=directory)
        try:
            store._initialize_client()
            assert store._connection is not None
            rows = []
            for index, vector in enumerate(vectors):
                memory = Memory(
                    content=f"Synthetic SQLite benchmark memory {index}",
                    embedding=vector.astype(float).tolist(),
                    metadata=MemoryMetadata(category="benchmark", summary=f"Memory {index}"),
                )
                embedding, stored_dimension = store._embedding_bytes(memory.embedding)
                rows.append((str(memory.id), store._record(memory), embedding, stored_dimension, store._title(memory)))
            with store._connection_lock:
                store._connection.executemany(
                    "INSERT INTO memories(id, memory_json, embedding, dimension, title) VALUES (?, ?, ?, ?, ?)",
                    rows,
                )
            populate_ms = (time.perf_counter() - populate_started) * 1_000
            store._embedding_service = SyntheticEmbeddingService(vectors[0])

            # Warm the SQLite page cache but keep the result out of the report.
            warmup = await store.search("sqlite benchmark", limit=limit, min_similarity=0.0, apply_temporal_decay=False)
            if len(warmup) != limit:
                raise RuntimeError("SQLite benchmark did not return the requested result count")

            samples: list[float] = []
            for _ in range(queries):
                started = time.perf_counter()
                results = await store.search("sqlite benchmark", limit=limit, min_similarity=0.0, apply_temporal_decay=False)
                elapsed = (time.perf_counter() - started) * 1_000
                if len(results) != limit:
                    raise RuntimeError("SQLite benchmark did not return the requested result count")
                samples.append(elapsed)
            return {
                "backend": "sqlite-exact-cosine",
                "records": records,
                "queries": queries,
                "dimension": dimension,
                "limit": limit,
                "populate_ms": round(populate_ms, 3),
                "seed": seed,
                "search_ms": {
                    "min": round(min(samples), 3),
                    "p50": round(median(samples), 3),
                    "p95": round(_percentile(samples, 0.95), 3),
                    "max": round(max(samples), 3),
                },
                "database_file_bytes": store.database_path.stat().st_size,
            }
        finally:
            store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=5_000)
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--dimension", type=int, default=768)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--max-p95-ms", type=float, default=None)
    args = parser.parse_args(argv)
    report = asyncio.run(
        run_benchmark(
            records=args.records,
            queries=args.queries,
            dimension=args.dimension,
            limit=args.limit,
            seed=args.seed,
        )
    )
    print(json.dumps(report, sort_keys=True))
    if args.max_p95_ms is not None and report["search_ms"]["p95"] > args.max_p95_ms:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
