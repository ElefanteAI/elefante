"""Runtime integration for the consent-gated Session Intelligence ledger.

The dashboard remains snapshot-only and the daemon never creates the ledger as
a side effect of starting.  A user must first grant consent through the
operator CLI; only then can automatic MCP capture or the loopback usage endpoint
persist metadata-only events and refresh the redacted snapshot.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.session_intelligence.ledger import (
    DEFAULT_DB_PATH,
    PURPOSE_ENTERPRISE_TRAINING,
    ConsentRequiredError,
    InvocationEvent,
    SessionIntelligenceLedger,
)


SESSION_DB_ENV = "ELEFANTE_SESSION_INTELLIGENCE_DB"
SESSION_SNAPSHOT_ENV = "ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT"
DEFAULT_SNAPSHOT_NAME = "session_intelligence_snapshot.json"
DEFAULT_CAPTURE_PENDING_LIMIT = 64
_INGEST_LOCK = threading.Lock()


def configured_ledger_path() -> Path:
    """Return the explicit ledger path or the configured Elefante data path."""
    override = os.environ.get(SESSION_DB_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    try:
        from src.utils.config import get_config

        return (
            Path(get_config().elefante.data_dir).expanduser().resolve()
            / DEFAULT_DB_PATH.name
        )
    except Exception:
        return DEFAULT_DB_PATH.expanduser().resolve()


def configured_snapshot_path(ledger_path: Path | None = None) -> Path:
    """Return the explicit snapshot path or one beside the ledger."""
    override = os.environ.get(SESSION_SNAPSHOT_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    path = ledger_path or configured_ledger_path()
    return path.parent / DEFAULT_SNAPSHOT_NAME


def build_runtime_snapshot(ledger: SessionIntelligenceLedger) -> dict[str, Any]:
    """Build one metadata-only dashboard payload from the open ledger."""
    consent = ledger.consent_status()
    enabled = bool(consent.get("enabled"))
    purposes = set(consent.get("purposes") or [])
    signal_card = ledger.build_signal_card().to_dict() if enabled else None
    enterprise_report = None
    if enabled and PURPOSE_ENTERPRISE_TRAINING in purposes:
        enterprise_report = ledger.build_enterprise_report(group_by="tool").to_dict()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "consent": consent,
        "signal_card": signal_card,
        "enterprise_report": enterprise_report,
        "privacy": {
            "metadata_only": True,
            "prompts_stored": False,
            "transcripts_stored": False,
            "responses_stored": False,
            "employee_ranking": False,
            "sensitive_trait_inference": False,
        },
    }


def write_runtime_snapshot(
    ledger: SessionIntelligenceLedger,
    path: Path | None = None,
) -> Path:
    """Atomically replace the redacted dashboard snapshot with mode 0600."""
    target = (path or configured_snapshot_path()).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_runtime_snapshot(ledger)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=True, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def ingest_runtime_usage(
    event: InvocationEvent | Mapping[str, Any],
    *,
    ledger_path: Path | None = None,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Persist one consented usage event and refresh the safe snapshot."""
    path = (ledger_path or configured_ledger_path()).expanduser().resolve()
    if not path.is_file():
        raise ConsentRequiredError(
            "Session Intelligence is disabled; grant explicit consent before usage ingestion."
        )
    # Automatic capture and explicit HTTP ingress share this process. Serialize
    # their persist/build/replace sequence so an older snapshot cannot win a race.
    with _INGEST_LOCK, SessionIntelligenceLedger(path) as ledger:
        receipt = ledger.ingest_event(event)
        snapshot = write_runtime_snapshot(
            ledger,
            snapshot_path or configured_snapshot_path(path),
        )
        card = ledger.build_signal_card()
        return {
            "success": True,
            "receipt": receipt.to_dict(),
            "signal_card_id": card.card_id,
            "snapshot_refreshed": True,
            "snapshot_name": snapshot.name,
        }


