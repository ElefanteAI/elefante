"""Focused, disposable tests for the opt-in live Distiller watcher."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.modules.distiller import __main__ as distiller_cli
from src.modules.distiller.privacy import PrivacyFilter
from src.modules.distiller.scanner import (
    MAX_WATCH_INTERVAL,
    MIN_WATCH_INTERVAL,
    SessionInfo,
    SessionScanner,
)


def _session_info(path: str, *, mtime: float = 1.0, size: int = 1) -> SessionInfo:
    """Build metadata without parsing or retaining any transcript content."""
    from datetime import datetime, timezone

    return SessionInfo(
        file_path=path,
        session_id=Path(path).stem,
        format=Path(path).suffix.lstrip("."),
        workspace_id="workspace-fixture",
        size_bytes=size,
        modified_at=datetime.fromtimestamp(mtime, tz=timezone.utc),
    )


@pytest.mark.parametrize("field", [
    "api_key", "password", "client_secret", "AWS_SECRET_ACCESS_KEY", "clientSecret",
    "accessToken", "secret_token", "access_key", "AWS_ACCESS_KEY_ID",
])
def test_privacy_scrubs_explicit_secret_fields_before_ingestion(field):
    secret = "synthetic-credential-" + "x" * 32
    payload = {"nested": [{field: secret}], "token_count": 42, "public_key": "public fixture"}
    scrubbed, count, _ = PrivacyFilter().scrub_payload(payload)
    assert secret not in str(scrubbed)
    assert count == 1
    assert scrubbed["token_count"] == 42
    assert scrubbed["public_key"] == "public fixture"
    assert payload["nested"][0][field] == secret
    assert PrivacyFilter().scrub_payload(scrubbed)[:2] == (scrubbed, 0)


@pytest.mark.parametrize("prefix", ["sk-", "sk-proj-", "sk-admin-"])
def test_privacy_scrubs_prefixed_tokens_in_free_text(prefix, caplog):
    token = prefix + "x" * 40
    scrubbed, result = PrivacyFilter().scrub("Temporary credential: " + token)
    assert token not in scrubbed
    assert result.redactions == 1
    assert token not in caplog.text


def test_privacy_redaction_types_reconcile_across_nested_fields():
    payload = {"api_key": "x" * 40, "nested": [{"password": "y" * 40}, {"clientSecret": "z" * 40}]}
    _, count, kinds = PrivacyFilter().scrub_payload(payload)
    assert count == 3
    assert kinds == ["CREDENTIAL_FIELD(3)"]


def test_watch_detects_new_session_outside_recent_item_cap(tmp_path, monkeypatch):
    """A new, old-mtime file is seen even when 201 files predate the watch."""
    chat_dir = tmp_path / "workspace-fixture" / "chatSessions"
    chat_dir.mkdir(parents=True)
    for index in range(201):
        (chat_dir / f"baseline-{index}.json").write_bytes(b"{}")

    scanner = SessionScanner(storage_root=str(tmp_path))
    real_scan = scanner._iter_session_infos
    new_path = chat_dir / "newly-discovered.json"
    scan_count = 0

    def scan_with_late_file():
        nonlocal scan_count
        scan_count += 1
        if scan_count == 2:
            new_path.write_bytes(b"{}")
            os.utime(new_path, (1, 1))
        return real_scan()

    monkeypatch.setattr(scanner, "_iter_session_infos", scan_with_late_file)

    watched = scanner.watch(interval=1)
    discovered = next(watched)

    assert discovered.session_id == "newly-discovered"
    assert scan_count == 2


def test_watch_prunes_deleted_paths_and_detects_recreated_path(monkeypatch):
    """Deleted metadata does not remain sticky when the path is recreated."""
    first = _session_info("/fixture/session.json", mtime=1.0, size=1)
    scans = iter(
        [
            [first],  # baseline
            [],  # deleted
            [first],  # recreated and therefore new again
        ]
    )
    scanner = SessionScanner(storage_root="/fixture")
    monkeypatch.setattr(scanner, "_iter_session_infos", lambda: iter(next(scans)))
    monkeypatch.setattr("time.sleep", lambda _interval: None)

    watched = scanner.watch(interval=1)
    assert next(watched).session_id == "session"


def test_watch_interval_is_bounded_and_cli_is_opt_in():
    parser = distiller_cli._build_parser()

    default_args = parser.parse_args(["distill"])
    watch_args = parser.parse_args(["distill", "--watch", "--interval", "2.5"])

    assert default_args.watch is False
    assert watch_args.watch is True
    assert watch_args.interval == 2.5
    assert SessionScanner.validate_watch_interval(MIN_WATCH_INTERVAL) == MIN_WATCH_INTERVAL
    assert SessionScanner.validate_watch_interval(MAX_WATCH_INTERVAL) == MAX_WATCH_INTERVAL

    for invalid in (0, -1, float("nan"), float("inf"), MAX_WATCH_INTERVAL + 1):
        with pytest.raises(ValueError):
            SessionScanner.validate_watch_interval(invalid)

    with pytest.raises(SystemExit):
        parser.parse_args(["distill", "--watch", "--interval", "0"])


def test_watch_loop_is_serial_isolates_errors_and_stops_cleanly(monkeypatch, caplog, capsys):
    first = _session_info("/fixture/first.json")
    second = _session_info("/fixture/second.json")
    intervals = []

    class FakeScanner:
        def watch(self, *, interval):
            intervals.append(interval)
            yield first
            yield second
            raise KeyboardInterrupt

    calls = []

    def fake_distill(path, *args, **kwargs):
        calls.append((path, kwargs["ingester"]))
        if path == first.file_path:
            raise RuntimeError("fixture failure")
        return "ok"

    monkeypatch.setattr(distiller_cli, "_distill_one", fake_distill)
    caplog.set_level("ERROR", logger="elefante.distiller.cli")

    result = distiller_cli._watch_sessions(
        FakeScanner(),
        object(),
        object(),
        object(),
        interval=2.5,
    )

    assert result == 0
    assert intervals == [2.5]
    assert calls == [(first.file_path, None), (second.file_path, None)]
    assert any(first.session_id in record.getMessage() for record in caplog.records)
    assert "Live watch stopped." in capsys.readouterr().err


def test_cli_watch_without_store_does_not_pass_an_ingester(monkeypatch):
    info = _session_info("/fixture/session.json")
    captured = []

    class FakeScanner:
        def watch(self, *, interval):
            yield info
            raise KeyboardInterrupt

    monkeypatch.setattr(distiller_cli, "SessionScanner", FakeScanner)
    monkeypatch.setattr(distiller_cli, "ChatParser", lambda: object())
    monkeypatch.setattr(distiller_cli, "PrivacyFilter", lambda: object())
    monkeypatch.setattr(distiller_cli, "SessionTracker", lambda: object())

    def fake_distill(path, *args, **kwargs):
        captured.append(kwargs["ingester"])
        return "ok"

    monkeypatch.setattr(distiller_cli, "_distill_one", fake_distill)
    args = distiller_cli._build_parser().parse_args(["distill", "--watch"])

    assert distiller_cli.cmd_distill(args) == 0
    assert captured == [None]
