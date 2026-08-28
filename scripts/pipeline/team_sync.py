#!/usr/bin/env python3
"""Local CLI for signed, scope-bound Team Sync bundles.

The command is deliberately a thin adapter over :mod:`src.collaboration.team_sync`.
It opens Elefante's configured vector store, never accepts a store path or a
secret value on the command line, and keeps import dry-run-first.  The bundle
format, conflict detection, embedding regeneration, and partial-write rollback
remain owned by the existing Team Sync API.

Examples::

    python scripts/pipeline/team_sync.py export \
        --scope project:example \
        --memory-id MEMORY_UUID \
        --key-file /path/to/team-sync.key \
        --output team-sync.bundle

    python scripts/pipeline/team_sync.py inspect team-sync.bundle \
        --key-file /path/to/team-sync.key

    python scripts/pipeline/team_sync.py import team-sync.bundle \
        --key-file /path/to/team-sync.key \
        --scope project:example

    python scripts/pipeline/team_sync.py import team-sync.bundle \
        --key-file /path/to/team-sync.key \
        --scope project:example \
        --apply \
        --confirm-scope project:example \
        --confirm-stopped STOPPED \
        --backup-archive /path/to/verified-backup.zip
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID


# Allow direct execution from any working directory while keeping imports
# rooted in the checkout that owns this script.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.collaboration.team_sync import (  # noqa: E402
    MAX_BUNDLE_BYTES,
    apply_team_import,
    build_team_import_plan,
    create_signed_bundle,
    verify_signed_bundle,
)


MAX_EXISTING_MEMORIES = 1_000_001
MAX_OUTPUT_BYTES = 64 * 1024
MAX_OUTPUT_IDS = 100
MAX_OUTPUT_TEXT = 256
OWNER_READ_ONLY = 0o400
OWNER_READ_WRITE = 0o600


class TeamSyncCliError(ValueError):
    """Raised when local CLI input or local safety checks fail."""


def _bounded_text(value: Any, *, limit: int = MAX_OUTPUT_TEXT) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _bounded_ids(values: Iterable[Any]) -> tuple[list[str], bool]:
    normalized = [str(value) for value in values]
    return normalized[:MAX_OUTPUT_IDS], len(normalized) > MAX_OUTPUT_IDS


def _bounded_pairs(values: Iterable[Iterable[Any]]) -> tuple[list[list[str]], bool]:
    normalized = [[str(part) for part in pair] for pair in values]
    return normalized[:MAX_OUTPUT_IDS], len(normalized) > MAX_OUTPUT_IDS


def _emit(result: dict[str, Any]) -> None:
    """Emit one bounded, JSON-safe line and never include secrets."""
    try:
        rendered = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        rendered = json.dumps(
            {
                "status": "error",
                "error": "CLI result was not JSON-serializable",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    if len(rendered.encode("utf-8")) > MAX_OUTPUT_BYTES:
        rendered = json.dumps(
            {
                "status": "error",
                "error": "CLI result exceeded the output size limit",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    print(rendered)


def _error_text(error: Exception) -> str:
    message = " ".join(str(error).split())
    return _bounded_text(message or type(error).__name__)


def load_hmac_key(path: str | Path) -> bytes:
    """Load an HMAC key from an owner-only regular file.

    The final path component is checked with ``lstat`` and opened with
    ``O_NOFOLLOW`` when the platform provides it.  On POSIX, only ``0400`` and
    ``0600`` are accepted.  The key is returned as raw bytes; it is never
    logged or included in CLI output.
    """
    if path is None or not str(path).strip():
        raise TeamSyncCliError("--key-file is required")
    candidate = Path(path).expanduser()

    try:
        initial = os.lstat(candidate)
    except FileNotFoundError as error:
        raise TeamSyncCliError("HMAC key file was not found") from error
    except OSError as error:
        raise TeamSyncCliError("HMAC key file could not be inspected") from error

    if stat.S_ISLNK(initial.st_mode):
        raise TeamSyncCliError("HMAC key file must not be a symlink")
    if not stat.S_ISREG(initial.st_mode):
        raise TeamSyncCliError("HMAC key file must be a regular file")
    if os.name == "posix" and stat.S_IMODE(initial.st_mode) not in (
        OWNER_READ_ONLY,
        OWNER_READ_WRITE,
    ):
        raise TeamSyncCliError("HMAC key file permissions must be 0400 or 0600")

    flags = os.O_RDONLY
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    flags |= no_follow
    descriptor: int | None = None
    try:
        descriptor = os.open(candidate, flags)
        current = os.fstat(descriptor)
        if stat.S_ISLNK(current.st_mode) or not stat.S_ISREG(current.st_mode):
            raise TeamSyncCliError("HMAC key file must be a stable regular file")
        if current.st_dev != initial.st_dev or current.st_ino != initial.st_ino:
            raise TeamSyncCliError("HMAC key file changed while it was opened")
        if os.name == "posix" and stat.S_IMODE(current.st_mode) not in (
            OWNER_READ_ONLY,
            OWNER_READ_WRITE,
        ):
            raise TeamSyncCliError("HMAC key file permissions must be 0400 or 0600")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = None
            key = stream.read()
    except TeamSyncCliError:
        raise
    except OSError as error:
        raise TeamSyncCliError("HMAC key file could not be read") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if len(key) < 32:
        raise TeamSyncCliError("Team Sync HMAC key must contain at least 32 bytes")
    return key


def get_configured_vector_store() -> Any:
    """Return the configured local vector store through the canonical factory."""
    from src.core.vector_store import get_vector_store

    return get_vector_store()


def get_configured_embedding_service() -> Any:
    """Return the configured local embedding service through its factory."""
    from src.core.embeddings import get_embedding_service

    return get_embedding_service()


def verify_binary_backup(path: str | Path) -> dict[str, Any]:
    """Validate a checksummed Elefante binary backup without extracting it."""
    from scripts.lifecycle.restore_elefante_data import read_verified_manifest

    try:
        manifest = read_verified_manifest(Path(path).expanduser())
    except (FileNotFoundError, OSError, ValueError) as error:
        raise TeamSyncCliError(
            f"verified binary backup check failed: {error}"
        ) from error
    if not isinstance(manifest, dict):
        raise TeamSyncCliError("verified binary backup manifest is invalid")
    return manifest


def _require_scope(value: str | None, *, option: str = "--scope") -> str:
    scope = str(value or "").strip()
    if not scope:
        raise TeamSyncCliError(f"{option} requires a non-empty exact scope")
    return scope


def _parse_memory_ids(values: Iterable[str] | None) -> list[UUID]:
    raw_values = list(values or [])
    if not raw_values:
        raise TeamSyncCliError("export requires at least one repeated --memory-id")
    parsed: list[UUID] = []
    seen: set[UUID] = set()
    for raw_value in raw_values:
        try:
            memory_id = UUID(str(raw_value))
        except (AttributeError, ValueError) as error:
            raise TeamSyncCliError(
                f"invalid --memory-id: {_bounded_text(raw_value)}"
            ) from error
        if memory_id in seen:
            raise TeamSyncCliError(f"duplicate --memory-id: {memory_id}")
        seen.add(memory_id)
        parsed.append(memory_id)
    return parsed


def _parse_exported_at(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise TeamSyncCliError("--exported-at must be ISO-8601") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def _fetch_memories_by_id(store: Any, memory_ids: Iterable[UUID]) -> list[Any]:
    """Fetch exactly the user-allowlisted IDs from the configured store."""
    requested = list(memory_ids)
    getter = getattr(store, "get_memory", None) or getattr(store, "get_by_id", None)
    if callable(getter):
        memories = []
        for memory_id in requested:
            memory = await getter(memory_id)
            if memory is None:
                raise TeamSyncCliError(f"memory ID was not found: {memory_id}")
            memories.append(memory)
        return memories

    get_all = getattr(store, "get_all", None)
    if not callable(get_all):
        raise TeamSyncCliError("configured vector store cannot retrieve memories")
    all_memories = await get_all(limit=MAX_EXISTING_MEMORIES)
    by_id = {str(memory.id): memory for memory in all_memories}
    missing = [str(memory_id) for memory_id in requested if str(memory_id) not in by_id]
    if missing:
        raise TeamSyncCliError("memory IDs were not found: " + ", ".join(missing))
    return [by_id[str(memory_id)] for memory_id in requested]


async def _fetch_all_memories(store: Any) -> list[Any]:
    get_all = getattr(store, "get_all", None)
    if not callable(get_all):
        raise TeamSyncCliError("configured vector store cannot inspect memories")
    memories = list(await get_all(limit=MAX_EXISTING_MEMORIES))
    if len(memories) >= MAX_EXISTING_MEMORIES:
        raise TeamSyncCliError(
            f"target store exceeds the safe inspection limit of {MAX_EXISTING_MEMORIES - 1} memories"
        )
    return memories


def _store_type(store: Any) -> str:
    config = getattr(store, "config", None)
    elefante = getattr(config, "elefante", None)
    vector_config = getattr(elefante, "vector_store", None)
    configured_type = getattr(vector_config, "type", None)
    return _bounded_text(configured_type or type(store).__name__)


def _close_store(store: Any) -> None:
    close = getattr(store, "close", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        asyncio.run(result)


def _bundle_summary(payload: dict[str, Any]) -> dict[str, Any]:
    record_ids = [
        item.get("memory", {}).get("id")
        for item in payload.get("records", [])
        if isinstance(item, dict) and isinstance(item.get("memory"), dict)
    ]
    ids, truncated = _bounded_ids(record_ids)
    return {
        "format": _bounded_text(payload.get("format", "")),
        "format_version": payload.get("format_version"),
        "source_id": _bounded_text(payload.get("source_id", "")),
        "scope": _bounded_text(payload.get("scope", "")),
        "exported_at": _bounded_text(payload.get("exported_at", "")),
        "count": payload.get("count", 0),
        "memory_ids": ids,
        "memory_ids_truncated": truncated,
        "signature_verified": True,
    }


def _read_bundle(path: str | Path) -> bytes:
    candidate = Path(path).expanduser()
    try:
        size = candidate.stat().st_size
    except FileNotFoundError as error:
        raise TeamSyncCliError("Team Sync bundle was not found") from error
    except OSError as error:
        raise TeamSyncCliError("Team Sync bundle could not be inspected") from error
    if size > MAX_BUNDLE_BYTES:
        raise TeamSyncCliError("Team Sync bundle exceeds the safe size limit")
    try:
        return candidate.read_bytes()
    except OSError as error:
        raise TeamSyncCliError("Team Sync bundle could not be read") from error


def _write_bundle(path: str | Path, bundle: bytes) -> Path:
    candidate = Path(path).expanduser()
    try:
        existing = os.lstat(candidate)
    except FileNotFoundError:
        existing = None
    except OSError as error:
        raise TeamSyncCliError("export output could not be inspected") from error
    if existing is not None and stat.S_ISLNK(existing.st_mode):
        raise TeamSyncCliError("export output must not be a symlink")
    if not isinstance(bundle, bytes) or len(bundle) > MAX_BUNDLE_BYTES:
        raise TeamSyncCliError("Team Sync bundle size is invalid")
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(candidate, flags | no_follow, 0o600)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as output:
                descriptor = -1
                output.write(bundle)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except OSError as error:
        raise TeamSyncCliError("Team Sync bundle could not be written") from error
    return candidate.resolve()


def _import_summary(
    plan: Any,
    *,
    target_count: int,
    vector_store_type: str,
    dry_run: bool,
    backup_verified: bool = False,
) -> dict[str, Any]:
    importable_ids, importable_truncated = _bounded_ids(
        memory.id for memory in plan.importable
    )
    identical_ids, identical_truncated = _bounded_ids(plan.identical_ids)
    conflicting_ids, conflicting_truncated = _bounded_ids(plan.conflicting_ids)
    semantic_conflicts, semantic_truncated = _bounded_pairs(plan.semantic_conflicts)
    return {
        "status": "ok",
        "command": "import",
        "dry_run": dry_run,
        "applied": False,
        "source_id": _bounded_text(plan.source_id),
        "scope": _bounded_text(plan.scope),
        "vector_store_type": vector_store_type,
        "source_count": len(plan.importable)
        + len(plan.identical_ids)
        + len(plan.conflicting_ids),
        "target_count": target_count,
        "target_non_empty": target_count > 0,
        "importable_count": len(plan.importable),
        "importable_ids": importable_ids,
        "importable_ids_truncated": importable_truncated,
        "identical_count": len(plan.identical_ids),
        "identical_ids": identical_ids,
        "identical_ids_truncated": identical_truncated,
        "conflicting_count": len(plan.conflicting_ids),
        "conflicting_ids": conflicting_ids,
        "conflicting_ids_truncated": conflicting_truncated,
        "semantic_conflict_count": len(plan.semantic_conflicts),
        "semantic_conflicts": semantic_conflicts,
        "semantic_conflicts_truncated": semantic_truncated,
        "can_apply": bool(plan.can_apply),
        "deletes": 0,
        "overwrites": 0,
        "backup_required": target_count > 0,
        "backup_verified": backup_verified,
    }


def _command_export(args: argparse.Namespace) -> dict[str, Any]:
    key = load_hmac_key(args.key_file)
    scope = _require_scope(args.scope)
    memory_ids = _parse_memory_ids(args.memory_ids)
    output_value = args.output or args.output_path
    if not output_value:
        raise TeamSyncCliError("export requires --output PATH")
    exported_at = _parse_exported_at(args.exported_at)

    store = None
    try:
        store = get_configured_vector_store()
        memories = asyncio.run(_fetch_memories_by_id(store, memory_ids))
        bundle = create_signed_bundle(
            memories,
            source_id=args.source_id,
            scope=scope,
            memory_ids=memory_ids,
            key=key,
            exported_at=exported_at,
        )
        output_path = _write_bundle(output_value, bundle)
        result = _bundle_summary(verify_signed_bundle(bundle, key=key))
        result.update(
            {
                "status": "ok",
                "command": "export",
                "output": _bounded_text(output_path),
                "vector_store_type": _store_type(store),
                "requested_count": len(memory_ids),
            }
        )
        return result
    finally:
        if store is not None:
            _close_store(store)


def _command_inspect(args: argparse.Namespace) -> dict[str, Any]:
    key = load_hmac_key(args.key_file)
    payload = verify_signed_bundle(_read_bundle(args.bundle), key=key)
    if args.expected_scope is not None:
        expected_scope = _require_scope(args.expected_scope, option="--scope")
        if payload.get("scope") != expected_scope:
            raise TeamSyncCliError("bundle scope does not exactly match --scope")
    result = _bundle_summary(payload)
    result.update({"status": "ok", "command": "inspect", "dry_run": True})
    return result


def _command_import(args: argparse.Namespace) -> dict[str, Any]:
    key = load_hmac_key(args.key_file)
    payload = verify_signed_bundle(_read_bundle(args.bundle), key=key)
    bundle_scope = _require_scope(str(payload.get("scope") or ""))
    if args.accepted_scope is None:
        if args.apply:
            raise TeamSyncCliError("--apply requires an explicit --scope")
        accepted_scope = bundle_scope
    else:
        accepted_scope = _require_scope(args.accepted_scope)

    store = None
    try:
        store = get_configured_vector_store()
        existing = asyncio.run(_fetch_all_memories(store))
        plan = build_team_import_plan(
            payload,
            existing,
            accepted_scope=accepted_scope,
        )
        if not args.apply:
            return _import_summary(
                plan,
                target_count=len(existing),
                vector_store_type=_store_type(store),
                dry_run=True,
            )

        if args.confirm_scope != plan.scope:
            raise TeamSyncCliError(
                "--apply requires --confirm-scope to exactly match the bundle scope"
            )
        if args.confirm_stopped != "STOPPED":
            raise TeamSyncCliError("--apply requires --confirm-stopped STOPPED")

        backup_verified = False
        if len(existing) > 0:
            if not args.backup_archive:
                raise TeamSyncCliError(
                    "--apply requires --backup-archive with a non-empty target store"
                )
            verify_binary_backup(args.backup_archive)
            backup_verified = True
        elif args.backup_archive:
            verify_binary_backup(args.backup_archive)
            backup_verified = True

        embedding_service = get_configured_embedding_service()
        preload = getattr(embedding_service, "_load_model", None)
        if callable(preload):
            preload()
        imported_ids = asyncio.run(
            apply_team_import(
                plan,
                store,
                embedding_service,
                invocation_mode="user_directed",
                confirm_scope=plan.scope,
            )
        )
        result = _import_summary(
            plan,
            target_count=len(existing),
            vector_store_type=_store_type(store),
            dry_run=False,
            backup_verified=backup_verified,
        )
        bounded_imported_ids, imported_truncated = _bounded_ids(imported_ids)
        result.update(
            {
                "applied": True,
                "imported_count": len(imported_ids),
                "imported_ids": bounded_imported_ids,
                "imported_ids_truncated": imported_truncated,
                "embeddings_regenerated": len(imported_ids),
                "rollback": "delegated_to_team_sync_api",
            }
        )
        return result
    finally:
        if store is not None:
            _close_store(store)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local signed, scope-bound Team Sync CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser(
        "export", help="Export an explicit scoped ID allowlist"
    )
    export.add_argument("output_path", nargs="?", help=argparse.SUPPRESS)
    export.add_argument("--scope", required=True, help="Exact memory scope")
    export.add_argument(
        "--memory-id",
        dest="memory_ids",
        action="append",
        required=True,
        help="Memory UUID to export; repeat for every record",
    )
    export.add_argument(
        "--source-id",
        default="local-cli",
        help="Stable source identifier stored in the bundle (default: local-cli)",
    )
    export.add_argument("--key-file", required=True, help="Owner-only HMAC key file")
    export.add_argument("--output", help="Bundle output path")
    export.add_argument(
        "--exported-at",
        help="Optional ISO-8601 timestamp for reproducible exports",
    )

    inspect_parser = subparsers.add_parser(
        "inspect", help="Verify and summarize a bundle"
    )
    inspect_parser.add_argument("bundle", help="Signed Team Sync bundle")
    inspect_parser.add_argument(
        "--key-file", required=True, help="Owner-only HMAC key file"
    )
    inspect_parser.add_argument(
        "--scope",
        "--expected-scope",
        dest="expected_scope",
        help="Optional exact scope assertion",
    )

    import_parser = subparsers.add_parser(
        "import",
        help="Inspect or add non-conflicting records from a bundle",
    )
    import_parser.add_argument("bundle", help="Signed Team Sync bundle")
    import_parser.add_argument(
        "--key-file", required=True, help="Owner-only HMAC key file"
    )
    import_parser.add_argument(
        "--scope",
        "--accepted-scope",
        dest="accepted_scope",
        help="Exact target scope; required explicitly for --apply",
    )
    mode = import_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply only after exact scope, STOPPED, and backup gates",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect only (the default)",
    )
    import_parser.add_argument(
        "--confirm-scope",
        default="",
        help="Must exactly equal the signed bundle scope with --apply",
    )
    import_parser.add_argument(
        "--confirm-stopped",
        default="",
        help="Must be exactly STOPPED with --apply",
    )
    import_parser.add_argument(
        "--backup-archive",
        "--backup",
        dest="backup_archive",
        default="",
        help="Verified binary backup required for a non-empty target",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            result = _command_export(args)
        elif args.command == "inspect":
            result = _command_inspect(args)
        elif args.command == "import":
            result = _command_import(args)
        else:  # pragma: no cover - argparse enforces the subcommands
            raise TeamSyncCliError("unknown Team Sync command")
    except Exception as error:
        _emit(
            {
                "status": "error",
                "command": getattr(args, "command", "unknown"),
                "error": _error_text(error),
            }
        )
        return 1
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
