"""Verified reversible correction operations for one project-scoped memory.

Edit, Replace, Archive, and Restore each own their semantic mutation, but share
the product-level completion contract: bind an exact preimage, write once,
verify vector and graph authority, atomically refresh Home, prove scoped Recall,
and restore the exact prior state on any failed postcondition.

Permanent deletion is deliberately not implemented here. Erased data cannot
honestly promise ordinary rollback until the Recover slice supplies a verified
backup boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from src.core.governance import is_protected
from src.core.verified_operation import (
    VerifiedOperationCheck,
    VerifiedOperationStatus,
    entity_record_sha256,
    load_snapshot,
    memory_record_sha256,
    memory_scope_values,
    recall_scope,
    scope_sha256,
    snapshot_digest,
)
from src.models.entity import Entity, EntityType
from src.models.memory import Memory, MemoryStatus
from src.utils.atomic_json import (
    PrivateFileState,
    capture_private_file,
    restore_private_file,
)
from src.utils.curation import (
    canonicalize_concepts,
    canonicalize_recall_cues,
    canonicalize_surfaces_when,
    extract_concepts,
    generate_summary,
    generate_title,
    infer_surfaces_when,
)
from src.utils.validators import validate_memory_content


RefreshSnapshot = Callable[[], Awaitable[Mapping[str, Any] | None]]
RecallSelectedIds = Callable[..., Awaitable[Sequence[str]]]

ARCHIVE_RESTORE_POINT_KEY = "verified_archive_restore_point"
CORRECTION_HISTORY_KEY = "verified_correction_history"


def _set_recall_cue(memory: Memory, question: str, *, replace: bool) -> None:
    """Bind a successful active correction to the customer's future question."""
    cues = [question] if replace else [*memory.metadata.recall_cues, question]
    canonical = canonicalize_recall_cues(cues)
    memory.metadata.recall_cues = canonical
    custom = dict(memory.metadata.custom_metadata or {})
    custom["recall_cues"] = canonical
    memory.metadata.custom_metadata = custom


class CorrectionAction(str, Enum):
    EDIT = "edit"
    REPLACE = "replace"
    ARCHIVE = "archive"
    RESTORE = "restore"
    PERMANENT_DELETE = "permanent_delete"


@dataclass(frozen=True)
class VerifiedCorrectionPlan:
    schema_version: int
    action: CorrectionAction
    memory_id: str
    applicable: bool
    reason_code: str | None
    reason: str
    protected: bool
    irreversible: bool
    record_sha256: dict[str, str]
    graph_sha256: dict[str, str]
    scope_sha256: str | None
    content_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action": self.action.value,
            "memory_id": self.memory_id,
            "applicable": self.applicable,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "protected": self.protected,
            "irreversible": self.irreversible,
            "record_sha256": dict(self.record_sha256),
            "graph_sha256": dict(self.graph_sha256),
            "scope_sha256": self.scope_sha256,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class VerifiedCorrectionReceipt:
    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedOperationStatus
    authority: str
    started_at: str
    finished_at: str
    memory_ids: dict[str, str]
    scope_sha256: str
    record_sha256: dict[str, str]
    graph_sha256: dict[str, str]
    checks: tuple[VerifiedOperationCheck, ...]
    error_codes: tuple[str, ...]
    rollback: str
    changed: bool
    recoverable: bool
    recovery_operation_id: str | None = None
    recovery_archive_name: str | None = None
    recovery_archive_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "operation": self.operation,
            "status": self.status.value,
            "authority": self.authority,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "memory_ids": dict(self.memory_ids),
            "scope_sha256": self.scope_sha256,
            "record_sha256": dict(self.record_sha256),
            "graph_sha256": dict(self.graph_sha256),
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
            "rollback": self.rollback,
            "changed": self.changed,
            "recoverable": self.recoverable,
            "recovery_operation_id": self.recovery_operation_id,
            "recovery_archive_name": self.recovery_archive_name,
            "recovery_archive_sha256": self.recovery_archive_sha256,
        }


@dataclass(frozen=True)
class VerifiedCorrectionResult:
    status: VerifiedOperationStatus
    plan: VerifiedCorrectionPlan
    receipt: VerifiedCorrectionReceipt

    @property
    def success(self) -> bool:
        return self.status is VerifiedOperationStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "plan": self.plan.to_dict(),
            "receipt": self.receipt.to_dict(),
        }


