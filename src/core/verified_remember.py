"""Verified project-scoped Remember operation.

Remember is a customer action, not a successful vector write.  This service
searches the exact project for material overlap, creates one new record only
when that is safe or explicitly requested, verifies SQLite, Kuzu, Home, and
scoped Recall, and removes the new record if any postcondition fails.

Customer content and the disposable Recall question never enter the receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
from pathlib import Path
import re
from typing import Any, Awaitable, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from src.core.conflict_detection import ConflictOutcome, assess_conflict
from src.core.verified_operation import (
    VerifiedOperationCheck,
    VerifiedOperationStatus,
    entity_record_sha256,
    load_snapshot,
    memory_record_sha256,
    scope_sha256,
    snapshot_digest,
)
from src.models.entity import Entity, EntityType
from src.models.memory import Memory, MemoryStatus
from src.models.query import QueryMode, SearchFilters
from src.utils.atomic_json import (
    PrivateFileState,
    capture_private_file,
    restore_private_file,
)
from src.utils.curation import (
    canonicalize_concepts,
    canonicalize_recall_cues,
    generate_title,
)
from src.utils.validators import validate_memory_content


RefreshSnapshot = Callable[[], Awaitable[Mapping[str, Any] | None]]


@dataclass(frozen=True)
class RecallVerification:
    """Bounded Recall outcome used only for Remember postconditions."""

    selected_ids: tuple[str, ...]
    conflict_count: int = 0


RecallSelectedIds = Callable[
    ...,
    Awaitable[Sequence[str] | RecallVerification],
]


KNOWLEDGE_KIND_TO_MEMORY_TYPE = {
    "decision": "decision",
    "constraint": "specification",
    "preference": "preference",
    "lesson": "insight",
}
MEMORY_TYPE_TO_KNOWLEDGE_KIND = {
    "decision": "decision",
    "specification": "constraint",
    "directive": "constraint",
    "preference": "preference",
    "insight": "lesson",
}
REMEMBER_CHOICES = ("update", "supersede", "keep_both", "cancel")


def _text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _near_duplicate(left: str, right: str) -> bool:
    left_value = _normalized(left)
    right_value = _normalized(right)
    return left_value == right_value or SequenceMatcher(
        None,
        left_value,
        right_value,
    ).ratio() >= 0.92


def _projection_sha256(concepts: Sequence[str]) -> str:
    normalized = "\x1f".join(
        sorted(canonicalize_concepts(list(concepts), max_concepts=5))
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _inactive(memory: Memory) -> bool:
    return bool(
        memory.metadata.archived
        or memory.metadata.deprecated
        or memory.metadata.superseded_by_id
        or _text(memory.metadata.status).casefold()
        in {MemoryStatus.ARCHIVED.value, MemoryStatus.DEPRECATED.value}
    )


def _memory_title(memory: Memory) -> str:
    custom = dict(memory.metadata.custom_metadata or {})
    return str(
        custom.get("title")
        or generate_title(content=memory.content, max_len=120)
    )[:120]


def _expected_entity(memory: Memory) -> Entity:
    custom = dict(memory.metadata.custom_metadata or {})
    title = _memory_title(memory)
    entity_name = title if title and "Memory" not in title else f"memory_{memory.id}"
    summary = str(custom.get("summary") or memory.metadata.summary or "")
    processing = custom.get("processing_status", "raw")
    return Entity(
        id=memory.id,
        name=entity_name,
        type=EntityType.MEMORY,
        description=summary,
        created_at=memory.metadata.created_at,
        properties={
            "content": memory.content[:200],
            "memory_type": _text(memory.metadata.memory_type),
            "score": memory.metadata.score,
            "status": _text(memory.metadata.status),
            "timestamp": memory.metadata.created_at.isoformat(),
            "processing_status": _text(processing),
        },
    )


def _snapshot_matches(snapshot: Mapping[str, Any], memory: Memory) -> bool:
    if not snapshot.get("generated_at") or not isinstance(
        snapshot.get("nodes"),
        list,
    ):
        return False
    for node in snapshot["nodes"]:
        if not isinstance(node, Mapping) or str(node.get("id")) != str(memory.id):
            continue
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            return False
        return all(
            (
                properties.get("content") == memory.content,
                properties.get("project") == memory.metadata.project,
                properties.get("workspace") == memory.metadata.workspace,
                properties.get("scope") == memory.metadata.scope,
                properties.get("memory_type")
                == _text(memory.metadata.memory_type),
            )
        )
    return False


@dataclass(frozen=True)
class RememberOverlap:
    memory_id: str
    relation: str
    title: str
    record_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "memory_id": self.memory_id,
            "relation": self.relation,
            "title": self.title,
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True)
class VerifiedRememberPlan:
    schema_version: int
    applicable: bool
    reason_code: str | None
    reason: str
    knowledge_kind: str
    memory_type: str
    project_id: str
    project_name: str
    content_sha256: str
    scope_sha256: str
    overlaps: tuple[RememberOverlap, ...]
    choices: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "applicable": self.applicable,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "knowledge_kind": self.knowledge_kind,
            "memory_type": self.memory_type,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "content_sha256": self.content_sha256,
            "scope_sha256": self.scope_sha256,
            "overlaps": [overlap.to_dict() for overlap in self.overlaps],
            "choices": list(self.choices),
        }


@dataclass(frozen=True)
class VerifiedRememberReceipt:
    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedOperationStatus
    authority: str
    started_at: str
    finished_at: str
    memory_id: str | None
    knowledge_kind: str
    project_id: str
    project_name: str
    scope_sha256: str
    record_sha256: str | None
    graph_sha256: str | None
    relationship_sha256: str | None
    checks: tuple[VerifiedOperationCheck, ...]
    error_codes: tuple[str, ...]
    rollback: str
    changed: bool
    recoverable: bool

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
            "knowledge_kind": self.knowledge_kind,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "scope_sha256": self.scope_sha256,
            "record_sha256": self.record_sha256,
            "graph_sha256": self.graph_sha256,
            "relationship_sha256": self.relationship_sha256,
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
            "rollback": self.rollback,
            "changed": self.changed,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True)
class VerifiedRememberResult:
    status: VerifiedOperationStatus
    plan: VerifiedRememberPlan
    receipt: VerifiedRememberReceipt
    title: str | None = None

    @property
    def success(self) -> bool:
        return self.status is VerifiedOperationStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "status": self.status.value,
            "remember_status": self.status.value,
            "plan": self.plan.to_dict(),
            "receipt": self.receipt.to_dict(),
            **(
                {
                    "remembered": {
                        "title": self.title,
                        "kind": self.plan.knowledge_kind,
                        "project": {
                            "project_id": self.plan.project_id,
                            "name": self.plan.project_name,
                        },
                        "recall_verified": self.success,
                    }
                }
                if self.title
                else {}
            ),
        }
        if not self.success and self.status is not VerifiedOperationStatus.NEEDS_HUMAN:
            errors = set(self.receipt.error_codes)
            if self.status is VerifiedOperationStatus.UNSAFE:
                payload["error"] = (
                    "Remember could not prove a safe rollback. Open Recover before "
                    "trying again."
                )
            elif "RECALL_POSTCONDITION_FAILED" in errors:
                payload["error"] = (
                    "Elefante could not prove this memory would be recalled from "
                    "that question. Nothing was saved."
                )
            elif self.status is VerifiedOperationStatus.FAILED_ROLLED_BACK:
                payload["error"] = "Remember failed safely. Nothing was saved."
            else:
                payload["error"] = "Remember stopped safely before saving anything."
        return payload


class VerifiedRememberService:
    """Search, write once, prove, and compensate one explicit Remember."""

    def __init__(
        self,
        orchestrator: Any,
        *,
        snapshot_path: Path,
        refresh_snapshot: RefreshSnapshot,
        recall_selected_ids: RecallSelectedIds,
        source_context: Mapping[str, str],
        verification_attempts: int = 2,
        now: Callable[[], datetime] | None = None,
        operation_id: Callable[[], UUID] | None = None,
        memory_id: Callable[[], UUID] | None = None,
    ) -> None:
        if not 1 <= verification_attempts <= 3:
            raise ValueError("verification_attempts must be from 1 to 3")
        self.orchestrator = orchestrator
        self.store = orchestrator.vector_store
        self.graph_store = orchestrator.graph_store
        self.snapshot_path = Path(snapshot_path)
        self.refresh_snapshot = refresh_snapshot
        self.recall_selected_ids = recall_selected_ids
        self.source_context = dict(source_context)
        self.verification_attempts = verification_attempts
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._operation_id = operation_id or uuid4
        self._memory_id = memory_id or uuid4

    async def _search_overlaps(
        self,
        content: str,
        *,
        project_id: str,
        workspace: str,
    ) -> tuple[RememberOverlap, ...]:
        results = await self.orchestrator.search_memories(
            query=content,
            mode=QueryMode.HYBRID,
            limit=8,
            filters=SearchFilters(
                project=project_id,
                workspace=workspace,
                include_conversation=False,
                include_stored=True,
            ),
            min_similarity=0.3,
            include_conversation=False,
            include_stored=True,
            apply_temporal_decay=False,
            reinforce_access=False,
        )
        overlaps: list[RememberOverlap] = []
        seen: set[str] = set()
        for result in results:
            memory = result.memory
            memory_id = str(memory.id)
            if memory_id in seen or _inactive(memory):
                continue
            if (
                str(memory.metadata.project or "") != project_id
                or str(memory.metadata.workspace or "") != workspace
            ):
                continue
            score = float(getattr(result, "score", 0.0) or 0.0)
            conflict = assess_conflict(content, memory.content)
            duplicate = _near_duplicate(content, memory.content)
            if (
                not duplicate
                and conflict.outcome is not ConflictOutcome.CONFLICT
                and score < 0.65
            ):
                continue
            # Explicit contradiction wins over textual near-duplication.  A
            # one-word negation is often visually near-identical but materially
            # opposite; labelling it duplicate makes Resolve unreachable.
            relation = (
                "conflict"
                if conflict.outcome is ConflictOutcome.CONFLICT
                else "duplicate"
                if duplicate
                else "related"
            )
            overlaps.append(
                RememberOverlap(
                    memory_id=memory_id,
                    relation=relation,
                    title=_memory_title(memory),
                    record_sha256=memory_record_sha256(memory),
                )
            )
            seen.add(memory_id)
            if len(overlaps) >= 3:
                break
        return tuple(overlaps)

    def _plan(
        self,
        *,
        content: str,
        knowledge_kind: str,
        project_id: str,
        project_name: str,
        workspace: str,
        scope: str,
        overlaps: Sequence[RememberOverlap],
        keep_both: bool,
    ) -> VerifiedRememberPlan:
        memory_type = KNOWLEDGE_KIND_TO_MEMORY_TYPE[knowledge_kind]
        reason_code = None
        reason = "This knowledge can be remembered and verified now."
        choices: tuple[str, ...] = ()
        if overlaps and not keep_both:
            reason_code = "REMEMBER_OVERLAP_REQUIRES_CHOICE"
            reason = (
                "Related project knowledge already exists. Choose whether to "
                "update, supersede, keep both, or cancel."
            )
            choices = REMEMBER_CHOICES
        return VerifiedRememberPlan(
            schema_version=1,
            applicable=reason_code is None,
            reason_code=reason_code,
            reason=reason,
            knowledge_kind=knowledge_kind,
            memory_type=memory_type,
            project_id=project_id,
            project_name=project_name,
            content_sha256=_content_sha256(content),
            scope_sha256=scope_sha256(
                (
                    project_id.casefold(),
                    workspace.casefold(),
                    scope.casefold(),
                )
            ),
            overlaps=tuple(overlaps),
            choices=choices,
        )

    def _receipt(
        self,
        *,
        operation_id: str,
        started_at: str,
        status: VerifiedOperationStatus,
        plan: VerifiedRememberPlan,
        memory_id: UUID | None = None,
        record_sha256: str | None = None,
        graph_sha256: str | None = None,
        relationship_sha256: str | None = None,
        checks: Sequence[VerifiedOperationCheck] = (),
        error_codes: Sequence[str] = (),
        rollback: str = "not_required",
        changed: bool = False,
    ) -> VerifiedRememberReceipt:
        return VerifiedRememberReceipt(
            schema_version=1,
            operation_id=operation_id,
            operation="remember",
            status=status,
            authority="user_directed",
            started_at=started_at,
            finished_at=self._now().astimezone(timezone.utc).isoformat(),
            memory_id=str(memory_id) if memory_id is not None else None,
            knowledge_kind=plan.knowledge_kind,
            project_id=plan.project_id,
            project_name=plan.project_name,
            scope_sha256=plan.scope_sha256,
            record_sha256=record_sha256,
            graph_sha256=graph_sha256,
            relationship_sha256=relationship_sha256,
            checks=tuple(checks)[:8],
            error_codes=tuple(dict.fromkeys(error_codes))[:8],
            rollback=rollback,
            changed=changed,
            recoverable=status is not VerifiedOperationStatus.UNSAFE,
        )

    def _terminal(
        self,
        *,
        operation_id: str,
        started_at: str,
        status: VerifiedOperationStatus,
        plan: VerifiedRememberPlan,
        title: str | None = None,
        memory_id: UUID | None = None,
        record_sha256: str | None = None,
        graph_sha256: str | None = None,
        relationship_sha256: str | None = None,
        checks: Sequence[VerifiedOperationCheck] = (),
        error_codes: Sequence[str] = (),
        rollback: str = "not_required",
        changed: bool = False,
    ) -> VerifiedRememberResult:
        return VerifiedRememberResult(
            status=status,
            plan=plan,
            receipt=self._receipt(
                operation_id=operation_id,
                started_at=started_at,
                status=status,
                plan=plan,
                memory_id=memory_id,
                record_sha256=record_sha256,
                graph_sha256=graph_sha256,
                relationship_sha256=relationship_sha256,
                checks=checks,
                error_codes=error_codes,
                rollback=rollback,
                changed=changed,
            ),
            title=title,
        )

    async def _source_state(self) -> tuple[str | None, bool]:
        required = ("source_id_for", "source_exists", "delete_source_if_orphan")
        if any(not hasattr(self.graph_store, name) for name in required):
            return None, True
        source_id = str(self.graph_store.source_id_for(self.source_context))
        return source_id, bool(await self.graph_store.source_exists(source_id))

    async def _restore_snapshot(self, state: PrivateFileState) -> bool:
        try:
            restore_private_file(self.snapshot_path, state)
            expected = (
                hashlib.sha256(state.payload).hexdigest()
                if state.existed and state.payload is not None
                else None
            )
            return snapshot_digest(self.snapshot_path) == expected
        except Exception:
            return False

    async def _rollback(
        self,
        memory_id: UUID,
        snapshot_before: PrivateFileState,
        source_id: str | None,
        source_preexisted: bool,
        conflict_peers_before: Sequence[Memory] = (),
    ) -> bool:
        try:
            await self.graph_store.delete_entity(memory_id)
            await self.store.delete_memory(memory_id)
            peers_ok = True
            for peer_before in conflict_peers_before:
                if not await self.store.replace_memory(peer_before):
                    peers_ok = False
                    continue
                restored = await self.store.get_memory(peer_before.id)
                peers_ok = bool(
                    peers_ok
                    and restored is not None
                    and memory_record_sha256(restored)
                    == memory_record_sha256(peer_before)
                )
            memory_absent = await self.store.get_memory(memory_id) is None
            graph_absent = await self.graph_store.get_entity(memory_id) is None
            source_ok = True
            if source_id is not None and not source_preexisted:
                source_ok = bool(
                    await self.graph_store.delete_source_if_orphan(source_id)
                )
            snapshot_ok = await self._restore_snapshot(snapshot_before)
            return (
                memory_absent
                and graph_absent
                and peers_ok
                and source_ok
                and snapshot_ok
            )
        except Exception:
            return False

    async def execute(
        self,
        *,
        content: str,
        knowledge_kind: str,
        project_id: str,
        project_name: str,
        workspace: str,
        scope: str,
        verification_question: str,
        metadata: Mapping[str, Any] | None = None,
        tags: Sequence[str] | None = None,
        entities: Sequence[Mapping[str, str]] | None = None,
        keep_both: bool = False,
        expected_overlap_sha256: Mapping[str, str] | None = None,
    ) -> VerifiedRememberResult:
        operation_id = str(self._operation_id())
        started_at = self._now().astimezone(timezone.utc).isoformat()
        content = validate_memory_content(content)
        knowledge_kind = str(knowledge_kind or "").strip().casefold()
        verification_question = str(verification_question or "").strip()
        if knowledge_kind not in KNOWLEDGE_KIND_TO_MEMORY_TYPE:
            raise ValueError("knowledge_kind must be decision, constraint, preference, or lesson")
        if not 1 <= len(verification_question) <= 1000:
            raise ValueError("verification_question must be from 1 to 1000 characters")
        if not project_id or not project_name or not workspace or not scope:
            raise ValueError("one registered project is required")

        write_metadata = dict(metadata or {})
        # The customer supplied this wording specifically as the way they expect
        # to retrieve the memory later. Persist it as a bounded project-only cue;
        # it is never copied into the public operation receipt.
        write_metadata["recall_cues"] = canonicalize_recall_cues(
            [verification_question]
        )

        try:
            overlaps = await self._search_overlaps(
                content,
                project_id=project_id,
                workspace=workspace,
            )
        except Exception:
            overlaps = ()
            plan = self._plan(
                content=content,
                knowledge_kind=knowledge_kind,
                project_id=project_id,
                project_name=project_name,
                workspace=workspace,
                scope=scope,
                overlaps=overlaps,
                keep_both=False,
            )
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                plan=plan,
                error_codes=("REMEMBER_OVERLAP_SEARCH_FAILED",),
            )

        plan = self._plan(
            content=content,
            knowledge_kind=knowledge_kind,
            project_id=project_id,
            project_name=project_name,
            workspace=workspace,
            scope=scope,
            overlaps=overlaps,
            keep_both=keep_both,
        )
        current_overlap_hashes = {
            overlap.memory_id: overlap.record_sha256 for overlap in overlaps
        }
        if keep_both and (
            not overlaps
            or dict(expected_overlap_sha256 or {}) != current_overlap_hashes
        ):
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                error_codes=("REMEMBER_OVERLAP_PLAN_STALE",),
            )
        if not plan.applicable:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                error_codes=(plan.reason_code or "REMEMBER_REVIEW_REQUIRED",),
            )

        new_memory_id = self._memory_id()
        conflict_peer_ids = tuple(
            UUID(overlap.memory_id)
            for overlap in overlaps
            if keep_both and overlap.relation == "conflict"
        )
        conflict_peers_before: list[Memory] = []
        try:
            for peer_id in conflict_peer_ids:
                peer = await self.store.get_memory(peer_id)
                if peer is None:
                    raise RuntimeError("REMEMBER_CONFLICT_PEER_MISSING")
                conflict_peers_before.append(peer.model_copy(deep=True))
        except Exception:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                plan=plan,
                error_codes=("REMEMBER_OVERLAP_PLAN_STALE",),
            )
        snapshot_before = capture_private_file(self.snapshot_path)
        prior_snapshot_digest = snapshot_digest(self.snapshot_path)
        try:
            source_id, source_preexisted = await self._source_state()
        except Exception:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                plan=plan,
                error_codes=("REMEMBER_SOURCE_INSPECTION_FAILED",),
            )

        memory: Memory | None = None
        write_error: str | None = None
        try:
            memory = await self.orchestrator.add_memory(
                content=content,
                memory_type=plan.memory_type,
                tags=list(tags or []),
                entities=[dict(entity) for entity in (entities or [])],
                metadata=write_metadata,
                force_new=True,
                memory_id=new_memory_id,
                conflict_ids=list(conflict_peer_ids),
            )
            if memory is None or memory.id != new_memory_id:
                raise RuntimeError("REMEMBER_WRITE_REJECTED")

            # Make the conflict visible from either side.  Recall and Task
            # Intelligence inspect memory metadata, so a one-way link could let
            # the older assertion escape without a conflict warning.
            for peer_before in conflict_peers_before:
                peer = await self.store.get_memory(peer_before.id)
                if peer is None:
                    raise RuntimeError("REMEMBER_CONFLICT_PEER_MISSING")
                peer.metadata.conflict_ids = list(
                    dict.fromkeys([*(peer.metadata.conflict_ids or []), new_memory_id])
                )
                peer.metadata.status = MemoryStatus.CONTRADICTORY
                peer.metadata.last_modified = self._now().replace(tzinfo=None)
                if not await self.store.replace_memory(peer):
                    raise RuntimeError("REMEMBER_CONFLICT_LINK_FAILED")
        except Exception as error:
            write_error = str(error) if str(error).startswith("REMEMBER_") else "REMEMBER_WRITE_FAILED"
            memory = None

        if memory is None:
            partial_change = False
            try:
                partial_change = (
                    await self.store.get_memory(new_memory_id) is not None
                    or await self.graph_store.get_entity(new_memory_id) is not None
                )
            except Exception:
                partial_change = True
            rollback_ok = await self._rollback(
                new_memory_id,
                snapshot_before,
                source_id,
                source_preexisted,
                conflict_peers_before,
            )
            status = (
                VerifiedOperationStatus.FAILED_ROLLED_BACK
                if partial_change and rollback_ok
                else VerifiedOperationStatus.FAILED_NO_CHANGE
                if rollback_ok
                else VerifiedOperationStatus.UNSAFE
            )
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=status,
                plan=plan,
                memory_id=new_memory_id,
                error_codes=(write_error or "REMEMBER_WRITE_FAILED",),
                rollback=("verified" if partial_change and rollback_ok else "not_required" if rollback_ok else "incomplete"),
                changed=not rollback_ok,
            )

        expected_entity = _expected_entity(memory)
        expected_concepts = tuple(
            canonicalize_concepts(list(memory.metadata.concepts or []), max_concepts=5)
        )
        checks: list[VerifiedOperationCheck] = []
        postcondition_error: str | None = None
        record_hash = memory_record_sha256(memory)
        graph_hash: str | None = None
        relationship_hash = _projection_sha256(expected_concepts)

        authoritative_ok = False
        authoritative_attempts = self.verification_attempts
        for attempt in range(1, self.verification_attempts + 1):
            try:
                current_memory = await self.store.get_memory(new_memory_id)
                current_entity = await self.graph_store.get_entity(new_memory_id)
                authoritative_ok = bool(
                    current_memory is not None
                    and memory_record_sha256(current_memory) == record_hash
                    and current_entity is not None
                    and entity_record_sha256(current_entity)
                    == entity_record_sha256(expected_entity)
                    and str(current_memory.metadata.project or "") == project_id
                    and str(current_memory.metadata.workspace or "") == workspace
                    and str(current_memory.metadata.scope or "") == scope
                )
                if authoritative_ok:
                    authoritative_attempts = attempt
                    graph_hash = entity_record_sha256(current_entity)
                    break
            except Exception:
                pass
        checks.append(
            VerifiedOperationCheck(
                "authoritative_store_and_graph",
                authoritative_ok,
                authoritative_attempts,
                "AUTHORITATIVE_POSTCONDITION_OK" if authoritative_ok else "AUTHORITATIVE_POSTCONDITION_FAILED",
            )
        )
        if not authoritative_ok:
            postcondition_error = "AUTHORITATIVE_POSTCONDITION_FAILED"

        if postcondition_error is None and conflict_peer_ids:
            conflict_ok = True
            conflict_attempts = self.verification_attempts
            for attempt in range(1, self.verification_attempts + 1):
                try:
                    current = await self.store.get_memory(new_memory_id)
                    peers = [
                        await self.store.get_memory(peer_id)
                        for peer_id in conflict_peer_ids
                    ]
                    conflict_ok = bool(
                        current is not None
                        and set(current.metadata.conflict_ids or [])
                        == set(conflict_peer_ids)
                        and all(
                            peer is not None
                            and new_memory_id in (peer.metadata.conflict_ids or [])
                            and _text(peer.metadata.status).casefold()
                            == MemoryStatus.CONTRADICTORY.value
                            for peer in peers
                        )
                    )
                    if conflict_ok:
                        conflict_attempts = attempt
                        break
                except Exception:
                    conflict_ok = False
            checks.append(
                VerifiedOperationCheck(
                    "conflict_projection",
                    conflict_ok,
                    conflict_attempts,
                    "CONFLICT_POSTCONDITION_OK"
                    if conflict_ok
                    else "CONFLICT_POSTCONDITION_FAILED",
                )
            )
            if not conflict_ok:
                postcondition_error = "CONFLICT_POSTCONDITION_FAILED"

        if postcondition_error is None:
            relationship_ok = False
            relationship_attempts = self.verification_attempts
            for attempt in range(1, self.verification_attempts + 1):
                try:
                    current = await self.graph_store.get_memory_concepts(new_memory_id)
                    relationship_ok = _projection_sha256(current) == relationship_hash
                    if relationship_ok:
                        relationship_attempts = attempt
                        break
                except Exception:
                    pass
            checks.append(
                VerifiedOperationCheck(
                    "relationship_projection",
                    relationship_ok,
                    relationship_attempts,
                    "RELATIONSHIP_POSTCONDITION_OK" if relationship_ok else "RELATIONSHIP_POSTCONDITION_FAILED",
                )
            )
            if not relationship_ok:
                postcondition_error = "RELATIONSHIP_POSTCONDITION_FAILED"

        if postcondition_error is None:
            snapshot_ok = False
            snapshot_attempts = self.verification_attempts
            for attempt in range(1, self.verification_attempts + 1):
                try:
                    await self.refresh_snapshot()
                    snapshot_ok = bool(
                        snapshot_digest(self.snapshot_path) != prior_snapshot_digest
                        and _snapshot_matches(load_snapshot(self.snapshot_path), memory)
                    )
                    if snapshot_ok:
                        snapshot_attempts = attempt
                        break
                except Exception:
                    pass
            checks.append(
                VerifiedOperationCheck(
                    "dashboard_snapshot",
                    snapshot_ok,
                    snapshot_attempts,
                    "SNAPSHOT_POSTCONDITION_OK" if snapshot_ok else "SNAPSHOT_POSTCONDITION_FAILED",
                )
            )
            if not snapshot_ok:
                postcondition_error = "SNAPSHOT_POSTCONDITION_FAILED"

        if postcondition_error is None:
            recall_ok = False
            recall_attempts = self.verification_attempts
            for attempt in range(1, self.verification_attempts + 1):
                try:
                    recall_result = await self.recall_selected_ids(
                        verification_question,
                        project=project_id,
                        workspace=workspace,
                    )
                    if isinstance(recall_result, RecallVerification):
                        selected = {
                            str(item) for item in recall_result.selected_ids
                        }
                        conflict_count = recall_result.conflict_count
                    else:
                        selected = {str(item) for item in recall_result}
                        conflict_count = 0
                    if conflict_peer_ids:
                        conflict_pair = {
                            str(new_memory_id),
                            *(str(item) for item in conflict_peer_ids),
                        }
                        recall_ok = bool(
                            conflict_count > 0
                            and selected.isdisjoint(conflict_pair)
                        )
                    else:
                        recall_ok = str(new_memory_id) in selected
                    if recall_ok:
                        recall_attempts = attempt
                        break
                except Exception:
                    pass
            checks.append(
                VerifiedOperationCheck(
                    "scoped_recall",
                    recall_ok,
                    recall_attempts,
                    (
                        "RECALL_CONFLICT_POSTCONDITION_OK"
                        if recall_ok and conflict_peer_ids
                        else "RECALL_POSTCONDITION_OK"
                        if recall_ok
                        else "RECALL_POSTCONDITION_FAILED"
                    ),
                )
            )
            if not recall_ok:
                postcondition_error = "RECALL_POSTCONDITION_FAILED"

        if postcondition_error is None:
            return self._terminal(
                operation_id=operation_id,
                started_at=started_at,
                status=VerifiedOperationStatus.VERIFIED_COMPLETE,
                plan=plan,
                title=_memory_title(memory),
                memory_id=new_memory_id,
                record_sha256=record_hash,
                graph_sha256=graph_hash,
                relationship_sha256=relationship_hash,
                checks=checks,
                changed=True,
            )

        rollback_ok = await self._rollback(
            new_memory_id,
            snapshot_before,
            source_id,
            source_preexisted,
            conflict_peers_before,
        )
        status = (
            VerifiedOperationStatus.FAILED_ROLLED_BACK
            if rollback_ok
            else VerifiedOperationStatus.UNSAFE
        )
        errors = [postcondition_error]
        if not rollback_ok:
            errors.append("REMEMBER_ROLLBACK_INCOMPLETE")
        return self._terminal(
            operation_id=operation_id,
            started_at=started_at,
            status=status,
            plan=plan,
            memory_id=new_memory_id,
            record_sha256=record_hash,
            graph_sha256=graph_hash,
            relationship_sha256=relationship_hash,
            checks=checks,
            error_codes=errors,
            rollback="verified" if rollback_ok else "incomplete",
            changed=not rollback_ok,
        )


__all__ = [
    "KNOWLEDGE_KIND_TO_MEMORY_TYPE",
    "MEMORY_TYPE_TO_KNOWLEDGE_KIND",
    "REMEMBER_CHOICES",
    "RecallVerification",
    "RememberOverlap",
    "VerifiedRememberPlan",
    "VerifiedRememberReceipt",
    "VerifiedRememberResult",
    "VerifiedRememberService",
]
