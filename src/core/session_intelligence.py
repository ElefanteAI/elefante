"""Opt-in local evidence store for developer-value measurement.

Session Intelligence stores bounded workflow facts, never prompts, responses,
memory bodies, source diffs, or hidden reasoning.  Task Intelligence remains the
authority for task outcomes; this module owns local clocks, usage provenance,
retention, and user controls needed to join those outcomes into an explainable
value signal.

The store is deliberately not wired into the MCP server automatically.  A
caller must construct it with ``enabled=True`` for an explicitly consented
measurement purpose.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from src.core.task_intelligence_ledger import (
    TaskIntelligenceLedger,
    TaskIntelligenceLedgerError,
    canonical_digest,
)
from src.utils.config import get_config


SESSION_INTELLIGENCE_SCHEMA_VERSION = 1
INVOCATION_RETENTION_DAYS = 30
SESSION_RETENTION_DAYS = 90
RATE_CARD_RETENTION_DAYS = 365

MEASUREMENT_PURPOSES = {"developer-value-evaluation"}
CONSENT_SOURCES = {"user-directed", "operator-configured"}
WORKFLOW_CONDITIONS = {"control", "treatment"}
WORKFLOW_TERMINAL_STATES = {"accepted", "failed", "stopped", "unknown"}
WORKFLOW_EVENT_TYPES = {"retry", "correction", "rework"}
INVOCATION_STATUSES = {"success", "error", "ignored", "blocked"}
INVOCATION_KINDS = {"model-attempt", "elefante-call", "tool-call"}
USAGE_SOURCES = {
    "provider-actual",
    "host-actual",
    "local-estimated",
    "unknown",
}
USAGE_SCOPES = {"provider-workflow", "elefante-diagnostic"}
ACTIVE_TIME_SOURCES = {"host-actual", "user-timed"}
QUALITY_EVIDENCE_SOURCES = {"user", "host", "test", "causal-evaluator"}
CORE_QUALITY_FLOORS = {
    "correctness",
    "relevance",
    "decision_usefulness",
    "hallucination_control",
    "privacy",
    "authority",
}

_IDENTIFIER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class SessionIntelligenceError(ValueError):
    """A fail-closed schema, privacy, clock, provenance, or control error."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SessionIntelligenceError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise SessionIntelligenceError(f"{field} must be a UTC ISO-8601 timestamp")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise SessionIntelligenceError(
            f"{field} must be a UTC ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise SessionIntelligenceError(f"{field} must be a UTC ISO-8601 timestamp")
    return parsed