class CorrectionWriteError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _content_sha256(content: str | None) -> str | None:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _relationship_projection_sha256(concepts: Sequence[str]) -> str:
    canonical = sorted(canonicalize_concepts(list(concepts), max_concepts=5))
    payload = json.dumps(canonical, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _inactive(memory: Memory) -> bool:
    return bool(
        memory.metadata.archived
        or memory.metadata.deprecated
        or memory.metadata.superseded_by_id
        or _enum_text(memory.metadata.status).casefold()
        in {MemoryStatus.ARCHIVED.value, MemoryStatus.DEPRECATED.value}
    )


def _bounded_history(memory: Memory) -> list[dict[str, Any]]:
    custom = dict(memory.metadata.custom_metadata or {})
    raw = custom.get(CORRECTION_HISTORY_KEY)
    return list(raw) if isinstance(raw, list) else []


def _append_history(
    memory: Memory,
    *,
    operation_id: str,
    action: CorrectionAction,
    reason: str,
    at: datetime,
    memory_ids: Mapping[str, str],
) -> None:
    custom = dict(memory.metadata.custom_metadata or {})
    history = _bounded_history(memory)
    history.append(
        {
            "operation_id": operation_id,
            "action": action.value,
            "at": at.isoformat(),
            "reason": reason,
            "invocation_mode": "user_directed",
            "memory_ids": dict(memory_ids),
        }
    )
    custom[CORRECTION_HISTORY_KEY] = history[-50:]
    memory.metadata.custom_metadata = custom


def _archive_restore_point(memory: Memory, *, kind: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": kind,
        "status": _enum_text(memory.metadata.status),
        "archived": bool(memory.metadata.archived),
        "deprecated": bool(memory.metadata.deprecated),
        "superseded_by_id": (
            str(memory.metadata.superseded_by_id)
            if memory.metadata.superseded_by_id
            else None
        ),
        "conflict_ids": [str(item) for item in (memory.metadata.conflict_ids or [])],
        "record_sha256": memory_record_sha256(memory),
    }


def _read_restore_point(memory: Memory) -> dict[str, Any] | None:
    value = (memory.metadata.custom_metadata or {}).get(ARCHIVE_RESTORE_POINT_KEY)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        return None
    return dict(value)


def _curate_content(memory: Memory, content: str) -> None:
    custom = dict(memory.metadata.custom_metadata or {})
    concepts = canonicalize_concepts(extract_concepts(content, max_concepts=5))
    surfaces = canonicalize_surfaces_when(infer_surfaces_when(content, concepts))
    title = generate_title(content=content, max_len=120)
    summary = generate_summary(content=content, max_len=220)
    custom.update(
        {
            "title": title,
            "summary": summary,
            "concepts": concepts,
            "surfaces_when": surfaces,
            "processing_status": "processed",
            "relationship_projection_status": "deterministic_concepts",
            "relationship_projection_sha256": _relationship_projection_sha256(
                concepts
            ),
        }
    )
    memory.content = content
    memory.embedding = None
    memory.metadata.summary = summary
    memory.metadata.concepts = concepts
    memory.metadata.surfaces_when = surfaces
    memory.metadata.custom_metadata = custom


def _entity_projection(memory: Memory, existing: Entity | None = None) -> Entity:
    custom = dict(memory.metadata.custom_metadata or {})
    title = str(custom.get("title") or generate_title(content=memory.content, max_len=120))
    summary = str(
        custom.get("summary") or memory.metadata.summary or generate_summary(content=memory.content, max_len=220)
    )
    properties = dict(existing.properties if existing is not None else {})
    properties.update(
        {
            "content": memory.content[:200],
            "memory_type": _enum_text(memory.metadata.memory_type),
            "score": memory.metadata.score,
            "status": _enum_text(memory.metadata.status),
            "timestamp": memory.metadata.created_at.isoformat(),
            "processing_status": custom.get("processing_status", "raw"),
            "relationship_projection_status": custom.get(
                "relationship_projection_status", "unverified"
            ),
            "relationship_projection_sha256": custom.get(
                "relationship_projection_sha256", ""
            ),
            "archived": bool(memory.metadata.archived),
            "deprecated": bool(memory.metadata.deprecated),
            "version": int(memory.metadata.version),
        }
    )
    return Entity(
        id=memory.id,
        name=title,
        type=EntityType.MEMORY,
        description=summary,
        created_at=(existing.created_at if existing is not None else memory.metadata.created_at),
        updated_at=memory.metadata.last_modified,
        properties=properties,
        tags=(list(existing.tags) if existing is not None else []),
    )


def _snapshot_memory_matches(node: Mapping[str, Any], memory: Memory) -> bool:
    properties = node.get("properties")
    if not isinstance(properties, Mapping):
        return False
    expected = {
        "content": memory.content,
        "status": _enum_text(memory.metadata.status),
        "archived": bool(memory.metadata.archived),
        "deprecated": bool(memory.metadata.deprecated),
        "supersedes_id": (
            str(memory.metadata.supersedes_id) if memory.metadata.supersedes_id else ""
        ),
        "superseded_by_id": (
            str(memory.metadata.superseded_by_id)
            if memory.metadata.superseded_by_id
            else ""
        ),
        "version": max(1, int(memory.metadata.version)),
    }
    return all(properties.get(key) == value for key, value in expected.items())


def _snapshot_matches(
    snapshot: Mapping[str, Any],
    expected: Sequence[Memory],
) -> bool:
    if not snapshot.get("generated_at") or not isinstance(snapshot.get("nodes"), list):
        return False
    nodes = {
        str(node.get("id")): node
        for node in snapshot["nodes"]
        if isinstance(node, Mapping) and node.get("id") is not None
    }
    return all(
        str(memory.id) in nodes
        and _snapshot_memory_matches(nodes[str(memory.id)], memory)
        for memory in expected
    )


class VerifiedCorrectionService:
    """Execute reversible correction actions with product-level proof."""

    def __init__(
        self,
        store: Any,
        graph_store: Any,
        *,
        snapshot_path: Path,
        refresh_snapshot: RefreshSnapshot,
        recall_selected_ids: RecallSelectedIds,
        source_context: Mapping[str, str] | None = None,
        verification_attempts: int = 2,
        now: Callable[[], datetime] | None = None,
        operation_id: Callable[[], UUID] | None = None,
        replacement_id: Callable[[], UUID] | None = None,
    ) -> None:
        if not 1 <= verification_attempts <= 3:
            raise ValueError("verification_attempts must be from 1 to 3")
        self.store = store
        self.graph_store = graph_store
        self.snapshot_path = Path(snapshot_path)
        self.refresh_snapshot = refresh_snapshot
        self.recall_selected_ids = recall_selected_ids
        self.source_context = dict(source_context or {})
        self.verification_attempts = verification_attempts
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._operation_id = operation_id or uuid4
        self._replacement_id = replacement_id or uuid4

    async def _load_target(
        self,
        memory_id: UUID,
    ) -> tuple[Memory | None, Entity | None, tuple[str, ...]]:
        memory = await self.store.get_memory(memory_id)
        entity = await self.graph_store.get_entity(memory_id) if memory is not None else None
        concepts = (
            tuple(await self.graph_store.get_memory_concepts(memory_id))
            if entity is not None
            else ()
        )
        return memory, entity, concepts

    async def plan(
        self,
        memory_id: UUID,
        *,
        action: CorrectionAction | str,
        content: str | None = None,
        confirm_protected: bool = False,
    ) -> VerifiedCorrectionPlan:
        selected = CorrectionAction(str(getattr(action, "value", action)))
        try:
            memory, entity, relationship_concepts = await self._load_target(memory_id)
        except Exception:
            return self._blocked_plan(
                memory_id,
                selected,
                code="RELATIONSHIP_PROJECTION_UNAVAILABLE",
                reason="The memory connections could not be inspected safely.",
            )
        if memory is None:
            return self._blocked_plan(
                memory_id,
                selected,
                code="MEMORY_NOT_FOUND",
                reason="The selected memory no longer exists.",
            )
        record_hash = memory_record_sha256(memory)
        graph_hash = entity_record_sha256(entity) if entity is not None else ""
        scope = memory_scope_values(memory)
        declared_scope = scope_sha256(scope) if any(scope) else None
        protected = is_protected(memory.metadata)
        reason_code: str | None = None
        reason = "The correction is ready for explicit confirmation."
        normalized_content: str | None = None

        if not any(scope):
            reason_code = "DECLARED_SCOPE_REQUIRED"
            reason = "The memory needs one exact declared project scope before correction."
        elif entity is None:
            reason_code = "GRAPH_PROJECTION_REQUIRED"
            reason = "The memory graph projection is missing and must be repaired first."
        elif protected and not confirm_protected:
            reason_code = "PROTECTED_CONFIRMATION_REQUIRED"
            reason = "This protected memory requires explicit protected-memory confirmation."
        elif selected is CorrectionAction.PERMANENT_DELETE:
            reason = (
                "Elefante will create and verify a fresh local backup before "
                "permanently deleting this memory and its unshared attachments."
            )
        elif selected in {CorrectionAction.EDIT, CorrectionAction.REPLACE}:
            try:
                normalized_content = validate_memory_content(content or "")
            except (TypeError, ValueError):
                reason_code = "CORRECTION_CONTENT_INVALID"
                reason = "A bounded replacement value is required."
            if reason_code is None and normalized_content == memory.content:
                reason_code = "NO_SEMANTIC_CHANGE"
                reason = "The proposed content is identical to the current memory."
            elif reason_code is None and _inactive(memory):
                reason_code = "ACTIVE_MEMORY_REQUIRED"
                reason = "Restore this memory before editing or replacing it."
        elif selected is CorrectionAction.ARCHIVE:
            if _inactive(memory):
                reason_code = "ACTIVE_MEMORY_REQUIRED"
                reason = "The memory is already inactive."
            elif _read_restore_point(memory) is not None:
                reason_code = "RESTORE_POINT_CONFLICT"
                reason = "An unresolved archive restore point already exists."
        elif selected is CorrectionAction.RESTORE:
            restore_point = _read_restore_point(memory)
            if not _inactive(memory):
                reason_code = "ARCHIVED_MEMORY_REQUIRED"
                reason = "Only an archived memory can be restored."
            elif restore_point is None:
                reason_code = "RESTORE_POINT_REQUIRED"
                reason = "This legacy archive has no verified restore point."
            elif restore_point.get("kind") != "manual_archive":
                reason_code = "PAIR_CORRECTION_REQUIRED"
                reason = "A superseded memory must be corrected with its paired successor."

        return VerifiedCorrectionPlan(
            schema_version=1,
            action=selected,
            memory_id=str(memory_id),
            applicable=reason_code is None,
            reason_code=reason_code,
            reason=reason,
            protected=protected,
            irreversible=selected is CorrectionAction.PERMANENT_DELETE,
            record_sha256={"target": record_hash},
            graph_sha256=(
                {
                    "target": graph_hash,
                    "target_relationships": _relationship_projection_sha256(
                        relationship_concepts
                    ),
                }
                if graph_hash
                else {}
            ),
            scope_sha256=declared_scope,
            content_sha256=_content_sha256(normalized_content),
        )

    def _blocked_plan(
        self,
        memory_id: UUID,
        action: CorrectionAction,
        *,
        code: str,
        reason: str,
    ) -> VerifiedCorrectionPlan:
        return VerifiedCorrectionPlan(
            schema_version=1,
            action=action,
            memory_id=str(memory_id),
            applicable=False,
            reason_code=code,
            reason=reason,
            protected=False,
            irreversible=action is CorrectionAction.PERMANENT_DELETE,
            record_sha256={},
            graph_sha256={},
            scope_sha256=None,
            content_sha256=None,
        )

    def _edit_after(
        self,
        before: Memory,
        *,
        content: str,
        operation_id: str,
        reason: str,
        now: datetime,
    ) -> Memory:
        after = before.model_copy(deep=True)
        _curate_content(after, content)
        after.metadata.last_modified = now.replace(tzinfo=None)
        after.metadata.version = max(1, int(before.metadata.version)) + 1
        _append_history(
            after,
            operation_id=operation_id,
            action=CorrectionAction.EDIT,
            reason=reason,
            at=now,
            memory_ids={"target": str(before.id)},
        )
        return after

    def _archive_after(
        self,
        before: Memory,
        *,
        operation_id: str,
        reason: str,
        now: datetime,
        kind: str = "manual_archive",
        replacement_id: UUID | None = None,
    ) -> Memory:
        after = before.model_copy(deep=True)
        custom = dict(after.metadata.custom_metadata or {})
        custom[ARCHIVE_RESTORE_POINT_KEY] = _archive_restore_point(before, kind=kind)
        after.metadata.custom_metadata = custom
        after.metadata.status = MemoryStatus.ARCHIVED.value
        after.metadata.archived = True
        after.metadata.deprecated = True
        if replacement_id is not None:
            after.metadata.superseded_by_id = replacement_id
        after.metadata.last_modified = now.replace(tzinfo=None)
        after.metadata.version = max(1, int(before.metadata.version)) + 1
        _append_history(
            after,
            operation_id=operation_id,
            action=(
                CorrectionAction.REPLACE
                if replacement_id is not None
                else CorrectionAction.ARCHIVE
            ),
            reason=reason,
            at=now,
            memory_ids={
                "target": str(before.id),
                "replacement": str(replacement_id) if replacement_id else "",
            },
        )
        return after

    def _restore_after(
        self,
        before: Memory,
        *,
        operation_id: str,
        reason: str,
        now: datetime,
    ) -> Memory:
        point = _read_restore_point(before)
        if point is None or point.get("kind") != "manual_archive":
            raise CorrectionWriteError("RESTORE_POINT_REQUIRED")
        after = before.model_copy(deep=True)
        try:
            after.metadata.status = MemoryStatus(str(point["status"])).value
            after.metadata.archived = bool(point["archived"])
            after.metadata.deprecated = bool(point["deprecated"])
            after.metadata.superseded_by_id = (
                UUID(str(point["superseded_by_id"]))
                if point.get("superseded_by_id")
                else None
            )
            after.metadata.conflict_ids = [
                UUID(str(item)) for item in point.get("conflict_ids", [])
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise CorrectionWriteError("RESTORE_POINT_INVALID") from error
        custom = dict(after.metadata.custom_metadata or {})
        custom.pop(ARCHIVE_RESTORE_POINT_KEY, None)
        after.metadata.custom_metadata = custom
        after.metadata.last_modified = now.replace(tzinfo=None)
        after.metadata.version = max(1, int(before.metadata.version)) + 1
        _append_history(
            after,
            operation_id=operation_id,
            action=CorrectionAction.RESTORE,
            reason=reason,
            at=now,
            memory_ids={"target": str(before.id)},
        )
        return after

    def _replacement_pair(
        self,
        before: Memory,
        *,
        content: str,
        operation_id: str,
        reason: str,
        now: datetime,
    ) -> tuple[Memory, Memory]:
        replacement = before.model_copy(deep=True)
        replacement.id = self._replacement_id()
        _curate_content(replacement, content)
        replacement.metadata.created_at = now.replace(tzinfo=None)
        replacement.metadata.last_accessed = now.replace(tzinfo=None)
        replacement.metadata.last_modified = now.replace(tzinfo=None)
        replacement.metadata.access_count = 0
        replacement.metadata.version = 1
        replacement.metadata.status = MemoryStatus.VERIFIED.value
        replacement.metadata.verified = True
        replacement.metadata.archived = False
        replacement.metadata.deprecated = False
        replacement.metadata.conflict_ids = []
        replacement.metadata.supersedes_id = before.id
        replacement.metadata.superseded_by_id = None
        replacement.metadata.source_detail = "verified_correction_replace"
        replacement_custom = dict(replacement.metadata.custom_metadata or {})
        replacement_custom.pop(ARCHIVE_RESTORE_POINT_KEY, None)
        replacement_custom["elefante_source"] = dict(self.source_context)
        replacement.metadata.custom_metadata = replacement_custom
        _append_history(
            replacement,
            operation_id=operation_id,
            action=CorrectionAction.REPLACE,
            reason=reason,
            at=now,
            memory_ids={"target": str(before.id), "replacement": str(replacement.id)},
        )
        target_after = self._archive_after(
            before,
            operation_id=operation_id,
            reason=reason,
            now=now,
            kind="replacement",
            replacement_id=replacement.id,
        )
        return target_after, replacement

    async def _replace_vector(self, memory: Memory) -> None:
        try:
            await self.store.replace_memory(memory)
        except Exception as error:
            raise CorrectionWriteError("VECTOR_WRITE_FAILED") from error
        current = await self.store.get_memory(memory.id)
        if current is None or memory_record_sha256(current) != memory_record_sha256(memory):
            raise CorrectionWriteError("VECTOR_WRITE_FAILED")

    async def _replace_graph(self, entity: Entity) -> None:
        try:
            await self.graph_store.replace_entity(entity)
        except Exception as error:
            raise CorrectionWriteError("GRAPH_WRITE_FAILED") from error
        current = await self.graph_store.get_entity(entity.id)
        if current is None or entity_record_sha256(current) != entity_record_sha256(entity):
            raise CorrectionWriteError("GRAPH_WRITE_FAILED")

    async def _replace_relationship_projection(self, memory: Memory) -> tuple[str, ...]:
        expected = tuple(
            canonicalize_concepts(list(memory.metadata.concepts or []), max_concepts=5)
        )
        try:
            current = tuple(
                await self.graph_store.replace_memory_concepts(memory.id, list(expected))
            )
        except Exception as error:
            raise CorrectionWriteError("RELATIONSHIP_MINING_FAILED") from error
        if _relationship_projection_sha256(current) != _relationship_projection_sha256(
            expected
        ):
            raise CorrectionWriteError("RELATIONSHIP_MINING_FAILED")
        return expected

    async def _write_single(
        self,
        after: Memory,
        graph_after: Entity,
    ) -> None:
        await self._replace_vector(after)
        await self._replace_graph(graph_after)

    async def _write_replacement(
        self,
        target_after: Memory,
        target_graph_after: Entity,
        replacement: Memory,
        replacement_entity: Entity,
    ) -> None:
        try:
            await self.store.add_memory(replacement)
        except Exception as error:
            raise CorrectionWriteError("REPLACEMENT_VECTOR_CREATE_FAILED") from error
        current = await self.store.get_memory(replacement.id)
        if current is None or memory_record_sha256(current) != memory_record_sha256(replacement):
            raise CorrectionWriteError("REPLACEMENT_VECTOR_CREATE_FAILED")
        try:
            await self.graph_store.create_entity(replacement_entity)
            if hasattr(self.graph_store, "record_memory_source"):
                await self.graph_store.record_memory_source(
                    replacement.id,
                    self.source_context,
                )
        except Exception as error:
            raise CorrectionWriteError("REPLACEMENT_GRAPH_CREATE_FAILED") from error
        created = await self.graph_store.get_entity(replacement.id)
        if created is None or entity_record_sha256(created) != entity_record_sha256(
            replacement_entity
        ):
            raise CorrectionWriteError("REPLACEMENT_GRAPH_CREATE_FAILED")
        await self._replace_vector(target_after)
        await self._replace_graph(target_graph_after)

    async def _replacement_source_state(self) -> tuple[str | None, bool]:
        """Capture whether replacement provenance exists before any write."""
        if not hasattr(self.graph_store, "record_memory_source"):
            return None, True
        required = ("source_id_for", "source_exists", "delete_source_if_orphan")
        if any(not hasattr(self.graph_store, name) for name in required):
            raise CorrectionWriteError("SOURCE_ROLLBACK_UNAVAILABLE")
        try:
            source_id = str(self.graph_store.source_id_for(self.source_context))
            return source_id, bool(await self.graph_store.source_exists(source_id))
        except Exception as error:
            raise CorrectionWriteError("SOURCE_INSPECTION_FAILED") from error

    async def _verify_authoritative(
        self,
        memories: Sequence[Memory],
        entities: Sequence[Entity],
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                memory_ok = True
                for expected in memories:
                    current_memory = await self.store.get_memory(expected.id)
                    if (
                        current_memory is None
                        or memory_record_sha256(current_memory)
                        != memory_record_sha256(expected)
                    ):
                        memory_ok = False
                        break

                entity_ok = True
                for expected in entities:
                    current_entity = await self.graph_store.get_entity(expected.id)
                    if (
                        current_entity is None
                        or entity_record_sha256(current_entity)
                        != entity_record_sha256(expected)
                    ):
                        entity_ok = False
                        break
                if memory_ok and entity_ok:
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _verify_relationship_projection(
        self,
        expected: Mapping[UUID, Sequence[str]],
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                matches = True
                for memory_id, concepts in expected.items():
                    current = await self.graph_store.get_memory_concepts(memory_id)
                    if _relationship_projection_sha256(
                        current
                    ) != _relationship_projection_sha256(concepts):
                        matches = False
                        break
                if matches:
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _refresh_and_verify_snapshot(
        self,
        memories: Sequence[Memory],
        *,
        previous_digest: str | None,
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                result = await self.refresh_snapshot()
                if isinstance(result, Mapping) and result.get("success") is False:
                    continue
                current_digest = snapshot_digest(self.snapshot_path)
                if current_digest is None or current_digest == previous_digest:
                    continue
                if _snapshot_matches(load_snapshot(self.snapshot_path), memories):
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _verify_recall(
        self,
        question: str,
        *,
        memory: Memory,
        include_ids: set[str],
        exclude_ids: set[str],
    ) -> tuple[bool, int]:
        project, workspace = recall_scope(memory)
        for attempt in range(1, self.verification_attempts + 1):
            try:
                selected = {
                    str(item)
                    for item in await self.recall_selected_ids(
                        question,
                        project=project,
                        workspace=workspace,
                    )
                }
                if include_ids.issubset(selected) and not selected.intersection(exclude_ids):
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _restore_snapshot(self, state: PrivateFileState) -> bool:
        try:
            restore_private_file(self.snapshot_path, state)
        except Exception:
            return False
        if not state.existed:
            return not self.snapshot_path.exists()
        return bool(
            state.payload is not None
            and snapshot_digest(self.snapshot_path)
            == hashlib.sha256(state.payload).hexdigest()
        )

    async def _rollback_single(
        self,
        before: Memory,
        graph_before: Entity,
        relationships_before: Sequence[str],
        snapshot_before: PrivateFileState,
    ) -> bool:
        vector_ok = graph_ok = relationships_ok = False
        try:
            await self.store.replace_memory(before)
            current = await self.store.get_memory(before.id)
            vector_ok = bool(
                current is not None
                and memory_record_sha256(current) == memory_record_sha256(before)
            )
        except Exception:
            vector_ok = False
        try:
            await self.graph_store.replace_entity(graph_before)
            current_entity = await self.graph_store.get_entity(graph_before.id)
            graph_ok = bool(
                current_entity is not None
                and entity_record_sha256(current_entity)
                == entity_record_sha256(graph_before)
            )
        except Exception:
            graph_ok = False
        try:
            restored = await self.graph_store.replace_memory_concepts(
                before.id,
                list(relationships_before),
            )
            relationships_ok = _relationship_projection_sha256(
                restored
            ) == _relationship_projection_sha256(relationships_before)
        except Exception:
            relationships_ok = False
        snapshot_ok = await self._restore_snapshot(snapshot_before)
        return vector_ok and graph_ok and relationships_ok and snapshot_ok

    async def _rollback_replacement(
        self,
        before: Memory,
        graph_before: Entity,
        relationships_before: Sequence[str],
        replacement_id: UUID,
        snapshot_before: PrivateFileState,
        source_id: str | None,
        source_preexisted: bool,
    ) -> bool:
        base_ok = await self._rollback_single(
            before,
            graph_before,
            relationships_before,
            snapshot_before,
        )
        try:
            replacement_entity = await self.graph_store.get_entity(replacement_id)
            if replacement_entity is None:
                replacement_relationships_removed = True
            else:
                replacement_relationships_removed = not bool(
                    await self.graph_store.replace_memory_concepts(replacement_id, [])
                )
        except Exception:
            replacement_relationships_removed = False
        try:
            await self.graph_store.delete_entity(replacement_id)
            graph_removed = await self.graph_store.get_entity(replacement_id) is None
        except Exception:
            graph_removed = False
        try:
            await self.store.delete_memory(replacement_id)
            vector_removed = await self.store.get_memory(replacement_id) is None
        except Exception:
            vector_removed = False
        source_ok = True
        if source_id is not None and not source_preexisted:
            try:
                source_ok = bool(
                    await self.graph_store.delete_source_if_orphan(source_id)
                )
            except Exception:
                source_ok = False
        return (
            base_ok
            and replacement_relationships_removed
            and graph_removed
            and vector_removed
            and source_ok
        )

    async def _state_is_before(
        self,
        memory: Memory,
        entity: Entity,
        relationships: Sequence[str],
    ) -> bool:
        try:
            current_memory = await self.store.get_memory(memory.id)
            current_entity = await self.graph_store.get_entity(entity.id)
            current_relationships = await self.graph_store.get_memory_concepts(
                memory.id
            )
        except Exception:
            return False
        return bool(
            current_memory is not None
            and current_entity is not None
            and memory_record_sha256(current_memory) == memory_record_sha256(memory)
            and entity_record_sha256(current_entity) == entity_record_sha256(entity)
            and _relationship_projection_sha256(current_relationships)
            == _relationship_projection_sha256(relationships)
        )

    def _receipt(
        self,
        *,
        operation_id: str,
        started_at: str,
        status: VerifiedOperationStatus,
        plan: VerifiedCorrectionPlan,
        memory_ids: Mapping[str, str],
        record_hashes: Mapping[str, str],
        graph_hashes: Mapping[str, str],
        checks: Sequence[VerifiedOperationCheck],
        error_codes: Sequence[str],
        rollback: str,
        changed: bool,
    ) -> VerifiedCorrectionReceipt:
        return VerifiedCorrectionReceipt(
            schema_version=1,
            operation_id=operation_id,
            operation=plan.action.value,
            status=status,
            authority="user_directed",
            started_at=started_at,
            finished_at=self._now().astimezone(timezone.utc).isoformat(),
            memory_ids=dict(memory_ids),
            scope_sha256=plan.scope_sha256 or "",
            record_sha256=dict(record_hashes),
            graph_sha256=dict(graph_hashes),
            checks=tuple(checks)[:8],
            error_codes=tuple(dict.fromkeys(error_codes))[:8],
            rollback=rollback,
            changed=changed,
            recoverable=plan.action is not CorrectionAction.PERMANENT_DELETE,
        )

    def _terminal(
        self,
        *,
        operation_id: str,
        started_at: str,
        status: VerifiedOperationStatus,
        plan: VerifiedCorrectionPlan,
        memory_ids: Mapping[str, str],
        record_hashes: Mapping[str, str] | None = None,
        graph_hashes: Mapping[str, str] | None = None,
        checks: Sequence[VerifiedOperationCheck] = (),
        error_codes: Sequence[str] = (),
        rollback: str = "not_required",
        changed: bool = False,
    ) -> VerifiedCorrectionResult:
        return VerifiedCorrectionResult(
            status=status,
            plan=plan,
            receipt=self._receipt(
                operation_id=operation_id,
                started_at=started_at,
                status=status,
                plan=plan,
                memory_ids=memory_ids,
                record_hashes=record_hashes or {},
                graph_hashes=graph_hashes or {},
                checks=checks,
                error_codes=error_codes,
                rollback=rollback,
                changed=changed,
            ),
        )

    async def execute(
        self,
        memory_id: UUID,
        *,
        action: CorrectionAction | str,
        content: str | None,
        reason: str,
        verification_question: str,
        confirm_protected: bool = False,
        expected_record_sha256: Mapping[str, str] | None = None,
        expected_graph_sha256: Mapping[str, str] | None = None,
        expected_content_sha256: str | None = None,
    ) -> VerifiedCorrectionResult:
        operation_id = str(self._operation_id())
        started_at = self._now().astimezone(timezone.utc).isoformat()
        selected = CorrectionAction(str(getattr(action, "value", action)))
        reason = str(reason or "").strip()
        verification_question = str(verification_question or "").strip()
        plan = await self.plan(
            memory_id,
            action=selected,
            content=content,
            confirm_protected=confirm_protected,
        )
        base_ids = {"target": str(memory_id), "replacement": ""}
        if not plan.applicable:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                memory_ids=base_ids,
                error_codes=(plan.reason_code or "CORRECTION_BLOCKED",),
            )
        if expected_record_sha256 is not None and dict(expected_record_sha256) != plan.record_sha256:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                memory_ids=base_ids,
                error_codes=("PLAN_STALE",),
            )
        if expected_graph_sha256 is not None and dict(expected_graph_sha256) != plan.graph_sha256:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                memory_ids=base_ids,
                error_codes=("PLAN_STALE",),
            )
        if expected_content_sha256 is not None and expected_content_sha256 != plan.content_sha256:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                memory_ids=base_ids,
                error_codes=("PLAN_STALE",),
            )
        validation_errors: list[str] = []
        if not reason or len(reason) > 1000:
            validation_errors.append("AUDIT_REASON_REQUIRED")
        if not verification_question or len(verification_question) > 1000:
            validation_errors.append("VERIFICATION_QUESTION_REQUIRED")
        if validation_errors:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                memory_ids=base_ids,
                error_codes=validation_errors,
            )

        try:
            before, graph_before, relationships_before = await self._load_target(
                memory_id
            )
        except Exception:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                plan=plan,
                memory_ids=base_ids,
                error_codes=("RELATIONSHIP_INSPECTION_FAILED",),
            )
        if before is None or graph_before is None:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                plan=plan,
                memory_ids=base_ids,
                error_codes=("TARGET_INSPECTION_FAILED",),
            )
        if (
            memory_record_sha256(before) != plan.record_sha256["target"]
            or entity_record_sha256(graph_before) != plan.graph_sha256["target"]
            or _relationship_projection_sha256(relationships_before)
            != plan.graph_sha256["target_relationships"]
        ):
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                memory_ids=base_ids,
                error_codes=("PLAN_STALE",),
            )

        snapshot_before = capture_private_file(self.snapshot_path)
        prior_snapshot_digest = snapshot_digest(self.snapshot_path)
        now = self._now().astimezone(timezone.utc)
        replacement: Memory | None = None
        replacement_source_id: str | None = None
        replacement_source_preexisted = True
        expected_memories: list[Memory]
        expected_entities: list[Entity]
        expected_relationships: dict[UUID, tuple[str, ...]]
        include_ids: set[str]
        exclude_ids: set[str]

        try:
            if selected is CorrectionAction.EDIT:
                after = self._edit_after(
                    before,
                    content=str(content),
                    operation_id=operation_id,
                    reason=reason,
                    now=now,
                )
                _set_recall_cue(after, verification_question, replace=True)
                graph_after = _entity_projection(after, graph_before)
                await self._write_single(after, graph_after)
                mined_concepts = await self._replace_relationship_projection(after)
                expected_memories = [after]
                expected_entities = [graph_after]
                expected_relationships = {after.id: mined_concepts}
                include_ids = {str(after.id)}
                exclude_ids = set()
            elif selected is CorrectionAction.ARCHIVE:
                after = self._archive_after(
                    before,
                    operation_id=operation_id,
                    reason=reason,
                    now=now,
                )
                graph_after = _entity_projection(after, graph_before)
                await self._write_single(after, graph_after)
                expected_memories = [after]
                expected_entities = [graph_after]
                expected_relationships = {after.id: relationships_before}
                include_ids = set()
                exclude_ids = {str(after.id)}
            elif selected is CorrectionAction.RESTORE:
                after = self._restore_after(
                    before,
                    operation_id=operation_id,
                    reason=reason,
                    now=now,
                )
                _set_recall_cue(after, verification_question, replace=False)
                graph_after = _entity_projection(after, graph_before)
                await self._write_single(after, graph_after)
                expected_memories = [after]
                expected_entities = [graph_after]
                expected_relationships = {after.id: relationships_before}
                include_ids = {str(after.id)}
                exclude_ids = set()
            elif selected is CorrectionAction.REPLACE:
                (
                    replacement_source_id,
                    replacement_source_preexisted,
                ) = await self._replacement_source_state()
                target_after, replacement = self._replacement_pair(
                    before,
                    content=str(content),
                    operation_id=operation_id,
                    reason=reason,
                    now=now,
                )
                _set_recall_cue(replacement, verification_question, replace=True)
                target_graph_after = _entity_projection(target_after, graph_before)
                replacement_entity = _entity_projection(replacement)
                await self._write_replacement(
                    target_after,
                    target_graph_after,
                    replacement,
                    replacement_entity,
                )
                replacement_concepts = await self._replace_relationship_projection(
                    replacement
                )
                expected_memories = [target_after, replacement]
                expected_entities = [target_graph_after, replacement_entity]
                expected_relationships = {
                    target_after.id: relationships_before,
                    replacement.id: replacement_concepts,
                }
                include_ids = {str(replacement.id)}
                exclude_ids = {str(before.id)}
                base_ids["replacement"] = str(replacement.id)
            else:
                raise CorrectionWriteError("RECOVERY_BASELINE_REQUIRED")
        except Exception as error:
            state_is_before = await self._state_is_before(
                before,
                graph_before,
                relationships_before,
            )
            error_code = str(getattr(error, "code", "CORRECTION_WRITE_FAILED"))
            if state_is_before and replacement is None:
                snapshot_ok = await self._restore_snapshot(snapshot_before)
                status = (
                    VerifiedOperationStatus.FAILED_NO_CHANGE
                    if snapshot_ok
                    else VerifiedOperationStatus.UNSAFE
                )
                rollback = "not_required" if snapshot_ok else "incomplete"
            else:
                rollback_ok = (
                    await self._rollback_replacement(
                        before,
                        graph_before,
                        relationships_before,
                        replacement.id,
                        snapshot_before,
                        replacement_source_id,
                        replacement_source_preexisted,
                    )
                    if replacement is not None
                    else await self._rollback_single(
                        before,
                        graph_before,
                        relationships_before,
                        snapshot_before,
                    )
                )
                status = (
                    VerifiedOperationStatus.FAILED_ROLLED_BACK
                    if rollback_ok
                    else VerifiedOperationStatus.UNSAFE
                )
                rollback = "verified" if rollback_ok else "incomplete"
                if not rollback_ok:
                    error_code = f"{error_code}|ROLLBACK_INCOMPLETE"
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=status,
                plan=plan,
                memory_ids=base_ids,
                record_hashes={"target_before": memory_record_sha256(before)},
                graph_hashes={
                    "target_before": entity_record_sha256(graph_before),
                    "target_relationships_before": _relationship_projection_sha256(
                        relationships_before
                    ),
                },
                error_codes=tuple(error_code.split("|")),
                rollback=rollback,
                changed=status is VerifiedOperationStatus.UNSAFE,
            )

        checks: list[VerifiedOperationCheck] = []
        authoritative_ok, authoritative_attempts = await self._verify_authoritative(
            expected_memories,
            expected_entities,
        )
        checks.append(
            VerifiedOperationCheck(
                name="authoritative_store_and_graph",
                passed=authoritative_ok,
                attempts=authoritative_attempts,
                code=(
                    "AUTHORITATIVE_POSTCONDITION_OK"
                    if authoritative_ok
                    else "AUTHORITATIVE_POSTCONDITION_FAILED"
                ),
            )
        )
        postcondition_error: str | None = None
        if not authoritative_ok:
            postcondition_error = "AUTHORITATIVE_POSTCONDITION_FAILED"
        else:
            relationship_ok, relationship_attempts = (
                await self._verify_relationship_projection(expected_relationships)
            )
            checks.append(
                VerifiedOperationCheck(
                    name="relationship_projection",
                    passed=relationship_ok,
                    attempts=relationship_attempts,
                    code=(
                        "RELATIONSHIP_POSTCONDITION_OK"
                        if relationship_ok
                        else "RELATIONSHIP_POSTCONDITION_FAILED"
                    ),
                )
            )
            if not relationship_ok:
                postcondition_error = "RELATIONSHIP_POSTCONDITION_FAILED"
            else:
                snapshot_ok, snapshot_attempts = (
                    await self._refresh_and_verify_snapshot(
                        expected_memories,
                        previous_digest=prior_snapshot_digest,
                    )
                )
                checks.append(
                    VerifiedOperationCheck(
                        name="dashboard_snapshot",
                        passed=snapshot_ok,
                        attempts=snapshot_attempts,
                        code=(
                            "SNAPSHOT_POSTCONDITION_OK"
                            if snapshot_ok
                            else "SNAPSHOT_POSTCONDITION_FAILED"
                        ),
                    )
                )
                if not snapshot_ok:
                    postcondition_error = "SNAPSHOT_POSTCONDITION_FAILED"
                else:
                    recall_memory = replacement or expected_memories[0]
                    recall_ok, recall_attempts = await self._verify_recall(
                        verification_question,
                        memory=recall_memory,
                        include_ids=include_ids,
                        exclude_ids=exclude_ids,
                    )
                    checks.append(
                        VerifiedOperationCheck(
                            name="scoped_recall",
                            passed=recall_ok,
                            attempts=recall_attempts,
                            code=(
                                "RECALL_POSTCONDITION_OK"
                                if recall_ok
                                else "RECALL_POSTCONDITION_FAILED"
                            ),
                        )
                    )
                    if not recall_ok:
                        postcondition_error = "RECALL_POSTCONDITION_FAILED"

        record_hashes = {"target_before": memory_record_sha256(before)}
        graph_hashes = {
            "target_before": entity_record_sha256(graph_before),
            "target_relationships_before": _relationship_projection_sha256(
                relationships_before
            ),
        }
        for index, memory in enumerate(expected_memories):
            key = "replacement_after" if replacement is not None and memory.id == replacement.id else "target_after"
            record_hashes[key] = memory_record_sha256(memory)
            graph_hashes[key] = entity_record_sha256(expected_entities[index])
            graph_hashes[f"{key}_relationships"] = _relationship_projection_sha256(
                expected_relationships[memory.id]
            )

        if postcondition_error is None:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.VERIFIED_COMPLETE,
                plan=plan,
                memory_ids=base_ids,
                record_hashes=record_hashes,
                graph_hashes=graph_hashes,
                checks=checks,
                changed=True,
            )

        rollback_ok = (
            await self._rollback_replacement(
                before,
                graph_before,
                relationships_before,
                replacement.id,
                snapshot_before,
                replacement_source_id,
                replacement_source_preexisted,
            )
            if replacement is not None
            else await self._rollback_single(
                before,
                graph_before,
                relationships_before,
                snapshot_before,
            )
        )
        status = (
            VerifiedOperationStatus.FAILED_ROLLED_BACK
            if rollback_ok
            else VerifiedOperationStatus.UNSAFE
        )
        error_codes = [postcondition_error]
        if not rollback_ok:
            error_codes.append("ROLLBACK_INCOMPLETE")
        return self._terminal(
            operation_id=operation_id,
            started_at=started_at,
            status=status,
            plan=plan,
            memory_ids=base_ids,
            record_hashes=record_hashes,
            graph_hashes=graph_hashes,
            checks=checks,
            error_codes=error_codes,
            rollback="verified" if rollback_ok else "incomplete",
            changed=not rollback_ok,
        )


__all__ = [
    "ARCHIVE_RESTORE_POINT_KEY",
    "CORRECTION_HISTORY_KEY",
    "CorrectionAction",
    "VerifiedCorrectionPlan",
    "VerifiedCorrectionReceipt",
    "VerifiedCorrectionResult",
    "VerifiedCorrectionService",
]
