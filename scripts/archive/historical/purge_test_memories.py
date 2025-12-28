"""Purge test memories from the databases.

Default behavior is DRY-RUN.

This is intended to clean up accidental E2E/persistence artifacts that were stored
in the production memory store.

Safety:
- Requires --apply (or --force) to actually delete.
- Requires ELEFANTE_PRIVILEGED=1 and --confirm DELETE for destructive writes.
- Deletions remove from BOTH vector store (Chroma) and graph store (Kuzu).
- Writes a JSON backup before deletion.

Usage:
  python scripts/purge_test_memories.py
  python scripts/purge_test_memories.py --apply
    ELEFANTE_PRIVILEGED=1 python scripts/purge_test_memories.py --apply --confirm DELETE
  python scripts/purge_test_memories.py --ids <uuid> <uuid> --apply

"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import UUID

from pathlib import Path

# Ensure repo root is on sys.path so `import src.*` works when running as a script.
_REPO_ROOT = Path(__file__).resolve()
for _ in range(5):
    candidate = _REPO_ROOT.parent
    if (candidate / "src").exists():
        sys.path.insert(0, str(candidate))
        break
    _REPO_ROOT = candidate

from src.core.orchestrator import get_orchestrator
from src.core.refinery import infer_namespace


@dataclass(frozen=True)
class Candidate:
    memory_id: UUID
    reason: str
    preview: str


def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _backup_dir(default_root: Optional[str] = None) -> Path:
    if default_root:
        return Path(default_root).expanduser().resolve()
    return (Path.home() / ".elefante" / "data" / "backups" / "purge_test_memories").resolve()


def _write_backup(candidates: Sequence[Candidate], dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"purge_test_memories_backup_{_utc_ts()}.json"

    payload: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(),
        "count": len(candidates),
        "items": [
            {
                "memory_id": str(c.memory_id),
                "reason": c.reason,
                "preview": c.preview,
            }
            for c in candidates
        ],
    }

    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out_path


def _safe_preview(text: str, limit: int = 120) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def _looks_test_like_reason(memory) -> Optional[str]:
    custom = memory.metadata.custom_metadata or {}
    namespace = str(custom.get("namespace") or "").strip().lower()
    if namespace == "test":
        return "custom_metadata.namespace=test"

    category = str(memory.metadata.category or "").strip().lower()
    if category == "test":
        return "metadata.category=test"
    if category.startswith("hybrid_test_"):
        return "metadata.category startswith hybrid_test_"

    tags = {t.strip().lower() for t in (memory.metadata.tags or []) if isinstance(t, str) and t.strip()}
    if "test" in tags:
        return "tags contains test"
    if "e2e" in tags:
        return "tags contains e2e"
    if any(t.startswith("hybrid_test_") for t in tags):
        return "tags startswith hybrid_test_"

    content = (memory.content or "").strip().lower()
    if content.startswith("elefante e2e test memory"):
        return "content startswith 'elefante e2e test memory'"
    if content.startswith("hybrid search test memory"):
        return "content startswith 'hybrid search test memory'"

    inferred = infer_namespace(memory)
    if inferred == "test":
        return "inferred namespace=test"

    return None


def _collect_candidates(memories: Iterable) -> List[Candidate]:
    out: List[Candidate] = []
    for m in memories:
        reason = _looks_test_like_reason(m)
        if not reason:
            continue
        if infer_namespace(m) != "test":
            # Keep scope tight: only purge items that the canonical heuristic
            # considers test namespace.
            continue
        out.append(Candidate(memory_id=m.id, reason=reason, preview=_safe_preview(m.content)))
    return out


async def _iter_all_memories(limit: int = 500) -> List:
    orch = get_orchestrator()
    all_memories = []
    offset = 0
    while True:
        page = await orch.list_all_memories(limit=limit, offset=offset)
        if not page:
            break
        all_memories.extend(page)
        offset += len(page)
        if len(page) < limit:
            break
    return all_memories


async def _delete_ids(ids: Sequence[UUID]) -> dict:
    orch = get_orchestrator()

    deleted_vector = 0
    deleted_graph = 0
    failed_vector: List[str] = []
    failed_graph: List[str] = []

    for memory_id in ids:
        ok_graph = await orch.graph_store.delete_entity(memory_id)
        if ok_graph:
            deleted_graph += 1
        else:
            failed_graph.append(str(memory_id))

        # Safety: do not delete from vector store if graph deletion failed.
        if ok_graph:
            ok_vec = await orch.vector_store.delete_memory(memory_id)
            if ok_vec:
                deleted_vector += 1
            else:
                failed_vector.append(str(memory_id))
        else:
            failed_vector.append(str(memory_id))

    return {
        "requested": len(ids),
        "deleted_graph": deleted_graph,
        "deleted_vector": deleted_vector,
        "failed_graph": failed_graph,
        "failed_vector": failed_vector,
    }


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid UUID: {value}") from e


async def main() -> int:
    parser = argparse.ArgumentParser(description="Purge test memories (dry-run by default)")
    parser.add_argument("--apply", action="store_true", help="Actually delete (otherwise dry-run)")
    parser.add_argument("--force", action="store_true", help="Alias for --apply")
    parser.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")
    parser.add_argument("--max-delete", type=int, default=100, help="Safety cap for deletions per run")
    parser.add_argument("--backup-dir", type=str, default="", help="Backup output directory")
    parser.add_argument(
        "--ids",
        nargs="*",
        type=_parse_uuid,
        default=None,
        help="Specific memory UUIDs to delete (bypasses auto-detection)",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply or args.force)

    # Privilege gate for destructive writes
    if apply_changes:
        if not _truthy_env("ELEFANTE_PRIVILEGED"):
            raise SystemExit("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        if (args.confirm or "").strip() != "DELETE":
            raise SystemExit("Refusing to apply: pass --confirm DELETE")

        # If applying, ensure graph DB is available (we require graph+vector delete).
        orch = get_orchestrator()
        try:
            await orch.graph_store.get_stats()
        except Exception as e:
            raise SystemExit(f"Refusing to apply: graph store unavailable/locked: {e}")

    if args.ids:
        candidates = [Candidate(memory_id=i, reason="explicit --ids", preview="") for i in args.ids]
    else:
        memories = await _iter_all_memories()
        candidates = _collect_candidates(memories)

    if not candidates:
        print("No test memories found.")
        return 0

    print(f"Test-memory candidates: {len(candidates)}")
    for c in candidates[:50]:
        print(f"- {c.memory_id} | {c.reason} | {c.preview}")
    if len(candidates) > 50:
        print(f"... ({len(candidates) - 50} more)")

    if not args.apply:
        print("Dry-run only. Re-run with --apply/--force to delete.")
        return 0

    backup_path = _write_backup(candidates, _backup_dir(args.backup_dir or None))
    print(f"Backup written: {backup_path}")

    if len(candidates) > int(args.max_delete):
        raise SystemExit(f"Refusing: would delete {len(candidates)} > --max-delete {args.max_delete}")

    summary = await _delete_ids([c.memory_id for c in candidates])
    print("Deletion summary:")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
