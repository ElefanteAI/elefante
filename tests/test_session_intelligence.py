"""Contracts for the opt-in local Session Intelligence evidence store."""

from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.ci.summarize_task_intelligence_evaluation import (
    main as summarize_main,
    summarize_value_evidence,
)
from scripts.ci.run_task_intelligence_baseline import (
    record_codex_attempt_evidence,
)
from src.core.session_intelligence import (
    CORE_QUALITY_FLOORS,
    INVOCATION_RETENTION_DAYS,
    SESSION_INTELLIGENCE_SCHEMA_VERSION,
    SESSION_RETENTION_DAYS,
    SessionIntelligenceError,
    SessionIntelligenceStore,
    build_value_baseline_card,
    build_value_signal_card,
)
from src.core.task_intelligence_ledger import (
    TaskIntelligenceLedger,
    canonical_digest,
    task_trace_provenance_digest,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.monotonic_value = 1_000_000_000

    def now(self) -> datetime:
        return self.value

    def monotonic_ns(self) -> int:
        return self.monotonic_value

    def advance(self, *, milliseconds: int) -> None:
        self.value += timedelta(milliseconds=milliseconds)
        self.monotonic_value += milliseconds * 1_000_000


def _store(tmp_path: Path, clock: _Clock) -> SessionIntelligenceStore:
    return SessionIntelligenceStore(
        tmp_path / "session_intelligence.db",
        enabled=True,
        now=clock.now,
        monotonic_ns=clock.monotonic_ns,
        clock_instance_id="test-clock",
    )


def _register_contract(
    store: SessionIntelligenceStore,
    *,
    preregistered_at_utc: str,
    value_units: list[dict] | None = None,
) -> str:
    return store.register_task_value_contract(
        goal_sha256=_digest("deliver accepted implementation"),
        question_sha256=_digest("exact frozen question"),
        acceptance_rubric_sha256=canonical_digest(["binary rubric"]),
        task_class="developer-implementation",
        quality_floors=sorted(CORE_QUALITY_FLOORS),
        value_units=value_units
        or [
            {
                "id": "accepted-change",
                "weight": 1,
                "criterion_sha256": _digest("all maintained checks pass"),
                "evidence_source": "test",
            }
        ],
        time_boundary_sha256=_digest("start through acceptance or stop"),
        resource_boundary_sha256=_digest("all observed provider attempts"),
        preregistered_at_utc=preregistered_at_utc,
    )


def _start_workflow(
    store: SessionIntelligenceStore,
    *,
    session_id: str,
    contract_sha256: str,
    comparison_id: str | None = None,
    condition: str = "treatment",
    task_trace_id: str | None = None,
    task_trace_provenance_sha256: str | None = None,
) -> dict[str, str]:
    return store.start_workflow(
        session_id=session_id,
        comparison_id=comparison_id or str(uuid4()),
        condition=condition,
        task_value_contract_sha256=contract_sha256,
        matched_context_sha256=_digest("same model tools source and policy"),
        task_trace_id=task_trace_id,
        task_trace_provenance_sha256=task_trace_provenance_sha256,
        task_observed_at_utc="2026-08-27T12:00:00+00:00",
        independently_arising=True,
        evidence_previously_consumed=False,
        memory_evidence_sha256=_digest("pre-existing memory evidence"),
        memory_created_at_utc="2026-08-26T12:00:00+00:00",
    )


def test_store_is_explicit_opt_in_and_uses_versioned_private_sqlite(
    tmp_path: Path,
) -> None:
    path = tmp_path / "session_intelligence.db"
    with pytest.raises(SessionIntelligenceError, match="enabled=True"):
        SessionIntelligenceStore(path)
    assert not path.exists()

    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == (
        SESSION_INTELLIGENCE_SCHEMA_VERSION
    )
    assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert connection.execute("SELECT version FROM schema_migrations").fetchone()[0] == 1
    connection.close()
    assert path.stat().st_mode & 0o777 == 0o600
    store.close()


def test_read_only_store_inspects_without_creating_pruning_or_mutating(
    tmp_path: Path,
) -> None:
    path = tmp_path / "session_intelligence.db"
    missing = tmp_path / "missing.db"
    with pytest.raises(SessionIntelligenceError, match="does not exist"):
        SessionIntelligenceStore(missing, read_only=True)
    assert not missing.exists()

    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    writable = _store(tmp_path, clock)
    session = writable.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    writable.close()
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()

    read_only = SessionIntelligenceStore(path, read_only=True, now=clock.now)
    snapshot = read_only.export_snapshot()
    assert [item["session_id"] for item in snapshot["sessions"]] == [
        session["session_id"]
    ]
    with pytest.raises(SessionIntelligenceError, match="open read-only"):
        read_only.prune()
    with pytest.raises(SessionIntelligenceError, match="open read-only"):
        read_only.reset(confirm="DELETE SESSION INTELLIGENCE")
    read_only.close()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest_before


def test_preregistered_contract_survives_reopen_before_workflow(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    store.close()

    reopened = _store(tmp_path, clock)
    workflow = _start_workflow(
        reopened,
        session_id=session["session_id"],
        contract_sha256=contract,
    )
    assert workflow["workflow_id"]
    reopened.close()


def test_schema_fails_closed_for_future_corrupt_or_unversioned_state(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))

    future = tmp_path / "future.db"
    connection = sqlite3.connect(future)
    connection.execute("PRAGMA user_version=99")
    connection.close()
    with pytest.raises(SessionIntelligenceError, match="newer unsupported"):
        SessionIntelligenceStore(
            future,
            enabled=True,
            now=clock.now,
            monotonic_ns=clock.monotonic_ns,
        )

    corrupt = tmp_path / "corrupt.db"
    connection = sqlite3.connect(corrupt)
    connection.execute("CREATE TABLE sessions (session_id TEXT PRIMARY KEY)")
    connection.execute("PRAGMA user_version=1")
    connection.close()
    with pytest.raises(SessionIntelligenceError, match="schema is incomplete"):
        SessionIntelligenceStore(
            corrupt,
            enabled=True,
            now=clock.now,
            monotonic_ns=clock.monotonic_ns,
        )

    unversioned = tmp_path / "unversioned.db"
    connection = sqlite3.connect(unversioned)
    connection.execute("CREATE TABLE foreign_data (value TEXT)")
    connection.commit()
    connection.close()
    with pytest.raises(SessionIntelligenceError, match="Unversioned non-empty"):
        SessionIntelligenceStore(
            unversioned,
            enabled=True,
            now=clock.now,
            monotonic_ns=clock.monotonic_ns,
        )


def test_metadata_only_round_trip_separates_invocation_and_workflow_clocks(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
        client_session_id="raw-client-session-identifier",
    )
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    workflow = _start_workflow(
        store,
        session_id=session["session_id"],
        contract_sha256=contract,
    )

    invocation_id = str(uuid4())
    started = clock.now()
    result = store.append_invocation(
        invocation_id=invocation_id,
        session_id=session["session_id"],
        workflow_id=workflow["workflow_id"],
        invocation_kind="model-attempt",
        client_name="codex",
        tool_name="model-attempt",
        started_at_utc=started,
        finished_at_utc=started + timedelta(milliseconds=100),
        started_monotonic_ns=2_000_000_000,
        finished_monotonic_ns=2_100_000_000,
        status="success",
        result_count=1,
        usage_source="provider-actual",
        usage_scope="provider-workflow",
        provider="openai",
        model="gpt-5.6-sol",
        input_tokens=900,
        cached_input_tokens=400,
        output_tokens=100,
        recall_context_tokens=120,
    )
    assert result == {
        "invocation_id": invocation_id,
        "duplicate": False,
        "duration_ms": 100,
    }
    store.append_workflow_event(
        workflow_id=workflow["workflow_id"],
        event_type="retry",
        evidence_source="host",
    )
    clock.advance(milliseconds=5_000)
    finished = store.finish_workflow(
        workflow["workflow_id"], terminal_status="accepted"
    )

    assert finished["workflow_elapsed_ms"] == 5_000
    assert finished["invocations"][0]["duration_ms"] == 100
    assert finished["workflow_elapsed_ms"] != finished["invocations"][0]["duration_ms"]
    assert finished["active_developer_time_ms"] is None
    assert finished["active_time_source"] is None
    assert finished["event_counts"] == {"correction": 0, "retry": 1, "rework": 0}
    assert finished["task_value_contract"]["value_units"][0]["id"] == (
        "accepted-change"
    )

    store.end_session(session["session_id"])
    export = store.export_snapshot()
    assert export["raw_transcripts_stored"] is False
    assert export["remote_telemetry"] is False
    assert "started_monotonic_ns" not in json.dumps(export)
    store.close()


def test_workflow_requires_observation_then_preregistration_then_start(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )

    premature_contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T11:59:00+00:00"
    )
    with pytest.raises(
        SessionIntelligenceError,
        match="cannot precede natural task observation",
    ):
        _start_workflow(
            store,
            session_id=session["session_id"],
            contract_sha256=premature_contract,
        )

    late_contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:03:00+00:00"
    )
    with pytest.raises(
        SessionIntelligenceError,
        match="must precede workflow start",
    ):
        _start_workflow(
            store,
            session_id=session["session_id"],
            contract_sha256=late_contract,
        )

    valid_contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    workflow = _start_workflow(
        store,
        session_id=session["session_id"],
        contract_sha256=valid_contract,
    )
    assert workflow["started_at_utc"] == "2026-08-27T12:02:00+00:00"
    store.close()


