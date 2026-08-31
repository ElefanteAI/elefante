#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : verify_dashboard_snapshot.py
# PURPOSE : Validate the generated dashboard_snapshot.json for structural
#           integrity and edge validity without booting the live server.
# WHEN    : After running update_dashboard_data.py, to confirm the snapshot is
#           valid before the frontend consumes it. Run in CI after any change
#           to dashboard_serializer.py or update_dashboard_data.py.
# USAGE   : python scripts/verify/verify_dashboard_snapshot.py [--snapshot PATH]
# NOTES   : Offline — no server required. If this fails, the dashboard will
#           show broken graphs or missing nodes. Fix update_dashboard_data.py
#           or dashboard_serializer.py, re-run the pipeline, then re-verify.
# ─────────────────────────────────────────────────────────────────────────────
"""Validate dashboard_snapshot.json (offline).

This script is safe to run with Elefante Mode OFF.
It checks structural integrity, edge endpoint validity, and (optionally)
curated fields presence for memory nodes.

Usage:
  python scripts/verify/verify_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json
  python scripts/verify/verify_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json --require-curation
  python scripts/verify/verify_dashboard_snapshot.py --path data/dashboard_snapshot.json --strict
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from src.utils.atomic_json import read_json_strict


@dataclass
class ValidationResult:
    errors: List[str]
    warnings: List[str]
    info: List[str]

    def ok(self, *, strict: bool) -> bool:
        if self.errors:
            return False
        if strict and self.warnings:
            return False
        return True


def _default_snapshot_path() -> Path:
    return Path.home() / ".elefante" / "data" / "dashboard_snapshot.json"


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get_edge_endpoints(edge: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    src = edge.get("from") or edge.get("source")
    dst = edge.get("to") or edge.get("target")
    if not isinstance(src, str):
        src = None
    if not isinstance(dst, str):
        dst = None
    return src, dst


def _is_memory_node(node: Dict[str, Any]) -> bool:
    return (node.get("type") or "memory") == "memory"


HEALTH_STATUSES = {"healthy", "stale", "at_risk", "orphan"}
HEALTH_DIMENSIONS = ("score", "freshness", "coverage", "usage", "connectivity")
USAGE_FIELDS = (
    "total_accesses",
    "retrieved_memories",
    "never_retrieved",
    "retrieval_rate",
    "average_access_count",
    "max_access_count",
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_snapshot_intelligence(
    stats: Dict[str, Any],
    memory_nodes: List[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
    info: List[str],
) -> None:
    """Validate optional health/usage summaries when a current snapshot emits them."""
    health = stats.get("health")
    status_counts: Dict[str, int] = {}
    nodes_with_health = 0
    for index, node in enumerate(memory_nodes):
        props = _as_dict(node.get("properties"))
        status = props.get("health_status")
        if status is None:
            continue
        nodes_with_health += 1
        if not isinstance(status, str) or status not in HEALTH_STATUSES:
            errors.append(f"Memory node[{index}] has invalid health_status={status!r}")
        else:
            status_counts[status] = status_counts.get(status, 0) + 1
        reason = props.get("health_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"Memory node[{index}] health_status has no health_reason")
        connection_count = props.get("connection_count")
        if (
            not isinstance(connection_count, int)
            or isinstance(connection_count, bool)
            or connection_count < 0
        ):
            errors.append(f"Memory node[{index}] has invalid connection_count")

    if nodes_with_health and nodes_with_health != len(memory_nodes):
        warnings.append(
            "Only some memory nodes carry canonical health fields; legacy snapshot mix"
        )

    if health is not None:
        if not isinstance(health, dict):
            errors.append("stats.health must be an object")
        else:
            for dimension in HEALTH_DIMENSIONS:
                value = health.get(dimension)
                if not _is_number(value) or not 0 <= float(value) <= 100:
                    errors.append(f"stats.health.{dimension} must be a number from 0 to 100")
            counts = health.get("counts")
            if not isinstance(counts, dict):
                errors.append("stats.health.counts must be an object")
            else:
                for status, count in counts.items():
                    if status not in HEALTH_STATUSES:
                        errors.append(f"stats.health.counts has invalid status={status!r}")
                    if (
                        not isinstance(count, int)
                        or isinstance(count, bool)
                        or count < 0
                    ):
                        errors.append(f"stats.health.counts.{status} must be a non-negative integer")
                if nodes_with_health == len(memory_nodes) and counts != status_counts:
                    errors.append("stats.health.counts does not match memory health_status fields")
            info.append(f"Health score: {health.get('score', 'unknown')}")

    usage = stats.get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            errors.append("stats.usage must be an object")
        else:
            for field in USAGE_FIELDS:
                if field not in usage:
                    errors.append(f"stats.usage missing {field}")
            for field in ("total_accesses", "retrieved_memories", "never_retrieved", "max_access_count"):
                value = usage.get(field)
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 0
                ):
                    errors.append(f"stats.usage.{field} must be a non-negative integer")
            for field in ("retrieval_rate", "average_access_count"):
                value = usage.get(field)
                if not _is_number(value) or float(value) < 0:
                    errors.append(f"stats.usage.{field} must be a non-negative number")
            retrieval_rate = usage.get("retrieval_rate")
            if _is_number(retrieval_rate) and float(retrieval_rate) > 100:
                errors.append("stats.usage.retrieval_rate must be no more than 100")
            retrieved = usage.get("retrieved_memories")
            never = usage.get("never_retrieved")
            if (
                isinstance(retrieved, int)
                and not isinstance(retrieved, bool)
                and isinstance(never, int)
                and not isinstance(never, bool)
                and retrieved + never != len(memory_nodes)
            ):
                errors.append("stats.usage memory counts do not match memory node count")
            info.append(f"Usage: {usage.get('retrieval_rate', 'unknown')}% retrieved")


def _validate_project_registry(
    data: Dict[str, Any],
    errors: List[str],
    info: List[str],
) -> None:
    registry = data.get("project_registry")
    if not isinstance(registry, dict):
        errors.append("Top-level 'project_registry' must be an object")
        return
    status = registry.get("status")
    mode = registry.get("mode")
    projects = registry.get("projects")
    if status not in {"ready", "invalid", "unavailable"}:
        errors.append("project_registry.status is invalid")
        return
    if not isinstance(projects, list):
        errors.append("project_registry.projects must be a list")
        return
    if status != "ready":
        if mode != "invalid" or projects:
            errors.append("Unavailable Project Registry state must fail closed")
        if not isinstance(registry.get("error_code"), str):
            errors.append("Unavailable Project Registry state requires error_code")
        info.append(f"Project Registry: {status}")
        return
    if registry.get("schema_version") != 1:
        errors.append("project_registry.schema_version must be 1")
    if mode not in {"compatibility", "strict"}:
        errors.append("Ready project_registry.mode is invalid")
    revision = registry.get("revision")
    if (
        not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 0
    ):
        errors.append("project_registry.revision must be a non-negative integer")
    active_count = 0
    seen_ids: set[str] = set()
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            errors.append(f"project_registry.projects[{index}] must be an object")
            continue
        try:
            project_id = str(UUID(str(project.get("project_id"))))
        except (TypeError, ValueError, AttributeError):
            errors.append(f"project_registry.projects[{index}] has invalid project_id")
            continue
        if project_id in seen_ids:
            errors.append("project_registry contains duplicate project IDs")
        seen_ids.add(project_id)
        if not isinstance(project.get("name"), str) or not project["name"].strip():
            errors.append(f"project_registry.projects[{index}] has invalid name")
        root = project.get("root")
        if not isinstance(root, str) or not Path(root).is_absolute():
            errors.append(f"project_registry.projects[{index}] has invalid root")
        if not isinstance(project.get("active"), bool):
            errors.append(f"project_registry.projects[{index}] has invalid active state")
        elif project["active"]:
            active_count += 1
        if project.get("root_status") not in {"available", "missing"}:
            errors.append(f"project_registry.projects[{index}] has invalid root_status")
    if mode == "strict" and active_count == 0:
        errors.append("Strict Project Registry requires an active project")
    info.append(f"Project Registry: {mode}, {len(projects)} project(s)")


def validate_snapshot(data: Dict[str, Any], *, require_curation: bool) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    info: List[str] = []

    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        warnings.append("Missing or invalid top-level 'generated_at' (expected non-empty string)")

    nodes = _as_list(data.get("nodes"))
    edges = _as_list(data.get("edges"))
    stats = _as_dict(data.get("stats"))
    _validate_project_registry(data, errors, info)

    if not isinstance(data.get("nodes"), list):
        errors.append("Top-level 'nodes' must be a list")
    if not isinstance(data.get("edges"), list):
        errors.append("Top-level 'edges' must be a list")
    if not isinstance(data.get("stats"), dict):
        warnings.append("Top-level 'stats' should be an object")

    node_ids: List[str] = []
    bad_nodes = 0
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            bad_nodes += 1
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            errors.append(f"Node[{i}] missing valid 'id'")
            continue
        node_ids.append(nid)

        ntype = n.get("type")
        if not isinstance(ntype, str) or not ntype.strip():
            warnings.append(f"Node[{i}] id={nid} missing 'type' (defaulting to memory in UI)")

        name = n.get("name")
        if not isinstance(name, str) or not name.strip():
            warnings.append(f"Node[{i}] id={nid} missing 'name' (UI label may be blank)")

        props = _as_dict(n.get("properties"))
        if _is_memory_node(n):
            title = props.get("title")
            summary = props.get("summary")
            if require_curation:
                if not isinstance(title, str) or not title.strip():
                    errors.append(f"Memory node id={nid} missing properties.title")
                if not isinstance(summary, str) or not summary.strip():
                    errors.append(f"Memory node id={nid} missing properties.summary")
            else:
                if not isinstance(title, str) or not title.strip():
                    warnings.append(f"Memory node id={nid} missing properties.title")
                if not isinstance(summary, str) or not summary.strip():
                    warnings.append(f"Memory node id={nid} missing properties.summary")

    if bad_nodes:
        warnings.append(f"Found {bad_nodes} non-object entries in nodes[]")

    # Uniqueness
    unique_ids = set(node_ids)
    if len(unique_ids) != len(node_ids):
        dup_count = len(node_ids) - len(unique_ids)
        errors.append(f"Duplicate node ids found: {dup_count} duplicates")

    # Edge endpoint validity + degree counts
    degree: Dict[str, int] = {nid: 0 for nid in unique_ids}
    bad_edges = 0
    missing_endpoint = 0
    dangling = 0

    for _j, e in enumerate(edges):
        if not isinstance(e, dict):
            bad_edges += 1
            continue
        src, dst = _get_edge_endpoints(e)
        if not src or not dst:
            missing_endpoint += 1
            continue
        if src not in unique_ids or dst not in unique_ids:
            dangling += 1
            continue
        degree[src] = degree.get(src, 0) + 1
        degree[dst] = degree.get(dst, 0) + 1

    if bad_edges:
        warnings.append(f"Found {bad_edges} non-object entries in edges[]")
    if missing_endpoint:
        errors.append(f"Found {missing_endpoint} edges missing endpoints (from/to or source/target)")
    if dangling:
        warnings.append(
            f"Found {dangling} edges referencing unknown node ids (dashboard will ignore these)"
        )

    isolated = [nid for nid, d in degree.items() if d == 0]
    if isolated:
        warnings.append(f"Isolated nodes (degree=0): {len(isolated)}")

    if stats:
        expected_total_nodes = len(nodes)
        expected_edges = len(edges)
        stat_total_nodes = stats.get("total_nodes")
        stat_edges = stats.get("edges")
        if isinstance(stat_total_nodes, int) and stat_total_nodes != expected_total_nodes:
            warnings.append(
                f"stats.total_nodes={stat_total_nodes} does not match nodes length={expected_total_nodes}"
            )
        if isinstance(stat_edges, int) and stat_edges != expected_edges:
            warnings.append(f"stats.edges={stat_edges} does not match edges length={expected_edges}")

    # Score health check — detect stale stored scores (the "all 100s" bug class)
    memory_nodes = [n for n in nodes if isinstance(n, dict) and _is_memory_node(n)]
    _validate_snapshot_intelligence(stats, memory_nodes, errors, warnings, info)
    if memory_nodes:
        scores = []
        for mn in memory_nodes:
            p = _as_dict(mn.get("properties"))
            s = p.get("score")
            if isinstance(s, (int, float)):
                scores.append(int(s))
        if scores:
            count_100 = sum(1 for s in scores if s == 100)
            pct_100 = count_100 / len(scores)
            avg = sum(scores) / len(scores)
            info.append(f"Scores: avg={avg:.0f}, min={min(scores)}, max={max(scores)}, count_100={count_100}/{len(scores)}")
            if pct_100 > 0.25:
                errors.append(
                    f"Score staleness detected: {count_100}/{len(scores)} ({pct_100:.0%}) memories have score=100. "
                    f"Scores must be live-computed via dashboard_serializer.py — see workspace/postmortems/dashboard.md Issue #9"
                )
            elif count_100 > 5:
                warnings.append(f"{count_100} memories have score=100 — verify scores are live-computed")

    info.append(f"Nodes: {len(nodes)}")
    info.append(f"Edges: {len(edges)}")

    return ValidationResult(errors=errors, warnings=warnings, info=info)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dashboard snapshot JSON")
    parser.add_argument(
        "--path",
        type=str,
        default=str(_default_snapshot_path()),
        help="Path to dashboard_snapshot.json (default: ~/.elefante/data/dashboard_snapshot.json)",
    )
    parser.add_argument(
        "--require-curation",
        action="store_true",
        help="Fail validation if memory nodes are missing properties.title or properties.summary",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (non-zero exit)",
    )

    args = parser.parse_args()
    snapshot_path = Path(args.path).expanduser()

    if not snapshot_path.exists():
        print(f"[error] snapshot not found: {snapshot_path}", file=sys.stderr)
        return 2

    try:
        data = read_json_strict(snapshot_path)
    except Exception as e:
        print(f"[error] failed to parse JSON: {e}", file=sys.stderr)
        return 2

    result = validate_snapshot(data, require_curation=bool(args.require_curation))

    for line in result.info:
        print(f"[info] {line}", file=sys.stderr)
    for line in result.warnings:
        print(f"[warn] {line}", file=sys.stderr)
    for line in result.errors:
        print(f"[fail] {line}", file=sys.stderr)

    if result.ok(strict=bool(args.strict)):
        print("[ok] snapshot validation passed", file=sys.stderr)
        return 0

    print("[error] snapshot validation failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
