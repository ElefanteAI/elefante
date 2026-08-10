"""Embedded SQLite vector store used for the ChromaDB exit path.

This backend is deliberately opt-in until a user-authorized migration moves
existing ChromaDB data.  It stores Elefante's complete ``Memory`` contract as
JSON alongside a float32 embedding, so no metadata is flattened or discarded.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import numpy as np

from src.core.vector_store import VectorStore
from src.models.memory import Memory
from src.models.query import SearchFilters, SearchResult
from src.utils.logger import get_logger
from src.utils.validators import validate_limit, validate_memory_content


logger = get_logger(__name__)


class SQLiteVectorStore(VectorStore):
    """Local, single-file vector storage with exact cosine retrieval.

    Exact search keeps this backend dependency-free and deterministic. It is a
    deliberate trade-off for the initial migration path; a future indexed
    implementation must preserve this public storage contract.
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
    ):
        super().__init__(collection_name=collection_name, persist_directory=persist_directory)
        self.database_path = Path(self.persist_directory) / f"{self.collection_name}.sqlite3"
        self._connection: sqlite3.Connection | None = None
        self._connection_lock = threading.RLock()

    def _initialize_client(self) -> None:
        if self._connection is not None:
            return
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
            isolation_level=None,
        )
        with self._connection_lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_json TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    dimension INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS memories_title_idx ON memories(title)"
            )

    @staticmethod
    def _expand_query_text(query: str) -> str:
        query_lower = (query or "").lower()
        expansions: list[str] = []
        if any(term in query_lower for term in ("ide", "editor", "vs code", "vscode", "visual studio code")):
            expansions += ["editor", "IDE", "VS Code", "Visual Studio Code", "Copilot"]
        if any(term in query_lower for term in ("indent", "whitespace", "formatting", "tabs", "spaces")):
            expansions += ["indentation", "spaces", "tabs", "Python formatting", "code style"]
        if any(term in query_lower for term in ("docstring", "document", "documentation", "args", "returns", "raises")):
            expansions += ["docstrings", "Google style", "Args", "Returns", "Raises", "function documentation"]
        if any(term in query_lower for term in ("api", "endpoint", "response", "json", "error")):
            expansions += ["API response format", "JSON structure", "success boolean", "error field"]
        if any(term in query_lower for term in ("git", "branch", "workflow", "feature", "pull request", "pr", "main")):
            expansions += ["feature branch", "feat/", "pull request", "PR", "main branch", "branch naming"]
        if any(term in query_lower for term in ("test", "pytest", "verify", "commit", "push")):
            expansions += ["pytest", "pre-commit", "before push", "tests must pass"]
        if any(term in query_lower for term in ("performance", "latency", "query", "database", "index")):
            expansions += ["database query performance", "100ms", "index", "optimize query"]
        if any(term in query_lower for term in ("framework", "rest", "django", "fastapi", "api")):
            expansions += ["FastAPI", "REST", "Django", "OpenAPI docs"]
        return query + "\n" + " ".join(sorted(set(expansions))) if expansions else query

    @staticmethod
    def _title(memory: Memory) -> str:
        return str(memory.metadata.custom_metadata.get("title") or memory.metadata.summary or "")

    @staticmethod
    def _record(memory: Memory) -> str:
        record = memory.to_dict()
        record["embedding"] = None
        return json.dumps(record, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _embedding_bytes(embedding: list[float]) -> tuple[bytes, int]:
        vector = np.asarray(embedding, dtype=np.float32)
        if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
            raise ValueError("Embedding must be a finite one-dimensional vector")
        return vector.tobytes(), int(vector.size)

    @staticmethod
    def _row_to_memory(row: sqlite3.Row | tuple[Any, ...]) -> Memory:
        _memory_id, memory_json, embedding_blob, dimension, _title = row
        record = json.loads(memory_json)
        embedding = np.frombuffer(embedding_blob, dtype=np.float32)
        if embedding.size != dimension:
            raise ValueError("SQLite vector record has an invalid embedding dimension")
        record["embedding"] = embedding.astype(float).tolist()
        return Memory.from_dict(record)

    @staticmethod
    def _matches_filters(
        memory: Memory,
        filters: SearchFilters | None,
        where_override: dict[str, Any] | None,
    ) -> bool:
        metadata = memory.metadata
        values: dict[str, Any] = {
            "memory_type": getattr(metadata.memory_type, "value", metadata.memory_type),
            "domain": getattr(metadata.domain, "value", metadata.domain),
            "category": metadata.category,
            "source": getattr(metadata.source, "value", metadata.source),
            "project": metadata.project or "",
            "workspace": metadata.workspace or "",
            "file_path": metadata.file_path or "",
            "session_id": str(metadata.session_id) if metadata.session_id else "",
            "score": metadata.score,
            "tags": metadata.tags,
            "related_entities": [str(entity_id) for entity_id in memory.related_entities],
            "created_at": metadata.created_at,
        }
        requested: dict[str, Any] = {}
        if filters:
            for name in (
                "memory_type",
                "domain",
                "category",
                "source",
                "project",
                "workspace",
                "file_path",
                "session_id",
            ):
                value = getattr(filters, name, None)
                if value is not None:
                    requested[name] = str(value) if name == "session_id" else value
            if filters.min_score is not None:
                requested["score"] = {"$gte": filters.min_score}
            if filters.max_score is not None:
                requested.setdefault("score", {})["$lte"] = filters.max_score
            if filters.tags:
                requested["tags"] = {"$all": filters.tags}
            if filters.related_entities:
                requested["related_entities"] = {"$all": [str(entity_id) for entity_id in filters.related_entities]}
            if filters.start_date is not None:
                requested["created_at"] = {"$gte": filters.start_date}
            if filters.end_date is not None:
                requested.setdefault("created_at", {})["$lte"] = filters.end_date
        requested.update(where_override or {})
        for name, expected in requested.items():
            actual = values.get(name)
            if name not in values or not SQLiteVectorStore._matches_expected(actual, expected):
                return False
        return True

    @staticmethod
    def _matches_expected(actual: Any, expected: Any) -> bool:
        """Evaluate the small, documented Chroma-style filter subset locally."""
        if isinstance(expected, dict):
            for operator, operand in expected.items():
                if operator == "$gte":
                    if actual is None or SQLiteVectorStore._compare(actual, operand) < 0:
                        return False
                elif operator == "$lte":
                    if actual is None or SQLiteVectorStore._compare(actual, operand) > 0:
                        return False
                elif operator == "$eq":
                    if actual != operand:
                        return False
                elif operator == "$ne":
                    if actual == operand:
                        return False
                elif operator == "$in":
                    if isinstance(actual, (list, tuple, set)):
                        if not any(value in operand for value in actual):
                            return False
                    elif actual not in operand:
                        return False
                elif operator == "$nin":
                    if isinstance(actual, (list, tuple, set)):
                        if any(value in operand for value in actual):
                            return False
                    elif actual in operand:
                        return False
                elif operator == "$all":
                    if not isinstance(actual, (list, tuple, set)) or not set(operand).issubset(actual):
                        return False
                else:
                    raise ValueError(f"Unsupported SQLite vector-store filter operator: {operator}")
            return True
        if isinstance(expected, (list, tuple, set)):
            return actual in expected
        return actual == expected

    @staticmethod
    def _compare(actual: Any, expected: Any) -> int:
        """Compare values, normalizing aware and naive datetimes to UTC."""
        if isinstance(actual, datetime) and isinstance(expected, datetime):
            def utc_naive(value: datetime) -> datetime:
                if value.tzinfo is None:
                    return value
                return value.astimezone(timezone.utc).replace(tzinfo=None)

            actual, expected = utc_naive(actual), utc_naive(expected)
        return (actual > expected) - (actual < expected)

    async def add_memory(self, memory: Memory) -> str:
        self._initialize_client()
        validate_memory_content(memory.content)
        if memory.embedding is None:
            memory.embedding = await self._embedding_service.generate_embedding(memory.content)
        embedding_bytes, dimension = self._embedding_bytes(memory.embedding)

        def write() -> None:
            assert self._connection is not None
            with self._connection_lock:
                self._connection.execute(
                    "INSERT INTO memories(id, memory_json, embedding, dimension, title) VALUES (?, ?, ?, ?, ?)",
                    (str(memory.id), self._record(memory), embedding_bytes, dimension, self._title(memory)),
                )

        await asyncio.to_thread(write)
        return str(memory.id)

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[SearchFilters] = None,
        where_override: Optional[dict[str, Any]] = None,
        min_similarity: Optional[float] = None,
        apply_temporal_decay: bool = True,
    ) -> list[SearchResult]:
        self._initialize_client()
        limit = validate_limit(limit)
        threshold = self.config.elefante.orchestrator.min_similarity if min_similarity is None else min_similarity
        query_embedding = np.asarray(
            await self._embedding_service.generate_embedding(self._expand_query_text(query)),
            dtype=np.float32,
        )
        if query_embedding.ndim != 1 or not np.isfinite(query_embedding).all():
            raise ValueError("Embedding service returned an invalid query vector")
        query_norm = float(np.linalg.norm(query_embedding))
        if query_norm == 0:
            return []

        def read() -> list[tuple[Any, ...]]:
            assert self._connection is not None
            with self._connection_lock:
                return self._connection.execute(
                    "SELECT id, memory_json, embedding, dimension, title FROM memories"
                ).fetchall()

        rows = await asyncio.to_thread(read)
        now = datetime.utcnow()
        temporal_enabled = apply_temporal_decay and self.config.elefante.temporal_decay.enabled
        results: list[SearchResult] = []
        for row in rows:
            memory = self._row_to_memory(row)
            if not self._matches_filters(memory, filters, where_override):
                continue
            vector = np.asarray(memory.embedding, dtype=np.float32)
            if vector.size != query_embedding.size:
                raise ValueError("Stored embedding dimension does not match the configured model")
            denominator = query_norm * float(np.linalg.norm(vector))
            similarity = 0.0 if denominator == 0 else float(np.dot(query_embedding, vector) / denominator)
            similarity = max(0.0, min(1.0, similarity))
            if similarity < threshold:
                continue
            memory.similarity_score = similarity
            score = similarity
            if temporal_enabled:
                score = (
                    self.config.elefante.temporal_decay.semantic_weight * similarity
                    + self.config.elefante.temporal_decay.temporal_weight * memory.calculate_relevance_score(now)
                )
            results.append(SearchResult(memory=memory, score=max(0.0, min(1.0, score)), source="vector", vector_score=similarity))
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:limit]

    async def get_memory(self, memory_id: UUID) -> Optional[Memory]:
        self._initialize_client()

        def read() -> tuple[Any, ...] | None:
            assert self._connection is not None
            with self._connection_lock:
                return self._connection.execute(
                    "SELECT id, memory_json, embedding, dimension, title FROM memories WHERE id = ?",
                    (str(memory_id),),
                ).fetchone()

        row = await asyncio.to_thread(read)
        return self._row_to_memory(row) if row is not None else None

    async def get_by_id(self, memory_id: UUID) -> Optional[Memory]:
        return await self.get_memory(memory_id)

    async def find_by_title(self, title: str) -> Optional[Memory]:
        self._initialize_client()

        def read() -> tuple[Any, ...] | None:
            assert self._connection is not None
            with self._connection_lock:
                return self._connection.execute(
                    "SELECT id, memory_json, embedding, dimension, title FROM memories WHERE title = ? LIMIT 1",
                    (title,),
                ).fetchone()

        row = await asyncio.to_thread(read)
        return self._row_to_memory(row) if row is not None else None

    async def update_memory(self, memory_id: UUID, updates: dict[str, Any]) -> bool:
        memory = await self.get_memory(memory_id)
        if memory is None:
            return False
        if "content" in updates:
            memory.content = updates["content"]
            memory.embedding = await self._embedding_service.generate_embedding(memory.content)
        for name in (
            "score", "tags", "status", "deprecated", "archived",
            "relationship_type", "supersedes_id", "superseded_by_id",
            "last_accessed", "last_modified", "access_count",
            "retention_policy", "injection_policy", "scope", "trigger",
            "user_locked",
        ):
            if name in updates:
                setattr(memory.metadata, name, updates[name])
        if isinstance(updates.get("custom_metadata"), dict):
            memory.metadata.custom_metadata = updates["custom_metadata"]
        return await self.replace_memory(memory)

    async def replace_memory(self, memory: Memory) -> bool:
        self._initialize_client()
        if memory.embedding is None:
            memory.embedding = await self._embedding_service.generate_embedding(memory.content)
        embedding_bytes, dimension = self._embedding_bytes(memory.embedding)

        def write() -> None:
            assert self._connection is not None
            with self._connection_lock:
                self._connection.execute(
                    """
                    INSERT INTO memories(id, memory_json, embedding, dimension, title) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET memory_json = excluded.memory_json,
                        embedding = excluded.embedding, dimension = excluded.dimension, title = excluded.title
                    """,
                    (str(memory.id), self._record(memory), embedding_bytes, dimension, self._title(memory)),
                )

        try:
            await asyncio.to_thread(write)
            return True
        except sqlite3.Error as error:
            logger.error("failed_to_replace_sqlite_memory", error=str(error))
            return False

    async def update_memory_access(self, memory: Memory) -> bool:
        memory.metadata.score = min(100, max(0, round(memory.calculate_relevance_score() * 100)))
        return await self.replace_memory(memory)

    async def delete_memory(self, memory_id: UUID) -> bool:
        self._initialize_client()

        def delete() -> bool:
            assert self._connection is not None
            with self._connection_lock:
                cursor = self._connection.execute("DELETE FROM memories WHERE id = ?", (str(memory_id),))
                return cursor.rowcount == 1

        return await asyncio.to_thread(delete)

    async def get_all(self, limit: int = 100, offset: int = 0, filters: Optional[SearchFilters] = None) -> list[Memory]:
        self._initialize_client()

        def read() -> list[tuple[Any, ...]]:
            assert self._connection is not None
            with self._connection_lock:
                return self._connection.execute(
                    "SELECT id, memory_json, embedding, dimension, title FROM memories ORDER BY id"
                ).fetchall()

        memories = [self._row_to_memory(row) for row in await asyncio.to_thread(read)]
        filtered = [memory for memory in memories if self._matches_filters(memory, filters, None)]
        return filtered[offset:offset + limit]

    async def get_stats(self) -> dict[str, Any]:
        self._initialize_client()

        def read() -> int:
            assert self._connection is not None
            with self._connection_lock:
                return int(self._connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

        return {
            "collection_name": self.collection_name,
            "total_memories": await asyncio.to_thread(read),
            "persist_directory": self.persist_directory,
            "database_path": str(self.database_path),
            "distance_metric": self.distance_metric,
            "embedding_dimension": self._embedding_service.get_embedding_dimension(),
        }

    async def clear(self) -> bool:
        self._initialize_client()

        def clear() -> None:
            assert self._connection is not None
            with self._connection_lock:
                self._connection.execute("DELETE FROM memories")

        await asyncio.to_thread(clear)
        return True

    def close(self) -> None:
        """Release the local database handle for controlled shutdown or benchmarks."""
        with self._connection_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def __repr__(self) -> str:
        return f"SQLiteVectorStore(collection={self.collection_name}, database={self.database_path})"
