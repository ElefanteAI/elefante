#!/usr/bin/env python3
"""Validate dashboard_snapshot.json (offline).

This script is safe to run with Elefante Mode OFF.
It checks structural integrity, edge endpoint validity, and (optionally)
curated fields presence for memory nodes.

Usage:
  python scripts/validate_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json
  python scripts/validate_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json --require-curation
  python scripts/validate_dashboard_snapshot.py --path data/dashboard_snapshot.json --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


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

    for j, e in enumerate(edges):
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

    # Isolation check (use current snapshot connectivity)
    isolated = [nid for nid, d in degree.items() if d == 0]
    if isolated:
        warnings.append(f"Isolated nodes (degree=0): {len(isolated)}")

    # Stats sanity
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
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
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
