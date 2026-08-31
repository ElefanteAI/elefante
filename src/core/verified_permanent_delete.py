"""Backup-bound permanent deletion for one exact project-scoped memory.

This is the destructive edge of Correct. It accepts only a freshly completed
Recover backup created while the caller holds the product write boundary. It
then removes one exact vector record, graph projection, derived concept links,
and unshared attachment bytes. Any failed postcondition restores the verified
backup through Recover instead of pretending a partial delete was reversible.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from src.core.multimodal import AttachmentStore, AttachmentValidationError
from src.core.verified_correction import (
    CorrectionAction,
    VerifiedCorrectionPlan,
    VerifiedCorrectionReceipt,
    VerifiedCorrectionResult,
    _relationship_projection_sha256,
)
from src.core.verified_operation import (
    VerifiedOperationCheck,
    VerifiedOperationStatus,
    entity_record_sha256,
    load_snapshot,
    memory_record_sha256,
    recall_scope,
    snapshot_digest,
)
from src.models.memory import Memory


RefreshSnapshot = Callable[[], Awaitable[Mapping[str, Any] | None]]
RecallSelectedIds = Callable[..., Awaitable[Sequence[str]]]
RestoreBackup = Callable[[str, str, str], Awaitable[bool]]
VerifyBackup = Callable[[str, str, str], Awaitable[bool]]
DiscardBackup = Callable[[str, str, str], Awaitable[bool]]

_MAX_MEMORY_SCAN = 100_000
_SCAN_PAGE = 1_000


class PermanentDeleteError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _safe_backup_boundary(receipt: Mapping[str, Any]) -> dict[str, str] | None:
    status = str(getattr(receipt.get("status"), "value", receipt.get("status")))
    operation_id = str(receipt.get("operation_id") or "")
    archive_name = str(receipt.get("archive_name") or "")
    archive_sha256 = str(receipt.get("archive_sha256") or "").casefold()
    source_sha256 = str(receipt.get("source_sha256") or "").casefold()
    checks = receipt.get("checks")
    try:
        UUID(operation_id)
    except ValueError:
        return None
    if (
        receipt.get("operation") != "backup"
        or status != VerifiedOperationStatus.VERIFIED_COMPLETE.value
        or receipt.get("authority") != "workflow_managed"
        or receipt.get("recoverable") is not True
        or receipt.get("archive_consumed") is True
        or not archive_name
        or archive_name != Path(archive_name).name
        or not archive_name.lower().endswith(".zip")
        or len(archive_sha256) != 64
        or len(source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in archive_sha256)
        or any(character not in "0123456789abcdef" for character in source_sha256)
        or not isinstance(checks, (list, tuple))
    ):
        return None
    normalized_checks = [
        check.to_dict() if hasattr(check, "to_dict") else check
        for check in checks
    ]
    if not normalized_checks or any(
        not isinstance(check, Mapping) or check.get("passed") is not True
        for check in normalized_checks
    ):
        return None
    names = {str(check.get("name") or "") for check in normalized_checks}
    if not {
        "archive_readback",
        "staged_restore",
        "sqlite_integrity",
        "kuzu_integrity",
    }.issubset(names):
        return None
    return {
        "operation_id": operation_id,
        "archive_name": archive_name,
        "archive_sha256": archive_sha256,
        "source_sha256": source_sha256,
    }


class VerifiedPermanentDeleteService:
    """Delete one exact memory only behind a verified Recover boundary."""

    def __init__(
        self,
        store: Any,
        graph_store: Any,
        *,
        snapshot_path: Path,
        refresh_snapshot: RefreshSnapshot,
        recall_selected_ids: RecallSelectedIds,
        attachment_root: Path,
        restore_backup: RestoreBackup,
        verify_backup: VerifyBackup,
        discard_backup: DiscardBackup,
        now: Callable[[], datetime] | None = None,
        operation_id: Callable[[], UUID] | None = None,
    ) -> None:
        self.store = store
        self.graph_store = graph_store
        self.snapshot_path = Path(snapshot_path)
        self.refresh_snapshot = refresh_snapshot
        self.recall_selected_ids = recall_selected_ids
        self.attachment_store = AttachmentStore(Path(attachment_root))
        self.restore_backup = restore_backup
        self.verify_backup = verify_backup
        self.discard_backup = discard_backup
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._operation_id = operation_id or uuid4

    async def _load_target(
        self,
        memory_id: UUID,
    ) -> tuple[Memory | None, Any | None, tuple[str, ...]]:
        memory = await self.store.get_memory(memory_id)
        entity = await self.graph_store.get_entity(memory_id) if memory else None
        concepts = (
            tuple(await self.graph_store.get_memory_concepts(memory_id))
            if entity is not None
            else ()
        )
        return memory, entity, concepts

    @staticmethod
    def _attachment_descriptors(memory: Memory) -> tuple[Mapping[str, Any], ...]:
        custom = memory.metadata.custom_metadata or {}
        raw = custom.get("attachments")
        if raw is None:
            return ()
        if not isinstance(raw, list) or any(not isinstance(item, Mapping) for item in raw):
            raise PermanentDeleteError("ATTACHMENT_METADATA_INVALID")
        return tuple(raw)

    async def _remaining_attachment_paths(self) -> set[str]:
        paths: set[str] = set()
        offset = 0
        while offset < _MAX_MEMORY_SCAN:
            batch = await self.store.get_all(limit=_SCAN_PAGE, offset=offset)
            for memory in batch:
                for descriptor in self._attachment_descriptors(memory):
                    storage_path = descriptor.get("storage_path")
                    if isinstance(storage_path, str) and storage_path:
                        paths.add(storage_path)
            if len(batch) < _SCAN_PAGE:
                return paths
            offset += len(batch)
        raise PermanentDeleteError("ATTACHMENT_REFERENCE_SCAN_LIMIT")

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    async def _delete_unshared_attachments(self, memory: Memory) -> int:
        descriptors = self._attachment_descriptors(memory)
        if not descriptors:
            return 0
        referenced = await self._remaining_attachment_paths()
        removed = 0
        for descriptor in descriptors:
            storage_path = str(descriptor.get("storage_path") or "")
            if storage_path in referenced:
                continue
            try:
                path = self.attachment_store.resolve(descriptor)
            except AttachmentValidationError as error:
                raise PermanentDeleteError("ATTACHMENT_PATH_UNSAFE") from error
            if not path.exists():
                continue
            if path.is_symlink() or not path.is_file():
                raise PermanentDeleteError("ATTACHMENT_PATH_UNSAFE")
            expected_sha256 = str(descriptor.get("sha256") or "").casefold()
            if len(expected_sha256) != 64 or await asyncio.to_thread(
                self._file_sha256,
                path,
            ) != expected_sha256:
                raise PermanentDeleteError("ATTACHMENT_INTEGRITY_FAILED")
            await asyncio.to_thread(path.unlink)
            if path.exists():
                raise PermanentDeleteError("ATTACHMENT_DELETE_FAILED")
            removed += 1
        return removed

    async def _verify_snapshot_absent(
        self,
        memory_id: UUID,
        previous_digest: str | None,
    ) -> bool:
        result = await self.refresh_snapshot()
        if isinstance(result, Mapping) and result.get("success") is False:
            return False
        current_digest = snapshot_digest(self.snapshot_path)
        if current_digest is None or current_digest == previous_digest:
            return False
        snapshot = load_snapshot(self.snapshot_path)
        nodes = snapshot.get("nodes")
        return bool(
            isinstance(nodes, list)
            and all(
                not isinstance(node, Mapping)
                or str(node.get("id") or "") != str(memory_id)
                for node in nodes
            )
        )

    async def _verify_recall_absent(self, memory: Memory, question: str) -> bool:
        project, workspace = recall_scope(memory)
        selected = {
            str(item)
            for item in await self.recall_selected_ids(
                question,
                project=project,
                workspace=workspace,
            )
        }
        return str(memory.id) not in selected

    async def _state_is_unchanged(
        self,
        memory: Memory,
        entity: Any,
        concepts: Sequence[str],
    ) -> bool:
        try:
            current_memory, current_entity, current_concepts = await self._load_target(
                memory.id
            )
        except Exception:
            return False
        return bool(
            current_memory is not None
            and current_entity is not None
            and memory_record_sha256(current_memory) == memory_record_sha256(memory)
            and entity_record_sha256(current_entity) == entity_record_sha256(entity)
            and _relationship_projection_sha256(current_concepts)
            == _relationship_projection_sha256(concepts)
        )

    def _receipt(
        self,
        *,
        plan: VerifiedCorrectionPlan,
        boundary: Mapping[str, str],
        started_at: str,
        status: VerifiedOperationStatus,
        record_hashes: Mapping[str, str],
        graph_hashes: Mapping[str, str],
        checks: Sequence[VerifiedOperationCheck],
        error_codes: Sequence[str],
        rollback: str,
        changed: bool,
        recoverable: bool,
    ) -> VerifiedCorrectionReceipt:
        return VerifiedCorrectionReceipt(
            schema_version=1,
            operation_id=str(self._operation_id()),
            operation=CorrectionAction.PERMANENT_DELETE.value,
            status=status,
            authority="user_directed",
            started_at=started_at,
            finished_at=self._now().astimezone(timezone.utc).isoformat(),
            memory_ids={"target": plan.memory_id, "replacement": ""},
            scope_sha256=plan.scope_sha256 or "",
            record_sha256=dict(record_hashes),
            graph_sha256=dict(graph_hashes),
            checks=tuple(checks)[:8],
            error_codes=tuple(dict.fromkeys(error_codes))[:8],
            rollback=rollback,
            changed=changed,
            recoverable=recoverable,
            recovery_operation_id=boundary["operation_id"],
            recovery_archive_name=boundary["archive_name"],
            recovery_archive_sha256=boundary["archive_sha256"],
        )

    async def execute(
        self,
        memory_id: UUID,
        *,
        plan: VerifiedCorrectionPlan,
        backup_receipt: Mapping[str, Any],
        reason: str,
        verification_question: str,
        expected_record_sha256: Mapping[str, str],
        expected_graph_sha256: Mapping[str, str],
    ) -> VerifiedCorrectionResult:
        started_at = self._now().astimezone(timezone.utc).isoformat()
        boundary = _safe_backup_boundary(backup_receipt)
        if (
            boundary is None
            or plan.action is not CorrectionAction.PERMANENT_DELETE
            or not plan.applicable
            or dict(expected_record_sha256) != plan.record_sha256
            or dict(expected_graph_sha256) != plan.graph_sha256
            or not str(reason).strip()
            or not str(verification_question).strip()
        ):
            empty_boundary = boundary or {
                "operation_id": "",
                "archive_name": "",
                "archive_sha256": "",
            }
            receipt = self._receipt(
                plan=plan,
                boundary=empty_boundary,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                record_hashes={},
                graph_hashes={},
                checks=(),
                error_codes=("RECOVERY_BASELINE_REQUIRED",),
                rollback="not_required",
                changed=False,
                recoverable=False,
            )
            return VerifiedCorrectionResult(receipt.status, plan, receipt)

        try:
            backup_verified = await self.verify_backup(
                boundary["archive_name"],
                boundary["archive_sha256"],
                boundary["operation_id"],
            )
        except Exception:
            backup_verified = False
        if not backup_verified:
            receipt = self._receipt(
                plan=plan,
                boundary=boundary,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                record_hashes={},
                graph_hashes={},
                checks=(
                    VerifiedOperationCheck(
                        "verified_backup",
                        False,
                        1,
                        "RECOVERY_BACKUP_STALE",
                    ),
                ),
                error_codes=("RECOVERY_BASELINE_STALE",),
                rollback="not_required",
                changed=False,
                recoverable=False,
            )
            return VerifiedCorrectionResult(receipt.status, plan, receipt)

        before, graph_before, concepts_before = await self._load_target(memory_id)
        if before is None or graph_before is None:
            receipt = self._receipt(
                plan=plan,
                boundary=boundary,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                record_hashes={},
                graph_hashes={},
                checks=(),
                error_codes=("PLAN_STALE",),
                rollback="not_required",
                changed=False,
                recoverable=True,
            )
            return VerifiedCorrectionResult(receipt.status, plan, receipt)
        if (
            memory_record_sha256(before) != plan.record_sha256.get("target")
            or entity_record_sha256(graph_before) != plan.graph_sha256.get("target")
            or _relationship_projection_sha256(concepts_before)
            != plan.graph_sha256.get("target_relationships")
        ):
            receipt = self._receipt(
                plan=plan,
                boundary=boundary,
                started_at=started_at,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                record_hashes={},
                graph_hashes={},
                checks=(),
                error_codes=("PLAN_STALE",),
                rollback="not_required",
                changed=False,
                recoverable=True,
            )
            return VerifiedCorrectionResult(receipt.status, plan, receipt)

        previous_snapshot_digest = snapshot_digest(self.snapshot_path)
        checks = [
            VerifiedOperationCheck(
                "verified_backup",
                True,
                1,
                "RECOVERY_BACKUP_VERIFIED",
            )
        ]
        changed = False
        error_code = "PERMANENT_DELETE_FAILED"
        try:
            await self.graph_store.replace_memory_concepts(memory_id, [])
            if await self.graph_store.get_memory_concepts(memory_id):
                raise PermanentDeleteError("RELATIONSHIP_DELETE_FAILED")
            await self.graph_store.delete_entity(memory_id)
            changed = True
            if await self.graph_store.get_entity(memory_id) is not None:
                raise PermanentDeleteError("GRAPH_DELETE_FAILED")
            await self.store.delete_memory(memory_id)
            if await self.store.get_memory(memory_id) is not None:
                raise PermanentDeleteError("VECTOR_DELETE_FAILED")
            source = (before.metadata.custom_metadata or {}).get("elefante_source")
            if isinstance(source, Mapping) and hasattr(
                self.graph_store,
                "delete_source_if_orphan",
            ):
                source_id = self.graph_store.source_id_for(dict(source))
                await self.graph_store.delete_source_if_orphan(source_id)
            attachments_removed = await self._delete_unshared_attachments(before)
            checks.append(
                VerifiedOperationCheck(
                    "authoritative_deletion",
                    True,
                    1,
                    "PERMANENT_DELETE_AUTHORITATIVE_OK",
                )
            )
            checks.append(
                VerifiedOperationCheck(
                    "unshared_attachments",
                    True,
                    1,
                    (
                        "PERMANENT_DELETE_ATTACHMENTS_REMOVED"
                        if attachments_removed
                        else "PERMANENT_DELETE_ATTACHMENTS_NOT_PRESENT"
                    ),
                )
            )
            snapshot_ok = await self._verify_snapshot_absent(
                memory_id,
                previous_snapshot_digest,
            )
            checks.append(
                VerifiedOperationCheck(
                    "dashboard_snapshot",
                    snapshot_ok,
                    1,
                    (
                        "PERMANENT_DELETE_SNAPSHOT_OK"
                        if snapshot_ok
                        else "PERMANENT_DELETE_SNAPSHOT_FAILED"
                    ),
                )
            )
            if not snapshot_ok:
                raise PermanentDeleteError("PERMANENT_DELETE_SNAPSHOT_FAILED")
            recall_ok = await self._verify_recall_absent(before, verification_question)
            checks.append(
                VerifiedOperationCheck(
                    "scoped_recall",
                    recall_ok,
                    1,
                    (
                        "PERMANENT_DELETE_RECALL_OK"
                        if recall_ok
                        else "PERMANENT_DELETE_RECALL_FAILED"
                    ),
                )
            )
            if not recall_ok:
                raise PermanentDeleteError("PERMANENT_DELETE_RECALL_FAILED")
            backup_removed = await self.discard_backup(
                boundary["archive_name"],
                boundary["archive_sha256"],
                boundary["operation_id"],
            )
            checks.append(
                VerifiedOperationCheck(
                    "safety_backup_removal",
                    backup_removed,
                    1,
                    (
                        "PERMANENT_DELETE_BACKUP_REMOVED"
                        if backup_removed
                        else "PERMANENT_DELETE_BACKUP_REMOVE_FAILED"
                    ),
                )
            )
            if not backup_removed:
                raise PermanentDeleteError(
                    "PERMANENT_DELETE_BACKUP_REMOVE_FAILED"
                )
        except Exception as error:
            error_code = str(getattr(error, "code", "PERMANENT_DELETE_FAILED"))
            unchanged = await self._state_is_unchanged(
                before,
                graph_before,
                concepts_before,
            )
            if unchanged:
                status = VerifiedOperationStatus.FAILED_NO_CHANGE
                rollback = "not_required"
                changed = False
            else:
                restored = await self.restore_backup(
                    boundary["archive_name"],
                    boundary["archive_sha256"],
                    verification_question,
                )
                status = (
                    VerifiedOperationStatus.FAILED_ROLLED_BACK
                    if restored
                    else VerifiedOperationStatus.UNSAFE
                )
                rollback = "verified" if restored else "incomplete"
                changed = not restored
                if not restored:
                    error_code = f"{error_code}|ROLLBACK_INCOMPLETE"
            receipt = self._receipt(
                plan=plan,
                boundary=boundary,
                started_at=started_at,
                status=status,
                record_hashes={"target_before": memory_record_sha256(before)},
                graph_hashes={
                    "target_before": entity_record_sha256(graph_before),
                    "target_relationships_before": _relationship_projection_sha256(
                        concepts_before
                    ),
                },
                checks=checks,
                error_codes=tuple(error_code.split("|")),
                rollback=rollback,
                changed=changed,
                recoverable=True,
            )
            return VerifiedCorrectionResult(receipt.status, plan, receipt)

        receipt = self._receipt(
            plan=plan,
            boundary=boundary,
            started_at=started_at,
            status=VerifiedOperationStatus.VERIFIED_COMPLETE,
            record_hashes={"target_before": memory_record_sha256(before)},
            graph_hashes={
                "target_before": entity_record_sha256(graph_before),
                "target_relationships_before": _relationship_projection_sha256(
                    concepts_before
                ),
            },
            checks=checks,
            error_codes=(),
            rollback="not_required",
            changed=True,
            recoverable=False,
        )
        return VerifiedCorrectionResult(receipt.status, plan, receipt)


__all__ = ["VerifiedPermanentDeleteService"]
