"""Focused contracts for the isolated Session Intelligence core."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.session_intelligence import (
    AntiSurveillanceError,
    ConsentRequiredError,
    EvidenceClass,
    IdempotencyConflictError,
    InvocationEvent,
    PrivacyViolationError,
    PURPOSE_ENTERPRISE_TRAINING,
    PURPOSE_PROVIDER_USAGE,
    PURPOSE_USAGE_ANALYTICS,
    RateCard,
    SCHEMA_VERSION,
    SessionIntelligenceError,
    SessionIntelligenceLedger,
    UnknownEventError,
    UNKNOWN,
    OutcomeEvidence,
    fingerprint_query,
)


NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _actual_event(
    event_id: str = "event-1",
    *,
    session_id: str = "session-1",
    started_at: datetime = NOW,
    finished_at: datetime = NOW + timedelta(seconds=2),
    rate_card_id: str | None = None,
    rate_card_version: str | None = None,
    idempotency_key: str | None = None,
) -> InvocationEvent:
    return InvocationEvent.provider_actual(
        event_id=event_id,
        invocation_id=f"invocation-{event_id}",
        session_id=session_id,
        client_name="Codex CLI",
        tool_name="elefante-Recall",
        started_at=started_at,
        finished_at=finished_at,
        provider="provider-a",
        model="model-a",
        input_tokens=1_000_000,
        cached_input_tokens=500_000,
        output_tokens=100_000,
        usage_source="provider-sdk",
        returned_memory_ids=("memory-b", "memory-a"),
        query_fingerprint=fingerprint_query("private task text", "local-key"),
        rate_card_id=rate_card_id,
        rate_card_version=rate_card_version,
        idempotency_key=idempotency_key,
    )


def _estimated_event(
    event_id: str = "estimated-1",
    *,
    session_id: str = "session-1",
    finished_at: datetime = NOW + timedelta(seconds=3),
) -> InvocationEvent:
    return InvocationEvent.estimated(
        event_id=event_id,
        invocation_id=f"invocation-{event_id}",
        session_id=session_id,
        client_name="VS Code Copilot",
        tool_name="elefante-Memory",
        started_at=NOW,
        finished_at=finished_at,
        input_tokens=300,
        output_tokens=120,
        overhead_tokens=20,
        estimator="local-token-counter-v1",
    )


def _grant_usage(ledger: SessionIntelligenceLedger) -> None:
    ledger.grant_consent(
        {PURPOSE_USAGE_ANALYTICS, PURPOSE_PROVIDER_USAGE},
        consent_version="consent-v1",
        at=NOW,
    )


def _rate_card(*, card_id: str = "card-a", version: str = "2026-08") -> RateCard:
    return RateCard(
        rate_card_id=card_id,
        version=version,
        provider="provider-a",
        model="model-a",
        currency="USD",
        effective_from=NOW - timedelta(days=1),
        source="provider-published-rate-card",
        input_uncached_per_million="3.00",
        input_cached_per_million="1.00",
        output_per_million="5.00",
    )


def test_schema_is_explicitly_versioned_and_disabled_by_default(tmp_path) -> None:
    path = tmp_path / "session-intelligence.sqlite3"
    ledger = SessionIntelligenceLedger(path)

    assert ledger.consent_status() == {
        "schema_version": SCHEMA_VERSION,
        "enabled": False,
        "purposes": [],
    }
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert connection.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()[0] == str(SCHEMA_VERSION)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    connection.close()
    assert {"usage_events", "session_records", "outcome_evidence", "rate_cards"} <= tables
    ledger.close()


def test_disabled_by_default_blocks_persistence_before_any_event_write(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite3"
    ledger = SessionIntelligenceLedger(path)

    with pytest.raises(ConsentRequiredError):
        ledger.ingest_event(_estimated_event())

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM session_records").fetchone()[0] == 0
    connection.close()
    ledger.close()


def test_provider_actual_requires_its_own_purpose(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)

    with pytest.raises(ConsentRequiredError):
        ledger.ingest_event(_actual_event())

    estimated = ledger.ingest_event(_estimated_event())
    assert estimated.persisted is True
    assert estimated.evidence_class is EvidenceClass.LOCAL_ESTIMATED
    ledger.close()


def test_actual_and_estimated_usage_remain_separate_across_restart(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite3"
    ledger = SessionIntelligenceLedger(path)
    _grant_usage(ledger)
    ledger.ingest_event(_actual_event())
    ledger.ingest_event(_estimated_event())
    ledger.close()

    reopened = SessionIntelligenceLedger(path)
    events = reopened.inspect_events()
    assert [event["usage"]["kind"] for event in events] == [
        "provider_actual",
        "estimated",
    ]
    actual, estimated = events
    assert actual["usage"]["evidence_class"] == EvidenceClass.PROVIDER_ACTUAL.value
    assert actual["usage"]["input_tokens"] == 1_000_000
    assert "estimated_input_tokens" not in actual["usage"]
    assert estimated["usage"]["evidence_class"] == EvidenceClass.LOCAL_ESTIMATED.value
    assert estimated["usage"]["estimated_input_tokens"] == 300
    assert "input_tokens" not in estimated["usage"]
    assert reopened.consent_status()["enabled"] is True
    reopened.close()


def test_usage_mapping_rejects_actual_and_estimated_fields_together() -> None:
    with pytest.raises(SessionIntelligenceError):
        InvocationEvent.from_dict(
            {
                "event_id": "mixed-event",
                "session_id": "session-1",
                "client_name": "codex",
                "tool_name": "tool",
                "started_at": NOW,
                "finished_at": NOW,
                "usage_kind": "estimated",
                "estimated_input_tokens": 10,
                "provider_input_tokens": 11,
            }
        )


def test_idempotency_is_exact_and_conflicting_reuse_fails(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    event = _actual_event(idempotency_key="same-request")

    first = ledger.ingest_event(event)
    duplicate = ledger.ingest_event(event)
    assert first.persisted is True
    assert duplicate.duplicate is True
    assert duplicate.persisted is False

    conflicting = _actual_event(
        event_id="event-2",
        idempotency_key="same-request",
    )
    with pytest.raises(IdempotencyConflictError):
        ledger.ingest_event(conflicting)

    changed = InvocationEvent.provider_actual(
        event_id=event.event_id,
        invocation_id=event.invocation_id,
        session_id=event.session_id,
        client_name=event.client_name,
        tool_name=event.tool_name,
        started_at=event.started_at,
        finished_at=event.finished_at,
        provider="provider-a",
        model="model-a",
        input_tokens=999,
        cached_input_tokens=0,
        output_tokens=1,
    )
    with pytest.raises(IdempotencyConflictError):
        ledger.ingest_event(changed)
    ledger.close()


def test_privacy_boundary_rejects_raw_content_and_only_persists_keyed_fingerprint(
    tmp_path,
) -> None:
    with pytest.raises(PrivacyViolationError):
        InvocationEvent.from_dict(
            {
                "event_id": "bad",
                "session_id": "session",
                "client_name": "codex",
                "tool_name": "tool",
                "started_at": NOW,
                "finished_at": NOW,
                "prompt": "do not persist this private prompt",
                "usage_kind": "estimated",
                "estimated_input_tokens": 10,
            }
        )
    with pytest.raises(PrivacyViolationError):
        InvocationEvent.from_dict(
            {
                "event_id": "bad",
                "session_id": "session",
                "client_name": "codex",
                "tool_name": "tool",
                "started_at": NOW,
                "finished_at": NOW,
                "query_fingerprint": "plain-query",
                "usage_kind": "estimated",
                "estimated_input_tokens": 10,
            }
        )

    secret = "never-store-this-transcript"
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    event = InvocationEvent.estimated(
        event_id="private-event",
        session_id="private-session",
        client_name="codex",
        tool_name="tool",
        started_at=NOW,
        finished_at=NOW,
        input_tokens=12,
        output_tokens=2,
        query_fingerprint=fingerprint_query(secret, "local-key"),
    )
    ledger.ingest_event(event)
    dump = "\n".join(ledger._connection.iterdump())
    assert secret not in dump
    assert "prompt" not in dump.lower()
    assert fingerprint_query(secret, "local-key") in dump
    ledger.close()


def test_retention_pruning_is_bounded_and_runs_on_new_ingest(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3", retention_days=1)
    _grant_usage(ledger)
    old_time = NOW - timedelta(days=2)
    old_event = _actual_event(
        "old-event",
        finished_at=old_time,
        started_at=old_time,
        session_id="old-session",
    )
    ledger.ingest_event(old_event)
    current_event = _estimated_event(
        "current-event",
        session_id="current-session",
        finished_at=NOW,
    )
    ledger.ingest_event(current_event)

    assert ledger.get_event("old-event") is None
    assert ledger.get_event("current-event") is not None
    assert ledger.inspect_session("current-session")["events"][0]["event_id"] == "current-event"
    with pytest.raises(UnknownEventError):
        ledger.inspect_session("old-session")
    ledger.close()


def test_cost_requires_provider_actual_usage_and_matching_versioned_rate_card(
    tmp_path,
) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    card = _rate_card()
    ledger.register_rate_card(card)
    actual = _actual_event(
        rate_card_id=card.rate_card_id,
        rate_card_version=card.version,
    )
    ledger.ingest_event(actual)
    estimated = _estimated_event()
    ledger.ingest_event(estimated)

    actual_cost = ledger.calculate_cost(actual.event_id)
    assert actual_cost.known is True
    assert actual_cost.amount == 2.5
    assert actual_cost.currency == "USD"
    assert actual_cost.rate_card_version == card.version
    assert ledger.calculate_cost(estimated.event_id).status == UNKNOWN
    assert ledger.calculate_cost(estimated.event_id).reason == (
        "estimated_usage_is_not_provider_billing"
    )
    ledger.close()


def test_incomplete_or_mismatched_rate_inputs_remain_unknown(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    incomplete = RateCard(
        rate_card_id="incomplete",
        version="1",
        provider="provider-a",
        model="model-a",
        currency="USD",
        effective_from=NOW,
        source="provider-document",
        input_uncached_per_million="3",
        input_cached_per_million=None,
        output_per_million="5",
    )
    ledger.register_rate_card(incomplete)
    event = _actual_event(
        event_id="incomplete-event",
        rate_card_id="incomplete",
        rate_card_version="1",
    )
    ledger.ingest_event(event)
    result = ledger.calculate_cost(event.event_id)
    assert result.status == UNKNOWN
    assert result.amount is None
    assert result.reason == "rate_card_input_is_incomplete"

    mismatch = RateCard(
        rate_card_id="mismatch",
        version="1",
        provider="provider-a",
        model="other-model",
        currency="USD",
        effective_from=NOW,
        source="provider-document",
        input_uncached_per_million="3",
        input_cached_per_million="1",
        output_per_million="5",
    )
    ledger.register_rate_card(mismatch)
    mismatch_event = _actual_event(
        event_id="mismatch-event",
        rate_card_id="mismatch",
        rate_card_version="1",
    )
    ledger.ingest_event(mismatch_event)
    assert ledger.calculate_cost(mismatch_event.event_id).status == UNKNOWN
    ledger.close()


def test_signal_card_is_deterministic_and_separates_cost_usage_and_outcomes(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    card = _rate_card()
    ledger.register_rate_card(card)
    ledger.ingest_event(
        _actual_event(rate_card_id=card.rate_card_id, rate_card_version=card.version)
    )
    ledger.ingest_event(_estimated_event())

    first = ledger.build_signal_card()
    second = ledger.build_signal_card()
    assert first.to_dict() == second.to_dict()
    assert first.usage["actual"]["input_tokens"] == 1_000_000
    assert first.usage["estimated"]["input_tokens"] == 300
    assert first.cost["status"] == UNKNOWN
    assert first.cost["amount"] == UNKNOWN
    assert first.accepted_outcome_evidence["accepted"] is None
    assert "accepted_outcome_evidence=UNKNOWN" in first.unknowns
    assert "currency_cost_unknown_without_complete_rate_provenance" in first.unknowns
    ledger.close()


def test_signal_card_requires_causal_outcome_evidence_for_accepted_value(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    event = _actual_event()
    ledger.ingest_event(event)
    ledger.ingest_outcome(
        OutcomeEvidence(
            outcome_id="asserted-outcome",
            session_id=event.session_id,
            invocation_id=event.invocation_id,
            evidence_class=EvidenceClass.USER_ASSERTED,
            evidence_source="user-feedback",
            accepted=True,
            created_at=NOW + timedelta(minutes=1),
        )
    )
    asserted_card = ledger.build_signal_card()
    assert asserted_card.accepted_outcome_evidence["accepted"] is None
    assert asserted_card.accepted_outcome_evidence["evidence_class"] == (
        EvidenceClass.USER_ASSERTED.value
    )
    assert "causal_outcome_evidence=UNKNOWN" in asserted_card.unknowns

    ledger.ingest_outcome(
        OutcomeEvidence(
            outcome_id="causal-outcome",
            session_id=event.session_id,
            invocation_id=event.invocation_id,
            evidence_class=EvidenceClass.CAUSALLY_EVALUATED,
            evidence_source="frozen-evaluator",
            accepted=True,
            comparison_id="pair-1",
            comparable=True,
            created_at=NOW + timedelta(minutes=2),
        )
    )
    causal_card = ledger.build_signal_card()
    assert causal_card.accepted_outcome_evidence["accepted"] is True
    assert causal_card.accepted_outcome_evidence["evidence_class"] == (
        EvidenceClass.CAUSALLY_EVALUATED.value
    )
    assert "accepted_outcome_evidence=UNKNOWN" not in causal_card.unknowns
    ledger.close()


def test_inspect_export_and_delete_are_metadata_only_controls(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    event = _actual_event()
    ledger.ingest_event(event)
    ledger.ingest_outcome(
        OutcomeEvidence(
            outcome_id="outcome-1",
            session_id=event.session_id,
            invocation_id=event.invocation_id,
            evidence_class=EvidenceClass.USER_ASSERTED,
            evidence_source="user-feedback",
            accepted=False,
            created_at=NOW + timedelta(seconds=3),
        )
    )

    inspected = ledger.inspect_session(event.session_id)
    exported = ledger.export_data(session_id=event.session_id)
    exported_json = ledger.export_json(session_id=event.session_id)
    assert inspected["events"][0]["event_id"] == event.event_id
    assert len(inspected["outcomes"]) == 1
    assert exported["schema_version"] == SCHEMA_VERSION
    assert json.loads(exported_json) == exported
    encoded = json.dumps(exported, sort_keys=True)
    assert "prompt" not in encoded.lower()
    assert "transcript" not in encoded.lower()
    assert ledger.delete_event(event.event_id) is True
    assert ledger.get_event(event.event_id) is None
    assert ledger.export_data(session_id=event.session_id)["outcomes"] == []
    with pytest.raises(SessionIntelligenceError):
        ledger.delete_all()
    ledger.close()


def test_session_lifecycle_normalizes_client_and_is_inspectable(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    session_id = ledger.start_session(
        session_id="lifecycle-session",
        client_name="Codex CLI",
        started_at=NOW,
        client_session_id="vendor-session",
    )
    assert session_id == "lifecycle-session"
    assert ledger.end_session(session_id, ended_at=NOW + timedelta(minutes=2)) is True
    session = ledger.inspect_session(session_id)["session"]
    assert session["client_name"] == "codex-cli"
    assert session["client_session_id"] == "vendor-session"
    assert session["ended_at"] == "2026-08-28T12:02:00.000000+00:00"
    ledger.close()


def test_enterprise_output_is_aggregate_hypotheses_only_and_fail_closed(tmp_path) -> None:
    ledger = SessionIntelligenceLedger(tmp_path / "ledger.sqlite3")
    _grant_usage(ledger)
    with pytest.raises(ConsentRequiredError):
        ledger.build_enterprise_report()
    ledger.grant_consent(
        {PURPOSE_USAGE_ANALYTICS, PURPOSE_PROVIDER_USAGE, PURPOSE_ENTERPRISE_TRAINING},
        at=NOW,
    )
    ledger.ingest_event(_actual_event())
    ledger.ingest_event(_estimated_event("estimated-2", session_id="session-2"))

    report = ledger.build_enterprise_report(group_by="tool")
    payload = report.to_dict()
    assert payload["hypotheses_only"] is True
    assert payload["employee_ranking"] is False
    assert payload["sensitive_trait_inference"] is False
    assert payload["prohibited_uses"]
    assert [group["aggregate_key"] for group in payload["groups"]] == sorted(
        group["aggregate_key"] for group in payload["groups"]
    )
    assert all(hypothesis["hypothesis_only"] for hypothesis in payload["hypotheses"])
    assert all(
        "employee" not in json.dumps(hypothesis).lower()
        for hypothesis in payload["hypotheses"]
    )
    assert all(
        hypothesis["basis"]["accepted_outcome"] == UNKNOWN
        for hypothesis in payload["hypotheses"]
    )
    with pytest.raises(AntiSurveillanceError):
        ledger.build_enterprise_report(rank_employees=True)
    with pytest.raises(AntiSurveillanceError):
        ledger.build_enterprise_report(group_by="employee")
    with pytest.raises(AntiSurveillanceError):
        ledger.build_enterprise_report(requested_dimensions=("health",))
    ledger.close()
