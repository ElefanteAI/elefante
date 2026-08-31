"""Verified product operation for resolving one pair of scoped memories.

This module deliberately wraps the existing conflict resolver instead of
creating a general workflow engine.  A correction is complete only when the
authoritative store, the customer dashboard snapshot, and a scoped Recall all
agree.  Semantic writes are never retried.  Read-only verification and
snapshot refresh may retry a small bounded number of times.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from src.core.conflict_resolution import (
    ConflictResolutionError,
    ConflictResolutionPlan,
    ResolutionAction,
    plan_conflict_resolution,
    resolve_memory_pair,
)
from src.core.verified_operation import (
    VerifiedOperationCheck as VerifiedResolveCheck,
    VerifiedOperationStatus as VerifiedResolveStatus,
    load_snapshot as _load_snapshot,
    memory_record_sha256,
    memory_scope_values as _scope_values,
    recall_scope as _recall_scope,
    scope_sha256 as _scope_sha256,
    snapshot_digest as _snapshot_digest,
)
from src.models.memory import Memory, MemoryStatus


RefreshSnapshot = Callable[[], Awaitable[Mapping[str, Any] | None]]
RecallSelectedIds = Callable[..., Awaitable[Sequence[str]]]


@dataclass(frozen=True)
class VerifiedResolvePlan:
    """The existing semantic plan plus the product-level scope gate."""

    resolution: ConflictResolutionPlan
    reason_code: str | None
    scope_sha256: str | None
    record_sha256: dict[str, str]

    @property
    def applicable(self) -> bool:
        return self.reason_code is None and self.resolution.applicable

    @property
    def reason(self) -> str:
        if self.reason_code == "DECLARED_SCOPE_REQUIRED":
            return "Both memories require one exact declared scope before correction."
        if self.reason_code == "SCOPE_MISMATCH":
            return "The memories belong to different declared scopes."
        if self.reason_code == "INACTIVE_MEMORY_REQUIRES_RESTORE":
            return "Archived, deprecated, or superseded memories must be restored before correction."
        return self.resolution.reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "applicable": self.applicable,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "record_sha256": dict(self.record_sha256),
            "resolution": self.resolution.to_dict(),
        }


@dataclass(frozen=True)
class VerifiedResolveReceipt:
    """Bounded, privacy-safe proof of one terminal Resolve operation."""

    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedResolveStatus
    authority: str
    started_at: str
    finished_at: str
    memory_ids: dict[str, str]
    scope_sha256: str
    record_sha256: dict[str, str]
    checks: tuple[VerifiedResolveCheck, ...]
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
            "memory_ids": dict(self.memory_ids),
            "scope_sha256": self.scope_sha256,
            "record_sha256": dict(self.record_sha256),
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
            "rollback": self.rollback,
            "changed": self.changed,
        }


@dataclass(frozen=True)
class VerifiedResolveResult:
    """Headless product result returned to MCP and Home adapters."""

    status: VerifiedResolveStatus
    plan: VerifiedResolvePlan
    receipt: VerifiedResolveReceipt

    @property
    def success(self) -> bool:
        return self.status is VerifiedResolveStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "plan": self.plan.to_dict(),
            "receipt": self.receipt.to_dict(),
        }


def _is_inactive(memory: Memory) -> bool:
    status = str(getattr(memory.metadata.status, "value", memory.metadata.status)).casefold()
    return bool(
        memory.metadata.archived
        or memory.metadata.deprecated
        or memory.metadata.superseded_by_id
        or status in {MemoryStatus.ARCHIVED.value, MemoryStatus.DEPRECATED.value}
    )


def _blocked_resolution(
    left: Memory,
    right: Memory,
    reason: str,
) -> ConflictResolutionPlan:
    return ConflictResolutionPlan(
        action=ResolutionAction.BLOCKED,
        left_memory_id=str(left.id),
        right_memory_id=str(right.id),
        winner_memory_id=None,
        loser_memory_id=None,
        assessment="ABSTAIN",
        reason=reason,
    )


def _resolution_reason_code(plan: ConflictResolutionPlan) -> str | None:
    if plan.applicable:
        return None
    if plan.requires_user_winner:
        return "WINNER_REQUIRED"
    if plan.protected_loser:
        return "PROTECTED_CONFIRMATION_REQUIRED"
    if plan.assessment == "ABSTAIN":
        return "ASSERTION_RELATION_UNPROVEN"
    return "RESOLUTION_BLOCKED"


def _snapshot_record_matches(node: Mapping[str, Any], memory: Memory) -> bool:
    properties = node.get("properties")
    if not isinstance(properties, Mapping):
        return False
    status = str(getattr(memory.metadata.status, "value", memory.metadata.status))
    expected = {
        "status": status,
        "archived": bool(memory.metadata.archived),
        "deprecated": bool(memory.metadata.deprecated),
        "supersedes_id": (
            str(memory.metadata.supersedes_id)
            if memory.metadata.supersedes_id
            else ""
        ),
        "superseded_by_id": (
            str(memory.metadata.superseded_by_id)
            if memory.metadata.superseded_by_id
            else ""
        ),
    }
    return all(properties.get(key) == value for key, value in expected.items())


def _snapshot_matches(
    snapshot: Mapping[str, Any],
    expected_memories: Sequence[Memory],
) -> bool:
    if not snapshot.get("generated_at"):
        return False
    raw_nodes = snapshot.get("nodes")
    if not isinstance(raw_nodes, list):
        return False
    nodes = {
        str(node.get("id")): node
        for node in raw_nodes
        if isinstance(node, Mapping) and node.get("id") is not None
    }
    return all(
        str(memory.id) in nodes
        and _snapshot_record_matches(nodes[str(memory.id)], memory)
        for memory in expected_memories
    )


class VerifiedResolveService:
    """Execute exactly one Resolve operation with product-level proof."""

    def __init__(
        self,
        store: Any,
        *,
        snapshot_path: Path,
        refresh_snapshot: RefreshSnapshot,
        recall_selected_ids: RecallSelectedIds,
        verification_attempts: int = 2,
        now: Callable[[], datetime] | None = None,
        operation_id: Callable[[], UUID] | None = None,
    ) -> None:
        if not 1 <= verification_attempts <= 3:
            raise ValueError("verification_attempts must be from 1 to 3")
        self.store = store
        self.snapshot_path = Path(snapshot_path)
        self.refresh_snapshot = refresh_snapshot
        self.recall_selected_ids = recall_selected_ids
        self.verification_attempts = verification_attempts
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._operation_id = operation_id or uuid4

    async def _load_pair(
        self,
        left_memory_id: UUID,
        right_memory_id: UUID,
    ) -> tuple[Memory, Memory]:
        left = await self.store.get_memory(left_memory_id)
        right = await self.store.get_memory(right_memory_id)
        if left is None or right is None:
            missing = left_memory_id if left is None else right_memory_id
            raise ConflictResolutionError(f"Memory {missing} not found")
        return left, right

    async def plan(
        self,
        left_memory_id: UUID,
        right_memory_id: UUID,
        *,
        winner_memory_id: UUID | None = None,
        confirm_protected: bool = False,
    ) -> VerifiedResolvePlan:
        """Inspect the correction without changing data or customer snapshots."""
        left, right = await self._load_pair(left_memory_id, right_memory_id)
        record_sha256 = {
            "left": memory_record_sha256(left),
            "right": memory_record_sha256(right),
        }
        left_scope = _scope_values(left)
        right_scope = _scope_values(right)
        if not any(left_scope) or not any(right_scope):
            resolution = _blocked_resolution(
                left,
                right,
                "Both memories require one exact declared scope before correction.",
            )
            return VerifiedResolvePlan(
                resolution=resolution,
                reason_code="DECLARED_SCOPE_REQUIRED",
                scope_sha256=None,
                record_sha256=record_sha256,
            )
        if left_scope != right_scope:
            resolution = _blocked_resolution(
                left,
                right,
                "The memories belong to different declared scopes.",
            )
            return VerifiedResolvePlan(
                resolution=resolution,
                reason_code="SCOPE_MISMATCH",
                scope_sha256=None,
                record_sha256=record_sha256,
            )
        if _is_inactive(left) or _is_inactive(right):
            resolution = _blocked_resolution(
                left,
                right,
                "Inactive memories must be restored before correction.",
            )
            return VerifiedResolvePlan(
                resolution=resolution,
                reason_code="INACTIVE_MEMORY_REQUIRES_RESTORE",
                scope_sha256=_scope_sha256(left_scope),
                record_sha256=record_sha256,
            )
        resolution = plan_conflict_resolution(
            left,
            right,
            winner_memory_id=winner_memory_id,
            confirm_protected=confirm_protected,
        )
        return VerifiedResolvePlan(
            resolution=resolution,
            reason_code=_resolution_reason_code(resolution),
            scope_sha256=_scope_sha256(left_scope),
            record_sha256=record_sha256,
        )

    @staticmethod
    def _authoritative_state_matches(winner: Memory, loser: Memory) -> bool:
        winner_status = str(
            getattr(winner.metadata.status, "value", winner.metadata.status)
        )
        loser_status = str(
            getattr(loser.metadata.status, "value", loser.metadata.status)
        )
        return bool(
            winner_status in {
                MemoryStatus.VERIFIED.value,
                MemoryStatus.CONSOLIDATED.value,
            }
            and not winner.metadata.archived
            and not winner.metadata.deprecated
            and winner.metadata.supersedes_id == loser.id
            and loser_status == MemoryStatus.ARCHIVED.value
            and loser.metadata.archived
            and loser.metadata.deprecated
            and loser.metadata.superseded_by_id == winner.id
            and loser.id not in (winner.metadata.conflict_ids or [])
            and winner.id not in (loser.metadata.conflict_ids or [])
            and bool(
                (winner.metadata.custom_metadata or {}).get(
                    "conflict_resolution_history"
                )
            )
            and bool(
                (loser.metadata.custom_metadata or {}).get(
                    "conflict_resolution_history"
                )
            )
        )

    async def _verify_authoritative_state(
        self,
        winner_id: UUID,
        loser_id: UUID,
    ) -> tuple[bool, int, Memory | None, Memory | None]:
        winner: Memory | None = None
        loser: Memory | None = None
        for attempt in range(1, self.verification_attempts + 1):
            try:
                winner = await self.store.get_memory(winner_id)
                loser = await self.store.get_memory(loser_id)
                if (
                    winner is not None
                    and loser is not None
                    and self._authoritative_state_matches(winner, loser)
                ):
                    return True, attempt, winner, loser
            except Exception:
                winner = None
                loser = None
        return False, self.verification_attempts, winner, loser

    async def _refresh_and_verify_snapshot(
        self,
        expected_memories: Sequence[Memory],
        *,
        previous_digest: str | None,
    ) -> tuple[bool, int, str | None]:
        latest_digest: str | None = None
        for attempt in range(1, self.verification_attempts + 1):
            try:
                refresh_result = await self.refresh_snapshot()
                if (
                    isinstance(refresh_result, Mapping)
                    and refresh_result.get("success") is False
                ):
                    continue
                latest_digest = _snapshot_digest(self.snapshot_path)
                if latest_digest is None or latest_digest == previous_digest:
                    continue
                snapshot = _load_snapshot(self.snapshot_path)
                if _snapshot_matches(snapshot, expected_memories):
                    return True, attempt, latest_digest
            except Exception:
                latest_digest = _snapshot_digest(self.snapshot_path)
        return False, self.verification_attempts, latest_digest

    async def _verify_recall(
        self,
        question: str,
        *,
        project: str | None,
        workspace: str | None,
        winner_id: UUID,
        loser_id: UUID,
    ) -> tuple[bool, int]:
        for attempt in range(1, self.verification_attempts + 1):
            try:
                selected = {
                    str(memory_id)
                    for memory_id in await self.recall_selected_ids(
                        question,
                        project=project,
                        workspace=workspace,
                    )
                }
                if str(winner_id) in selected and str(loser_id) not in selected:
                    return True, attempt
            except Exception:
                pass
        return False, self.verification_attempts

    async def _restore_pair(
        self,
        winner_before: Memory,
        loser_before: Memory,
        *,
        previous_snapshot_digest: str | None,
    ) -> tuple[bool, str]:
        """Compensate once, then prove both store and snapshot restoration."""
        loser_written = False
        winner_written = False
        try:
            loser_written = bool(await self.store.replace_memory(loser_before))
        except Exception:
            loser_written = False
        try:
            winner_written = bool(await self.store.replace_memory(winner_before))
        except Exception:
            winner_written = False

        try:
            winner_current = await self.store.get_memory(winner_before.id)
            loser_current = await self.store.get_memory(loser_before.id)
        except Exception:
            winner_current = None
            loser_current = None
        store_verified = bool(
            loser_written
            and winner_written
            and winner_current is not None
            and loser_current is not None
            and memory_record_sha256(winner_current)
            == memory_record_sha256(winner_before)
            and memory_record_sha256(loser_current)
            == memory_record_sha256(loser_before)
        )
        if not store_verified:
            return False, "incomplete"

        snapshot_verified, _, _ = await self._refresh_and_verify_snapshot(
            [winner_before, loser_before],
            previous_digest=previous_snapshot_digest,
        )
        if not snapshot_verified:
            return False, "store_verified_snapshot_failed"
        return True, "verified"

    async def _pair_matches_before(
        self,
        winner_before: Memory,
        loser_before: Memory,
    ) -> bool:
        """Read back both records instead of trusting an adapter failure label."""
        try:
            winner_current = await self.store.get_memory(winner_before.id)
            loser_current = await self.store.get_memory(loser_before.id)
        except Exception:
            return False
        return bool(
            winner_current is not None
            and loser_current is not None
            and memory_record_sha256(winner_current)
            == memory_record_sha256(winner_before)
            and memory_record_sha256(loser_current)
            == memory_record_sha256(loser_before)
        )

    def _receipt(
        self,
        *,
        operation_id: str,
        started_at: str,
        status: VerifiedResolveStatus,
        plan: VerifiedResolvePlan,
        left_id: UUID,
        right_id: UUID,
        winner_id: UUID | None,
        loser_id: UUID | None,
        record_sha256: Mapping[str, str],
        checks: Sequence[VerifiedResolveCheck],
        error_codes: Sequence[str],
        rollback: str,
        changed: bool,
    ) -> VerifiedResolveReceipt:
        return VerifiedResolveReceipt(
            schema_version=1,
            operation_id=operation_id,
            operation="resolve",
            status=status,
            authority="user_directed",
            started_at=started_at,
            finished_at=self._now().astimezone(timezone.utc).isoformat(),
            memory_ids={
                "left": str(left_id),
                "right": str(right_id),
                "winner": str(winner_id) if winner_id else "",
                "loser": str(loser_id) if loser_id else "",
            },
            scope_sha256=plan.scope_sha256 or "",
            record_sha256=dict(record_sha256),
            checks=tuple(checks)[:6],
            error_codes=tuple(dict.fromkeys(error_codes))[:8],
            rollback=rollback,
            changed=changed,
        )

    def _terminal(
        self,
        *,
        operation_id: str,
        started_at: str,
        status: VerifiedResolveStatus,
        plan: VerifiedResolvePlan,
        left_id: UUID,
        right_id: UUID,
        winner_id: UUID | None,
        loser_id: UUID | None,
        record_sha256: Mapping[str, str],
        checks: Sequence[VerifiedResolveCheck] = (),
        error_codes: Sequence[str] = (),
        rollback: str = "not_required",
        changed: bool = False,
    ) -> VerifiedResolveResult:
        return VerifiedResolveResult(
            status=status,
            plan=plan,
            receipt=self._receipt(
                operation_id=operation_id,
                started_at=started_at,
                status=status,
                plan=plan,
                left_id=left_id,
                right_id=right_id,
                winner_id=winner_id,
                loser_id=loser_id,
                record_sha256=record_sha256,
                checks=checks,
                error_codes=error_codes,
                rollback=rollback,
                changed=changed,
            ),
        )

    async def execute(
        self,
        left_memory_id: UUID,
        right_memory_id: UUID,
        *,
        winner_memory_id: UUID | None,
        reason: str,
        verification_question: str,
        confirm_protected: bool = False,
        expected_record_sha256: Mapping[str, str] | None = None,
    ) -> VerifiedResolveResult:
        """Apply once, verify three surfaces, and compensate on any failure."""
        operation_id = str(self._operation_id())
        started_at = self._now().astimezone(timezone.utc).isoformat()
        reason = str(reason or "").strip()
        verification_question = str(verification_question or "").strip()

        try:
            plan = await self.plan(
                left_memory_id,
                right_memory_id,
                winner_memory_id=winner_memory_id,
                confirm_protected=confirm_protected,
            )
            left_before, right_before = await self._load_pair(
                left_memory_id, right_memory_id
            )
        except (ConflictResolutionError, ValueError):
            placeholder = ConflictResolutionPlan(
                action=ResolutionAction.BLOCKED,
                left_memory_id=str(left_memory_id),
                right_memory_id=str(right_memory_id),
                winner_memory_id=None,
                loser_memory_id=None,
                assessment="ABSTAIN",
                reason="The selected memory pair could not be inspected.",
            )
            plan = VerifiedResolvePlan(
                resolution=placeholder,
                reason_code="PAIR_INSPECTION_FAILED",
                scope_sha256=None,
                record_sha256={},
            )
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedResolveStatus.FAILED_NO_CHANGE,
                plan=plan,
                left_id=left_memory_id,
                right_id=right_memory_id,
                winner_id=None,
                loser_id=None,
                record_sha256={},
                error_codes=("PAIR_INSPECTION_FAILED",),
            )

        winner_id = (
            UUID(plan.resolution.winner_memory_id)
            if plan.resolution.winner_memory_id
            else None
        )
        loser_id = (
            UUID(plan.resolution.loser_memory_id)
            if plan.resolution.loser_memory_id
            else None
        )
        records = {left_before.id: left_before, right_before.id: right_before}
        hashes: dict[str, str] = {
            "left_before": memory_record_sha256(left_before),
            "right_before": memory_record_sha256(right_before),
        }

        if expected_record_sha256 is not None and (
            dict(expected_record_sha256) != plan.record_sha256
        ):
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedResolveStatus.NEEDS_HUMAN,
                plan=plan,
                left_id=left_memory_id,
                right_id=right_memory_id,
                winner_id=winner_id,
                loser_id=loser_id,
                record_sha256=hashes,
                error_codes=("PLAN_STALE",),
            )

        validation_errors: list[str] = []
        if not plan.applicable:
            validation_errors.append(plan.reason_code or "RESOLUTION_BLOCKED")
        if not reason or len(reason) > 1000:
            validation_errors.append("AUDIT_REASON_REQUIRED")
        if not verification_question or len(verification_question) > 1000:
            validation_errors.append("VERIFICATION_QUESTION_REQUIRED")
        if validation_errors or winner_id is None or loser_id is None:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedResolveStatus.NEEDS_HUMAN,
                plan=plan,
                left_id=left_memory_id,
                right_id=right_memory_id,
                winner_id=winner_id,
                loser_id=loser_id,
                record_sha256=hashes,
                error_codes=validation_errors or ("RESOLUTION_BLOCKED",),
            )

        winner_before = records[winner_id]
        loser_before = records[loser_id]
        hashes = {
            "winner_before": memory_record_sha256(winner_before),
            "loser_before": memory_record_sha256(loser_before),
        }
        snapshot_before_digest = _snapshot_digest(self.snapshot_path)

        try:
            await resolve_memory_pair(
                self.store,
                left_memory_id,
                right_memory_id,
                winner_memory_id=winner_id,
                apply=True,
                invocation_mode="user_directed",
                reason=reason,
                confirm_protected=confirm_protected,
            )
        except Exception as error:
            rollback_performed = bool(
                getattr(error, "rollback_performed", False)
            )
            state_is_original = await self._pair_matches_before(
                winner_before,
                loser_before,
            )
            rollback_status = "not_required"
            error_codes = [
                str(
                    getattr(
                        error,
                        "error_code",
                        "UNEXPECTED_RESOLUTION_WRITE_FAILURE",
                    )
                )
            ]
            if state_is_original:
                status = (
                    VerifiedResolveStatus.FAILED_ROLLED_BACK
                    if rollback_performed
                    else VerifiedResolveStatus.FAILED_NO_CHANGE
                )
                rollback_status = "verified" if rollback_performed else "not_required"
            elif rollback_performed:
                # The resolver already consumed its one compensating attempt.
                # Do not retry semantic writes under a different abstraction.
                status = VerifiedResolveStatus.UNSAFE
                rollback_status = "incomplete"
                error_codes.append("ROLLBACK_INCOMPLETE")
            else:
                rollback_verified, rollback_status = await self._restore_pair(
                    winner_before,
                    loser_before,
                    previous_snapshot_digest=snapshot_before_digest,
                )
                status = (
                    VerifiedResolveStatus.FAILED_ROLLED_BACK
                    if rollback_verified
                    else VerifiedResolveStatus.UNSAFE
                )
                if not rollback_verified:
                    error_codes.append("ROLLBACK_INCOMPLETE")
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=status,
                plan=plan,
                left_id=left_memory_id,
                right_id=right_memory_id,
                winner_id=winner_id,
                loser_id=loser_id,
                record_sha256=hashes,
                error_codes=error_codes,
                rollback=rollback_status,
                changed=status is VerifiedResolveStatus.UNSAFE,
            )

        checks: list[VerifiedResolveCheck] = []
        store_ok, store_attempts, winner_after, loser_after = (
            await self._verify_authoritative_state(winner_id, loser_id)
        )
        checks.append(
            VerifiedResolveCheck(
                name="authoritative_store",
                passed=store_ok,
                attempts=store_attempts,
                code="STORE_POSTCONDITION_OK"
                if store_ok
                else "STORE_POSTCONDITION_FAILED",
            )
        )
        postcondition_error: str | None = None
        latest_snapshot_digest = snapshot_before_digest
        if not store_ok or winner_after is None or loser_after is None:
            postcondition_error = "STORE_POSTCONDITION_FAILED"
        else:
            hashes["winner_after"] = memory_record_sha256(winner_after)
            hashes["loser_after"] = memory_record_sha256(loser_after)
            snapshot_ok, snapshot_attempts, latest_snapshot_digest = (
                await self._refresh_and_verify_snapshot(
                    [winner_after, loser_after],
                    previous_digest=snapshot_before_digest,
                )
            )
            checks.append(
                VerifiedResolveCheck(
                    name="dashboard_snapshot",
                    passed=snapshot_ok,
                    attempts=snapshot_attempts,
                    code="SNAPSHOT_POSTCONDITION_OK"
                    if snapshot_ok
                    else "SNAPSHOT_POSTCONDITION_FAILED",
                )
            )
            if not snapshot_ok:
                postcondition_error = "SNAPSHOT_POSTCONDITION_FAILED"
            else:
                recall_project, recall_workspace = _recall_scope(winner_after)
                recall_ok, recall_attempts = await self._verify_recall(
                    verification_question,
                    project=recall_project,
                    workspace=recall_workspace,
                    winner_id=winner_id,
                    loser_id=loser_id,
                )
                checks.append(
                    VerifiedResolveCheck(
                        name="scoped_recall",
                        passed=recall_ok,
                        attempts=recall_attempts,
                        code="RECALL_POSTCONDITION_OK"
                        if recall_ok
                        else "RECALL_POSTCONDITION_FAILED",
                    )
                )
                if not recall_ok:
                    postcondition_error = "RECALL_POSTCONDITION_FAILED"

        if postcondition_error is None:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedResolveStatus.VERIFIED_COMPLETE,
                plan=plan,
                left_id=left_memory_id,
                right_id=right_memory_id,
                winner_id=winner_id,
                loser_id=loser_id,
                record_sha256=hashes,
                checks=checks,
                rollback="not_required",
                changed=True,
            )

        rollback_verified, rollback_status = await self._restore_pair(
            winner_before,
            loser_before,
            previous_snapshot_digest=latest_snapshot_digest,
        )
        status = (
            VerifiedResolveStatus.FAILED_ROLLED_BACK
            if rollback_verified
            else VerifiedResolveStatus.UNSAFE
        )
        error_codes = [postcondition_error]
        if not rollback_verified:
            error_codes.append("ROLLBACK_INCOMPLETE")
        return self._terminal(
            operation_id=operation_id,
            started_at=started_at,
            status=status,
            plan=plan,
            left_id=left_memory_id,
            right_id=right_memory_id,
            winner_id=winner_id,
            loser_id=loser_id,
            record_sha256=hashes,
            checks=checks,
            error_codes=error_codes,
            rollback=rollback_status,
            changed=not rollback_verified,
        )


__all__ = [
    "VerifiedResolveCheck",
    "VerifiedResolvePlan",
    "VerifiedResolveReceipt",
    "VerifiedResolveResult",
    "VerifiedResolveService",
    "VerifiedResolveStatus",
    "memory_record_sha256",
]
