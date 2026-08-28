#!/usr/bin/env python3
"""Audit whether v2 retrieval reaches known repair files without using future content."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.run_task_intelligence_evaluation import (  # noqa: E402
    V2_SOURCE_SUFFIXES,
    source_grounded_candidates,
)
from scripts.ci.verify_task_intelligence_benchmark import (  # noqa: E402
    validate_manifest,
)


def _git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _is_implementation_path(path: str) -> bool:
    if path.startswith(("docs/", "tests/", "workspace/", "benchmarks/")):
        return False
    return PurePosixPath(path).suffix.casefold() in V2_SOURCE_SUFFIXES


def audit_task(repo_root: Path, task: dict[str, Any], *, top_k: int) -> dict[str, Any]:
    """Retrieve first; inspect the historical fix only to score the frozen result."""
    candidates = source_grounded_candidates(repo_root, task)
    retrieved_paths = list(dict.fromkeys(item["path"] for item in candidates))[:top_k]

    changed = _git(
        repo_root,
        "diff",
        "--name-only",
        task["base_ref"],
        task["acceptance_ref"],
    )
    if changed.returncode != 0:
        raise RuntimeError(f"cannot score historical repair for {task['id']}")
    repair_paths = []
    for path in changed.stdout.splitlines():
        if not _is_implementation_path(path):
            continue
        exists = _git(repo_root, "cat-file", "-e", f"{task['base_ref']}:{path}")
        if exists.returncode == 0:
            repair_paths.append(path)
    hits = sorted(set(retrieved_paths).intersection(repair_paths))
    return {
        "task_id": task["id"],
        "scorable": bool(repair_paths),
        "hit": bool(hits),
        "hits": hits,
        "retrieved_paths": retrieved_paths,
        "eligible_repair_path_count": len(repair_paths),
    }


def audit(
    repo_root: Path,
    manifest: dict[str, Any],
    *,
    split: str,
    top_k: int,
) -> dict[str, Any]:
    tasks = [task for task in manifest["tasks"] if task["split"] == split]
    results = [audit_task(repo_root, task, top_k=top_k) for task in tasks]
    scorable = [result for result in results if result["scorable"]]
    hits = sum(int(result["hit"]) for result in scorable)
    return {
        "benchmark_id": manifest["benchmark_id"],
        "split": split,
        "top_k": top_k,
        "tasks": len(tasks),
        "scorable_tasks": len(scorable),
        "hits": hits,
        "hit_rate": 0.0 if not scorable else round(hits / len(scorable), 6),
        "diagnostic_only": True,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--split", choices=("calibration", "holdout"), default="calibration"
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--minimum-hit-rate", type=float, default=0.8)
    args = parser.parse_args(argv)
    if args.top_k < 1 or not 0 <= args.minimum_hit_rate <= 1:
        parser.error(
            "top-k must be positive and minimum-hit-rate must be between 0 and 1"
        )

    verification = validate_manifest(args.manifest, ROOT)
    if verification["errors"]:
        print(json.dumps({"errors": verification["errors"]}, indent=2))
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = audit(ROOT, manifest, split=args.split, top_k=args.top_k)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["hit_rate"] >= args.minimum_hit_rate else 3


if __name__ == "__main__":
    raise SystemExit(main())
