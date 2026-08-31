"""Verified assignment of one legacy unscoped memory to one registered project.

The operation never infers scope from memory text.  A customer selects the
target project, Elefante binds the exact unscoped preimage, writes the declared
project tuple once, verifies every customer-visible projection, and restores
the exact preimage if any postcondition fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    scope_sha256,
    snapshot_digest,
)
from src.models.entity import Entity, EntityType
from src.models.memory import Memory
from src.utils.atomic_json import (
    PrivateFileState,
    capture_private_file,
    restore_private_file,
)
from src.utils.curation import generate_summary, generate_title


RefreshSnapshot = Callable[[], Awaitable[Mapping[str, Any] | None]]
ScopedMemoryIds = Callable[..., Awaitable[Sequence[str]]]

PROJECT_ASSIGNMENT_HISTORY_KEY = "verified_project_assignment_history"


@dataclass(frozen=True)
class VerifiedProjectAssignmentPlan:
    schema_version: int
    memory_id: str
    project_id: str
    project_name: str
    applicable: bool
    reason_code: str | None
    reason: str
    protected: bool
    record_sha256: str | None
    graph_existed: bool
    graph_sha256: str | None
    relationship_sha256: str | None
    target_scope_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "memory_id": self.memory_id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "applicable": self.applicable,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "protected": self.protected,
            "record_sha256": self.record_sha256,
            "graph_existed": self.graph_existed,
            "graph_sha256": self.graph_sha256,
            "relationship_sha256": self.relationship_sha256,
            "target_scope_sha256": self.target_scope_sha256,
        }


@dataclass(frozen=True)
class VerifiedProjectAssignmentReceipt:
    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedOperationStatus
    authority: str
    started_at: str
    finished_at: str
    memory_id: str
    project_id: str
    target_scope_sha256: str
    record_sha256: dict[str, str]
    graph_sha256: dict[str, str]
    checks: tuple[VerifiedOperationCheck, ...]
    error_codes: tuple[str, ...]
    rollback: str
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "operation": self.operation,
            "status": self.status.value,
            "authority": self.authority,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "memory_id": self.memory_id,
            "project_id": self.project_id,
            "target_scope_sha256": self.target_scope_sha256,
            "record_sha256": dict(self.record_sha256),
            "graph_sha256": dict(self.graph_sha256),
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
            "rollback": self.rollback,
            "changed": self.changed,
        }


@dataclass(frozen=True)
class VerifiedProjectAssignmentResult:
    status: VerifiedOperationStatus
    plan: VerifiedProjectAssignmentPlan
    receipt: VerifiedProjectAssignmentReceipt
    title: str | None = None

    @property
    def success(self) -> bool:
        return self.status is VerifiedOperationStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "status": self.status.value,
            "assignment_status": self.status.value,
            "plan": self.plan.to_dict(),
            "receipt": self.receipt.to_dict(),
        }
        if self.success and self.title:
            payload["assigned"] = {
                "memory_id": self.plan.memory_id,
                "title": self.title,
                "project": {
                    "project_id": self.plan.project_id,
                    "name": self.plan.project_name,
                },
            }
        return payload


class ProjectAssignmentWriteError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _relationship_sha256(concepts: Sequence[str]) -> str:
    payload = json.dumps(
        sorted({str(value).strip().casefold() for value in concepts if str(value).strip()}),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _title(memory: Memory) -> str:
    custom = dict(memory.metadata.custom_metadata or {})
    return str(custom.get("title") or generate_title(content=memory.content, max_len=120))


def _summary(memory: Memory) -> str:
    custom = dict(memory.metadata.custom_metadata or {})
    return str(
        custom.get("summary")
        or memory.metadata.summary
        or generate_summary(content=memory.content, max_len=220)
    )


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _assignment_entity(memory: Memory, existing: Entity | None) -> Entity:
    properties = dict(existing.properties if existing is not None else {})
    properties.update(
        {
            "content": memory.content[:200],
            "memory_type": _enum_text(memory.metadata.memory_type),
            "score": memory.metadata.score,
            "status": _enum_text(memory.metadata.status),
            "timestamp": memory.metadata.created_at.isoformat(),
            "project": memory.metadata.project,
            "workspace": memory.metadata.workspace,
            "scope": memory.metadata.scope,
            "version": max(1, int(memory.metadata.version)),
        }
    )
    return Entity(
        id=memory.id,
        name=(existing.name if existing is not None else _title(memory)),
        type=(existing.type if existing is not None else EntityType.MEMORY),
        description=(existing.description if existing is not None else _summary(memory)),
        created_at=(existing.created_at if existing is not None else memory.metadata.created_at),
        updated_at=memory.metadata.last_modified,
        properties=properties,
        tags=(list(existing.tags) if existing is not None else []),
    )


def _snapshot_has_assignment(
    snapshot: Mapping[str, Any],
    memory: Memory,
) -> bool:
    nodes = snapshot.get("nodes")
    if not isinstance(nodes, list) or not snapshot.get("generated_at"):
        return False
    for node in nodes:
        if not isinstance(node, Mapping) or str(node.get("id")) != str(memory.id):
            continue
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            return False
        return (
            properties.get("project") == memory.metadata.project
            and properties.get("workspace") == memory.metadata.workspace
            and properties.get("scope") == memory.metadata.scope
            and int(properties.get("version") or 0)
            == max(1, int(memory.metadata.version))
        )
    return False


class VerifiedProjectAssignmentService:
    """Assign one exact legacy unscoped record with reversible proof."""

    def __init__(
        self,
        store: Any,
        graph_store: Any,
        *,
        snapshot_path: Path,
        refresh_snapshot: RefreshSnapshot,
        scoped_memory_ids: ScopedMemoryIds,
        verification_attempts: int = 2,
        now: Callable[[], datetime] | None = None,
        operation_id: Callable[[], UUID] | None = None,
    ) -> None:
        if not 1 <= verification_attempts <= 3:
            raise ValueError("verification_attempts must be from 1 to 3")
        self.store = store
        self.graph_store = graph_store
        self.snapshot_path = Path(snapshot_path)
        self.refresh_snapshot = refresh_snapshot
        self.scoped_memory_ids = scoped_memory_ids
        self.verification_attempts = verification_attempts
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._operation_id = operation_id or uuid4

    async def _load_target(
        self,
        memory_id: UUID,
    ) -> tuple[Memory | None, Entity | None, tuple[str, ...]]:
        memory = await self.store.get_memory(memory_id)
        if memory is None:
            return None, None, ()
        entity = await self.graph_store.get_entity(memory_id)
        concepts = tuple(await self.graph_store.get_memory_concepts(memory_id))
        return memory, entity, concepts

    async def plan(
        self,
        memory_id: UUID,
        *,
        project_id: str,
        project_name: str,
        workspace: str,
        scope: str,
        confirm_protected: bool = False,
    ) -> VerifiedProjectAssignmentPlan:
        try:
            normalized_project_id = str(UUID(str(project_id)))
        except (TypeError, ValueError):
            return self._blocked_plan(
                memory_id,
                project_id=str(project_id),
                project_name=str(project_name),
                code="PROJECT_ID_INVALID",
                reason="The selected project identity is invalid.",
            )
        expected_scope = f"project:{normalized_project_id}"
        if (
            not str(project_name).strip()
            or not str(workspace).strip()
            or str(scope).strip() != expected_scope
        ):
            return self._blocked_plan(
                memory_id,
                project_id=normalized_project_id,
                project_name=str(project_name),
                code="PROJECT_SCOPE_INVALID",
                reason="The selected project scope is incomplete or inconsistent.",
            )
        try:
            memory, entity, concepts = await self._load_target(memory_id)
        except Exception:
            return self._blocked_plan(
                memory_id,
                project_id=normalized_project_id,
                project_name=str(project_name),
                code="PROJECT_ASSIGNMENT_INSPECTION_FAILED",
                reason="The selected memory could not be inspected safely.",
            )
        if memory is None:
            return self._blocked_plan(
                memory_id,
                project_id=normalized_project_id,
                project_name=str(project_name),
                code="MEMORY_NOT_FOUND",
                reason="The selected memory no longer exists.",
            )
        if any(memory_scope_values(memory)):
            return self._blocked_plan(
                memory_id,
                project_id=normalized_project_id,
                project_name=str(project_name),
                code="LEGACY_UNSCOPED_MEMORY_REQUIRED",
                reason="Only a fully unassigned legacy memory can use this review action.",
            )
        if entity is None and concepts:
            return self._blocked_plan(
                memory_id,
                project_id=normalized_project_id,
                project_name=str(project_name),
                code="GRAPH_PROJECTION_INCONSISTENT",
                reason="The memory graph needs repair before its project can be assigned.",
            )
        protected = is_protected(memory.metadata)
        applicable = not protected or confirm_protected
        return VerifiedProjectAssignmentPlan(
            schema_version=1,
            memory_id=str(memory_id),
            project_id=normalized_project_id,
            project_name=str(project_name).strip(),
            applicable=applicable,
            reason_code=(None if applicable else "PROTECTED_CONFIRMATION_REQUIRED"),
            reason=(
                "The unassigned memory is ready for verified project assignment."
                if applicable
                else "This protected memory requires explicit confirmation before its project can change."
            ),
            protected=protected,
            record_sha256=memory_record_sha256(memory),
            graph_existed=entity is not None,
            graph_sha256=(entity_record_sha256(entity) if entity is not None else None),
            relationship_sha256=_relationship_sha256(concepts),
            target_scope_sha256=scope_sha256(
                (
                    normalized_project_id.casefold(),
                    str(workspace).strip().casefold(),
                    expected_scope.casefold(),
                )
            ),
        )

    @staticmethod
    def _blocked_plan(
        memory_id: UUID,
        *,
        project_id: str,
        project_name: str,
        code: str,
        reason: str,
    ) -> VerifiedProjectAssignmentPlan:
        return VerifiedProjectAssignmentPlan(
            schema_version=1,
            memory_id=str(memory_id),
            project_id=project_id,
            project_name=project_name,
            applicable=False,
            reason_code=code,
            reason=reason,
            protected=False,
            record_sha256=None,
            graph_existed=False,
            graph_sha256=None,
            relationship_sha256=None,
            target_scope_sha256=None,
        )

    def _assigned_memory(
        self,
        before: Memory,
        *,
        project_id: str,
        workspace: str,
        scope: str,
        operation_id: str,
        now: datetime,
    ) -> Memory:
        after = before.model_copy(deep=True)
        after.metadata.project = project_id
        after.metadata.workspace = workspace
        after.metadata.scope = scope
        after.metadata.last_modified = now.replace(tzinfo=None)
        after.metadata.version = max(1, int(before.metadata.version)) + 1
        custom = dict(after.metadata.custom_metadata or {})
        raw_history = custom.get(PROJECT_ASSIGNMENT_HISTORY_KEY)
        history = list(raw_history) if isinstance(raw_history, list) else []
        history.append(
            {
                "operation_id": operation_id,
                "action": "assign_project",
                "at": now.isoformat(),
                "project_id": project_id,
                "invocation_mode": "user_directed",
            }
        )
        custom[PROJECT_ASSIGNMENT_HISTORY_KEY] = history[-50:]
        after.metadata.custom_metadata = custom
        return after

    async def _replace_memory(self, memory: Memory) -> None:
        try:
            written = await self.store.replace_memory(memory)
        except Exception as error:
            raise ProjectAssignmentWriteError("VECTOR_WRITE_FAILED") from error
        if written is False:
            raise ProjectAssignmentWriteError("VECTOR_WRITE_FAILED")

    async def _replace_or_create_entity(
        self,
        entity: Entity,
        *,
        existed: bool,
    ) -> None:
        try:
            written = (
                await self.graph_store.replace_entity(entity)
                if existed
                else await self.graph_store.create_entity(entity)
            )
        except Exception as error:
            raise ProjectAssignmentWriteError("GRAPH_WRITE_FAILED") from error
        if written is False:
            raise ProjectAssignmentWriteError("GRAPH_WRITE_FAILED")

    async def _verify_authoritative(
        self,
        memory: Memory,
        entity: Entity,
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                current_memory = await self.store.get_memory(memory.id)
                current_entity = await self.graph_store.get_entity(entity.id)
                if (
                    current_memory is not None
                    and current_entity is not None
                    and memory_record_sha256(current_memory)
                    == memory_record_sha256(memory)
                    and entity_record_sha256(current_entity)
                    == entity_record_sha256(entity)
                ):
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _verify_relationships(
        self,
        memory_id: UUID,
        expected_sha256: str,
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                current = await self.graph_store.get_memory_concepts(memory_id)
                if _relationship_sha256(current) == expected_sha256:
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _verify_snapshot(
        self,
        memory: Memory,
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
                if _snapshot_has_assignment(load_snapshot(self.snapshot_path), memory):
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _verify_project_filter(
        self,
        memory: Memory,
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                selected = {
                    str(value)
                    for value in await self.scoped_memory_ids(
                        project=str(memory.metadata.project),
                        workspace=str(memory.metadata.workspace),
                    )
                }
                if str(memory.id) in selected:
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _rollback(
        self,
        *,
        before: Memory,
        entity_before: Entity | None,
        relationship_sha256: str,
        snapshot_before: PrivateFileState,
    ) -> bool:
        try:
            await self._replace_memory(before)
            if entity_before is None:
                await self.graph_store.delete_entity(before.id)
            else:
                replaced = await self.graph_store.replace_entity(entity_before)
                if replaced is False:
                    return False
            restore_private_file(self.snapshot_path, snapshot_before)
            current_memory = await self.store.get_memory(before.id)
            current_entity = await self.graph_store.get_entity(before.id)
            current_relationships = await self.graph_store.get_memory_concepts(before.id)
            return (
                current_memory is not None
                and memory_record_sha256(current_memory) == memory_record_sha256(before)
                and (
                    current_entity is None
                    if entity_before is None
                    else current_entity is not None
                    and entity_record_sha256(current_entity)
                    == entity_record_sha256(entity_before)
                )
                and _relationship_sha256(current_relationships) == relationship_sha256
                and capture_private_file(self.snapshot_path) == snapshot_before
            )
        except Exception:
            return False

    def _receipt(
        self,
        *,
        plan: VerifiedProjectAssignmentPlan,
        operation_id: str,
        status: VerifiedOperationStatus,
        started_at: datetime,
        finished_at: datetime,
        checks: Sequence[VerifiedOperationCheck],
        error_codes: Sequence[str],
        rollback: str,
        changed: bool,
        after_memory: Memory | None = None,
        after_entity: Entity | None = None,
    ) -> VerifiedProjectAssignmentReceipt:
        record_hashes = {}
        graph_hashes = {}
        if plan.record_sha256:
            record_hashes["before"] = plan.record_sha256
        if after_memory is not None:
            record_hashes["after"] = memory_record_sha256(after_memory)
        if plan.graph_sha256:
            graph_hashes["before"] = plan.graph_sha256
        if after_entity is not None:
            graph_hashes["after"] = entity_record_sha256(after_entity)
        if plan.relationship_sha256:
            graph_hashes["relationships"] = plan.relationship_sha256
        return VerifiedProjectAssignmentReceipt(
            schema_version=1,
            operation_id=operation_id,
            operation="assign_project",
            status=status,
            authority="user_directed",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            memory_id=plan.memory_id,
            project_id=plan.project_id,
            target_scope_sha256=plan.target_scope_sha256 or "",
            record_sha256=record_hashes,
            graph_sha256=graph_hashes,
            checks=tuple(checks),
            error_codes=tuple(dict.fromkeys(error_codes)),
            rollback=rollback,
            changed=changed,
        )

    async def execute(
        self,
        memory_id: UUID,
        *,
        project_id: str,
        project_name: str,
        workspace: str,
        scope: str,
        confirm_protected: bool,
        expected_record_sha256: str,
        expected_graph_existed: bool,
        expected_graph_sha256: str | None,
        expected_relationship_sha256: str,
        expected_target_scope_sha256: str,
    ) -> VerifiedProjectAssignmentResult:
        started_at = self._now()
        operation_id = str(self._operation_id())
        plan = await self.plan(
            memory_id,
            project_id=project_id,
            project_name=project_name,
            workspace=workspace,
            scope=scope,
            confirm_protected=confirm_protected,
        )
        if not plan.applicable:
            status = VerifiedOperationStatus.NEEDS_HUMAN
            receipt = self._receipt(
                plan=plan,
                operation_id=operation_id,
                status=status,
                started_at=started_at,
                finished_at=self._now(),
                checks=(),
                error_codes=(plan.reason_code or "PROJECT_ASSIGNMENT_BLOCKED",),
                rollback="not_required",
                changed=False,
            )
            return VerifiedProjectAssignmentResult(status, plan, receipt)
        if (
            plan.record_sha256 != expected_record_sha256
            or plan.graph_existed is not expected_graph_existed
            or plan.graph_sha256 != expected_graph_sha256
            or plan.relationship_sha256 != expected_relationship_sha256
            or plan.target_scope_sha256 != expected_target_scope_sha256
        ):
            status = VerifiedOperationStatus.NEEDS_HUMAN
            receipt = self._receipt(
                plan=plan,
                operation_id=operation_id,
                status=status,
                started_at=started_at,
                finished_at=self._now(),
                checks=(),
                error_codes=("PROJECT_ASSIGNMENT_PLAN_STALE",),
                rollback="not_required",
                changed=False,
            )
            return VerifiedProjectAssignmentResult(status, plan, receipt)

        before, entity_before, concepts_before = await self._load_target(memory_id)
        if before is None:
            status = VerifiedOperationStatus.NEEDS_HUMAN
            receipt = self._receipt(
                plan=plan,
                operation_id=operation_id,
                status=status,
                started_at=started_at,
                finished_at=self._now(),
                checks=(),
                error_codes=("MEMORY_NOT_FOUND",),
                rollback="not_required",
                changed=False,
            )
            return VerifiedProjectAssignmentResult(status, plan, receipt)

        snapshot_before = capture_private_file(self.snapshot_path)
        previous_snapshot_digest = snapshot_digest(self.snapshot_path)
        after = self._assigned_memory(
            before,
            project_id=plan.project_id,
            workspace=str(workspace).strip(),
            scope=str(scope).strip(),
            operation_id=operation_id,
            now=started_at,
        )
        entity_after = _assignment_entity(after, entity_before)
        checks: list[VerifiedOperationCheck] = []
        errors: list[str] = []
        try:
            await self._replace_memory(after)
            await self._replace_or_create_entity(
                entity_after,
                existed=entity_before is not None,
            )
            authoritative_ok, authoritative_attempts = await self._verify_authoritative(
                after,
                entity_after,
            )
            checks.append(
                VerifiedOperationCheck(
                    "authoritative_store_and_graph",
                    authoritative_ok,
                    authoritative_attempts,
                    "AUTHORITATIVE_STATE_VERIFIED" if authoritative_ok else "AUTHORITATIVE_STATE_FAILED",
                )
            )
            relationships_ok, relationship_attempts = await self._verify_relationships(
                memory_id,
                plan.relationship_sha256 or "",
            )
            checks.append(
                VerifiedOperationCheck(
                    "relationship_projection",
                    relationships_ok,
                    relationship_attempts,
                    "RELATIONSHIPS_PRESERVED" if relationships_ok else "RELATIONSHIPS_CHANGED",
                )
            )
            snapshot_ok, snapshot_attempts = await self._verify_snapshot(
                after,
                previous_digest=previous_snapshot_digest,
            )
            checks.append(
                VerifiedOperationCheck(
                    "dashboard_snapshot",
                    snapshot_ok,
                    snapshot_attempts,
                    "DASHBOARD_VERIFIED" if snapshot_ok else "DASHBOARD_POSTCONDITION_FAILED",
                )
            )
            scope_ok, scope_attempts = await self._verify_project_filter(after)
            checks.append(
                VerifiedOperationCheck(
                    "project_filter",
                    scope_ok,
                    scope_attempts,
                    "PROJECT_FILTER_VERIFIED" if scope_ok else "PROJECT_FILTER_FAILED",
                )
            )
            if all(check.passed for check in checks):
                receipt = self._receipt(
                    plan=plan,
                    operation_id=operation_id,
                    status=VerifiedOperationStatus.VERIFIED_COMPLETE,
                    started_at=started_at,
                    finished_at=self._now(),
                    checks=checks,
                    error_codes=(),
                    rollback="not_required",
                    changed=True,
                    after_memory=after,
                    after_entity=entity_after,
                )
                return VerifiedProjectAssignmentResult(
                    VerifiedOperationStatus.VERIFIED_COMPLETE,
                    plan,
                    receipt,
                    title=_title(after),
                )
            errors.extend(check.code for check in checks if not check.passed)
        except ProjectAssignmentWriteError as error:
            errors.append(error.code)
        except Exception:
            errors.append("PROJECT_ASSIGNMENT_WRITE_FAILED")

        rollback_ok = await self._rollback(
            before=before,
            entity_before=entity_before,
            relationship_sha256=_relationship_sha256(concepts_before),
            snapshot_before=snapshot_before,
        )
        status = (
            VerifiedOperationStatus.FAILED_ROLLED_BACK
            if rollback_ok
            else VerifiedOperationStatus.UNSAFE
        )
        if not rollback_ok:
            errors.append("PROJECT_ASSIGNMENT_ROLLBACK_INCOMPLETE")
        receipt = self._receipt(
            plan=plan,
            operation_id=operation_id,
            status=status,
            started_at=started_at,
            finished_at=self._now(),
            checks=checks,
            error_codes=errors,
            rollback="verified" if rollback_ok else "incomplete",
            changed=not rollback_ok,
            after_memory=after,
            after_entity=entity_after,
        )
        return VerifiedProjectAssignmentResult(status, plan, receipt)


__all__ = [
    "PROJECT_ASSIGNMENT_HISTORY_KEY",
    "VerifiedProjectAssignmentPlan",
    "VerifiedProjectAssignmentReceipt",
    "VerifiedProjectAssignmentResult",
    "VerifiedProjectAssignmentService",
]
