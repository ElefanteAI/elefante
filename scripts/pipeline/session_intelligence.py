#!/usr/bin/env python3
"""Operate Elefante's opt-in, metadata-only Session Intelligence ledger.

The command is the explicit consent and inspection boundary for provider usage,
rate-card authority, Signal Cards, and aggregate enterprise hypotheses. It does
not accept prompts, transcripts, responses, hidden reasoning, or credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.session_intelligence import (  # noqa: E402
    PURPOSE_ENTERPRISE_TRAINING,
    PURPOSE_PROVIDER_USAGE,
    PURPOSE_USAGE_ANALYTICS,
    ConsentRequiredError,
    InvocationEvent,
    OutcomeEvidence,
    RateCard,
    SessionIntelligenceError,
    SessionIntelligenceLedger,
    configured_ledger_path,
    configured_snapshot_path,
    ingest_runtime_usage,
    write_runtime_snapshot,
)


PURPOSES = (
    PURPOSE_USAGE_ANALYTICS,
    PURPOSE_PROVIDER_USAGE,
    PURPOSE_ENTERPRISE_TRAINING,
)
MAX_INPUT_BYTES = 1_048_576


def _json_object(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise FileNotFoundError(f"JSON input is not a regular file: {resolved}")
    if resolved.stat().st_size > MAX_INPUT_BYTES:
        raise SessionIntelligenceError("JSON input exceeds 1048576 bytes.")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SessionIntelligenceError("Input must be UTF-8 JSON.") from error
    if not isinstance(value, dict):
        raise SessionIntelligenceError("Input JSON must contain one object.")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
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


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _require_ledger(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ConsentRequiredError(
            "Session Intelligence is disabled; run the consent command first."
        )
    return resolved


def _refresh(ledger: SessionIntelligenceLedger, snapshot: Path) -> str:
    return write_runtime_snapshot(ledger, snapshot).name


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="Explicit ledger path")
    parser.add_argument(
        "--snapshot", type=Path, default=None, help="Explicit dashboard snapshot path"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="Inspect consent without creating a ledger")

    consent = commands.add_parser("consent", help="Grant explicit purposes")
    consent.add_argument("--purpose", choices=PURPOSES, action="append", required=True)
    consent.add_argument("--consent-version", default="1")
    consent.add_argument("--retention-days", type=int, default=30)
    consent.add_argument("--confirm", required=True, help="Must be exactly ENABLE")

    revoke = commands.add_parser("revoke", help="Revoke purposes")
    revoke.add_argument("--purpose", choices=PURPOSES, action="append")
    revoke.add_argument("--delete-events", action="store_true")
    revoke.add_argument("--confirm-delete", default="", help="Must be exactly DELETE")

    ingest = commands.add_parser("ingest", help="Persist one metadata-only usage event")
    ingest.add_argument("event", type=Path)

    outcome = commands.add_parser("outcome", help="Persist one bounded outcome record")
    outcome.add_argument("event", type=Path)

    rate = commands.add_parser("rate-card", help="Register versioned price authority")
    rate.add_argument("card", type=Path)

    signal = commands.add_parser("signal", help="Build a deterministic Signal Card")
    signal.add_argument("--session-id")
    signal.add_argument("--client-name")

    enterprise = commands.add_parser(
        "enterprise", help="Build aggregate, anti-surveillance training hypotheses"
    )
    enterprise.add_argument("--group-by", choices=("tool", "client", "day"), default="tool")

    export = commands.add_parser("export", help="Export metadata-only ledger records")
    export.add_argument("output", type=Path)
    export.add_argument("--session-id")

    delete = commands.add_parser("delete", help="Delete one event or session recoverably")
    target = delete.add_mutually_exclusive_group(required=True)
    target.add_argument("--event-id")
    target.add_argument("--session-id")
    target.add_argument("--all", action="store_true")
    delete.add_argument("--confirm", required=True)

    commands.add_parser("prune", help="Apply the configured retention window")
    commands.add_parser("snapshot", help="Refresh the safe dashboard snapshot")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ledger_path = (args.db or configured_ledger_path()).expanduser().resolve()
    snapshot_path = (
        args.snapshot or configured_snapshot_path(ledger_path)
    ).expanduser().resolve()
    try:
        if args.command == "status" and not ledger_path.is_file():
            _emit({"schema_version": 1, "enabled": False, "purposes": [], "ledger_exists": False})
            return 0

        if args.command == "consent":
            if args.confirm != "ENABLE":
                raise ConsentRequiredError("Consent requires --confirm ENABLE.")
            purposes = set(args.purpose)
            purposes.add(PURPOSE_USAGE_ANALYTICS)
            with SessionIntelligenceLedger(
                ledger_path, retention_days=args.retention_days
            ) as ledger:
                status = ledger.grant_consent(
                    purposes, consent_version=args.consent_version
                )
                status["snapshot_name"] = _refresh(ledger, snapshot_path)
                _emit(status)
            return 0

        ledger_path = _require_ledger(ledger_path)

        if args.command == "ingest":
            result = ingest_runtime_usage(
                InvocationEvent.from_dict(_json_object(args.event)),
                ledger_path=ledger_path,
                snapshot_path=snapshot_path,
            )
            _emit(result)
            return 0

        with SessionIntelligenceLedger(ledger_path) as ledger:
            if args.command == "status":
                result = ledger.consent_status()
                result["ledger_exists"] = True
            elif args.command == "revoke":
                if args.delete_events and args.confirm_delete != "DELETE":
                    raise SessionIntelligenceError(
                        "Deleting retained events requires --confirm-delete DELETE."
                    )
                result = ledger.revoke_consent(
                    args.purpose, delete_events=args.delete_events
                )
                result["snapshot_name"] = _refresh(ledger, snapshot_path)
            elif args.command == "outcome":
                receipt = ledger.ingest_outcome(
                    OutcomeEvidence.from_dict(_json_object(args.event))
                )
                result = receipt.to_dict()
                result["snapshot_name"] = _refresh(ledger, snapshot_path)
            elif args.command == "rate-card":
                card = ledger.register_rate_card(RateCard.from_dict(_json_object(args.card)))
                result = {
                    "registered": True,
                    "rate_card": card.to_dict(),
                    "snapshot_name": _refresh(ledger, snapshot_path),
                }
            elif args.command == "signal":
                result = ledger.build_signal_card(
                    session_id=args.session_id, client_name=args.client_name
                ).to_dict()
            elif args.command == "enterprise":
                result = ledger.build_enterprise_report(
                    group_by=args.group_by
                ).to_dict()
            elif args.command == "export":
                exported = ledger.export_data(session_id=args.session_id)
                output = _write_json(args.output, exported)
                result = {
                    "exported": True,
                    "output_name": output.name,
                    "event_count": len(exported.get("events", [])),
                    "outcome_count": len(exported.get("outcomes", [])),
                    "metadata_only": True,
                }
            elif args.command == "delete":
                if args.event_id:
                    if args.confirm != args.event_id:
                        raise SessionIntelligenceError(
                            "Event deletion requires --confirm matching --event-id."
                        )
                    deleted = int(ledger.delete_event(args.event_id))
                elif args.session_id:
                    if args.confirm != args.session_id:
                        raise SessionIntelligenceError(
                            "Session deletion requires --confirm matching --session-id."
                        )
                    deleted = ledger.delete_session(args.session_id)
                else:
                    if args.confirm != "DELETE ALL":
                        raise SessionIntelligenceError(
                            "Full deletion requires --confirm 'DELETE ALL'."
                        )
                    deleted = ledger.delete_all(confirm=True)
                result = {
                    "deleted_records": deleted,
                    "snapshot_name": _refresh(ledger, snapshot_path),
                }
            elif args.command == "prune":
                result = {
                    "pruned_records": ledger.prune(),
                    "snapshot_name": _refresh(ledger, snapshot_path),
                }
            elif args.command == "snapshot":
                result = {
                    "snapshot_refreshed": True,
                    "snapshot_name": _refresh(ledger, snapshot_path),
                }
            else:
                raise SessionIntelligenceError(f"Unsupported command: {args.command}")
            _emit(result)
        return 0
    except (FileNotFoundError, OSError, SessionIntelligenceError) as error:
        _emit({"success": False, "error": str(error)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
