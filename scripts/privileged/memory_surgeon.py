"""Privileged memory debugger: surgical review + deletion.

This tool is DANGEROUS.
- Default: DRY-RUN (no writes).
- To actually delete you must provide:
  - environment: ELEFANTE_PRIVILEGED=1
  - flag: --apply
  - flag: --confirm "DELETE"

What it does:
- Select candidate memories (by ids, query, or built-in rules).
- Computes an "impact report" for each candidate:
  - Temporal relevance score (score + recency + access reinforcement)
  - Graph degree / neighbor list (how many connections will be removed)
  - Safety classification (low/medium/high risk)
- Writes a JSON backup of every candidate before deletion.
- Deletes from BOTH vector store (ChromaDB) and graph store (Kuzu).

This is intended to keep the dashboard graph clean/scalable by removing low-value
artifacts (tests, redundant/archived items), while avoiding deletion of high-value
high-connectivity memories.

Usage examples:
  # Dry-run: list auto-detected test memories + risk scores
  python scripts/privileged/memory_surgeon.py --auto test

  # Delete specific IDs (after review)
  ELEFANTE_PRIVILEGED=1 python scripts/privileged/memory_surgeon.py --ids <uuid> <uuid> --apply --confirm DELETE

  # Delete auto-detected test memories (after review)
  ELEFANTE_PRIVILEGED=1 python scripts/privileged/memory_surgeon.py --auto test --apply --confirm DELETE

  # Select by query (semantic search), then decide by --apply
  python scripts/privileged/memory_surgeon.py --query "Hybrid search test memory" --query-mode semantic

"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import UUID

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
from src.models.query import QueryMode


# If Kuzu is locked by another process (dashboard/MCP), we avoid repeated init attempts.
_GRAPH_LOCKED: bool = False


@dataclass(frozen=True)
class Impact:
    memory_id: UUID
    namespace: str
    category: str
    tags: List[str]
    score: int
    access_count: int
    archived: bool
    deprecated: bool
    status: str
    temporal_score: float
    degree: int
    neighbors: List[str]
    semantic_degree: int
    semantic_max_similarity: float
    semantic_mean_similarity: float
    risk: str
    reason: str
    preview: str


def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _safe_preview(text: str, limit: int = 140) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid UUID: {value}") from e


def _risk_classification(
    *,
    temporal_score: float,
    degree: int,
    semantic_degree: int,
    semantic_max_similarity: float,
    score: int,
    namespace: str,
    archived: bool,
) -> Tuple[str, str]:
    """Classify deletion risk.

    Heuristic, deterministic:
    - High temporal_score or high degree => high risk.
    - Archived/redundant/test namespace => lower risk.
    """

    # Unknown graph connectivity (usually because Kuzu is locked): treat as high risk.
    if degree < 0:
        return "high", "graph connectivity unknown (graph store locked/unavailable)"

    # Hard safety bias: do not auto-delete high-scoring+connected prod memories.
    if namespace != "test" and (score >= 80 or temporal_score >= 0.6) and degree >= 6:
        return "high", "high-value and highly connected"

    # Strong semantic connectivity affects dashboard similarity edges.
    if semantic_degree >= 12 or (semantic_degree >= 6 and semantic_max_similarity >= 0.92):
        if namespace != "test":
            return "high", "high semantic connectivity"

    if namespace == "test":
        if temporal_score < 0.2:
            return "low", "test namespace + low temporal score"
        return "medium", "test namespace + non-trivial temporal score"

    if archived:
        if degree <= 2 and temporal_score < 0.25:
            return "low", "archived + low connectivity"
        return "medium", "archived but connected or temporally relevant"

    if temporal_score >= 0.65 or score >= 90:
        return "high", "high temporal score or high behavioral score"

    if degree >= 10:
        return "high", "high degree"

    if temporal_score < 0.2 and degree <= 2 and score <= 50:
        return "low", "low temporal score + low degree"

    return "medium", "default"


async def _get_semantic_connectivity(
    vector_store,
    memory,
    *,
    k: int = 15,
    min_similarity: float = 0.75,
) -> Tuple[int, float, float]:
    """Compute semantic neighborhood stats using stored embeddings (no external embedding call).

    Returns:
      (semantic_degree, max_similarity, mean_similarity)

    semantic_degree counts neighbors above min_similarity.
    """

    try:
        vector_store._initialize_client()
    except Exception:
        return -1, 0.0, 0.0

    embedding = getattr(memory, "embedding", None)
    if embedding is None:
        return 0, 0.0, 0.0

    # Ask for k+1 because the first result is often the item itself.
    n_results = max(1, int(k)) + 1

    try:
        results = await asyncio.to_thread(
            vector_store._collection.query,
            query_embeddings=[embedding],
            n_results=n_results,
            include=["distances", "ids"],
        )
    except Exception:
        return -1, 0.0, 0.0

    ids = (results or {}).get("ids") or [[]]
    distances = (results or {}).get("distances") or [[]]
    if not ids or not ids[0] or not distances or not distances[0]:
        return 0, 0.0, 0.0

    neighbor_sims: List[float] = []
    for rid, dist in zip(ids[0], distances[0]):
        if str(rid) == str(memory.id):
            continue
        try:
            similarity = 1.0 - float(dist)
        except Exception:
            continue
        similarity = max(0.0, min(1.0, similarity))
        if similarity < float(min_similarity):
            continue
        neighbor_sims.append(similarity)

    if not neighbor_sims:
        return 0, 0.0, 0.0

    return len(neighbor_sims), max(neighbor_sims), (sum(neighbor_sims) / len(neighbor_sims))


async def _get_degree_and_neighbors(graph_store, memory_id: UUID, *, depth: int = 1, neighbor_limit: int = 50) -> Tuple[int, List[str]]:
    global _GRAPH_LOCKED
    if _GRAPH_LOCKED:
        return -1, []

    # Degree: count relationships touching the node.
    degree_query = """
        MATCH (e:Entity)-[r]-(n:Entity)
        WHERE e.id = $id
        RETURN count(r)
    """

    try:
        # Use GraphStore's connection indirectly via execute_query to avoid touching privates.
        result = await graph_store.execute_query(degree_query, {"id": str(memory_id)})
        if result and isinstance(result[0], dict) and "values" in result[0]:
            degree = int(result[0]["values"][0])
        else:
            degree = 0
    except Exception as e:
        msg = str(e).lower()
        if "lock" in msg or "locked" in msg:
            _GRAPH_LOCKED = True
        return -1, []

    # Neighbors (best-effort)
    try:
        entities = await graph_store.get_neighbors(memory_id, depth=depth)
        neighbors = [str(e.id) for e in entities[:neighbor_limit]]
    except Exception as e:
        msg = str(e).lower()
        if "lock" in msg or "locked" in msg:
            _GRAPH_LOCKED = True
        neighbors = []

    return degree, neighbors


def _auto_candidates(memories: Iterable, mode: str) -> List[UUID]:
    mode = (mode or "").strip().lower()

    if mode == "test":
        ids: List[UUID] = []
        for m in memories:
            if infer_namespace(m) != "test":
                continue
            ids.append(m.id)
        return ids

    raise ValueError(f"Unknown --auto mode: {mode}")


async def _iter_all_memories(limit: int = 500) -> List:
    orch = get_orchestrator()
    all_memories: List = []
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


async def _select_by_query(query: str, mode: QueryMode, *, limit: int) -> List[UUID]:
    orch = get_orchestrator()
    results = await orch.search_memories(query=query, mode=mode, limit=limit)
    ids: List[UUID] = []
    for r in results:
        ids.append(r.memory.id)
    # De-dupe while preserving order
    seen = set()
    out: List[UUID] = []
    for mid in ids:
        if mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


async def _build_impact(memory_id: UUID) -> Optional[Impact]:
    orch = get_orchestrator()

    mem = await orch.vector_store.get_memory(memory_id)
    if mem is None:
        return None

    namespace = infer_namespace(mem)
    category = str(mem.metadata.category or "")
    tags = [t for t in (mem.metadata.tags or []) if isinstance(t, str)]
    score = int(mem.metadata.score or 0)
    access_count = int(mem.metadata.access_count or 0)
    archived = bool(getattr(mem.metadata, "archived", False))
    deprecated = bool(getattr(mem.metadata, "deprecated", False))
    status = str(mem.metadata.status.value if hasattr(mem.metadata.status, "value") else mem.metadata.status)

    temporal_score = float(mem.calculate_relevance_score())

    degree, neighbors = await _get_degree_and_neighbors(orch.graph_store, memory_id)

    semantic_degree, semantic_max_similarity, semantic_mean_similarity = await _get_semantic_connectivity(
        orch.vector_store,
        mem,
    )

    risk, reason = _risk_classification(
        temporal_score=temporal_score,
        degree=degree,
        semantic_degree=semantic_degree,
        semantic_max_similarity=semantic_max_similarity,
        score=score,
        namespace=namespace,
        archived=archived,
    )

    return Impact(
        memory_id=memory_id,
        namespace=namespace,
        category=category,
        tags=tags,
        score=score,
        access_count=access_count,
        archived=archived,
        deprecated=deprecated,
        status=status,
        temporal_score=temporal_score,
        degree=degree,
        neighbors=neighbors,
        semantic_degree=semantic_degree,
        semantic_max_similarity=semantic_max_similarity,
        semantic_mean_similarity=semantic_mean_similarity,
        risk=risk,
        reason=reason,
        preview=_safe_preview(mem.content),
    )


def _backup_dir(default_root: Optional[str] = None) -> Path:
    if default_root:
        return Path(default_root).expanduser().resolve()
    return (Path.home() / ".elefante" / "data" / "backups" / "memory_surgeon").resolve()


def _write_backup(impacts: Sequence[Impact], dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"memory_surgeon_backup_{_utc_ts()}.json"

    payload: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(),
        "count": len(impacts),
        "items": [asdict(i) for i in impacts],
    }

    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out_path


async def _delete_memory(memory_id: UUID) -> Dict[str, Any]:
    orch = get_orchestrator()

    # Order: graph first (detach relationships), then vector.
    # Safety: if graph deletion fails, do NOT delete from vector store.
    ok_graph = await orch.graph_store.delete_entity(memory_id)
    ok_vec = False
    if ok_graph:
        ok_vec = await orch.vector_store.delete_memory(memory_id)

    return {
        "memory_id": str(memory_id),
        "graph_deleted": bool(ok_graph),
        "vector_deleted": bool(ok_vec),
    }


def _print_report(impacts: Sequence[Impact], *, limit: int = 200) -> None:
    print(f"Candidates: {len(impacts)}")
    header = "id  ns  risk  deg  sdeg  smax  temporal  score  access  archived  category  tags  preview"
    print(header)
    print("-" * len(header))

    for i in impacts[:limit]:
        tags = ",".join(i.tags[:4])
        if len(i.tags) > 4:
            tags += ",..."

        print(
            f"{str(i.memory_id)[:8]}  {i.namespace:<4}  {i.risk:<6}  {i.degree:<3}  "
            f"{i.semantic_degree:<4}  {i.semantic_max_similarity:>4.2f}  "
            f"{i.temporal_score:>7.3f}  {i.score:<5}  {i.access_count:<6}  "
            f"{str(i.archived):<8}  {i.category[:12]:<12}  {tags[:16]:<16}  {i.preview}"
        )

    if len(impacts) > limit:
        print(f"... ({len(impacts) - limit} more)")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Privileged memory debugger: surgical review + deletion")

    parser.add_argument("--apply", action="store_true", help="Actually delete (otherwise dry-run)")
    parser.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")

    parser.add_argument("--ids", nargs="*", type=_parse_uuid, default=None, help="Explicit memory UUIDs")

    parser.add_argument("--auto", type=str, default="", help="Auto selection mode (supported: test)")

    parser.add_argument("--query", type=str, default="", help="Select candidates via search query")
    parser.add_argument(
        "--query-mode",
        type=str,
        default="hybrid",
        choices=["semantic", "structured", "hybrid"],
        help="Query mode for --query",
    )
    parser.add_argument("--query-limit", type=int, default=25, help="Max results from --query")

    parser.add_argument("--max-delete", type=int, default=100, help="Safety cap for deletions per run")
    parser.add_argument("--backup-dir", type=str, default="", help="Backup output directory")

    parser.add_argument(
        "--allow-high-risk",
        action="store_true",
        help="Allow deleting high-risk items (still requires apply/confirm)",
    )

    args = parser.parse_args()

    # If applying, ensure graph DB is available (we require graph+vector delete).
    if args.apply:
        orch = get_orchestrator()
        try:
            await orch.graph_store.get_stats()
        except Exception as e:
            raise SystemExit(f"Refusing to apply: graph store unavailable/locked: {e}")

    # Privilege gate
    if args.apply:
        if not _truthy_env("ELEFANTE_PRIVILEGED"):
            raise SystemExit("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        if (args.confirm or "").strip() != "DELETE":
            raise SystemExit("Refusing to apply: pass --confirm DELETE")

    # Selection
    selected_ids: List[UUID] = []

    if args.ids:
        selected_ids = list(args.ids)
    elif args.auto:
        all_memories = await _iter_all_memories()
        selected_ids = _auto_candidates(all_memories, args.auto)
    elif args.query:
        mode = QueryMode(args.query_mode)
        selected_ids = await _select_by_query(args.query, mode, limit=int(args.query_limit))
    else:
        raise SystemExit("No selection provided. Use --ids, --auto, or --query")

    # De-dupe
    seen = set()
    uniq_ids: List[UUID] = []
    for mid in selected_ids:
        if mid in seen:
            continue
        seen.add(mid)
        uniq_ids.append(mid)

    # Build impacts
    impacts_raw: List[Impact] = []
    for mid in uniq_ids:
        impact = await _build_impact(mid)
        if impact is not None:
            impacts_raw.append(impact)

    if not impacts_raw:
        print("No candidates resolved to existing memories.")
        return 0

    # Sort: safer first (low risk + low degree + low temporal)
    risk_rank = {"low": 0, "medium": 1, "high": 2}
    impacts = sorted(
        impacts_raw,
        key=lambda x: (risk_rank.get(x.risk, 9), (x.degree if x.degree >= 0 else 10**9), x.temporal_score),
    )

    _print_report(impacts)

    backup_path = _write_backup(impacts, _backup_dir(args.backup_dir or None))
    print(f"Backup written: {backup_path}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply --confirm DELETE (and ELEFANTE_PRIVILEGED=1) to delete.")
        return 0

    # Safety filters
    to_delete: List[Impact] = []
    for i in impacts:
        if i.risk == "high" and not args.allow_high_risk:
            continue
        to_delete.append(i)

    if not to_delete:
        print("Nothing eligible for deletion under current safety settings.")
        return 0

    if len(to_delete) > int(args.max_delete):
        raise SystemExit(f"Refusing: would delete {len(to_delete)} > --max-delete {args.max_delete}")

    results: List[Dict[str, Any]] = []
    for i in to_delete:
        results.append(await _delete_memory(i.memory_id))

    deleted = sum(1 for r in results if r.get("graph_deleted") and r.get("vector_deleted"))
    partial = len(results) - deleted

    print({"requested": len(results), "deleted_both": deleted, "partial_or_failed": partial})
    if partial:
        print("Details:")
        for r in results:
            if not (r.get("graph_deleted") and r.get("vector_deleted")):
                print(r)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
