"""Operator CLI contracts for consent, ingestion, cost, and data control."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.pipeline import session_intelligence as cli


def _read_output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _event(path: Path) -> Path:
    return _write_json(
        path,
        {
            "event_id": "event-1",
            "session_id": "session-1",
            "client_name": "codex",
            "tool_name": "elefante-Recall",
            "started_at": "2026-08-28T16:00:00Z",
            "finished_at": "2026-08-28T16:00:01Z",
            "usage": {
                "kind": "provider_actual",
                "provider": "provider-a",
                "model": "model-a",
                "input_tokens": 100,
                "cached_input_tokens": 25,
                "output_tokens": 20,
                "usage_source": "provider-sdk",
            },
        },
    )


def test_status_is_read_only_until_explicit_consent(tmp_path, capsys) -> None:
    ledger = tmp_path / "session.sqlite3"
    assert cli.main(["--db", str(ledger), "status"]) == 0
    payload = _read_output(capsys)
    assert payload["enabled"] is False
    assert payload["ledger_exists"] is False
    assert not ledger.exists()


def test_consent_requires_exact_confirmation(tmp_path, capsys) -> None:
    ledger = tmp_path / "session.sqlite3"
    result = cli.main(
        [
            "--db",
            str(ledger),
            "consent",
            "--purpose",
            "usage_analytics",
            "--confirm",
            "yes",
        ]
    )
    assert result == 1
    assert "--confirm ENABLE" in _read_output(capsys)["error"]
    assert not ledger.exists()


def test_cli_consent_provider_ingest_signal_and_export_are_metadata_only(
    tmp_path, capsys
) -> None:
    ledger = tmp_path / "session.sqlite3"
    snapshot = tmp_path / "snapshot.json"
    common = ["--db", str(ledger), "--snapshot", str(snapshot)]
    assert cli.main(
        common
        + [
            "consent",
            "--purpose",
            "usage_analytics",
            "--purpose",
            "provider_usage",
            "--confirm",
            "ENABLE",
        ]
    ) == 0
    _read_output(capsys)

    assert cli.main(common + ["ingest", str(_event(tmp_path / "event.json"))]) == 0
    receipt = _read_output(capsys)
    assert receipt["receipt"]["evidence_class"] == "provider_actual"

    assert cli.main(common + ["signal"]) == 0
    card = _read_output(capsys)
    assert card["usage"]["actual"]["event_count"] == 1
    assert card["accepted_outcome_evidence"]["accepted_outcome_status"] == "UNKNOWN"

    exported = tmp_path / "export.json"
    assert cli.main(common + ["export", str(exported)]) == 0
    summary = _read_output(capsys)
    assert summary["metadata_only"] is True
    encoded = exported.read_text(encoding="utf-8").lower()
    assert "private prompt" not in encoded
    assert "raw_response" not in encoded


def test_cli_delete_requires_exact_record_confirmation(tmp_path, capsys) -> None:
    ledger = tmp_path / "session.sqlite3"
    common = ["--db", str(ledger)]
    assert cli.main(
        common
        + [
            "consent",
            "--purpose",
            "usage_analytics",
            "--purpose",
            "provider_usage",
            "--confirm",
            "ENABLE",
        ]
    ) == 0
    _read_output(capsys)
    assert cli.main(common + ["ingest", str(_event(tmp_path / "event.json"))]) == 0
    _read_output(capsys)

    assert cli.main(
        common + ["delete", "--event-id", "event-1", "--confirm", "wrong"]
    ) == 1
    assert "matching --event-id" in _read_output(capsys)["error"]
    assert cli.main(
        common + ["delete", "--event-id", "event-1", "--confirm", "event-1"]
    ) == 0
    assert _read_output(capsys)["deleted_records"] == 1