def _sha256(value: str, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise SessionIntelligenceError(f"{field} must be SHA-256")
    return value


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise SessionIntelligenceError(
            f"{field} must be a lowercase bounded identifier"
        )
    return value


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise SessionIntelligenceError(f"{field} must be a UUID") from error


def _non_negative_integer(value: Any, field: str, *, required: bool) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SessionIntelligenceError(f"{field} must be a non-negative integer")
    return value


def _json_identifiers(values: Iterable[str], field: str) -> str:
    normalized = sorted(dict.fromkeys(_identifier(value, field) for value in values))
    return json.dumps(normalized, separators=(",", ":"))


def _json_uuids(values: Iterable[str], field: str) -> str:
    normalized = sorted(dict.fromkeys(_uuid(value, field) for value in values))
    return json.dumps(normalized, separators=(",", ":"))


class SessionIntelligenceStore:
    """SQLite-backed, metadata-only developer-value evidence store."""

    _EXPECTED_TABLES = {
        "schema_migrations",
        "sessions",
        "task_value_contracts",
        "workflow_runs",
        "workflow_events",
        "rate_cards",
        "invocation_events",
    }

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        enabled: bool = False,
        read_only: bool = False,
        now: Callable[[], datetime] = _utc_now,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        clock_instance_id: str | None = None,
    ) -> None:
        if read_only and enabled:
            raise SessionIntelligenceError(
                "read-only Session Intelligence cannot also be enabled for writes"
            )
        if not read_only and enabled is not True:
            raise SessionIntelligenceError(
                "Session Intelligence persistence requires explicit enabled=True"
            )
        default_path = (
            Path(get_config().elefante.data_dir) / "session_intelligence.db"
        )
        self.path = Path(path or default_path)
        self._read_only = read_only
        if read_only:
            if not self.path.is_file():
                raise SessionIntelligenceError(
                    "read-only Session Intelligence database does not exist"
                )
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._now = now
        self._monotonic_ns = monotonic_ns
        self._clock_instance_id = clock_instance_id or uuid4().hex
        connection_target = (
            f"file:{self.path.resolve()}?mode=ro" if read_only else str(self.path)
        )
        self._connection = sqlite3.connect(
            connection_target,
            timeout=5,
            check_same_thread=False,
            uri=read_only,
        )
        self._connection.row_factory = sqlite3.Row
        try:
            if read_only:
                self._connection.execute("PRAGMA query_only=ON")
            else:
                self._initialize_schema()
            self._verify_schema()
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=5000")
            if not read_only:
                self._connection.execute("PRAGMA journal_mode=WAL")
                try:
                    os.chmod(self.path, 0o600)
                except OSError:
                    pass
                self.prune()
        except Exception:
            self._connection.close()
            raise

    def _require_writable(self) -> None:
        if self._read_only:
            raise SessionIntelligenceError(
                "Session Intelligence store is open read-only"
            )

    def _initialize_schema(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SESSION_INTELLIGENCE_SCHEMA_VERSION:
            raise SessionIntelligenceError(
                "Session Intelligence database uses a newer unsupported schema"
            )
        if version == SESSION_INTELLIGENCE_SCHEMA_VERSION:
            return
        existing_tables = {
            row[0]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        if version == 0 and existing_tables:
            raise SessionIntelligenceError(
                "Unversioned non-empty Session Intelligence database; refusing migration"
            )
        if version != 0:
            raise SessionIntelligenceError(
                f"No migration path from Session Intelligence schema {version}"
            )
        try:
            self._connection.executescript(
                """
                BEGIN IMMEDIATE;

                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at_utc TEXT NOT NULL
                );

                CREATE TABLE sessions (
                    session_id TEXT PRIMARY KEY,
                    client_name TEXT NOT NULL,
                    client_session_sha256 TEXT,
                    purpose TEXT NOT NULL,
                    consent_source TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    ended_at_utc TEXT,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE task_value_contracts (
                    contract_sha256 TEXT PRIMARY KEY,
                    contract_schema_version INTEGER NOT NULL,
                    goal_sha256 TEXT NOT NULL,
                    question_sha256 TEXT NOT NULL,
                    acceptance_rubric_sha256 TEXT NOT NULL,
                    task_class TEXT NOT NULL,
                    quality_floors_json TEXT NOT NULL,
                    value_units_json TEXT NOT NULL,
                    time_boundary_sha256 TEXT NOT NULL,
                    resource_boundary_sha256 TEXT NOT NULL,
                    preregistered_at_utc TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE workflow_runs (
                    workflow_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    comparison_id TEXT NOT NULL,
                    condition TEXT NOT NULL CHECK(condition IN ('control', 'treatment')),
                    task_value_contract_sha256 TEXT NOT NULL REFERENCES task_value_contracts(contract_sha256),
                    matched_context_sha256 TEXT NOT NULL,
                    task_trace_id TEXT,
                    task_trace_provenance_sha256 TEXT,
                    independently_arising INTEGER NOT NULL,
                    evidence_previously_consumed INTEGER NOT NULL,
                    memory_evidence_sha256 TEXT,
                    memory_created_at_utc TEXT,
                    task_observed_at_utc TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    started_monotonic_ns INTEGER NOT NULL,
                    clock_instance_id TEXT NOT NULL,
                    finished_at_utc TEXT,
                    workflow_elapsed_ms INTEGER,
                    workflow_clock_source TEXT,
                    active_developer_time_ms INTEGER,
                    active_time_source TEXT,
                    terminal_status TEXT,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE(comparison_id, condition)
                );

                CREATE TABLE workflow_events (
                    event_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL REFERENCES workflow_runs(workflow_id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL CHECK(event_type IN ('retry', 'correction', 'rework')),
                    evidence_source TEXT NOT NULL,
                    occurred_at_utc TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE rate_cards (
                    rate_card_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    effective_at_utc TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE invocation_events (
                    invocation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    workflow_id TEXT REFERENCES workflow_runs(workflow_id) ON DELETE CASCADE,
                    invocation_kind TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    finished_at_utc TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    duration_source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    provider TEXT,
                    model TEXT,
                    input_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    output_tokens INTEGER,
                    recall_context_tokens INTEGER,
                    usage_source TEXT NOT NULL,
                    usage_scope TEXT NOT NULL,
                    returned_memory_ids_json TEXT NOT NULL,
                    rate_card_id TEXT REFERENCES rate_cards(rate_card_id),
                    currency TEXT,
                    calculated_cost_micros INTEGER,
                    record_sha256 TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE INDEX idx_session_started ON sessions(started_at_utc);
                CREATE INDEX idx_workflow_comparison ON workflow_runs(comparison_id);
                CREATE INDEX idx_workflow_session ON workflow_runs(session_id);
                CREATE INDEX idx_workflow_event_workflow ON workflow_events(workflow_id);
                CREATE INDEX idx_invocation_workflow ON invocation_events(workflow_id);
                CREATE INDEX idx_invocation_finished ON invocation_events(finished_at_utc);

                """
            )
            self._connection.execute(
                "INSERT INTO schema_migrations(version, applied_at_utc) VALUES (?, ?)",
                (SESSION_INTELLIGENCE_SCHEMA_VERSION, _iso(self._now())),
            )
            self._connection.execute(
                f"PRAGMA user_version={SESSION_INTELLIGENCE_SCHEMA_VERSION}"
            )
            self._connection.commit()
        except Exception:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise

    def _verify_schema(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SESSION_INTELLIGENCE_SCHEMA_VERSION:
            raise SessionIntelligenceError(
                f"Session Intelligence schema mismatch: expected {SESSION_INTELLIGENCE_SCHEMA_VERSION}, got {version}"
            )
        tables = {
            row[0]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        missing = self._EXPECTED_TABLES - tables
        if missing:
            raise SessionIntelligenceError(
                f"Session Intelligence schema is incomplete: {sorted(missing)}"
            )
        integrity = self._connection.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok":
            raise SessionIntelligenceError(
                f"Session Intelligence integrity check failed: {integrity}"
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SessionIntelligenceStore":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _delete_unreferenced_contracts(self, contract_sha256s: Iterable[str]) -> int:
        deleted = 0
        for contract_sha256 in set(contract_sha256s):
            cursor = self._connection.execute(
                """
                DELETE FROM task_value_contracts
                WHERE contract_sha256 = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM workflow_runs
                      WHERE task_value_contract_sha256 = ?
                  )
                """,
                (contract_sha256, contract_sha256),
            )
            deleted += max(0, int(cursor.rowcount))
        return deleted

    def prune(self, *, now: datetime | None = None) -> dict[str, int]:
        self._require_writable()
        current = now or self._now()
        invocation_cutoff = _iso(current - timedelta(days=INVOCATION_RETENTION_DAYS))
        session_cutoff = _iso(current - timedelta(days=SESSION_RETENTION_DAYS))
        rate_cutoff = _iso(current - timedelta(days=RATE_CARD_RETENTION_DAYS))
        with self._lock, self._connection:
            expiring_contracts = [
                row[0]
                for row in self._connection.execute(
                    """
                    SELECT DISTINCT w.task_value_contract_sha256
                    FROM workflow_runs AS w
                    JOIN sessions AS s ON s.session_id = w.session_id
                    WHERE COALESCE(s.ended_at_utc, s.started_at_utc) < ?
                    """,
                    (session_cutoff,),
                ).fetchall()
            ]
            invocation_cursor = self._connection.execute(
                "DELETE FROM invocation_events WHERE finished_at_utc < ?",
                (invocation_cutoff,),
            )
            session_cursor = self._connection.execute(
                """
                DELETE FROM sessions
                WHERE COALESCE(ended_at_utc, started_at_utc) < ?
                """,
                (session_cutoff,),
            )
            rate_cursor = self._connection.execute(
                """
                DELETE FROM rate_cards
                WHERE effective_at_utc < ?
                  AND rate_card_id NOT IN (
                      SELECT DISTINCT rate_card_id FROM invocation_events
                      WHERE rate_card_id IS NOT NULL
                  )
                """,
                (rate_cutoff,),
            )
            contract_count = self._delete_unreferenced_contracts(
                expiring_contracts
            )
            stale_contract_cursor = self._connection.execute(
                """
                DELETE FROM task_value_contracts
                WHERE created_at_utc < ?
                  AND NOT EXISTS (
                      SELECT 1 FROM workflow_runs
                      WHERE workflow_runs.task_value_contract_sha256 =
                            task_value_contracts.contract_sha256
                  )
                """,
                (session_cutoff,),
            )
            contract_count += max(0, int(stale_contract_cursor.rowcount))
        return {
            "invocation_events": max(0, int(invocation_cursor.rowcount)),
            "sessions": max(0, int(session_cursor.rowcount)),
            "rate_cards": max(0, int(rate_cursor.rowcount)),
            "task_value_contracts": contract_count,
        }

    def create_session(
        self,
        *,
        client_name: str,
        purpose: str,
        consent_source: str,
        client_session_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, str]:
        self._require_writable()
        client = _identifier(client_name, "client_name")
        if purpose not in MEASUREMENT_PURPOSES:
            raise SessionIntelligenceError("unsupported Session Intelligence purpose")
        if consent_source not in CONSENT_SOURCES:
            raise SessionIntelligenceError("unsupported consent source")
        created = now or self._now()
        session_id = str(uuid4())
        client_session_sha256 = (
            hashlib.sha256(client_session_id.encode("utf-8")).hexdigest()
            if client_session_id
            else None
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO sessions (
                    session_id, client_name, client_session_sha256, purpose,
                    consent_source, started_at_utc, ended_at_utc, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    session_id,
                    client,
                    client_session_sha256,
                    purpose,
                    consent_source,
                    _iso(created),
                    _iso(created),
                ),
            )
        return {"session_id": session_id, "started_at_utc": _iso(created)}

    def end_session(
        self, session_id: str, *, now: datetime | None = None
    ) -> dict[str, str]:
        self._require_writable()
        normalized = _uuid(session_id, "session_id")
        ended = now or self._now()
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT ended_at_utc FROM sessions WHERE session_id = ?",
                (normalized,),
            ).fetchone()
            if row is None:
                raise SessionIntelligenceError("unknown Session Intelligence session")
            if row["ended_at_utc"] is not None:
                return {"session_id": normalized, "ended_at_utc": row["ended_at_utc"]}
            open_workflows = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM workflow_runs WHERE session_id = ? AND finished_at_utc IS NULL",
                    (normalized,),
                ).fetchone()[0]
            )
            if open_workflows:
                raise SessionIntelligenceError(
                    "session has unfinished workflows; finish or delete them first"
                )
            self._connection.execute(
                "UPDATE sessions SET ended_at_utc = ? WHERE session_id = ?",
                (_iso(ended), normalized),
            )
        return {"session_id": normalized, "ended_at_utc": _iso(ended)}

    def register_task_value_contract(
        self,
        *,
        goal_sha256: str,
        question_sha256: str,
        acceptance_rubric_sha256: str,
        task_class: str,
        quality_floors: list[str],
        value_units: list[dict[str, Any]],
        time_boundary_sha256: str,
        resource_boundary_sha256: str,
        preregistered_at_utc: str,
        now: datetime | None = None,
    ) -> str:
        self._require_writable()
        normalized_floors = sorted(
            dict.fromkeys(_identifier(value, "quality_floor") for value in quality_floors)
        )
        missing_floors = CORE_QUALITY_FLOORS - set(normalized_floors)
        if missing_floors:
            raise SessionIntelligenceError(
                f"task-value contract is missing hard quality floors: {sorted(missing_floors)}"
            )
        if not value_units:
            raise SessionIntelligenceError("task-value contract requires value units")
        normalized_units: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for unit in value_units:
            if set(unit) != {"id", "weight", "criterion_sha256", "evidence_source"}:
                raise SessionIntelligenceError(
                    "value units require id, weight, criterion_sha256, and evidence_source"
                )
            unit_id = _identifier(unit["id"], "value_unit.id")
            if unit_id in seen_ids:
                raise SessionIntelligenceError("value unit IDs must be unique")
            seen_ids.add(unit_id)
            weight = unit["weight"]
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise SessionIntelligenceError("value_unit.weight must be numeric")
            if not math.isfinite(float(weight)) or float(weight) <= 0:
                raise SessionIntelligenceError("value_unit.weight must be positive")
            source = unit["evidence_source"]
            if source not in QUALITY_EVIDENCE_SOURCES:
                raise SessionIntelligenceError(
                    "value_unit.evidence_source is unsupported"
                )
            normalized_units.append(
                {
                    "criterion_sha256": _sha256(
                        unit["criterion_sha256"], "value_unit.criterion_sha256"
                    ),
                    "evidence_source": source,
                    "id": unit_id,
                    "weight": float(weight),
                }
            )
        preregistered = _parse_utc(preregistered_at_utc, "preregistered_at_utc")
        contract = {
            "contract_schema_version": 1,
            "goal_sha256": _sha256(goal_sha256, "goal_sha256"),
            "question_sha256": _sha256(question_sha256, "question_sha256"),
            "acceptance_rubric_sha256": _sha256(
                acceptance_rubric_sha256, "acceptance_rubric_sha256"
            ),
            "task_class": _identifier(task_class, "task_class"),
            "quality_floors": normalized_floors,
            "value_units": sorted(normalized_units, key=lambda item: item["id"]),
            "time_boundary_sha256": _sha256(
                time_boundary_sha256, "time_boundary_sha256"
            ),
            "resource_boundary_sha256": _sha256(
                resource_boundary_sha256, "resource_boundary_sha256"
            ),
            "preregistered_at_utc": _iso(preregistered),
        }
        digest = canonical_digest(contract)
        created = now or self._now()
        values = (
            digest,
            contract["contract_schema_version"],
            contract["goal_sha256"],
            contract["question_sha256"],
            contract["acceptance_rubric_sha256"],
            contract["task_class"],
            json.dumps(contract["quality_floors"], separators=(",", ":")),
            json.dumps(contract["value_units"], sort_keys=True, separators=(",", ":")),
            contract["time_boundary_sha256"],
            contract["resource_boundary_sha256"],
            contract["preregistered_at_utc"],
            _iso(created),
        )
        with self._lock, self._connection:
            prior = self._connection.execute(
                "SELECT * FROM task_value_contracts WHERE contract_sha256 = ?",
                (digest,),
            ).fetchone()
            if prior is None:
                self._connection.execute(
                    "INSERT INTO task_value_contracts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
        return digest

    def start_workflow(
        self,
        *,
        session_id: str,
        comparison_id: str,
        condition: str,
        task_value_contract_sha256: str,
        matched_context_sha256: str,
        task_observed_at_utc: str,
        independently_arising: bool,
        evidence_previously_consumed: bool,
        task_trace_id: str | None = None,
        task_trace_provenance_sha256: str | None = None,
        memory_evidence_sha256: str | None = None,
        memory_created_at_utc: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, str]:
        self._require_writable()
        session = _uuid(session_id, "session_id")
        comparison = _uuid(comparison_id, "comparison_id")
        if condition not in WORKFLOW_CONDITIONS:
            raise SessionIntelligenceError("condition must be control or treatment")
        contract_sha = _sha256(
            task_value_contract_sha256, "task_value_contract_sha256"
        )
        matched_sha = _sha256(matched_context_sha256, "matched_context_sha256")
        trace_id = _uuid(task_trace_id, "task_trace_id") if task_trace_id else None
        trace_provenance_sha = (
            _sha256(
                task_trace_provenance_sha256,
                "task_trace_provenance_sha256",
            )
            if task_trace_provenance_sha256
            else None
        )
        if (trace_id is None) != (trace_provenance_sha is None):
            raise SessionIntelligenceError(
                "task trace ID and provenance digest must be supplied together"
            )
        task_observed = _parse_utc(task_observed_at_utc, "task_observed_at_utc")
        memory_created = (
            _parse_utc(memory_created_at_utc, "memory_created_at_utc")
            if memory_created_at_utc
            else None
        )
        memory_sha = (
            _sha256(memory_evidence_sha256, "memory_evidence_sha256")
            if memory_evidence_sha256
            else None
        )
        if (memory_created is None) != (memory_sha is None):
            raise SessionIntelligenceError(
                "memory evidence hash and creation time must be supplied together"
            )
        if memory_created is not None and memory_created >= task_observed:
            raise SessionIntelligenceError("eligible memory must predate the task")
        started = now or self._now()
        started_monotonic_ns = int(self._monotonic_ns())
        with self._lock, self._connection:
            session_row = self._connection.execute(
                "SELECT ended_at_utc FROM sessions WHERE session_id = ?", (session,)
            ).fetchone()
            if session_row is None:
                raise SessionIntelligenceError("unknown Session Intelligence session")
            if session_row["ended_at_utc"] is not None:
                raise SessionIntelligenceError("cannot start a workflow in an ended session")
            contract_row = self._connection.execute(
                "SELECT preregistered_at_utc FROM task_value_contracts WHERE contract_sha256 = ?",
                (contract_sha,),
            ).fetchone()
            if contract_row is None:
                raise SessionIntelligenceError("unknown task-value contract")
            preregistered = _parse_utc(
                contract_row["preregistered_at_utc"], "preregistered_at_utc"
            )
            # The task must arise independently before its rubric is frozen;
            # preregistration still has to happen before either arm starts.
            if task_observed > preregistered:
                raise SessionIntelligenceError(
                    "preregistration cannot precede natural task observation"
                )
            if preregistered >= started:
                raise SessionIntelligenceError(
                    "preregistration must precede workflow start"
                )
            workflow_id = str(uuid4())
            self._connection.execute(
                """
                INSERT INTO workflow_runs (
                    workflow_id, session_id, comparison_id, condition,
                    task_value_contract_sha256, matched_context_sha256,
                    task_trace_id, task_trace_provenance_sha256,
                    independently_arising,
                    evidence_previously_consumed, memory_evidence_sha256,
                    memory_created_at_utc, task_observed_at_utc, started_at_utc,
                    started_monotonic_ns, clock_instance_id, finished_at_utc,
                    workflow_elapsed_ms, workflow_clock_source,
                    active_developer_time_ms, active_time_source,
                    terminal_status, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?)
                """,
                (
                    workflow_id,
                    session,
                    comparison,
                    condition,
                    contract_sha,
                    matched_sha,
                    trace_id,
                    trace_provenance_sha,
                    int(independently_arising is True),
                    int(evidence_previously_consumed is True),
                    memory_sha,
                    _iso(memory_created) if memory_created else None,
                    _iso(task_observed),
                    _iso(started),
                    started_monotonic_ns,
                    self._clock_instance_id,
                    _iso(started),
                ),
            )
        return {"workflow_id": workflow_id, "started_at_utc": _iso(started)}

    def append_workflow_event(
        self,
        *,
        workflow_id: str,
        event_type: str,
        evidence_source: str,
        occurred_at_utc: datetime | None = None,
    ) -> str:
        self._require_writable()
        workflow = _uuid(workflow_id, "workflow_id")
        if event_type not in WORKFLOW_EVENT_TYPES:
            raise SessionIntelligenceError("unsupported workflow event type")
        if evidence_source not in QUALITY_EVIDENCE_SOURCES:
            raise SessionIntelligenceError("unsupported workflow event evidence source")
        occurred = occurred_at_utc or self._now()
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT finished_at_utc FROM workflow_runs WHERE workflow_id = ?",
                (workflow,),
            ).fetchone()
            if row is None:
                raise SessionIntelligenceError("unknown workflow")
            if row["finished_at_utc"] is not None:
                raise SessionIntelligenceError("cannot append to a finished workflow")
            event_id = str(uuid4())
            self._connection.execute(
                "INSERT INTO workflow_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    workflow,
                    event_type,
                    evidence_source,
                    _iso(occurred),
                    _iso(self._now()),
                ),
            )
        return event_id

    def add_rate_card(
        self,
        *,
        rate_card_id: str,
        provider: str,
        model: str,
        currency: str,
        effective_at_utc: str,
        source_sha256: str,
        now: datetime | None = None,
    ) -> None:
        self._require_writable()
        card_id = _identifier(rate_card_id, "rate_card_id")
        provider_id = _identifier(provider, "provider")
        model_id = _identifier(model, "model")
        currency_id = currency.upper() if isinstance(currency, str) else ""
        if re.fullmatch(r"[A-Z]{3}", currency_id) is None:
            raise SessionIntelligenceError("currency must be a three-letter code")
        effective = _parse_utc(effective_at_utc, "effective_at_utc")
        source = _sha256(source_sha256, "source_sha256")
        values = (
            card_id,
            provider_id,
            model_id,
            currency_id,
            _iso(effective),
            source,
            _iso(now or self._now()),
        )
        with self._lock, self._connection:
            prior = self._connection.execute(
                "SELECT * FROM rate_cards WHERE rate_card_id = ?", (card_id,)
            ).fetchone()
            if prior is not None and tuple(prior)[:6] != values[:6]:
                raise SessionIntelligenceError(
                    "rate-card identifier already exists with different provenance"
                )
            if prior is None:
                self._connection.execute(
                    "INSERT INTO rate_cards VALUES (?, ?, ?, ?, ?, ?, ?)", values
                )

    def append_invocation(
        self,
        *,
        invocation_id: str | None = None,
        session_id: str,
        workflow_id: str | None,
        invocation_kind: str,
        client_name: str,
        tool_name: str,
        started_at_utc: datetime,
        finished_at_utc: datetime,
        started_monotonic_ns: int,
        finished_monotonic_ns: int,
        status: str,
        result_count: int,
        usage_source: str,
        usage_scope: str,
        input_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        output_tokens: int | None = None,
        recall_context_tokens: int | None = None,
        returned_memory_ids: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        rate_card_id: str | None = None,
        currency: str | None = None,
        calculated_cost_micros: int | None = None,
    ) -> dict[str, Any]:
        self._require_writable()
        normalized_invocation_id = (
            _uuid(invocation_id, "invocation_id")
            if invocation_id is not None
            else str(uuid4())
        )
        session = _uuid(session_id, "session_id")
        workflow = _uuid(workflow_id, "workflow_id") if workflow_id else None
        if invocation_kind not in INVOCATION_KINDS:
            raise SessionIntelligenceError("unsupported invocation kind")
        client = _identifier(client_name, "client_name")
        tool = _identifier(tool_name, "tool_name")
        if status not in INVOCATION_STATUSES:
            raise SessionIntelligenceError("unsupported invocation status")
        if usage_source not in USAGE_SOURCES:
            raise SessionIntelligenceError("unsupported usage source")
        if usage_scope not in USAGE_SCOPES:
            raise SessionIntelligenceError("unsupported usage scope")
        result_total = _non_negative_integer(result_count, "result_count", required=True)
        if (
            isinstance(started_monotonic_ns, bool)
            or not isinstance(started_monotonic_ns, int)
            or isinstance(finished_monotonic_ns, bool)
            or not isinstance(finished_monotonic_ns, int)
            or finished_monotonic_ns <= started_monotonic_ns
        ):
            raise SessionIntelligenceError(
                "invocation duration requires increasing monotonic clock values"
            )
        duration_ms = max(1, (finished_monotonic_ns - started_monotonic_ns) // 1_000_000)
        if finished_at_utc < started_at_utc:
            raise SessionIntelligenceError("invocation finish precedes start")
        input_count = _non_negative_integer(
            input_tokens, "input_tokens", required=usage_source != "unknown"
        )
        cached_count = _non_negative_integer(
            cached_input_tokens,
            "cached_input_tokens",
            required=usage_source != "unknown",
        )
        output_count = _non_negative_integer(
            output_tokens, "output_tokens", required=usage_source != "unknown"
        )
        recall_count = _non_negative_integer(
            recall_context_tokens,
            "recall_context_tokens",
            required=usage_source != "unknown",
        )
        if usage_source == "unknown" and any(
            value is not None
            for value in (
                input_tokens,
                cached_input_tokens,
                output_tokens,
                recall_context_tokens,
            )
        ):
            raise SessionIntelligenceError("unknown usage cannot carry token counts")
        if input_count is not None:
            if cached_count is not None and cached_count > input_count:
                raise SessionIntelligenceError(
                    "cached_input_tokens cannot exceed input_tokens"
                )
            if (
                recall_count is not None
                and usage_scope == "provider-workflow"
                and recall_count > input_count
            ):
                raise SessionIntelligenceError(
                    "recall_context_tokens cannot exceed provider input_tokens"
                )
            if (
                recall_count is not None
                and usage_scope == "elefante-diagnostic"
                and recall_count > int(output_count or 0)
            ):
                raise SessionIntelligenceError(
                    "diagnostic recall_context_tokens cannot exceed output_tokens"
                )
            if input_count + int(output_count or 0) <= 0:
                raise SessionIntelligenceError(
                    "input_tokens plus output_tokens must be positive"
                )
        provider_id = _identifier(provider, "provider") if provider else None
        model_id = _identifier(model, "model") if model else None
        if usage_source == "provider-actual" and (not provider_id or not model_id):
            raise SessionIntelligenceError(
                "provider-actual usage requires provider and model"
            )
        memory_ids_json = _json_uuids(
            returned_memory_ids or [], "returned_memory_id"
        )
        card_id = _identifier(rate_card_id, "rate_card_id") if rate_card_id else None
        cost = _non_negative_integer(
            calculated_cost_micros,
            "calculated_cost_micros",
            required=card_id is not None,
        )
        currency_id = currency.upper() if isinstance(currency, str) else None
        if card_id is None and (currency is not None or calculated_cost_micros is not None):
            raise SessionIntelligenceError(
                "cost requires a rate-card identifier and provenance"
            )
        if card_id is not None and usage_source != "provider-actual":
            raise SessionIntelligenceError("cost requires provider-actual usage")
        record_payload = {
            "invocation_id": normalized_invocation_id,
            "session_id": session,
            "workflow_id": workflow,
            "invocation_kind": invocation_kind,
            "client_name": client,
            "tool_name": tool,
            "started_at_utc": _iso(started_at_utc),
            "finished_at_utc": _iso(finished_at_utc),
            "duration_ms": duration_ms,
            "duration_source": "monotonic-clock",
            "status": status,
            "result_count": result_total,
            "provider": provider_id,
            "model": model_id,
            "input_tokens": input_count,
            "cached_input_tokens": cached_count,
            "output_tokens": output_count,
            "recall_context_tokens": recall_count,
            "usage_source": usage_source,
            "usage_scope": usage_scope,
            "returned_memory_ids": json.loads(memory_ids_json),
            "rate_card_id": card_id,
            "currency": currency_id,
            "calculated_cost_micros": cost,
        }
        record_sha256 = canonical_digest(record_payload)
        with self._lock, self._connection:
            prior_invocation = self._connection.execute(
                "SELECT record_sha256 FROM invocation_events WHERE invocation_id = ?",
                (normalized_invocation_id,),
            ).fetchone()
            if prior_invocation is not None:
                if prior_invocation["record_sha256"] != record_sha256:
                    raise SessionIntelligenceError(
                        "invocation ID already exists with different evidence"
                    )
                return {
                    "invocation_id": normalized_invocation_id,
                    "duplicate": True,
                    "duration_ms": duration_ms,
                }
            session_row = self._connection.execute(
                "SELECT client_name, ended_at_utc FROM sessions WHERE session_id = ?",
                (session,),
            ).fetchone()
            if session_row is None:
                raise SessionIntelligenceError("unknown Session Intelligence session")
            if session_row["client_name"] != client:
                raise SessionIntelligenceError("invocation client differs from session")
            if session_row["ended_at_utc"] is not None:
                raise SessionIntelligenceError("cannot append to an ended session")
            if workflow is not None:
                workflow_row = self._connection.execute(
                    "SELECT session_id, finished_at_utc FROM workflow_runs WHERE workflow_id = ?",
                    (workflow,),
                ).fetchone()
                if workflow_row is None or workflow_row["session_id"] != session:
                    raise SessionIntelligenceError(
                        "invocation workflow does not belong to the session"
                    )
                if workflow_row["finished_at_utc"] is not None:
                    raise SessionIntelligenceError(
                        "cannot append to a finished workflow"
                    )
            if card_id is not None:
                rate_row = self._connection.execute(
                    "SELECT provider, model, currency FROM rate_cards WHERE rate_card_id = ?",
                    (card_id,),
                ).fetchone()
                if rate_row is None:
                    raise SessionIntelligenceError("unknown rate card")
                if (rate_row["provider"], rate_row["model"], rate_row["currency"]) != (
                    provider_id,
                    model_id,
                    currency_id,
                ):
                    raise SessionIntelligenceError(
                        "rate-card provenance does not match invocation usage"
                    )
            self._connection.execute(
                """
                INSERT INTO invocation_events VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    normalized_invocation_id,
                    session,
                    workflow,
                    invocation_kind,
                    client,
                    tool,
                    _iso(started_at_utc),
                    _iso(finished_at_utc),
                    duration_ms,
                    "monotonic-clock",
                    status,
                    result_total,
                    provider_id,
                    model_id,
                    input_count,
                    cached_count,
                    output_count,
                    recall_count,
                    usage_source,
                    usage_scope,
                    memory_ids_json,
                    card_id,
                    currency_id,
                    cost,
                    record_sha256,
                    _iso(self._now()),
                ),
            )
        return {
            "invocation_id": normalized_invocation_id,
            "duplicate": False,
            "duration_ms": duration_ms,
        }

    def finish_workflow(
        self,
        workflow_id: str,
        *,
        terminal_status: str,
        active_developer_time_ms: int | None = None,
        active_time_source: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._require_writable()
        workflow = _uuid(workflow_id, "workflow_id")
        if terminal_status not in WORKFLOW_TERMINAL_STATES:
            raise SessionIntelligenceError("unsupported workflow terminal status")
        active_time = _non_negative_integer(
            active_developer_time_ms,
            "active_developer_time_ms",
            required=active_time_source is not None,
        )
        if (active_time is None) != (active_time_source is None):
            raise SessionIntelligenceError(
                "active developer time and its source must be supplied together"
            )
        if active_time_source is not None and active_time_source not in ACTIVE_TIME_SOURCES:
            raise SessionIntelligenceError("unsupported active developer time source")
        finished = now or self._now()
        finished_monotonic_ns = int(self._monotonic_ns())
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM workflow_runs WHERE workflow_id = ?", (workflow,)
            ).fetchone()
            if row is None:
                raise SessionIntelligenceError("unknown workflow")
            if row["finished_at_utc"] is not None:
                return self.inspect_workflow(workflow)
            if row["clock_instance_id"] != self._clock_instance_id:
                raise SessionIntelligenceError(
                    "workflow clock owner changed; elapsed time is unknown"
                )
            if finished_monotonic_ns <= int(row["started_monotonic_ns"]):
                raise SessionIntelligenceError(
                    "workflow finish requires an increasing monotonic clock"
                )
            elapsed_ms = max(
                1,
                (finished_monotonic_ns - int(row["started_monotonic_ns"]))
                // 1_000_000,
            )
            self._connection.execute(
                """
                UPDATE workflow_runs
                SET finished_at_utc = ?, workflow_elapsed_ms = ?,
                    workflow_clock_source = 'monotonic-clock',
                    active_developer_time_ms = ?, active_time_source = ?,
                    terminal_status = ?
                WHERE workflow_id = ?
                """,
                (
                    _iso(finished),
                    elapsed_ms,
                    active_time,
                    active_time_source,
                    terminal_status,
                    workflow,
                ),
            )
        return self.inspect_workflow(workflow)

    def inspect_workflow(self, workflow_id: str) -> dict[str, Any]:
        workflow = _uuid(workflow_id, "workflow_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM workflow_runs WHERE workflow_id = ?", (workflow,)
            ).fetchone()
            if row is None:
                raise SessionIntelligenceError("unknown workflow")
            events = self._connection.execute(
                """
                SELECT event_id, event_type, evidence_source, occurred_at_utc
                FROM workflow_events
                WHERE workflow_id = ? ORDER BY occurred_at_utc, event_id
                """,
                (workflow,),
            ).fetchall()
            invocations = self._connection.execute(
                """
                SELECT invocation_id, invocation_kind, client_name, tool_name,
                       started_at_utc, finished_at_utc, duration_ms,
                       duration_source, status, result_count, provider, model,
                       input_tokens, cached_input_tokens, output_tokens,
                       recall_context_tokens, usage_source, usage_scope,
                       returned_memory_ids_json, rate_card_id, currency,
                       calculated_cost_micros, record_sha256
                FROM invocation_events
                WHERE workflow_id = ? ORDER BY started_at_utc, invocation_id
                """,
                (workflow,),
            ).fetchall()
            contract = self._connection.execute(
                "SELECT * FROM task_value_contracts WHERE contract_sha256 = ?",
                (row["task_value_contract_sha256"],),
            ).fetchone()
        result = dict(row)
        result.pop("started_monotonic_ns", None)
        result.pop("clock_instance_id", None)
        result["independently_arising"] = bool(result["independently_arising"])
        result["evidence_previously_consumed"] = bool(
            result["evidence_previously_consumed"]
        )
        result["workflow_events"] = [dict(item) for item in events]
        result["event_counts"] = {
            event_type: sum(item["event_type"] == event_type for item in events)
            for event_type in sorted(WORKFLOW_EVENT_TYPES)
        }
        result["invocations"] = []
        for item in invocations:
            invocation = dict(item)
            invocation["returned_memory_ids"] = json.loads(
                invocation.pop("returned_memory_ids_json")
            )
            result["invocations"].append(invocation)
        contract_result = dict(contract) if contract is not None else None
        if contract_result is not None:
            contract_result["quality_floors"] = json.loads(
                contract_result.pop("quality_floors_json")
            )
            contract_result["value_units"] = json.loads(
                contract_result.pop("value_units_json")
            )
        result["task_value_contract"] = contract_result
        return result

    def comparison_workflows(self, comparison_id: str) -> list[dict[str, Any]]:
        comparison = _uuid(comparison_id, "comparison_id")
        with self._lock:
            rows = self._connection.execute(
                "SELECT workflow_id FROM workflow_runs WHERE comparison_id = ? ORDER BY condition",
                (comparison,),
            ).fetchall()
        return [self.inspect_workflow(row["workflow_id"]) for row in rows]

    def export_snapshot(self) -> dict[str, Any]:
        """Return a metadata-only local export; the caller chooses a file path."""
        with self._lock:
            sessions = [
                dict(row)
                for row in self._connection.execute(
                    "SELECT * FROM sessions ORDER BY started_at_utc, session_id"
                ).fetchall()
            ]
            workflow_ids = [
                row[0]
                for row in self._connection.execute(
                    "SELECT workflow_id FROM workflow_runs ORDER BY started_at_utc, workflow_id"
                ).fetchall()
            ]
            rate_cards = [
                dict(row)
                for row in self._connection.execute(
                    "SELECT * FROM rate_cards ORDER BY effective_at_utc, rate_card_id"
                ).fetchall()
            ]
        return {
            "schema_version": SESSION_INTELLIGENCE_SCHEMA_VERSION,
            "generated_at_utc": _iso(self._now()),
            "sessions": sessions,
            "workflows": [self.inspect_workflow(value) for value in workflow_ids],
            "rate_cards": rate_cards,
            "raw_transcripts_stored": False,
            "remote_telemetry": False,
        }

    def delete_session(self, session_id: str, *, confirm: str) -> bool:
        self._require_writable()
        session = _uuid(session_id, "session_id")
        if confirm != f"DELETE {session}":
            raise SessionIntelligenceError(
                "session deletion requires the exact confirmation phrase"
            )
        with self._lock, self._connection:
            contract_sha256s = [
                row[0]
                for row in self._connection.execute(
                    """
                    SELECT DISTINCT task_value_contract_sha256
                    FROM workflow_runs WHERE session_id = ?
                    """,
                    (session,),
                ).fetchall()
            ]
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session,)
            )
            self._delete_unreferenced_contracts(contract_sha256s)
        return int(cursor.rowcount) == 1

    def delete_workflow(self, workflow_id: str, *, confirm: str) -> bool:
        self._require_writable()
        workflow = _uuid(workflow_id, "workflow_id")
        if confirm != f"DELETE {workflow}":
            raise SessionIntelligenceError(
                "workflow deletion requires the exact confirmation phrase"
            )
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT task_value_contract_sha256 FROM workflow_runs
                WHERE workflow_id = ?
                """,
                (workflow,),
            ).fetchone()
            cursor = self._connection.execute(
                "DELETE FROM workflow_runs WHERE workflow_id = ?", (workflow,)
            )
            if row is not None:
                self._delete_unreferenced_contracts(
                    [row["task_value_contract_sha256"]]
                )
        return int(cursor.rowcount) == 1

    def reset(self, *, confirm: str) -> dict[str, int]:
        self._require_writable()
        if confirm != "DELETE SESSION INTELLIGENCE":
            raise SessionIntelligenceError(
                "reset requires the exact confirmation phrase"
            )
        with self._lock, self._connection:
            counts = {
                table: int(
                    self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in (
                    "sessions",
                    "task_value_contracts",
                    "rate_cards",
                )
            }
            self._connection.execute("DELETE FROM sessions")
            self._connection.execute("DELETE FROM task_value_contracts")
            self._connection.execute("DELETE FROM rate_cards")
        return counts


def build_value_baseline_card(store: SessionIntelligenceStore) -> dict[str, Any]:
    """Derive an honest first-use card without fabricating savings or lift."""
    snapshot = store.export_snapshot()
    workflows = snapshot["workflows"]
    completed = [item for item in workflows if item["finished_at_utc"] is not None]
    comparisons: dict[str, set[str]] = {}
    for workflow in completed:
        comparisons.setdefault(workflow["comparison_id"], set()).add(
            workflow["condition"]
        )
    complete_pairs = sum(
        conditions == WORKFLOW_CONDITIONS for conditions in comparisons.values()
    )
    return {
        "signal_card_schema_version": 1,
        "card_type": "value-baseline",
        "evidence_status": "pending" if complete_pairs == 0 else "local-only",
        "known": {
            "registered_value_contracts": len(
                {
                    workflow["task_value_contract_sha256"]
                    for workflow in workflows
                }
            ),
            "recorded_workflows": len(workflows),
            "complete_matched_pairs": complete_pairs,
            "local_first": True,
            "raw_transcripts_stored": False,
        },
        "unknowns": (
            [
                "accepted-value effect",
                "complete workflow-time effect",
                "provider-actual token effect",
                "representative product lift",
            ]
            if complete_pairs == 0
            else ["representative product lift"]
        ),
        "next_evidence": (
            "Pre-register and complete one eligible matched control/treatment pair."
            if complete_pairs == 0
            else "Review the local pair card and repeat on independent natural tasks."
        ),
        "public_claim_authorized": False,
        "persisted": False,
    }


def _workflow_arm(
    workflow: dict[str, Any],
    *,
    task_ledger: TaskIntelligenceLedger,
) -> dict[str, Any]:
    blockers: list[str] = []
    contract = workflow["task_value_contract"]
    trace_id = workflow.get("task_trace_id")
    trace: dict[str, Any] | None = None
    if not trace_id:
        blockers.append("missing-task-trace-reference")
    elif not workflow.get("task_trace_provenance_sha256"):
        blockers.append("missing-task-trace-provenance")
    else:
        try:
            trace = task_ledger.inspect_reference(
                trace_id,
                expected_provenance_sha256=workflow[
                    "task_trace_provenance_sha256"
                ],
                expected_task_sha256=contract["question_sha256"],
                expected_criteria_sha256=contract[
                    "acceptance_rubric_sha256"
                ],
            )
        except TaskIntelligenceLedgerError:
            blockers.append("task-trace-unavailable-or-binding-mismatch")

    quality_floor_ids = set(contract["quality_floors"])
    value_units = {item["id"]: item for item in contract["value_units"]}
    outcome = trace.get("outcome") if trace is not None else None
    if outcome is None:
        blockers.append("missing-task-intelligence-outcome")
    elif outcome.get("retracted"):
        blockers.append("task-intelligence-outcome-retracted")
    elif outcome.get("task_value_contract_sha256") != workflow[
        "task_value_contract_sha256"
    ]:
        blockers.append("task-value-contract-mismatch")

    quality_results = (
        outcome.get("quality_floor_results") if outcome is not None else None
    )
    value_results = outcome.get("value_unit_results") if outcome is not None else None
    if not isinstance(quality_results, dict) or set(quality_results) != quality_floor_ids:
        blockers.append("hard-quality-floor-results-incomplete")
    if not isinstance(value_results, dict) or set(value_results) != set(value_units):
        blockers.append("value-unit-results-incomplete")

    if (
        workflow.get("finished_at_utc") is None
        or workflow.get("workflow_elapsed_ms") is None
        or workflow.get("workflow_clock_source") != "monotonic-clock"
    ):
        blockers.append("complete-workflow-clock-unavailable")

    provider_events = [
        item
        for item in workflow["invocations"]
        if item["usage_scope"] == "provider-workflow"
    ]
    if not provider_events:
        blockers.append("provider-workflow-usage-unavailable")
    provider_actual = bool(provider_events) and all(
        item["usage_source"] == "provider-actual" for item in provider_events
    )
    if not provider_actual:
        blockers.append("provider-actual-usage-incomplete")
    total_input_tokens = sum(int(item["input_tokens"] or 0) for item in provider_events)
    cached_input_tokens = sum(
        int(item["cached_input_tokens"] or 0) for item in provider_events
    )
    total_output_tokens = sum(
        int(item["output_tokens"] or 0) for item in provider_events
    )
    total_tokens = total_input_tokens + total_output_tokens
    if provider_events and total_tokens <= 0:
        blockers.append("total-provider-token-cost-unavailable")

    event_counts = workflow["event_counts"]
    if provider_events and len(provider_events) != 1 + event_counts["retry"]:
        blockers.append("provider-attempts-do-not-reconcile-with-retries")
    if outcome is not None:
        if outcome.get("retries") != event_counts["retry"]:
            blockers.append("task-outcome-retries-do-not-reconcile")
        if outcome.get("corrections") != event_counts["correction"]:
            blockers.append("task-outcome-corrections-do-not-reconcile")

    recall_events = [
        item
        for item in workflow["invocations"]
        if item["tool_name"] == "elefante-recall"
    ]
    delivered_ids = set(trace.get("delivered_memory_ids", [])) if trace else set()
    active_use_events = [
        item for item in trace.get("use_events", []) if not item["retracted"]
    ] if trace else []
    declared_used_ids = {
        memory_id
        for event in active_use_events
        for memory_id in event["memory_ids"]
    }
    recall_context_tokens = sum(
        int(item["recall_context_tokens"] or 0) for item in recall_events
    )
    if recall_context_tokens > total_input_tokens:
        blockers.append("recall-context-does-not-reconcile-with-provider-input")
    if workflow["condition"] == "control":
        if recall_events:
            blockers.append("control-observed-elefante-recall")
        if delivered_ids or active_use_events:
            blockers.append("control-observed-memory-delivery-or-use")
    else:
        if len(recall_events) != 1:
            blockers.append("treatment-requires-one-recall-event")
        elif (
            recall_events[0]["status"] != "success"
            or recall_events[0]["result_count"] <= 0
            or recall_context_tokens <= 0
        ):
            blockers.append("treatment-memory-not-supplied")
        else:
            recall_ids = set(recall_events[0]["returned_memory_ids"])
            if recall_ids != delivered_ids:
                blockers.append("recall-delivery-trace-mismatch")
        if not delivered_ids:
            blockers.append("treatment-delivered-memory-missing")
        if not declared_used_ids:
            blockers.append("treatment-declared-use-missing")
        elif not declared_used_ids.issubset(delivered_ids):
            blockers.append("declared-use-not-bound-to-delivery")
        if workflow.get("memory_evidence_sha256") is None:
            blockers.append("eligible-pre-existing-memory-missing")

    if workflow["independently_arising"] is not True:
        blockers.append("task-not-independently-arising")
    if workflow["evidence_previously_consumed"] is not False:
        blockers.append("memory-evidence-previously-consumed")

    accepted_workflow_value: float | None = None
    hard_floors_passed: bool | None = None
    if isinstance(quality_results, dict) and isinstance(value_results, dict):
        hard_floors_passed = all(quality_results.values())
        accepted = outcome.get("accepted") is True if outcome is not None else False
        terminal_accepted = workflow.get("terminal_status") == "accepted"
        if accepted != terminal_accepted:
            blockers.append("workflow-terminal-and-outcome-disagree")
        accepted_workflow_value = (
            sum(
                float(value_units[unit_id]["weight"])
                for unit_id, passed in value_results.items()
                if passed
            )
            if accepted and terminal_accepted and hard_floors_passed
            else 0.0
        )

    all_costed = bool(provider_events) and all(
        item["rate_card_id"]
        and item["currency"]
        and item["calculated_cost_micros"] is not None
        for item in provider_events
    )
    currencies = {
        item["currency"] for item in provider_events if item["currency"] is not None
    }
    financial_effect = (
        {
            "status": "actual",
            "currency": next(iter(currencies)),
            "calculated_cost_micros": sum(
                int(item["calculated_cost_micros"] or 0) for item in provider_events
            ),
        }
        if all_costed and len(currencies) == 1
        else {"status": "unknown"}
    )

    return {
        "workflow_id": workflow["workflow_id"],
        "condition": workflow["condition"],
        "task_trace_id": trace_id,
        "terminal_status": workflow.get("terminal_status"),
        "accepted_workflow_value": accepted_workflow_value,
        "hard_floors_passed": hard_floors_passed,
        "quality_floor_results": quality_results,
        "value_unit_results": value_results,
        "workflow_elapsed_ms": workflow.get("workflow_elapsed_ms"),
        "invocation_duration_ms": sum(
            int(item["duration_ms"]) for item in workflow["invocations"]
        ),
        "active_developer_time_ms": workflow.get("active_developer_time_ms"),
        "active_time_source": workflow.get("active_time_source") or "unknown",
        "total_input_tokens": total_input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "total_output_tokens": total_output_tokens,
        "recall_context_tokens": recall_context_tokens,
        "total_tokens": total_tokens,
        "token_count_source": "provider-actual" if provider_actual else "unknown",
        "retries": event_counts["retry"],
        "corrections": event_counts["correction"],
        "rework_events": event_counts["rework"],
        "delivered_memory_ids": sorted(delivered_ids),
        "declared_used_memory_ids": sorted(declared_used_ids),
        "active_declared_use_event_ids": [
            item["event_id"] for item in active_use_events
        ],
        "financial_effect": financial_effect,
        "blockers": sorted(dict.fromkeys(blockers)),
    }


def build_value_signal_card(
    store: SessionIntelligenceStore,
    task_ledger: TaskIntelligenceLedger,
    *,
    comparison_id: str,
) -> dict[str, Any]:
    """Join one matched pair into a fail-closed, non-persisted Signal Card."""
    workflows = store.comparison_workflows(comparison_id)
    conditions = {item["condition"] for item in workflows}
    pair_blockers: list[str] = []
    if len(workflows) != 2 or conditions != WORKFLOW_CONDITIONS:
        pair_blockers.append("complete-control-treatment-pair-required")
    by_condition = {item["condition"]: item for item in workflows}
    if conditions == WORKFLOW_CONDITIONS:
        control_workflow = by_condition["control"]
        treatment_workflow = by_condition["treatment"]
        for field in (
            "task_value_contract_sha256",
            "matched_context_sha256",
            "memory_evidence_sha256",
            "memory_created_at_utc",
            "task_observed_at_utc",
        ):
            if control_workflow.get(field) != treatment_workflow.get(field):
                pair_blockers.append(f"matched-pair-differs-in-{field}")
        arms = {
            condition: _workflow_arm(
                by_condition[condition],
                task_ledger=task_ledger,
            )
            for condition in ("control", "treatment")
        }
    else:
        arms = {}

    arm_blockers = sorted(
        {
            blocker
            for arm in arms.values()
            for blocker in arm["blockers"]
        }
    )
    blockers = sorted(dict.fromkeys([*pair_blockers, *arm_blockers]))
    decision_class = "inconclusive"
    accepted_value_delta: float | None = None
    workflow_elapsed_delta_ms: int | None = None
    token_efficiency_delta: float | None = None
    token_financial_gate = "unknown"
    if not blockers and set(arms) == WORKFLOW_CONDITIONS:
        control = arms["control"]
        treatment = arms["treatment"]
        control_value = float(control["accepted_workflow_value"])
        treatment_value = float(treatment["accepted_workflow_value"])
        control_time = int(control["workflow_elapsed_ms"])
        treatment_time = int(treatment["workflow_elapsed_ms"])
        control_efficiency = control_value / int(control["total_tokens"])
        treatment_efficiency = treatment_value / int(treatment["total_tokens"])
        accepted_value_delta = treatment_value - control_value
        workflow_elapsed_delta_ms = treatment_time - control_time
        token_efficiency_delta = treatment_efficiency - control_efficiency
        token_financial_gate = (
            "pass" if token_efficiency_delta >= 0 else "resource-regression"
        )
        quality_regression = any(
            control["quality_floor_results"][field]
            and not treatment["quality_floor_results"][field]
            for field in control["quality_floor_results"]
        )
        if treatment_value < control_value or quality_regression:
            decision_class = "no-lift-harm"
        elif treatment_value > control_value and treatment_time <= control_time:
            decision_class = "developer-value-lift"
        elif treatment_value == control_value and treatment_time < control_time:
            decision_class = "workflow-time-lift"
        elif treatment_value > control_value and treatment_time > control_time:
            decision_class = "quality-first-trade"
        elif (
            treatment_value == control_value
            and treatment_time == control_time
            and token_efficiency_delta > 0
        ):
            decision_class = "token-only-lift"
        else:
            decision_class = "no-lift-harm"

    local_signal = decision_class != "inconclusive"
    return {
        "signal_card_schema_version": 1,
        "card_type": "matched-task-value",
        "scope": {
            "comparison_id": _uuid(comparison_id, "comparison_id"),
            "task_value_contract_sha256": (
                workflows[0]["task_value_contract_sha256"] if workflows else None
            ),
            "task_class": (
                workflows[0]["task_value_contract"]["task_class"]
                if workflows
                else None
            ),
        },
        "evidence_class": "local-causal-signal" if local_signal else "inconclusive",
        "arms": arms,
        "decision": {
            "class": decision_class,
            "accepted_value_delta": accepted_value_delta,
            "workflow_elapsed_delta_ms": workflow_elapsed_delta_ms,
            "accepted_value_per_total_token_delta": (
                round(token_efficiency_delta, 12)
                if token_efficiency_delta is not None
                else None
            ),
            "token_financial_gate": token_financial_gate,
            "blockers": blockers,
        },
        "claim_boundary": {
            "local_signal": local_signal,
            "representative_evidence": False,
            "public_claim_authorized": False,
            "reason": "One matched task cannot establish representative product lift.",
        },
        "raw_transcripts_stored": False,
        "persisted": False,
    }
