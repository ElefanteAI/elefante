"""Runtime and operator-surface contracts for Session Intelligence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.session_intelligence import (
    PURPOSE_ENTERPRISE_TRAINING,
    PURPOSE_PROVIDER_USAGE,
    PURPOSE_USAGE_ANALYTICS,
    ConsentRequiredError,
    RateCard,
    SessionIntelligenceLedger,
    ingest_runtime_usage,
)


NOW = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)


def _event() -> dict:
    return {
        "event_id": "provider-event-1",
        "invocation_id": "provider-invocation-1",
        "session_id": "session-1",
        "client_name": "codex",
        "tool_name": "elefante-Recall",
        "started_at": NOW.isoformat(),
        "finished_at": (NOW + timedelta(seconds=2)).isoformat(),
        "usage": {
            "kind": "provider_actual",
            "provider": "provider-a",
            "model": "model-a",
            "input_tokens": 1_000_000,
            "cached_input_tokens": 500_000,
            "output_tokens": 100_000,
            "usage_source": "provider-sdk",
        },
        "rate_card_id": "provider-a-model-a",
        "rate_card_version": "2026-08",
    }


def _rate_card() -> RateCard:
    return RateCard(
        rate_card_id="provider-a-model-a",
        version="2026-08",
        provider="provider-a",
        model="model-a",
        currency="USD",
        effective_from=NOW - timedelta(days=1),
        source="provider-published-rate-card",
        input_uncached_per_million="3",
        input_cached_per_million="1",
        output_per_million="5",
    )


def test_runtime_ingest_never_creates_an_unconsented_ledger(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    with pytest.raises(ConsentRequiredError):
        ingest_runtime_usage(_event(), ledger_path=ledger_path)
    assert not ledger_path.exists()


def test_runtime_ingest_persists_actual_usage_and_refreshes_safe_snapshot(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    snapshot_path = tmp_path / "session-snapshot.json"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent(
            {
                PURPOSE_USAGE_ANALYTICS,
                PURPOSE_PROVIDER_USAGE,
                PURPOSE_ENTERPRISE_TRAINING,
            },
            at=NOW,
        )
        ledger.register_rate_card(_rate_card())

    result = ingest_runtime_usage(
        _event(), ledger_path=ledger_path, snapshot_path=snapshot_path
    )

    assert result["receipt"]["evidence_class"] == "provider_actual"
    assert result["snapshot_refreshed"] is True
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["signal_card"]["usage"]["actual"]["input_tokens"] == 1_000_000
    assert payload["signal_card"]["cost"]["status"] == "known"
    assert payload["enterprise_report"]["employee_ranking"] is False
    assert payload["privacy"]["prompts_stored"] is False
    encoded = snapshot_path.read_text(encoding="utf-8").lower()
    assert "prompt text" not in encoded
    assert "transcript" in encoded  # the privacy declaration, never transcript data


def test_duplicate_runtime_ingest_is_idempotent_and_refreshes_snapshot(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    snapshot_path = tmp_path / "session-snapshot.json"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent(
            {PURPOSE_USAGE_ANALYTICS, PURPOSE_PROVIDER_USAGE}, at=NOW
        )

    first = ingest_runtime_usage(
        _event(), ledger_path=ledger_path, snapshot_path=snapshot_path
    )
    second = ingest_runtime_usage(
        _event(), ledger_path=ledger_path, snapshot_path=snapshot_path
    )

    assert first["receipt"]["persisted"] is True
    assert second["receipt"]["duplicate"] is True
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert len(ledger.inspect_events()) == 1