class RuntimeUsageCapture:
    """Bounded, process-local writer for automatic MCP usage estimates.

    Submitting an event never opens or creates a ledger on the caller's path.
    An existing ledger is only a prerequisite; the worker rechecks its consent.
    Persistence runs on a serialized worker task so SQLite contention cannot
    delay the MCP response.
    """

    def __init__(
        self,
        *,
        ledger_path: Path | None = None,
        snapshot_path: Path | None = None,
        pending_limit: int = DEFAULT_CAPTURE_PENDING_LIMIT,
    ) -> None:
        if isinstance(pending_limit, bool) or not isinstance(pending_limit, int):
            raise ValueError("pending_limit must be a positive integer")
        if pending_limit < 1:
            raise ValueError("pending_limit must be a positive integer")
        self._ledger_path = ledger_path
        self._snapshot_path = snapshot_path
        self._pending_limit = pending_limit
        self._pending: set[asyncio.Task[None]] = set()
        self._write_lock = asyncio.Lock()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.accepted_count = 0
        self.persisted_count = 0
        self.failed_count = 0
        self.dropped_count = 0
        self.last_error_code: str | None = None

    def status(self) -> dict[str, Any]:
        """Return content-free process health; never open the usage ledger."""
        state = "observing" if self.accepted_count else "idle"
        if self.last_error_code == "ConsentRequiredError":
            state = "permission_required"
        elif self.failed_count or self.dropped_count:
            state = "partial"
        return {
            "state": state,
            "since": self.started_at,
            "pending_count": len(self._pending),
            "persisted_count": self.persisted_count,
            "failed_count": self.failed_count,
            "dropped_count": self.dropped_count,
            "last_error_code": self.last_error_code,
            "coverage": "MCP calls observed by this process; not complete host usage",
        }

    def submit(self, event: InvocationEvent) -> bool:
        """Queue one safe event only when a ledger already exists."""
        ledger_path = (self._ledger_path or configured_ledger_path()).expanduser().resolve()
        if not ledger_path.is_file():
            if self.accepted_count:
                self.last_error_code = "ConsentRequiredError"
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.dropped_count += 1
            self.last_error_code = "no_running_event_loop"
            return False
        if len(self._pending) >= self._pending_limit:
            self.dropped_count += 1
            self.last_error_code = "capture_capacity_exceeded"
            return False

        snapshot_path = self._snapshot_path or configured_snapshot_path(ledger_path)
        task = loop.create_task(self._persist(event, ledger_path, snapshot_path))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        self.accepted_count += 1
        return True

    async def _persist(
        self, event: InvocationEvent, ledger_path: Path, snapshot_path: Path
    ) -> None:
        try:
            async with self._write_lock:
                result = await asyncio.to_thread(
                    ingest_runtime_usage,
                    event,
                    ledger_path=ledger_path,
                    snapshot_path=snapshot_path,
                )
            if result["receipt"]["persisted"]:
                self.persisted_count += 1
            self.last_error_code = None
        except ConsentRequiredError:
            self.last_error_code = "ConsentRequiredError"
        except Exception as error:  # Telemetry must never alter the MCP result.
            self.failed_count += 1
            self.last_error_code = type(error).__name__

    async def close(self) -> None:
        """Drain accepted writes during normal server shutdown."""
        pending = tuple(self._pending)
        if not pending:
            return
        done, unfinished = await asyncio.wait(pending, timeout=6.0)
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
            self.dropped_count += len(unfinished)
            self.last_error_code = "capture_shutdown_timeout"
        if done:
            await asyncio.gather(*done, return_exceptions=True)


__all__ = [
    "DEFAULT_CAPTURE_PENDING_LIMIT",
    "DEFAULT_SNAPSHOT_NAME",
    "SESSION_DB_ENV",
    "SESSION_SNAPSHOT_ENV",
    "RuntimeUsageCapture",
    "build_runtime_snapshot",
    "configured_ledger_path",
    "configured_snapshot_path",
    "ingest_runtime_usage",
    "write_runtime_snapshot",
]
