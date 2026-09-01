"""Shared proof primitives for verified customer-visible product operations.

This is intentionally small. Verified Resolve and the reversible correction
service prove that terminal states, content-free checks, exact record hashes,
declared scope, and private snapshot handling are common product mechanics.
Each operation still owns its semantic mutation and rollback rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any

from src.models.entity import Entity
from src.models.memory import Memory
from src.utils.atomic_json import read_json_strict


class VerifiedOperationStatus(str, Enum):
    """Terminal outcomes shared by verified product operations."""

    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    FAILED_NO_CHANGE = "FAILED_NO_CHANGE"
    FAILED_ROLLED_BACK = "FAILED_ROLLED_BACK"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    UNSAFE = "UNSAFE"


@dataclass(frozen=True)
class VerifiedOperationCheck:
    """One bounded, content-free postcondition result."""

    name: str
    passed: bool
    attempts: int
    code: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stable_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def memory_record_sha256(memory: Memory) -> str:
    """Hash durable semantic memory state without embeddings or live scores."""
    return _stable_sha256(
        memory.model_dump(
            mode="json",
            exclude={"embedding", "similarity_score", "relevance_score"},
        )
    )


def entity_record_sha256(entity: Entity) -> str:
    """Hash the graph entity fields that the Kuzu Entity table persists."""
    return _stable_sha256(
        entity.model_dump(mode="json", exclude={"updated_at", "tags"})
    )


def memory_scope_values(memory: Memory) -> tuple[str, str, str]:
    metadata = memory.metadata
    return tuple(
        str(value or "").strip().casefold()
        for value in (metadata.project, metadata.workspace, metadata.scope)
    )


def scope_sha256(scope: tuple[str, str, str]) -> str:
    return hashlib.sha256("\x1f".join(scope).encode("utf-8")).hexdigest()


def recall_scope(memory: Memory) -> tuple[str | None, str | None]:
    """Return explicit project/workspace, bridging conventional scope aliases."""
    project = str(memory.metadata.project or "").strip() or None
    workspace = str(memory.metadata.workspace or "").strip() or None
    declared = str(memory.metadata.scope or "").strip()
    if ":" in declared:
        kind, value = declared.split(":", 1)
        value = value.strip()
        if kind.casefold() == "project" and value and project is None:
            project = value
        elif kind.casefold() == "workspace" and value and workspace is None:
            workspace = value
    return project, workspace


def snapshot_digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def load_snapshot(path: Path) -> dict[str, Any]:
    payload = read_json_strict(Path(path))
    if not isinstance(payload, dict):
        raise ValueError("Dashboard snapshot must be a JSON object")
    return payload


__all__ = [
    "VerifiedOperationCheck",
    "VerifiedOperationStatus",
    "entity_record_sha256",
    "load_snapshot",
    "memory_record_sha256",
    "memory_scope_values",
    "recall_scope",
    "scope_sha256",
    "snapshot_digest",
]