def test_invocation_is_exact_idempotent_and_token_subsets_are_not_double_counted(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    workflow = _start_workflow(
        store,
        session_id=session["session_id"],
        contract_sha256=contract,
    )
    invocation_id = str(uuid4())
    arguments = {
        "invocation_id": invocation_id,
        "session_id": session["session_id"],
        "workflow_id": workflow["workflow_id"],
        "invocation_kind": "model-attempt",
        "client_name": "codex",
        "tool_name": "model-attempt",
        "started_at_utc": clock.now(),
        "finished_at_utc": clock.now() + timedelta(milliseconds=20),
        "started_monotonic_ns": 10,
        "finished_monotonic_ns": 20_000_010,
        "status": "success",
        "result_count": 1,
        "usage_source": "provider-actual",
        "usage_scope": "provider-workflow",
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "input_tokens": 600,
        "cached_input_tokens": 250,
        "output_tokens": 80,
        "recall_context_tokens": 120,
    }
    first = store.append_invocation(**arguments)
    duplicate = store.append_invocation(**arguments)
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True

    with pytest.raises(SessionIntelligenceError, match="different evidence"):
        store.append_invocation(**{**arguments, "output_tokens": 81})
    with pytest.raises(SessionIntelligenceError, match="cached_input_tokens"):
        store.append_invocation(
            **{
                **arguments,
                "invocation_id": str(uuid4()),
                "cached_input_tokens": 601,
            }
        )
    with pytest.raises(SessionIntelligenceError, match="recall_context_tokens"):
        store.append_invocation(
            **{
                **arguments,
                "invocation_id": str(uuid4()),
                "recall_context_tokens": 601,
            }
        )
    store.close()


def test_rate_card_cost_requires_provider_actual_matching_provenance(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    store.add_rate_card(
        rate_card_id="openai-sol-2026-08",
        provider="openai",
        model="gpt-5.6-sol",
        currency="USD",
        effective_at_utc="2026-08-01T00:00:00+00:00",
        source_sha256=_digest("dated provider rate card"),
    )
    store.add_rate_card(
        rate_card_id="openai-sol-2026-08",
        provider="openai",
        model="gpt-5.6-sol",
        currency="USD",
        effective_at_utc="2026-08-01T00:00:00+00:00",
        source_sha256=_digest("dated provider rate card"),
    )
    result = store.append_invocation(
        session_id=session["session_id"],
        workflow_id=None,
        invocation_kind="model-attempt",
        client_name="codex",
        tool_name="model-attempt",
        started_at_utc=clock.now(),
        finished_at_utc=clock.now() + timedelta(milliseconds=10),
        started_monotonic_ns=100,
        finished_monotonic_ns=10_000_100,
        status="success",
        result_count=1,
        usage_source="provider-actual",
        usage_scope="provider-workflow",
        provider="openai",
        model="gpt-5.6-sol",
        input_tokens=100,
        cached_input_tokens=0,
        output_tokens=10,
        recall_context_tokens=0,
        rate_card_id="openai-sol-2026-08",
        currency="USD",
        calculated_cost_micros=123,
    )
    assert result["duplicate"] is False

    with pytest.raises(SessionIntelligenceError, match="provider-actual"):
        store.append_invocation(
            session_id=session["session_id"],
            workflow_id=None,
            invocation_kind="model-attempt",
            client_name="codex",
            tool_name="model-attempt",
            started_at_utc=clock.now(),
            finished_at_utc=clock.now() + timedelta(milliseconds=10),
            started_monotonic_ns=100,
            finished_monotonic_ns=10_000_100,
            status="success",
            result_count=1,
            usage_source="local-estimated",
            usage_scope="provider-workflow",
            input_tokens=100,
            cached_input_tokens=0,
            output_tokens=10,
            recall_context_tokens=0,
            rate_card_id="openai-sol-2026-08",
            currency="USD",
            calculated_cost_micros=123,
        )
    store.close()


def test_retention_and_confirmed_deletion_are_scoped_and_local(tmp_path: Path) -> None:
    current = datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc)
    clock = _Clock(current)
    store = _store(tmp_path, clock)
    old_session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
        now=current - timedelta(days=SESSION_RETENTION_DAYS + 1),
    )
    store.append_invocation(
        session_id=old_session["session_id"],
        workflow_id=None,
        invocation_kind="tool-call",
        client_name="codex",
        tool_name="elefante-recall",
        started_at_utc=current - timedelta(days=INVOCATION_RETENTION_DAYS + 1),
        finished_at_utc=current
        - timedelta(days=INVOCATION_RETENTION_DAYS + 1)
        + timedelta(milliseconds=10),
        started_monotonic_ns=10,
        finished_monotonic_ns=10_000_010,
        status="ignored",
        result_count=0,
        usage_source="unknown",
        usage_scope="elefante-diagnostic",
    )
    pruned = store.prune(now=current)
    assert pruned["invocation_events"] == 1
    assert pruned["sessions"] == 1

    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    _start_workflow(
        store,
        session_id=session["session_id"],
        contract_sha256=contract,
    )
    with pytest.raises(SessionIntelligenceError, match="exact confirmation"):
        store.delete_session(session["session_id"], confirm="DELETE")
    assert store.delete_session(
        session["session_id"], confirm=f"DELETE {session['session_id']}"
    )
    connection = sqlite3.connect(tmp_path / "session_intelligence.db")
    assert (
        connection.execute("SELECT COUNT(*) FROM task_value_contracts").fetchone()[0]
        == 0
    )
    connection.close()

    workflow_session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    workflow_contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    workflow = _start_workflow(
        store,
        session_id=workflow_session["session_id"],
        contract_sha256=workflow_contract,
    )
    assert store.delete_workflow(
        workflow["workflow_id"], confirm=f"DELETE {workflow['workflow_id']}"
    )
    connection = sqlite3.connect(tmp_path / "session_intelligence.db")
    assert (
        connection.execute("SELECT COUNT(*) FROM task_value_contracts").fetchone()[0]
        == 0
    )
    connection.close()
    assert store.delete_session(
        workflow_session["session_id"],
        confirm=f"DELETE {workflow_session['session_id']}",
    )

    with pytest.raises(SessionIntelligenceError, match="exact confirmation"):
        store.reset(confirm="yes")
    assert store.reset(confirm="DELETE SESSION INTELLIGENCE") == {
        "sessions": 0,
        "task_value_contracts": 0,
        "rate_cards": 0,
    }
    store.close()


