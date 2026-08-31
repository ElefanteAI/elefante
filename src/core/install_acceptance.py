"""Disposable, project-scoped installation acceptance.

The official installer needs one real Recall proof without leaving demo content
in customer memory.  This service writes one generated ephemeral vector record,
uses the normal governed Recall selector, then removes and verifies that exact
record.  It deliberately creates no graph projection, so an interrupted or
completed acceptance run cannot leave concept/entity debris in Kuzu.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from src.core.verified_operation import VerifiedOperationCheck, VerifiedOperationStatus
from src.models.memory import (
    DomainType,
    InjectionPolicy,
    Memory,
    MemoryMetadata,
    MemoryStatus,
    MemoryType,
    RetentionPolicy,
    SourceType,
)


INSTALL_ACCEPTANCE_SCHEMA_VERSION = 1
INSTALL_ACCEPTANCE_CATEGORY = "system-test"
INSTALL_ACCEPTANCE_CREATED_BY = "elefante-installer"
MAX_ACCEPTANCE_SCAN = 10_000


RecallSelectedIds = Callable[[str, str, str], Awaitable[Sequence[str]]]


@dataclass(frozen=True)
class InstallAcceptanceReceipt:
    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedOperationStatus
    started_at: str
    finished_at: str
    checks: tuple[VerifiedOperationCheck, ...]
    error_codes: tuple[str, ...]
    changed: bool
    rollback: str
    recoverable: bool
    next_action: str
    stale_records_removed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "operation": self.operation,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
            "changed": self.changed,
            "rollback": self.rollback,
            "recoverable": self.recoverable,
            "next_action": self.next_action,
            "stale_records_removed": self.stale_records_removed,
            "memory_content_included": False,
            "project_path_included": False,
        }


@dataclass(frozen=True)
class InstallAcceptanceResult:
    status: VerifiedOperationStatus
    receipt: InstallAcceptanceReceipt

    @property
    def success(self) -> bool:
        return self.status is VerifiedOperationStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action": "installation_acceptance",
            "status": self.status.value,
            "receipt": self.receipt.to_dict(),
        }


class InstallAcceptanceService:
    """Prove stored Recall and exact cleanup for one registered project."""

    def __init__(
        self,
        vector_store: Any,
        embedding_service: Any,
        *,
        recall_selected_ids: RecallSelectedIds,
        id_factory: Callable[[], UUID] = uuid4,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.recall_selected_ids = recall_selected_ids
        self.id_factory = id_factory
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _is_acceptance_memory(memory: Memory) -> bool:
        custom = memory.metadata.custom_metadata or {}
        retention = str(
            getattr(memory.metadata.retention_policy, "value", memory.metadata.retention_policy)
        )
        return bool(
            memory.metadata.created_by == INSTALL_ACCEPTANCE_CREATED_BY
            and memory.metadata.category == INSTALL_ACCEPTANCE_CATEGORY
            and retention == RetentionPolicy.EPHEMERAL.value
            and isinstance(custom, Mapping)
            and custom.get("install_acceptance_schema_version")
            == INSTALL_ACCEPTANCE_SCHEMA_VERSION
        )

    async def _stale_acceptance_memories(self) -> list[Memory]:
        matches: list[Memory] = []
        offset = 0
        page_size = 250
        while offset < MAX_ACCEPTANCE_SCAN:
            page = await self.vector_store.get_all(
                limit=min(page_size, MAX_ACCEPTANCE_SCAN - offset),
                offset=offset,
            )
            if not page:
                break
            matches.extend(memory for memory in page if self._is_acceptance_memory(memory))
            offset += len(page)
            if len(page) < page_size:
                break
        if offset >= MAX_ACCEPTANCE_SCAN and await self.vector_store.get_all(
            limit=1,
            offset=offset,
        ):
            raise RuntimeError("INSTALL_ACCEPTANCE_SCAN_LIMIT")
        return matches

    async def _remove_and_verify(self, memory_id: UUID) -> bool:
        current = await self.vector_store.get_memory(memory_id)
        if current is None:
            return True
        if not self._is_acceptance_memory(current):
            return False
        await self.vector_store.delete_memory(memory_id)
        return await self.vector_store.get_memory(memory_id) is None

    async def execute(
        self,
        *,
        project_id: str,
        project_scope: str,
        workspace: str,
    ) -> InstallAcceptanceResult:
        operation_id = str(self.id_factory())
        started_at = self.now().isoformat()
        checks: list[VerifiedOperationCheck] = []
        errors: list[str] = []
        stale_removed = 0
        acceptance_memory: Memory | None = None
        record_written = False
        recall_verified = False
        cleanup_verified = False

        try:
            stale = await self._stale_acceptance_memories()
            stale_results = [
                await self._remove_and_verify(memory.id) for memory in stale
            ]
            stale_removed = sum(1 for removed in stale_results if removed)
            stale_ok = all(stale_results)
        except Exception:
            stale_ok = False
        checks.append(
            VerifiedOperationCheck(
                "stale_acceptance_cleanup",
                stale_ok,
                1,
                (
                    "STALE_ACCEPTANCE_CLEANUP_OK"
                    if stale_ok
                    else "STALE_ACCEPTANCE_CLEANUP_FAILED"
                ),
            )
        )
        if not stale_ok:
            errors.append("INSTALL_ACCEPTANCE_STALE_CLEANUP_FAILED")
        else:
            nonce = self.id_factory().hex
            question = (
                "Elefante connection check "
                f"{nonce[:12]}: what installation code was stored?"
            )
            content = f"The Elefante installation code is {nonce}."
            try:
                embedding = await self.embedding_service.generate_embedding(content)
                acceptance_memory = Memory(
                    id=self.id_factory(),
                    content=content,
                    embedding=embedding,
                    metadata=MemoryMetadata(
                        created_by=INSTALL_ACCEPTANCE_CREATED_BY,
                        author=INSTALL_ACCEPTANCE_CREATED_BY,
                        domain=DomainType.SYSTEM,
                        category=INSTALL_ACCEPTANCE_CATEGORY,
                        memory_type=MemoryType.FACT,
                        status=MemoryStatus.VERIFIED,
                        source=SourceType.SYSTEM_INFERRED,
                        source_detail="official_package_acceptance",
                        confidence=1.0,
                        verified=True,
                        tags=["installation-acceptance"],
                        project=project_id,
                        workspace=workspace,
                        scope=project_scope,
                        retention_policy=RetentionPolicy.EPHEMERAL,
                        injection_policy=InjectionPolicy.TRIGGERED,
                        trigger=[question],
                        summary="Disposable Elefante installation acceptance record.",
                        custom_metadata={
                            "title": "Disposable installation acceptance",
                            "summary": "Disposable Elefante installation acceptance record.",
                            "install_acceptance_schema_version": (
                                INSTALL_ACCEPTANCE_SCHEMA_VERSION
                            ),
                            "processing_status": "installation_acceptance",
                        },
                        system_metadata={
                            "install_acceptance": True,
                            "operation_id": operation_id,
                        },
                    ),
                )
                await self.vector_store.add_memory(acceptance_memory)
                stored = await self.vector_store.get_memory(acceptance_memory.id)
                record_written = bool(
                    stored is not None
                    and stored.content == content
                    and self._is_acceptance_memory(stored)
                )
                checks.append(
                    VerifiedOperationCheck(
                        "disposable_record_write",
                        record_written,
                        1,
                        (
                            "DISPOSABLE_RECORD_WRITE_OK"
                            if record_written
                            else "DISPOSABLE_RECORD_WRITE_FAILED"
                        ),
                    )
                )
                if record_written:
                    selected = {
                        str(value)
                        for value in await self.recall_selected_ids(
                            question,
                            project_id,
                            workspace,
                        )
                    }
                    recall_verified = str(acceptance_memory.id) in selected
                checks.append(
                    VerifiedOperationCheck(
                        "project_scoped_recall",
                        recall_verified,
                        1,
                        (
                            "PROJECT_SCOPED_RECALL_OK"
                            if recall_verified
                            else "PROJECT_SCOPED_RECALL_FAILED"
                        ),
                    )
                )
            except Exception:
                errors.append("INSTALL_ACCEPTANCE_EXECUTION_FAILED")
            finally:
                if acceptance_memory is not None:
                    try:
                        cleanup_verified = await self._remove_and_verify(
                            acceptance_memory.id
                        )
                    except Exception:
                        cleanup_verified = False
                else:
                    cleanup_verified = True
                checks.append(
                    VerifiedOperationCheck(
                        "disposable_record_cleanup",
                        cleanup_verified,
                        1,
                        (
                            "DISPOSABLE_RECORD_CLEANUP_OK"
                            if cleanup_verified
                            else "DISPOSABLE_RECORD_CLEANUP_FAILED"
                        ),
                    )
                )

        if not record_written:
            errors.append("INSTALL_ACCEPTANCE_RECORD_NOT_VERIFIED")
        if not recall_verified:
            errors.append("INSTALL_ACCEPTANCE_RECALL_NOT_VERIFIED")
        if not cleanup_verified:
            errors.append("INSTALL_ACCEPTANCE_CLEANUP_NOT_VERIFIED")
        errors = list(dict.fromkeys(errors))

        if stale_ok and record_written and recall_verified and cleanup_verified:
            status = VerifiedOperationStatus.VERIFIED_COMPLETE
            rollback = "verified_cleanup"
            recoverable = True
            next_action = "create_initial_backup"
        elif cleanup_verified:
            status = (
                VerifiedOperationStatus.FAILED_ROLLED_BACK
                if record_written
                else VerifiedOperationStatus.FAILED_NO_CHANGE
            )
            rollback = "verified_cleanup" if record_written else "not_required"
            recoverable = True
            next_action = "retry_installation_acceptance"
        else:
            status = VerifiedOperationStatus.NEEDS_HUMAN
            rollback = "incomplete"
            recoverable = False
            next_action = "create_support_report"

        receipt = InstallAcceptanceReceipt(
            schema_version=INSTALL_ACCEPTANCE_SCHEMA_VERSION,
            operation_id=operation_id,
            operation="installation_acceptance",
            status=status,
            started_at=started_at,
            finished_at=self.now().isoformat(),
            checks=tuple(checks),
            error_codes=tuple(errors),
            changed=False if cleanup_verified else record_written,
            rollback=rollback,
            recoverable=recoverable,
            next_action=next_action,
            stale_records_removed=stale_removed,
        )
        return InstallAcceptanceResult(status=status, receipt=receipt)


__all__ = [
    "INSTALL_ACCEPTANCE_CATEGORY",
    "INSTALL_ACCEPTANCE_CREATED_BY",
    "INSTALL_ACCEPTANCE_SCHEMA_VERSION",
    "InstallAcceptanceReceipt",
    "InstallAcceptanceResult",
    "InstallAcceptanceService",
]
