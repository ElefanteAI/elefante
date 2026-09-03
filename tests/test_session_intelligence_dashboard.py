"""Snapshot-only dashboard surface for Session Intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.dashboard import server


@pytest.mark.asyncio
async def test_missing_session_snapshot_reports_disabled_without_creating_files(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "session-intelligence.json"
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(target))

    result = await server.get_session_intelligence()

    assert result["consent"]["enabled"] is False
    assert result["signal_card"] is None
    assert result["privacy"]["metadata_only"] is True
    assert not target.exists()


@pytest.mark.asyncio
async def test_dashboard_returns_existing_metadata_only_snapshot(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "session-intelligence.json"
    payload = {
        "schema_version": 1,
        "generated_at": "2026-08-28T16:00:00Z",
        "consent": {"schema_version": 1, "enabled": True, "purposes": ["usage_analytics"]},
        "signal_card": {
            "card_id": "card-1", "scope": {},
            "usage": {"actual": {}, "estimated": {}}, "cost": {},
            "accepted_outcome_evidence": {}, "unknowns": [], "hypothesis": "No usage yet.",
        },
        "enterprise_report": None,
        "privacy": {"metadata_only": True},
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(target))

    assert await server.get_session_intelligence() == payload


@pytest.mark.asyncio
async def test_invalid_session_snapshot_fails_without_opening_a_database(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "session-intelligence.json"
    target.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(target))

    with pytest.raises(HTTPException) as captured:
        await server.get_session_intelligence()
    assert captured.value.status_code == 500


@pytest.mark.asyncio
async def test_existing_ledger_without_snapshot_is_unknown_not_disabled(
    tmp_path, monkeypatch
) -> None:
    ledger = tmp_path / "session.sqlite3"
    ledger.write_bytes(b"do not open this database")
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_DB", str(ledger))
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(tmp_path / "missing.json"))
    with pytest.raises(HTTPException) as captured:
        await server.get_session_intelligence()
    assert captured.value.status_code == 500
    assert ledger.read_bytes() == b"do not open this database"


@pytest.mark.asyncio
async def test_malformed_signal_card_is_an_error_not_a_browser_crash(
    tmp_path, monkeypatch
) -> None:
    snapshot = tmp_path / "session.json"
    snapshot.write_text(json.dumps({"consent": {"enabled": True}, "signal_card": {}}))
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(snapshot))
    with pytest.raises(HTTPException) as captured:
        await server.get_session_intelligence()
    assert captured.value.status_code == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    {"signal_card": {"scope": {}, "usage": {}, "cost": {},
                     "accepted_outcome_evidence": {}, "unknowns": [], "hypothesis": ""}},
    {"enterprise_report": {"hypotheses": None, "groups": []}},
    {"enterprise_report": {"hypotheses": [None], "groups": []}},
])
async def test_invalid_nested_evidence_is_unavailable(tmp_path, monkeypatch, invalid):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"consent": {"enabled": True}, **invalid}))
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(snapshot))
    with pytest.raises(HTTPException) as captured:
        await server.get_session_intelligence()
    assert captured.value.status_code == 500


def test_frontend_exposes_signal_cards_cost_unknowns_and_privacy_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    component = (
        root / "src/dashboard/ui/src/components/SessionIntelligencePanel.tsx"
    ).read_text(encoding="utf-8")
    store = (root / "src/dashboard/ui/src/store.ts").read_text(encoding="utf-8")

    assert 'aria-label="Session Intelligence report"' in component
    assert "Usage details" in component
    assert "Verified cost:" in component
    assert "Causal outcome:" in component
    assert "No employee ranking" in component
    assert "'/api/session-intelligence'" in store