def test_store_operations_need_no_network_and_never_persist_raw_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def blocked_socket(*_args, **_kwargs):
        raise AssertionError("Session Intelligence attempted network access")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    raw_marker = "NEVER-PERSIST-RAW-PROMPT-OR-TRANSCRIPT"
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
        client_session_id=raw_marker,
    )
    store.end_session(session["session_id"])
    store.close()

    connection = sqlite3.connect(tmp_path / "session_intelligence.db")
    dump = "\n".join(connection.iterdump())
    connection.close()
    assert raw_marker not in dump
    assert _digest(raw_marker) in dump


def _task_trace(
    ledger: TaskIntelligenceLedger,
    *,
    provenance: dict[str, str],
    delivered: list[str],
    task: str = "exact frozen question",
    success_criteria: list[str] | None = None,
    now: datetime,
) -> dict:
    return ledger.create_trace(
        provenance=provenance,
        invocation_mode="workflow_managed",
        task=task,
        success_criteria=success_criteria or ["binary rubric"],
        task_id="natural-value-task",
        project="elefante",
        workspace="/repo/elefante",
        stage="execution",
        profile="v2",
        delivery_mode="pilot" if delivered else "shadow",
        brief_digest=canonical_digest({"delivered": delivered}),
        selected_memory_ids=delivered,
        delivered_memory_ids=delivered,
        omission_count=0,
        conflict_count=0,
        abstained=not delivered,
        delivery_blocked=False,
        estimated_tokens=120,
        token_budget=1500,
        now=now,
    )


