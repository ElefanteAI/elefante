"""Local, metadata-only audit ledger for Task Intelligence delivery and outcomes.

The ledger deliberately stores hashes and identifiers, never task text, prompt
content, memory bodies, or outcome comments.  It separates four facts that must
not be conflated: retrieval, delivery, declared use, and task outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from src.utils.config import get_config


TRACE_ACTIVE_HOURS = 24
LEDGER_RETENTION_DAYS = 30


class TaskIntelligenceLedgerError(ValueError):
    """A fail-closed trace, provenance, or idempotency violation."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def canonical_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_text(rendered)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _json_ids(values: Iterable[str]) -> str:
    return json.dumps(sorted(dict.fromkeys(str(value) for value in values)))


class TaskIntelligenceLedger:
    """SQLite-backed trace ledger with session binding and exact idempotency."""

    def __init__(self, path: Path | str | None = None) -> None:
        default_path = (
            Path(get_config().elefante.data_dir) / "task_intelligence.sqlite3"
        )
        self.path = Path(path or default_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            timeout=5,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._initialize_schema()
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self.prune()

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_traces (
                    trace_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL,
                    expires_at_utc TEXT NOT NULL,
                    caller_tool TEXT NOT NULL,
                    caller_instance_id TEXT NOT NULL,
                    caller_session_id TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    invocation_mode TEXT NOT NULL,
                    task_sha256 TEXT NOT NULL,
                    criteria_sha256 TEXT NOT NULL,
                    task_id_sha256 TEXT,
                    project_sha256 TEXT,
                    workspace_sha256 TEXT,
                    stage TEXT,
                    profile TEXT NOT NULL,
                    delivery_mode TEXT NOT NULL,
                    brief_sha256 TEXT NOT NULL,
                    selected_ids_json TEXT NOT NULL,
                    delivered_ids_json TEXT NOT NULL,
                    selected_count INTEGER NOT NULL,
                    omission_count INTEGER NOT NULL,
                    conflict_count INTEGER NOT NULL,
                    abstained INTEGER NOT NULL,
                    delivery_blocked INTEGER NOT NULL,
                    estimated_tokens INTEGER NOT NULL,
                    token_budget INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_use_events (
                    event_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL REFERENCES task_traces(trace_id) ON DELETE CASCADE,
                    idempotency_sha256 TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    memory_ids_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    retracted_at_utc TEXT,
                    UNIQUE(trace_id, idempotency_sha256)
                );

                CREATE TABLE IF NOT EXISTS task_outcomes (
                    trace_id TEXT PRIMARY KEY REFERENCES task_traces(trace_id) ON DELETE CASCADE,
                    idempotency_sha256 TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    accepted INTEGER,
                    evidence_source TEXT NOT NULL,
                    retries INTEGER NOT NULL,
                    corrections INTEGER NOT NULL,
                    duration_ms INTEGER,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    failure_category TEXT,
                    created_at_utc TEXT NOT NULL,
                    retracted_at_utc TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_task_traces_created
                    ON task_traces(created_at_utc);
                CREATE INDEX IF NOT EXISTS idx_task_use_trace
                    ON task_use_events(trace_id);
                """
            )
            outcome_columns = {
                row[1]
                for row in self._connection.execute(
                    "PRAGMA table_info(task_outcomes)"
                ).fetchall()
            }
            if "retracted_at_utc" not in outcome_columns:
                self._connection.execute(
                    "ALTER TABLE task_outcomes ADD COLUMN retracted_at_utc TEXT"
                )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def prune(self, *, now: datetime | None = None) -> int:
        cutoff = _iso((now or _utc_now()) - timedelta(days=LEDGER_RETENTION_DAYS))
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM task_traces WHERE created_at_utc < ?", (cutoff,)
            )
            return max(0, int(cursor.rowcount))

    @staticmethod
    def _provenance_fields(provenance: dict[str, str]) -> tuple[str, str, str, str]:
        return (
            str(provenance.get("tool", "")),
            str(provenance.get("instance_id", "")),
            str(provenance.get("session_id", "")),
            str(provenance.get("transport", "")),
        )

    def create_trace(
        self,
        *,
        provenance: dict[str, str],
        invocation_mode: str,
        task: str,
        success_criteria: list[str],
        task_id: str | None,
        project: str | None,
        workspace: str | None,
        stage: str | None,
        profile: str,
        delivery_mode: str,
        brief_digest: str,
        selected_memory_ids: list[str],
        delivered_memory_ids: list[str],
        omission_count: int,
        conflict_count: int,
        abstained: bool,
        delivery_blocked: bool,
        estimated_tokens: int,
        token_budget: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        created = now or _utc_now()
        # Long-running daemons must enforce retention continuously, not only at
        # process start.
        self.prune(now=created)
        expires = created + timedelta(hours=TRACE_ACTIVE_HOURS)
        trace_id = str(uuid4())
        (
            caller_tool,
            caller_instance,
            caller_session,
            transport,
        ) = self._provenance_fields(provenance)
        values = (
            trace_id,
            _iso(created),
            _iso(expires),
            caller_tool,
            caller_instance,
            caller_session,
            transport,
            invocation_mode,
            sha256_text(task),
            canonical_digest(success_criteria),
            sha256_text(task_id) if task_id else None,
            sha256_text(project) if project else None,
            sha256_text(workspace) if workspace else None,
            stage,
            profile,
            delivery_mode,
            brief_digest,
            _json_ids(selected_memory_ids),
            _json_ids(delivered_memory_ids),
            len(set(selected_memory_ids)),
            int(omission_count),
            int(conflict_count),
            int(bool(abstained)),
            int(bool(delivery_blocked)),
            int(estimated_tokens),
            int(token_budget),
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO task_traces VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                values,
            )
        return {
            "trace_id": trace_id,
            "created_at_utc": _iso(created),
            "expires_at_utc": _iso(expires),
        }

    def _trace(self, trace_id: str) -> sqlite3.Row:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM task_traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
        if row is None:
            raise TaskIntelligenceLedgerError("Unknown task trace.")
        return row

    def validate_trace(
        self,
        trace_id: str,
        *,
        provenance: dict[str, str],
        require_delivery: bool = False,
        require_active: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or _utc_now()
        self.prune(now=current)
        row = self._trace(trace_id)
        expected = self._provenance_fields(provenance)
        observed = (
            row["caller_tool"],
            row["caller_instance_id"],
            row["caller_session_id"],
            row["transport"],
        )
        if observed != expected:
            raise TaskIntelligenceLedgerError(
                "Task trace belongs to a different tool instance or session."
            )
        if require_active and current >= datetime.fromisoformat(row["expires_at_utc"]):
            raise TaskIntelligenceLedgerError("Task trace has expired.")
        delivered_ids = json.loads(row["delivered_ids_json"])
        if require_delivery and not delivered_ids:
            raise TaskIntelligenceLedgerError(
                "No memory was delivered for this trace; use cannot be recorded."
            )
        result = dict(row)
        result["selected_memory_ids"] = json.loads(result.pop("selected_ids_json"))
        result["delivered_memory_ids"] = json.loads(result.pop("delivered_ids_json"))
        return result

    def record_use(
        self,
        *,
        trace_id: str,
        provenance: dict[str, str],
        memory_ids: list[str],
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        trace = self.validate_trace(
            trace_id,
            provenance=provenance,
            require_delivery=True,
            now=now,
        )
        unique_ids = sorted(dict.fromkeys(memory_ids))
        delivered = set(trace["delivered_memory_ids"])
        if not unique_ids or not set(unique_ids).issubset(delivered):
            raise TaskIntelligenceLedgerError(
                "record_use IDs must be a non-empty subset delivered by this trace."
            )
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise TaskIntelligenceLedgerError("idempotency_key is required.")
        if len(idempotency_key) > 256:
            raise TaskIntelligenceLedgerError(
                "idempotency_key must contain at most 256 characters."
            )
        key_digest = sha256_text(idempotency_key)
        payload_digest = canonical_digest(unique_ids)
        with self._lock, self._connection:
            prior = self._connection.execute(
                """
                SELECT event_id, payload_sha256, memory_ids_json, retracted_at_utc
                FROM task_use_events
                WHERE trace_id = ? AND idempotency_sha256 = ?
                """,
                (trace_id, key_digest),
            ).fetchone()
            if prior is not None:
                if prior["payload_sha256"] != payload_digest:
                    raise TaskIntelligenceLedgerError(
                        "Idempotency key was already used with a different payload."
                    )
                return {
                    "event_id": prior["event_id"],
                    "memory_ids": json.loads(prior["memory_ids_json"]),
                    "duplicate": True,
                    "retracted": prior["retracted_at_utc"] is not None,
                }
            event_id = str(uuid4())
            self._connection.execute(
                """
                INSERT INTO task_use_events (
                    event_id, trace_id, idempotency_sha256, payload_sha256,
                    memory_ids_json, created_at_utc, retracted_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    event_id,
                    trace_id,
                    key_digest,
                    payload_digest,
                    _json_ids(unique_ids),
                    _iso(now or _utc_now()),
                ),
            )
        return {
            "event_id": event_id,
            "memory_ids": unique_ids,
            "duplicate": False,
            "retracted": False,
        }

    def retract_use(
        self,
        *,
        trace_id: str,
        provenance: dict[str, str],
        event_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.validate_trace(
            trace_id, provenance=provenance, require_active=False, now=now
        )
        retracted_at = _iso(now or _utc_now())
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT retracted_at_utc FROM task_use_events
                WHERE trace_id = ? AND event_id = ?
                """,
                (trace_id, event_id),
            ).fetchone()
            if row is None:
                raise TaskIntelligenceLedgerError("Unknown use event for task trace.")
            if row["retracted_at_utc"] is not None:
                return {"event_id": event_id, "duplicate": True, "retracted": True}
            self._connection.execute(
                """
                UPDATE task_use_events SET retracted_at_utc = ?
                WHERE trace_id = ? AND event_id = ?
                """,
                (retracted_at, trace_id, event_id),
            )
        return {"event_id": event_id, "duplicate": False, "retracted": True}

    def record_outcome(
        self,
        *,
        trace_id: str,
        provenance: dict[str, str],
        idempotency_key: str,
        outcome: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.validate_trace(trace_id, provenance=provenance, now=now)
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise TaskIntelligenceLedgerError("idempotency_key is required.")
        if len(idempotency_key) > 256:
            raise TaskIntelligenceLedgerError(
                "idempotency_key must contain at most 256 characters."
            )
        key_digest = sha256_text(idempotency_key)
        payload_digest = canonical_digest(outcome)
        accepted = outcome.get("accepted")
        accepted_db = None if accepted is None else int(bool(accepted))
        with self._lock, self._connection:
            prior = self._connection.execute(
                "SELECT idempotency_sha256, payload_sha256 FROM task_outcomes WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            if prior is not None:
                if (
                    prior["idempotency_sha256"] != key_digest
                    or prior["payload_sha256"] != payload_digest
                ):
                    raise TaskIntelligenceLedgerError(
                        "Task outcome already exists with different data."
                    )
                return {"trace_id": trace_id, "duplicate": True}
            self._connection.execute(
                """
                INSERT INTO task_outcomes (
                    trace_id, idempotency_sha256, payload_sha256, status,
                    accepted, evidence_source, retries, corrections, duration_ms,
                    input_tokens, output_tokens, failure_category, created_at_utc,
                    retracted_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    trace_id,
                    key_digest,
                    payload_digest,
                    outcome["status"],
                    accepted_db,
                    outcome["evidence_source"],
                    int(outcome.get("retries", 0)),
                    int(outcome.get("corrections", 0)),
                    outcome.get("duration_ms"),
                    outcome.get("input_tokens"),
                    outcome.get("output_tokens"),
                    outcome.get("failure_category"),
                    _iso(now or _utc_now()),
                ),
            )
        return {"trace_id": trace_id, "duplicate": False}

    def retract_outcome(
        self,
        *,
        trace_id: str,
        provenance: dict[str, str],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.validate_trace(
            trace_id, provenance=provenance, require_active=False, now=now
        )
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT retracted_at_utc FROM task_outcomes WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            if row is None:
                raise TaskIntelligenceLedgerError("Task trace has no outcome.")
            if row["retracted_at_utc"] is not None:
                return {"trace_id": trace_id, "duplicate": True, "retracted": True}
            self._connection.execute(
                "UPDATE task_outcomes SET retracted_at_utc = ? WHERE trace_id = ?",
                (_iso(now or _utc_now()), trace_id),
            )
        return {"trace_id": trace_id, "duplicate": False, "retracted": True}

    def inspect(
        self,
        trace_id: str,
        *,
        provenance: dict[str, str],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        trace = self.validate_trace(
            trace_id, provenance=provenance, require_active=False, now=now
        )
        with self._lock:
            uses = self._connection.execute(
                """
                SELECT event_id, memory_ids_json, created_at_utc, retracted_at_utc
                FROM task_use_events WHERE trace_id = ? ORDER BY created_at_utc, event_id
                """,
                (trace_id,),
            ).fetchall()
            outcome = self._connection.execute(
                """
                SELECT status, accepted, evidence_source, retries, corrections,
                       duration_ms, input_tokens, output_tokens, failure_category,
                       created_at_utc, retracted_at_utc
                FROM task_outcomes WHERE trace_id = ?
                """,
                (trace_id,),
            ).fetchone()
        public_trace = {
            key: value
            for key, value in trace.items()
            if key
            not in {
                "caller_instance_id",
                "caller_session_id",
                "task_sha256",
                "criteria_sha256",
                "task_id_sha256",
                "project_sha256",
                "workspace_sha256",
            }
        }
        public_trace["use_events"] = [
            {
                "event_id": row["event_id"],
                "memory_ids": json.loads(row["memory_ids_json"]),
                "created_at_utc": row["created_at_utc"],
                "retracted": row["retracted_at_utc"] is not None,
            }
            for row in uses
        ]
        if outcome is not None:
            outcome_dict = dict(outcome)
            if outcome_dict["accepted"] is not None:
                outcome_dict["accepted"] = bool(outcome_dict["accepted"])
            outcome_dict["retracted"] = outcome_dict.pop("retracted_at_utc") is not None
            public_trace["outcome"] = outcome_dict
        else:
            public_trace["outcome"] = None
        return public_trace

    def summary(self) -> dict[str, Any]:
        """Return local observational metrics without asserting causal lift."""
        self.prune()
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT t.profile, t.delivery_mode,
                       COUNT(*) AS trace_count,
                       SUM(CASE WHEN t.abstained = 1 THEN 1 ELSE 0 END) AS abstained_count,
                       SUM(CASE WHEN t.delivery_blocked = 1 THEN 1 ELSE 0 END) AS blocked_count,
                       SUM(CASE WHEN o.trace_id IS NOT NULL THEN 1 ELSE 0 END) AS outcome_count,
                       SUM(CASE WHEN o.accepted = 1 THEN 1 ELSE 0 END) AS accepted_count,
                       SUM(CASE WHEN o.status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded_count,
                       SUM(COALESCE(o.retries, 0)) AS retries,
                       SUM(COALESCE(o.corrections, 0)) AS corrections,
                       AVG(o.duration_ms) AS mean_duration_ms,
                       AVG(o.input_tokens) AS mean_input_tokens,
                       AVG(o.output_tokens) AS mean_output_tokens
                FROM task_traces t
                LEFT JOIN task_outcomes o
                  ON o.trace_id = t.trace_id AND o.retracted_at_utc IS NULL
                GROUP BY t.profile, t.delivery_mode
                ORDER BY t.profile, t.delivery_mode
                """
            ).fetchall()
            use_row = self._connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN retracted_at_utc IS NULL THEN 1 ELSE 0 END) AS active
                FROM task_use_events
                """
            ).fetchone()
        groups = []
        for row in rows:
            values = dict(row)
            outcomes = int(values["outcome_count"] or 0)
            values["acceptance_rate"] = (
                round(int(values["accepted_count"] or 0) / outcomes, 6)
                if outcomes
                else None
            )
            groups.append(values)
        return {
            "groups": groups,
            "declared_use_events": int(use_row["total"] or 0),
            "active_declared_use_events": int(use_row["active"] or 0),
            "causal_promotion_evidence": False,
            "interpretation": (
                "Observational runtime metrics only. Use the reviewed paired "
                "evaluator and untouched holdout for promotion decisions."
            ),
        }
