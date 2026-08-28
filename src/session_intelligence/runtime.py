"""Runtime integration for the opt-in Session Intelligence ledger.

The dashboard remains snapshot-only and the daemon never creates the ledger as
a side effect of starting.  A user must first grant consent through the
operator CLI; only then can the loopback usage endpoint open the existing
ledger, persist a metadata-only event, and refresh the redacted snapshot.
"""

from __future__ import annotations

import json
import os
import tempfile
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
    with SessionIntelligenceLedger(path) as ledger:
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


__all__ = [
    "DEFAULT_SNAPSHOT_NAME",
    "SESSION_DB_ENV",
    "SESSION_SNAPSHOT_ENV",
    "build_runtime_snapshot",
    "configured_ledger_path",
    "configured_snapshot_path",
    "ingest_runtime_usage",
    "write_runtime_snapshot",
]