def _record_pair_arm(
    store: SessionIntelligenceStore,
    ledger: TaskIntelligenceLedger,
    clock: _Clock,
    *,
    comparison_id: str,
    contract_sha256: str,
    condition: str,
    memory_id: str,
    workflow_elapsed_ms: int,
    invocation_duration_ms: int,
    input_tokens: int,
    output_tokens: int,
    value_unit_results: dict[str, bool],
    quality_floor_results: dict[str, bool] | None = None,
    declared_use: bool = True,
    task: str = "exact frozen question",
) -> tuple[str, dict[str, str]]:
    provenance = {
        "tool": "codex",
        "instance_id": f"{condition}-window",
        "session_id": f"{condition}-session",
        "transport": "streamable-http",
    }
    delivered = [memory_id] if condition == "treatment" else []
    trace = _task_trace(
        ledger,
        provenance=provenance,
        delivered=delivered,
        task=task,
        now=clock.now(),
    )
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
        client_session_id=f"{condition}-client-session",
    )
    workflow = _start_workflow(
        store,
        session_id=session["session_id"],
        contract_sha256=contract_sha256,
        comparison_id=comparison_id,
        condition=condition,
        task_trace_id=trace["trace_id"],
        task_trace_provenance_sha256=task_trace_provenance_digest(provenance),
    )

    if condition == "treatment":
        store.append_invocation(
            session_id=session["session_id"],
            workflow_id=workflow["workflow_id"],
            invocation_kind="elefante-call",
            client_name="codex",
            tool_name="elefante-recall",
            started_at_utc=clock.now(),
            finished_at_utc=clock.now() + timedelta(milliseconds=20),
            started_monotonic_ns=10,
            finished_monotonic_ns=20_000_010,
            status="success",
            result_count=1,
            usage_source="local-estimated",
            usage_scope="elefante-diagnostic",
            input_tokens=5,
            cached_input_tokens=0,
            output_tokens=120,
            recall_context_tokens=120,
            returned_memory_ids=[memory_id],
        )
        if declared_use:
            ledger.record_use(
                trace_id=trace["trace_id"],
                provenance=provenance,
                memory_ids=[memory_id],
                idempotency_key=f"{condition}-use",
                now=clock.now(),
            )

    record_codex_attempt_evidence(
        store,
        session_id=session["session_id"],
        workflow_id=workflow["workflow_id"],
        evidence={
            "event_schema_version": 1,
            "started_at_utc": clock.now(),
            "finished_at_utc": clock.now()
            + timedelta(milliseconds=invocation_duration_ms),
            "started_monotonic_ns": 1_000_000_000,
            "finished_monotonic_ns": 1_000_000_000
            + invocation_duration_ms * 1_000_000,
            "status": "success",
            "result_count": 1,
            "provider": "openai",
            "model": "gpt-5.6-sol",
            "usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": min(200, input_tokens),
                "output_tokens": output_tokens,
                "usage_source": "provider-actual",
                "usage_scope": "single-complete-turn",
                "usage_event_count": 1,
            },
            "raw_content_included": False,
        },
    )
    floors = quality_floor_results or {
        field: True for field in sorted(CORE_QUALITY_FLOORS)
    }
    accepted = all(floors.values())
    ledger.record_outcome(
        trace_id=trace["trace_id"],
        provenance=provenance,
        idempotency_key=f"{condition}-outcome",
        outcome={
            "status": "succeeded" if accepted else "failed",
            "accepted": accepted,
            "evidence_source": "test",
            "retries": 0,
            "corrections": 0,
            "duration_ms": invocation_duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "failure_category": None if accepted else "validation",
            "task_value_contract_sha256": contract_sha256,
            "quality_floor_results": floors,
            "value_unit_results": value_unit_results,
        },
        now=clock.now(),
    )
    clock.advance(milliseconds=workflow_elapsed_ms)
    store.finish_workflow(
        workflow["workflow_id"],
        terminal_status="accepted" if accepted else "failed",
    )
    store.end_session(session["session_id"])
    return trace["trace_id"], provenance


