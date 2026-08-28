"""Deterministic, reversible repair for equivalent or conflicting memories.

The resolver never invents authority.  It can automatically consolidate two
equivalent assertions, or prefer the sole protected assertion.  Every other
material conflict requires a user-selected winner.  Applying a plan is
user-directed, recoverable, and rolls both vector records back if either write
fails.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from src.core.conflict_detection import ConflictOutcome, assess_conflict
from src.core.governance import is_protected
from src.models.memory import Memory, MemoryStatus


class ResolutionAction(str, Enum):
    """The bounded mutation a conflict-resolution plan may perform."""

    CONSOLIDATE = "consolidate"
    SUPERSEDE = "supersede"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ConflictResolutionPlan:
    """Inspectable plan produced before any memory is changed."""

    action: ResolutionAction
    left_memory_id: str
    right_memory_id: str
    winner_memory_id: str | None
    loser_memory_id: str | None
    assessment: str
    reason: str
    requires_user_winner: bool = False
    protected_loser: bool = False

    @property
    def applicable(self) -> bool:
        return self.action is not ResolutionAction.BLOCKED

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        payload["applicable"] = self.applicable
        return payload


@dataclass(frozen=True)
class ConflictResolutionResult:
    """Outcome of a dry-run or applied repair."""

    plan: ConflictResolutionPlan
    applied: bool
    rollback_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "applied": self.applied,
            "rollback_performed": self.rollback_performed,
        }


class ConflictResolutionError(RuntimeError):
    """Raised when an approved plan cannot be applied safely."""


def _scope_key(memory: Memory) -> tuple[str, str, str]:
    metadata = memory.metadata
    return tuple(
        str(value or "").strip().casefold()
        for value in (metadata.project, metadata.workspace, metadata.scope)
    )


def _canonical_equivalent(left: Memory, right: Memory) -> Memory:
    """Choose a stable canonical record without using mutable popularity."""
    left_protected = is_protected(left.metadata)
    right_protected = is_protected(right.metadata)
    if left_protected != right_protected:
        return left if left_protected else right
    left_key = (left.metadata.created_at, str(left.id))
    right_key = (right.metadata.created_at, str(right.id))
    return left if left_key <= right_key else right


def plan_conflict_resolution(
    left: Memory,
    right: Memory,
    *,
    winner_memory_id: UUID | str | None = None,
    confirm_protected: bool = False,
) -> ConflictResolutionPlan:
    """Plan a pair repair while refusing ambiguous authority or scope."""
    if left.id == right.id:
        raise ValueError("Conflict resolution requires two different memories")

    left_id = str(left.id)
    right_id = str(right.id)
    winner_id = str(winner_memory_id) if winner_memory_id is not None else None
    if winner_id is not None and winner_id not in {left_id, right_id}:
        raise ValueError("winner_memory_id must identify one of the two memories")

    assessment = assess_conflict(left.content, right.content)
    linked_as_conflict = (
        right.id in (left.metadata.conflict_ids or [])
        or left.id in (right.metadata.conflict_ids or [])
    )
    if _scope_key(left) != _scope_key(right):
        return ConflictResolutionPlan(
            ResolutionAction.BLOCKED,
            left_id,
            right_id,
            None,
            None,
            assessment.outcome.value,
            "Different declared scopes must coexist; update scope explicitly before resolution.",
        )

    if assessment.outcome is ConflictOutcome.NO_CONFLICT:
        winner = (
            left
            if winner_id == left_id
            else right
            if winner_id == right_id
            else _canonical_equivalent(left, right)
        )
        loser = right if winner.id == left.id else left
        protected_loser = is_protected(loser.metadata)
        if protected_loser and not confirm_protected:
            return ConflictResolutionPlan(
                ResolutionAction.BLOCKED,
                left_id,
                right_id,
                str(winner.id),
                str(loser.id),
                assessment.outcome.value,
                "The duplicate selected for archival is protected; explicit protected confirmation is required.",
                protected_loser=True,
            )
        return ConflictResolutionPlan(
            ResolutionAction.CONSOLIDATE,
            left_id,
            right_id,
            str(winner.id),
            str(loser.id),
            assessment.outcome.value,
            "Equivalent assertions can be consolidated without synthesizing new content.",
            protected_loser=protected_loser,
        )

    if assessment.outcome is ConflictOutcome.ABSTAIN and not linked_as_conflict:
        return ConflictResolutionPlan(
            ResolutionAction.BLOCKED,
            left_id,
            right_id,
            None,
            None,
            assessment.outcome.value,
            "The assertions are not proven equivalent or contradictory.",
        )

    if winner_id is None:
        protected = [memory for memory in (left, right) if is_protected(memory.metadata)]
        if len(protected) != 1:
            return ConflictResolutionPlan(
                ResolutionAction.BLOCKED,
                left_id,
                right_id,
                None,
                None,
                assessment.outcome.value,
                "No authoritative winner exists; a user must select winner_memory_id.",
                requires_user_winner=True,
            )
        winner = protected[0]
    else:
        winner = left if winner_id == left_id else right
    loser = right if winner.id == left.id else left
    protected_loser = is_protected(loser.metadata)
    if protected_loser and not confirm_protected:
        return ConflictResolutionPlan(
            ResolutionAction.BLOCKED,
            left_id,
            right_id,
            str(winner.id),
            str(loser.id),
            assessment.outcome.value,
            "The losing assertion is protected; explicit protected confirmation is required.",
            protected_loser=True,
        )
    return ConflictResolutionPlan(
        ResolutionAction.SUPERSEDE,
        left_id,
        right_id,
        str(winner.id),
        str(loser.id),
        assessment.outcome.value,
        "The authoritative assertion can supersede the losing assertion recoverably.",
        protected_loser=protected_loser,
    )


def _audit_event(
    *, plan: ConflictResolutionPlan, reason: str, invocation_mode: str
) -> dict[str, Any]:
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "action": plan.action.value,
        "winner_memory_id": plan.winner_memory_id,
        "loser_memory_id": plan.loser_memory_id,
        "reason": reason,
        "invocation_mode": invocation_mode,
    }


def _append_audit(memory: Memory, event: dict[str, Any]) -> None:
    custom = dict(memory.metadata.custom_metadata or {})
    history = list(custom.get("conflict_resolution_history") or [])
    history.append(event)
    custom["conflict_resolution_history"] = history[-50:]
    memory.metadata.custom_metadata = custom


async def resolve_memory_pair(
    store: Any,
    left_memory_id: UUID,
    right_memory_id: UUID,
    *,
    winner_memory_id: UUID | None = None,
    apply: bool = False,
    invocation_mode: str = "workflow_managed",
    reason: str = "",
    confirm_protected: bool = False,
) -> ConflictResolutionResult:
    """Plan or apply a recoverable pair repair against a vector-store contract."""
    left = await store.get_memory(left_memory_id)
    right = await store.get_memory(right_memory_id)
    if left is None or right is None:
        missing = left_memory_id if left is None else right_memory_id
        raise ConflictResolutionError(f"Memory {missing} not found")

    plan = plan_conflict_resolution(
        left,
        right,
        winner_memory_id=winner_memory_id,
        confirm_protected=confirm_protected,
    )
    if not apply:
        return ConflictResolutionResult(plan=plan, applied=False)
    if invocation_mode != "user_directed":
        raise ConflictResolutionError("Applying conflict repair must be user-directed")
    if not reason.strip():
        raise ConflictResolutionError("Applying conflict repair requires an audit reason")
    if not plan.applicable:
        raise ConflictResolutionError(plan.reason)

    records = {str(left.id): left, str(right.id): right}
    winner_before = records[str(plan.winner_memory_id)]
    loser_before = records[str(plan.loser_memory_id)]
    winner = winner_before.model_copy(deep=True)
    loser = loser_before.model_copy(deep=True)
    event = _audit_event(plan=plan, reason=reason.strip(), invocation_mode=invocation_mode)

    winner.metadata.conflict_ids = [
        item for item in (winner.metadata.conflict_ids or []) if item != loser.id
    ]
    loser.metadata.conflict_ids = [
        item for item in (loser.metadata.conflict_ids or []) if item != winner.id
    ]
    winner.metadata.status = (
        MemoryStatus.CONSOLIDATED
        if plan.action is ResolutionAction.CONSOLIDATE
        else MemoryStatus.VERIFIED
    )
    loser.metadata.status = MemoryStatus.ARCHIVED
    loser.metadata.archived = True
    loser.metadata.deprecated = True
    loser.metadata.superseded_by_id = winner.id
    if winner.metadata.supersedes_id in {None, loser.id}:
        winner.metadata.supersedes_id = loser.id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    winner.metadata.last_modified = now
    loser.metadata.last_modified = now
    if plan.action is ResolutionAction.CONSOLIDATE:
        tags = list(winner.metadata.tags or []) + list(loser.metadata.tags or [])
        winner.metadata.tags = list(dict.fromkeys(tag for tag in tags if str(tag).strip()))
    _append_audit(winner, event)
    _append_audit(loser, event)

    if not await store.replace_memory(loser):
        raise ConflictResolutionError("Could not persist the losing memory; no repair was applied")
    if await store.replace_memory(winner):
        return ConflictResolutionResult(plan=plan, applied=True)

    loser_restored = await store.replace_memory(loser_before)
    winner_restored = await store.replace_memory(winner_before)
    if not (loser_restored and winner_restored):
        raise ConflictResolutionError(
            "Conflict repair failed and automatic rollback was incomplete; restore the verified backup"
        )
    raise ConflictResolutionError("Conflict repair failed; both memories were rolled back")


__all__ = [
    "ConflictResolutionError",
    "ConflictResolutionPlan",
    "ConflictResolutionResult",
    "ResolutionAction",
    "plan_conflict_resolution",
    "resolve_memory_pair",
]