def test_empty_store_baseline_card_says_evidence_pending(tmp_path: Path) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    card = build_value_baseline_card(store)
    assert card["evidence_status"] == "pending"
    assert card["known"]["complete_matched_pairs"] == 0
    assert card["public_claim_authorized"] is False
    assert "accepted-value effect" in card["unknowns"]
    store.close()


def test_value_baseline_cli_reports_pending_without_mutating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "session_intelligence.db"
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    store.close()
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()

    result = summarize_main(
        ["--session-intelligence-db", str(path), "--value-baseline"]
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["card_type"] == "value-baseline"
    assert payload["evidence_status"] == "pending"
    assert payload["public_claim_authorized"] is False
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest_before


def test_complete_join_produces_local_workflow_time_signal_not_product_claim(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    ledger = TaskIntelligenceLedger(tmp_path / "task_intelligence.sqlite3")
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    comparison_id = str(uuid4())
    memory_id = str(uuid4())
    _record_pair_arm(
        store,
        ledger,
        clock,
        comparison_id=comparison_id,
        contract_sha256=contract,
        condition="control",
        memory_id=memory_id,
        workflow_elapsed_ms=5_000,
        invocation_duration_ms=500,
        input_tokens=900,
        output_tokens=100,
        value_unit_results={"accepted-change": True},
    )
    _record_pair_arm(
        store,
        ledger,
        clock,
        comparison_id=comparison_id,
        contract_sha256=contract,
        condition="treatment",
        memory_id=memory_id,
        workflow_elapsed_ms=3_000,
        invocation_duration_ms=700,
        input_tokens=600,
        output_tokens=80,
        value_unit_results={"accepted-change": True},
    )

    card = build_value_signal_card(
        store,
        ledger,
        comparison_id=comparison_id,
    )
    assert card["decision"] == {
        "class": "workflow-time-lift",
        "accepted_value_delta": 0.0,
        "workflow_elapsed_delta_ms": -2_000,
        "accepted_value_per_total_token_delta": round(
            1 / 680 - 1 / 1000, 12
        ),
        "token_financial_gate": "pass",
        "blockers": [],
    }
    assert card["arms"]["treatment"]["recall_context_tokens"] == 120
    assert card["arms"]["treatment"]["total_tokens"] == 680
    assert card["claim_boundary"]["local_signal"] is True
    assert card["claim_boundary"]["representative_evidence"] is False
    assert card["claim_boundary"]["public_claim_authorized"] is False
    assert card["persisted"] is False
    ledger.close()
    store.close()

    rendered = summarize_value_evidence(
        session_intelligence_db=tmp_path / "session_intelligence.db",
        task_intelligence_db=tmp_path / "task_intelligence.sqlite3",
        comparison_id=comparison_id,
    )
    assert rendered == card


def test_missing_declared_use_fails_join_closed_as_inconclusive(tmp_path: Path) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    ledger = TaskIntelligenceLedger(tmp_path / "task_intelligence.sqlite3")
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    comparison_id = str(uuid4())
    memory_id = str(uuid4())
    for condition, declared_use in (("control", True), ("treatment", False)):
        _record_pair_arm(
            store,
            ledger,
            clock,
            comparison_id=comparison_id,
            contract_sha256=contract,
            condition=condition,
            memory_id=memory_id,
            workflow_elapsed_ms=3_000,
            invocation_duration_ms=500,
            input_tokens=600,
            output_tokens=80,
            value_unit_results={"accepted-change": True},
            declared_use=declared_use,
        )

    card = build_value_signal_card(
        store,
        ledger,
        comparison_id=comparison_id,
    )
    assert card["decision"]["class"] == "inconclusive"
    assert "treatment-declared-use-missing" in card["decision"]["blockers"]
    assert card["claim_boundary"]["local_signal"] is False
    ledger.close()
    store.close()


def test_task_trace_must_match_frozen_question_and_rubric(tmp_path: Path) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    ledger = TaskIntelligenceLedger(tmp_path / "task_intelligence.sqlite3")
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    comparison_id = str(uuid4())
    memory_id = str(uuid4())
    _record_pair_arm(
        store,
        ledger,
        clock,
        comparison_id=comparison_id,
        contract_sha256=contract,
        condition="control",
        memory_id=memory_id,
        workflow_elapsed_ms=3_000,
        invocation_duration_ms=500,
        input_tokens=600,
        output_tokens=80,
        value_unit_results={"accepted-change": True},
    )
    _record_pair_arm(
        store,
        ledger,
        clock,
        comparison_id=comparison_id,
        contract_sha256=contract,
        condition="treatment",
        memory_id=memory_id,
        workflow_elapsed_ms=3_000,
        invocation_duration_ms=500,
        input_tokens=600,
        output_tokens=80,
        value_unit_results={"accepted-change": True},
        task="different frozen question",
    )

    card = build_value_signal_card(
        store,
        ledger,
        comparison_id=comparison_id,
    )
    assert card["decision"]["class"] == "inconclusive"
    assert "task-trace-unavailable-or-binding-mismatch" in card["decision"][
        "blockers"
    ]
    assert card["claim_boundary"]["local_signal"] is False
    ledger.close()
    store.close()


def test_fast_response_cannot_masquerade_as_faster_workflow(tmp_path: Path) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    ledger = TaskIntelligenceLedger(tmp_path / "task_intelligence.sqlite3")
    contract = _register_contract(
        store, preregistered_at_utc="2026-08-27T12:01:00+00:00"
    )
    comparison_id = str(uuid4())
    memory_id = str(uuid4())
    for condition, workflow_ms, invocation_ms in (
        ("control", 3_000, 900),
        ("treatment", 5_000, 100),
    ):
        _record_pair_arm(
            store,
            ledger,
            clock,
            comparison_id=comparison_id,
            contract_sha256=contract,
            condition=condition,
            memory_id=memory_id,
            workflow_elapsed_ms=workflow_ms,
            invocation_duration_ms=invocation_ms,
            input_tokens=600,
            output_tokens=80,
            value_unit_results={"accepted-change": True},
        )
    card = build_value_signal_card(
        store,
        ledger,
        comparison_id=comparison_id,
    )
    assert card["arms"]["treatment"]["invocation_duration_ms"] < (
        card["arms"]["control"]["invocation_duration_ms"]
    )
    assert card["decision"]["workflow_elapsed_delta_ms"] == 2_000
    assert card["decision"]["class"] == "no-lift-harm"
    ledger.close()
    store.close()


def test_more_value_for_more_time_is_quality_first_not_productivity(
    tmp_path: Path,
) -> None:
    clock = _Clock(datetime(2026, 8, 27, 12, 2, tzinfo=timezone.utc))
    store = _store(tmp_path, clock)
    ledger = TaskIntelligenceLedger(tmp_path / "task_intelligence.sqlite3")
    units = [
        {
            "id": unit_id,
            "weight": 1,
            "criterion_sha256": _digest(unit_id),
            "evidence_source": "test",
        }
        for unit_id in ("accepted-change", "durable-proof")
    ]
    contract = _register_contract(
        store,
        preregistered_at_utc="2026-08-27T12:01:00+00:00",
        value_units=units,
    )
    comparison_id = str(uuid4())
    memory_id = str(uuid4())
    for condition, workflow_ms, results in (
        (
            "control",
            3_000,
            {"accepted-change": True, "durable-proof": False},
        ),
        (
            "treatment",
            5_000,
            {"accepted-change": True, "durable-proof": True},
        ),
    ):
        _record_pair_arm(
            store,
            ledger,
            clock,
            comparison_id=comparison_id,
            contract_sha256=contract,
            condition=condition,
            memory_id=memory_id,
            workflow_elapsed_ms=workflow_ms,
            invocation_duration_ms=500,
            input_tokens=600,
            output_tokens=80,
            value_unit_results=results,
        )
    card = build_value_signal_card(
        store,
        ledger,
        comparison_id=comparison_id,
    )
    assert card["decision"]["accepted_value_delta"] == 1.0
    assert card["decision"]["workflow_elapsed_delta_ms"] == 2_000
    assert card["decision"]["class"] == "quality-first-trade"
    ledger.close()
    store.close()
