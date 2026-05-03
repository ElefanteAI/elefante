#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : verify_scoring_sandbox.py
# VERSION : 2.7.1
# CHANGED : 2026-04-16
# PURPOSE : Seed 100 crafted memories in a disposable temp Elefante sandbox,
#           verify the 5-signal retrieval contract plus dashboard-visible
#           taxonomy, topology, lifecycle, and customer-demo coverage, then
#           delete the sandbox so no ghost memories land in the user's real store.
# WHEN    : When changing retrieval.py, orchestrator scoring, co-activation,
#           temporal logic, or when you need a controlled second-brain dataset
#           to explain why specific memories surface.
# USAGE   : .venv/bin/python scripts/verify/verify_scoring_sandbox.py
# NOTES   : Uses a child process with temp HOME/USERPROFILE to contain all
#           import-time config writes and logs. Pass --keep-sandbox only for
#           debugging a failed scenario.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Isolated 100-memory scoring plus dashboard-demo verifier for Elefante."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class SeedSpec:
    title: str
    cohort: str
    content: str
    concepts: list[str]
    surfaces_when: list[str]
    memory_type: str
    domain: str
    topic: str
    ring: str
    knowledge_type: str
    score: int
    access_count: int
    created_days_ago: int
    accessed_days_ago: int
    tags: list[str]
    summary: str
    processing_status: str = "processed"
    status: str = "new"
    namespace: str = "customer-demo"
    deprecated: bool = False
    archived: bool = False
    supersedes_title: str | None = None
    superseded_by_title: str | None = None
    conflict_titles: list[str] = field(default_factory=list)
    graph_links: list[tuple[str, str]] = field(default_factory=list)
    authority_score: float | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class SeedPlan:
    seeds: list[SeedSpec]
    coactivation_clusters: list[list[str]]


def _one_line_summary(text: str) -> str:
    sentence = (text or "").strip().split(".")[0].strip()
    if not sentence:
        return ""
    if len(sentence) > 140:
        sentence = sentence[:137].rstrip() + "..."
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


def _list_string(values: list[str]) -> str:
    return json.dumps(values)


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str | None, str | None]:
    src = edge.get("from") or edge.get("source")
    dst = edge.get("to") or edge.get("target")
    return (src if isinstance(src, str) else None, dst if isinstance(dst, str) else None)


def _parent_main(keep_sandbox: bool) -> int:
    sandbox_root = Path(tempfile.mkdtemp(prefix="elefante-scoring-sandbox-"))
    sandbox_home = sandbox_root / "home"
    sandbox_home.mkdir(parents=True, exist_ok=True)
    real_home = Path(os.environ.get("HOME", str(Path.home()))).expanduser()

    env = os.environ.copy()
    shared_cache_root = Path(env.get("XDG_CACHE_HOME", str(real_home / ".cache"))).expanduser()
    env.update(
        {
            "HOME": str(sandbox_home),
            "USERPROFILE": str(sandbox_home),
            "ELEFANTE_DATA_DIR": str(sandbox_home / ".elefante" / "data"),
            "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
            "ELEFANTE_LOGGING_FORMAT": "text",
            "XDG_CACHE_HOME": str(shared_cache_root),
            "HF_HOME": env.get("HF_HOME", str(shared_cache_root / "huggingface")),
            "SENTENCE_TRANSFORMERS_HOME": env.get(
                "SENTENCE_TRANSFORMERS_HOME",
                str(shared_cache_root / "torch" / "sentence_transformers"),
            ),
        }
    )

    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", "--sandbox", str(sandbox_root)]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)

    if keep_sandbox:
        print(f"\nSandbox preserved at: {sandbox_root}")
        return result.returncode

    shutil.rmtree(sandbox_root, ignore_errors=True)
    sandbox_removed = not sandbox_root.exists()
    print(f"\n[{'PASS' if sandbox_removed else 'FAIL'}] sandbox cleanup -- {sandbox_root}")
    return result.returncode if sandbox_removed else 1


def _build_seed_plan() -> SeedPlan:
    seeds: list[SeedSpec] = []
    seen_titles: set[str] = set()

    def add_seed(
        *,
        title: str,
        cohort: str,
        content: str,
        concepts: list[str],
        memory_type: str,
        domain: str,
        topic: str,
        ring: str,
        knowledge_type: str,
        score: int,
        access_count: int,
        created_days_ago: int,
        accessed_days_ago: int,
        tags: list[str] | None = None,
        summary: str | None = None,
        surfaces_when: list[str] | None = None,
        processing_status: str = "processed",
        status: str = "new",
        namespace: str = "customer-demo",
        deprecated: bool = False,
        archived: bool = False,
        supersedes_title: str | None = None,
        superseded_by_title: str | None = None,
        conflict_titles: list[str] | None = None,
        graph_links: list[tuple[str, str]] | None = None,
        authority_score: float | None = None,
    ) -> None:
        if title in seen_titles:
            raise RuntimeError(f"Duplicate seed title: {title}")
        seen_titles.add(title)

        resolved_tags = sorted(
            {
                "sandbox",
                cohort,
                topic,
                ring,
                knowledge_type,
                *(tags or []),
            }
        )
        resolved_surfaces = surfaces_when or ([" ".join(concepts[:4])] if concepts else [title.lower()])
        resolved_authority = authority_score
        if resolved_authority is None:
            resolved_authority = round(min(1.0, (score / 100.0) * (1.0 + min(access_count, 20) / 25.0)), 3)

        seeds.append(
            SeedSpec(
                title=title,
                cohort=cohort,
                content=content,
                concepts=concepts,
                surfaces_when=resolved_surfaces,
                memory_type=memory_type,
                domain=domain,
                topic=topic,
                ring=ring,
                knowledge_type=knowledge_type,
                score=score,
                access_count=access_count,
                created_days_ago=created_days_ago,
                accessed_days_ago=accessed_days_ago,
                tags=resolved_tags,
                summary=summary or _one_line_summary(content),
                processing_status=processing_status,
                status=status,
                namespace=namespace,
                deprecated=deprecated,
                archived=archived,
                supersedes_title=supersedes_title,
                superseded_by_title=superseded_by_title,
                conflict_titles=list(conflict_titles or []),
                graph_links=list(graph_links or []),
                authority_score=resolved_authority,
            )
        )

    def add_group(cohort: str, defaults: dict[str, Any], items: list[dict[str, Any]]) -> None:
        for item in items:
            payload = {**defaults, **item}
            add_seed(cohort=cohort, **payload)

    semantic_defaults = {
        "memory_type": "fact",
        "domain": "reference",
        "topic": "debugging",
        "ring": "topic",
        "knowledge_type": "method",
        "score": 74,
        "access_count": 9,
        "created_days_ago": 28,
        "accessed_days_ago": 5,
        "namespace": "elefante-core",
        "tags": ["pytest", "graph-store", "regression"],
    }
    add_group(
        "semantic_python",
        semantic_defaults,
        [
            {
                "title": "Persistence tests prove the Kuzu lock contract",
                "content": "Run pytest on tests/test_memory_persistence.py before touching Kuzu lock logic or graph store close behavior.",
                "concepts": ["pytest", "memory", "persistence", "kuzu", "graph"],
                "surfaces_when": ["which pytest subset validates kuzu lock and graph store close behavior"],
                "score": 80,
                "access_count": 14,
                "created_days_ago": 18,
                "accessed_days_ago": 2,
                "status": "verified",
            },
            {
                "title": "Verify graph-store shutdown with persistence pytest",
                "content": "Verify memory persistence and Kuzu lock rules with pytest before changing graph store shutdown code.",
                "concepts": ["verify", "memory", "kuzu", "graph", "pytest"],
                "score": 78,
                "access_count": 12,
                "created_days_ago": 22,
                "accessed_days_ago": 3,
                "status": "related",
            },
            {
                "title": "The lock-regression subset lives in the persistence suite",
                "content": "The maintained regression subset for Kuzu lock contention lives in tests/test_memory_persistence.py.",
                "concepts": ["regression", "kuzu", "lock", "memory", "persistence"],
            },
            {
                "title": "Close-barrier regressions belong to persistence tests",
                "content": "Graph store close barriers belong to the memory persistence regression suite, not dashboard tests.",
                "concepts": ["graph", "close", "memory", "persistence", "tests"],
                "memory_type": "insight",
                "knowledge_type": "insight",
            },
            {
                "title": "Use TestKuzuLockContract before debugging lock files",
                "content": "Use pytest -k TestKuzuLockContract to verify the current write lock contract before debugging lock files.",
                "concepts": ["pytest", "kuzu", "lock", "contract", "write"],
                "memory_type": "decision",
            },
            {
                "title": "Start Kuzu debugging at the compendium and persistence suite",
                "content": "A healthy Kuzu debugging pass starts at workspace/ISSUES.md and the persistence tests, then source.",
                "concepts": ["kuzu", "debug", "persistence", "tests", "source"],
            },
            {
                "title": "Never chase graph races without rerunning persistence pytest",
                "content": "Never debug graph store races without rerunning the memory persistence verifier under pytest.",
                "concepts": ["graph", "races", "memory", "persistence", "pytest"],
                "memory_type": "directive",
                "knowledge_type": "law",
                "ring": "domain",
            },
            {
                "title": "Persistence pytest is still the fastest lock proof",
                "content": "The fastest proof for Kuzu lock regressions is still the memory persistence pytest file.",
                "concepts": ["kuzu", "lock", "regressions", "memory", "pytest"],
            },
            {
                "title": "Run persistence and coactivation tests before shipping graph fixes",
                "content": "Run the persistence and coactivation tests before claiming a graph-store fix is complete.",
                "concepts": ["persistence", "coactivation", "graph", "tests", "fix"],
                "topic": "coding-standards",
                "ring": "domain",
                "knowledge_type": "principle",
            },
            {
                "title": "Graph-store edits stay unsafe until the persistence contract passes",
                "content": "Graph store edits are not safe until pytest proves the persistence contract still holds.",
                "concepts": ["graph", "pytest", "persistence", "contract", "safe"],
                "topic": "coding-standards",
                "ring": "domain",
                "knowledge_type": "law",
                "memory_type": "directive",
            },
        ],
    )

    concept_defaults = {
        "memory_type": "insight",
        "domain": "reference",
        "topic": "debugging",
        "ring": "leaf",
        "knowledge_type": "insight",
        "score": 76,
        "access_count": 10,
        "created_days_ago": 48,
        "accessed_days_ago": 7,
        "namespace": "elefante-core",
        "tags": ["kuzu", "queryresult", "segfault"],
    }
    add_group(
        "concept_queryresult",
        concept_defaults,
        [
            {
                "title": "QueryResult lifetime leak can segfault FactorizedTable",
                "content": "Kuzu QueryResult lifetime leak can segfault in FactorizedTable destructor when async future finalization outlives the worker thread.",
                "concepts": ["kuzu", "queryresult", "lifetime", "factorizedtable", "segfault"],
                "surfaces_when": ["kuzu queryresult factorizedtable lifetime segfault"],
                "score": 86,
                "access_count": 19,
                "created_days_ago": 20,
                "accessed_days_ago": 1,
                "status": "verified",
            },
            {
                "title": "Materialize rows inside the worker thread",
                "content": "Materialize rows inside the worker thread so QueryResult and FactorizedTable die before future finalization.",
                "concepts": ["queryresult", "factorizedtable", "worker", "future", "finalization"],
                "knowledge_type": "method",
                "memory_type": "decision",
            },
            {
                "title": "A leaked QueryResult crashes later on macOS",
                "content": "A lingering QueryResult can crash later in FactorizedTable teardown on macOS.",
                "concepts": ["queryresult", "factorizedtable", "teardown", "macos", "crash"],
            },
            {
                "title": "Never return native QueryResult through asyncio futures",
                "content": "Never return native Kuzu QueryResult handles through asyncio futures.",
                "concepts": ["kuzu", "queryresult", "asyncio", "futures", "native"],
                "memory_type": "directive",
                "knowledge_type": "law",
                "ring": "domain",
            },
            {
                "title": "Python rows are safe; QueryResult handles are not",
                "content": "The safe boundary is rows in Python, not QueryResult in a future payload.",
                "concepts": ["queryresult", "rows", "python", "future", "payload"],
                "topic": "architecture",
                "ring": "topic",
                "knowledge_type": "principle",
            },
            {
                "title": "FactorizedTable crashes are ownership bugs in disguise",
                "content": "FactorizedTable lifetime bugs look random until QueryResult ownership is traced end to end.",
                "concepts": ["factorizedtable", "lifetime", "queryresult", "ownership", "trace"],
            },
            {
                "title": "Asynchronous Kuzu code must fully materialize rows",
                "content": "Asynchronous Kuzu code must fully materialize row data before the native result escapes.",
                "concepts": ["asynchronous", "kuzu", "materialize", "native", "result"],
                "topic": "architecture",
                "knowledge_type": "method",
                "memory_type": "decision",
            },
            {
                "title": "Destroy QueryResult before Python future cleanup begins",
                "content": "Worker-thread teardown must destroy QueryResult before Python future cleanup begins.",
                "concepts": ["worker", "queryresult", "future", "cleanup", "teardown"],
            },
            {
                "title": "FactorizedTable segfaults usually mean QueryResult lifetime escaped",
                "content": "Segfaults in FactorizedTable are often symptoms of a leaked QueryResult lifetime.",
                "concepts": ["segfaults", "factorizedtable", "queryresult", "lifetime", "leaked"],
            },
            {
                "title": "Async cleanup hides the QueryResult failure mode",
                "content": "The compendium entry for QueryResult lifetime exists because the failure mode hides behind async cleanup.",
                "concepts": ["queryresult", "lifetime", "compendium", "async", "cleanup"],
                "topic": "architecture",
                "knowledge_type": "insight",
            },
        ],
    )

    authority_titles = [
        "Search-before-write is the compliance gate",
        "Blocked responses must say action required",
        "Amendment is blocked until search proof exists",
        "Deletion is blocked until search proof exists",
        "Search proof protects the audit trail",
        "Compliance failures are explicit workflow events",
        "Search-before-write prevents silent memory mutation",
        "Blocked responses are workflow signals, not failure theater",
        "The audit trail starts with the search result",
        "Search-before-write is still mandatory on tired days",
    ]
    authority_extras = [
        "It is the first guardrail before any create, update, or delete operation touches stored memory.",
        "If search was skipped, the response is blocked and the next step must be explicit.",
        "Memory amendment is not allowed until search shows what already exists and what would change.",
        "Deletion needs the same search proof because auditability matters more than speed.",
        "Search results anchor the action so later reviewers can see why the write happened.",
        "Compliance blocks are workflow events that teach the operator what to do next.",
        "The gate exists to stop silent mutation, not to create ceremony.",
        "The blocked response is a product signal, not a generic failure screen.",
        "When the search result is visible, the write has context and a paper trail.",
        "Discipline matters most when the operator is tired and tempted to skip the search step.",
    ]
    authority_scores = [88, 96, 82, 80, 76, 70, 66, 58, 24, 18]
    authority_access = [18, 28, 16, 15, 12, 10, 8, 4, 1, 0]
    authority_created = [14, 10, 16, 18, 24, 30, 36, 42, 120, 9]
    authority_accessed = [3, 1, 4, 5, 9, 12, 15, 20, 120, 9]
    for idx, title in enumerate(authority_titles):
        add_seed(
            title=title,
            cohort="authority_compliance_gate",
            content=(
                "The compliance gate requires search before write, and blocked responses must include action required when search was skipped. "
                + authority_extras[idx]
            ),
            concepts=["compliance", "gate", "search", "before", "write"],
            surfaces_when=["compliance gate search before write blocked response action required"],
            memory_type="directive" if idx < 2 else "fact" if idx < 7 else "insight",
            domain="project",
            topic="workflow" if idx < 7 else "coding-standards",
            ring="core" if idx < 2 else "domain" if idx < 5 else "topic",
            knowledge_type="law" if idx < 2 else "method" if idx < 6 else "principle",
            score=authority_scores[idx],
            access_count=authority_access[idx],
            created_days_ago=authority_created[idx],
            accessed_days_ago=authority_accessed[idx],
            tags=["compliance", "audit", "write-path"],
            namespace="elefante-core",
            status="redundant" if idx == 9 else "new",
        )

    temporal_titles = [
        "Repo-local Python 3.11 is the installation authority",
        "Run repair and verification in the repo-local .venv",
        "Installer should create or adopt .venv automatically",
        "The configured interpreter beats bare python",
        "One interpreter per repo kills ghost installs",
        "Child-process temp HOME isolates live data safely",
        "Shared model cache may live outside the sandbox",
        "Keep sandbox only for failed investigations",
        "Local data dir must be explicit and inspectable",
        "System Python is not the verification path",
    ]
    temporal_extras = [
        "It is the path for install, repair, and verification because the system interpreter drifts.",
        "Repair commands and verifier runs should use the same repo-local Python 3.11 virtual environment.",
        "The installer earns trust when it adopts the existing .venv or creates one cleanly.",
        "Configured interpreter details beat shell habit because shell habit creates ghost installs.",
        "A repo-local Python 3.11 virtual environment keeps install verification deterministic.",
        "The worker uses temp HOME so the repo-local Python 3.11 verification cannot leak into live data.",
        "Shared model cache is fine, but Elefante data must stay in the repo-local sandbox during verification.",
        "Preserve the sandbox only after a failed verification; otherwise the repo-local install should clean up.",
        "Explicit data dirs make repo-local Python 3.11 install verification easy to inspect and explain.",
        "System Python is a ghost dependency when the verifier depends on the repo-local virtual environment.",
    ]
    temporal_created = [2, 4, 6, 12, 18, 26, 40, 60, 90, 360]
    temporal_accessed = [1, 2, 3, 6, 8, 12, 20, 30, 60, 240]
    for idx, title in enumerate(temporal_titles):
        add_seed(
            title=title,
            cohort="temporal_python",
            content=(
                "Use the repo-local Python 3.11 virtual environment for Elefante install, repair, and verification. "
                + temporal_extras[idx]
            ),
            concepts=["python", "virtual", "environment", "install", "verification"],
            surfaces_when=["python virtual environment install verification repo local"],
            memory_type="decision" if idx < 5 else "fact",
            domain="project",
            topic="tools-environment",
            ring="domain" if idx < 5 else "topic",
            knowledge_type="decision" if idx < 3 else "method" if idx < 7 else "fact",
            score=76,
            access_count=10,
            created_days_ago=temporal_created[idx],
            accessed_days_ago=temporal_accessed[idx],
            tags=["python-3.11", "sandbox", "venv"],
            namespace="elefante-core",
            status="verified" if idx == 0 else "new",
        )

    coactivation_defaults = {
        "memory_type": "fact",
        "domain": "project",
        "topic": "architecture",
        "ring": "topic",
        "knowledge_type": "method",
        "score": 72,
        "access_count": 9,
        "created_days_ago": 24,
        "accessed_days_ago": 3,
        "namespace": "elefante-core",
        "tags": ["dashboard", "snapshot", "startup"],
    }
    add_group(
        "coactivation_dashboard",
        coactivation_defaults,
        [
            {
                "title": "Server readiness gate fixes the blank first launch",
                "content": "The dashboard first-launch race was fixed by waiting for server readiness before opening the browser.",
                "concepts": ["dashboard", "first-launch", "retry", "backoff", "readiness"],
                "surfaces_when": ["dashboard blank launch retry backoff first launch"],
                "score": 84,
                "access_count": 15,
                "created_days_ago": 8,
                "accessed_days_ago": 1,
                "status": "verified",
            },
            {
                "title": "Retry backoff heals early snapshot fetches",
                "content": "Frontend retry backoff lets the dashboard recover if it asks for snapshot data before the server is ready.",
                "concepts": ["dashboard", "first-launch", "retry", "backoff", "readiness"],
                "score": 82,
                "access_count": 13,
                "created_days_ago": 8,
                "accessed_days_ago": 1,
            },
            {
                "title": "First-launch races are timing bugs, not dead dashboards",
                "content": "Persistent blank dashboard bugs should be verified with retry/backoff and server readiness checks.",
                "concepts": ["dashboard", "first-launch", "retry", "backoff", "readiness"],
                "memory_type": "insight",
                "knowledge_type": "insight",
            },
            {
                "title": "A few slow seconds can masquerade as total failure",
                "content": "A dashboard can look dead even when the snapshot server is only a few seconds late.",
                "concepts": ["dashboard", "snapshot", "startup", "latency", "trust"],
                "topic": "communication",
                "knowledge_type": "insight",
            },
            {
                "title": "Blank dashboard triage starts with the snapshot file",
                "content": "Blank dashboard triage starts by separating snapshot availability from frontend rendering.",
                "concepts": ["dashboard", "snapshot", "triage", "frontend", "availability"],
                "ring": "domain",
            },
            {
                "title": "Readiness waits plus retry logic close the launch gap",
                "content": "Retry backoff is the difference between a transient first-launch race and a persistent blank page.",
                "concepts": ["retry", "backoff", "launch", "race", "dashboard"],
            },
            {
                "title": "Snapshot startup order is product quality",
                "content": "Dashboard health depends on snapshot freshness, retry logic, and startup ordering.",
                "concepts": ["dashboard", "health", "snapshot", "startup", "ordering"],
                "topic": "collaboration",
                "knowledge_type": "principle",
            },
            {
                "title": "The dashboard should recover if it beats the backend",
                "content": "If the dashboard beats the backend once, exponential retry should heal the page automatically.",
                "concepts": ["dashboard", "backend", "retry", "recover", "snapshot"],
            },
            {
                "title": "Readiness waits and retry/backoff close the trust gap",
                "content": "Readiness waits plus retry/backoff close the dashboard first-launch gap.",
                "concepts": ["readiness", "retry", "backoff", "dashboard", "trust"],
                "topic": "communication",
                "knowledge_type": "principle",
            },
            {
                "title": "Live backend queries on every render keep the dashboard freshest",
                "content": "Some designs try to query the live backend on every dashboard render, but that creates fragile coupling and contradicts the snapshot-first contract.",
                "concepts": ["dashboard", "live", "backend", "render", "snapshot"],
                "memory_type": "note",
                "knowledge_type": "fact",
                "status": "contradictory",
                "processing_status": "failed",
                "score": 26,
                "access_count": 0,
                "created_days_ago": 120,
                "accessed_days_ago": 120,
            },
        ],
    )

    release_defaults = {
        "memory_type": "fact",
        "domain": "project",
        "topic": "workflow",
        "ring": "topic",
        "knowledge_type": "fact",
        "score": 82,
        "access_count": 14,
        "created_days_ago": 6,
        "accessed_days_ago": 1,
        "namespace": "release-ops",
        "tags": ["release", "github", "bug015"],
    }
    add_group(
        "release_troubleshoot",
        release_defaults,
        [
            {
                "title": "Linux release asset exceeded GitHub's 2 GiB limit",
                "content": "Create GitHub Release failed because the Linux release asset exceeded GitHub's 2 GiB per-file limit.",
                "concepts": ["release", "linux", "asset", "github", "limit"],
                "surfaces_when": ["why did create github release fail for v2.6.0 linux asset upload"],
                "score": 90,
                "access_count": 18,
                "created_days_ago": 4,
                "accessed_days_ago": 1,
                "status": "verified",
            },
            {
                "title": "The release object existed while the Linux zip was too large",
                "content": "The v2.6.0 release object existed, but the Linux binary zip was too large for GitHub Releases.",
                "concepts": ["release", "object", "linux", "zip", "github"],
            },
            {
                "title": "macOS and Windows succeeded because they were smaller",
                "content": "macOS and Windows assets uploaded successfully; Linux failed during release attachment due to size.",
                "concepts": ["macos", "windows", "linux", "upload", "size"],
                "topic": "debugging",
            },
            {
                "title": "A green build matrix can still fail at publish time",
                "content": "A green build matrix is not release proof when the Linux asset breaches the GitHub upload cap.",
                "concepts": ["build", "matrix", "release", "linux", "cap"],
                "memory_type": "insight",
                "knowledge_type": "insight",
                "topic": "debugging",
            },
            {
                "title": "Artifact upload success does not guarantee release success",
                "content": "GitHub release assets can fail even after Actions artifacts upload successfully.",
                "concepts": ["artifact", "upload", "release", "actions", "success"],
                "memory_type": "insight",
                "knowledge_type": "principle",
            },
            {
                "title": "The Linux artifact was over four billion bytes",
                "content": "The Linux artifact measured more than four billion bytes, above GitHub's release limit.",
                "concepts": ["linux", "artifact", "bytes", "release", "limit"],
                "topic": "debugging",
            },
            {
                "title": "Preflight asset size before GitHub release publish",
                "content": "The fix for release publication is to preflight asset sizes before softprops/action-gh-release runs.",
                "concepts": ["preflight", "asset", "size", "release", "publish"],
                "memory_type": "decision",
                "knowledge_type": "method",
                "ring": "domain",
            },
            {
                "title": "Draft release notes typed manually in workflow YAML",
                "content": "Before release-note rendering existed, some notes were typed by hand in workflow YAML, which was brittle and easy to forget.",
                "concepts": ["draft", "release", "notes", "workflow", "yaml"],
                "memory_type": "note",
                "knowledge_type": "fact",
                "score": 32,
                "access_count": 0,
                "created_days_ago": 210,
                "accessed_days_ago": 210,
                "status": "deprecated",
                "deprecated": True,
                "topic": "coding-standards",
            },
            {
                "title": "PyInstaller was blamed, but that was the wrong diagnosis",
                "content": "Some early guesses blamed PyInstaller for the publish failure, but the actual release-stage cause was the oversized Linux asset.",
                "concepts": ["pyinstaller", "publish", "failure", "release", "linux"],
                "memory_type": "note",
                "knowledge_type": "fact",
                "score": 28,
                "access_count": 0,
                "created_days_ago": 120,
                "accessed_days_ago": 120,
                "status": "contradictory",
                "processing_status": "failed",
                "topic": "debugging",
            },
            {
                "title": "Branch-local version bump checklist from pre-script days",
                "content": "An old branch-local checklist once handled version bumps by hand, but scripted bumping replaced it and the checklist should stay archived.",
                "concepts": ["branch", "version", "bump", "checklist", "script"],
                "memory_type": "note",
                "knowledge_type": "fact",
                "score": 24,
                "access_count": 0,
                "created_days_ago": 320,
                "accessed_days_ago": 320,
                "status": "archived",
                "archived": True,
                "topic": "workflow",
            },
        ],
    )

    system_defaults = {
        "memory_type": "specification",
        "domain": "system",
        "topic": "architecture",
        "ring": "core",
        "knowledge_type": "law",
        "score": 92,
        "access_count": 22,
        "created_days_ago": 7,
        "accessed_days_ago": 1,
        "namespace": "elefante-core",
        "tags": ["system", "release-notes", "architecture"],
    }
    add_group(
        "system_specs",
        system_defaults,
        [
            {
                "title": "Snapshot-first dashboard contract",
                "content": "The dashboard reads a generated snapshot file; it does not query live Kuzu on every render.",
                "concepts": ["dashboard", "snapshot", "contract", "kuzu", "render"],
                "topic": "architecture",
                "knowledge_type": "law",
            },
            {
                "title": "Dashboard serializer is the single source of truth",
                "content": "dashboard_serializer.py is the single source of truth for dashboard node shape, redaction, and live score projection.",
                "concepts": ["dashboard", "serializer", "single", "source", "truth"],
                "topic": "architecture",
                "knowledge_type": "principle",
                "ring": "domain",
            },
            {
                "title": "GitHub release bodies render from CHANGELOG entries",
                "content": "Architecture rule: GitHub release bodies must be rendered from the matching CHANGELOG entry.",
                "concepts": ["github", "release", "changelog", "body", "render"],
                "surfaces_when": ["what architecture directive governs release notes and specification retrieval"],
            },
            {
                "title": "Version strings are owned by the bump script",
                "content": "Directive: version strings must be updated by the release scripts, never by hand.",
                "concepts": ["version", "strings", "bump", "script", "release"],
                "memory_type": "directive",
                "knowledge_type": "law",
                "topic": "coding-standards",
            },
            {
                "title": "Never ship an empty GitHub release page",
                "content": "Directive: never ship an empty GitHub release page when a tagged version exists.",
                "concepts": ["github", "release", "empty", "page", "tagged"],
                "memory_type": "directive",
                "knowledge_type": "law",
                "topic": "communication",
            },
            {
                "title": "Oversized assets are skipped, not allowed to fail the whole release",
                "content": "Specification: release publication runs after artifact selection and must skip oversized assets cleanly.",
                "concepts": ["release", "publication", "artifact", "oversized", "skip"],
                "topic": "workflow",
                "knowledge_type": "method",
                "ring": "domain",
            },
            {
                "title": "System intent decides when directives should dominate retrieval",
                "content": "Architecture rule: system queries should boost specification and directive memories only when intent is system.",
                "concepts": ["system", "intent", "directive", "retrieval", "boost"],
                "topic": "agent-behavior",
                "knowledge_type": "principle",
                "ring": "core",
            },
            {
                "title": "Specification boosts belong to system questions only",
                "content": "System retrieval stays grounded when specification boosts are gated to system questions instead of generic troubleshooting.",
                "concepts": ["specification", "boost", "system", "questions", "retrieval"],
                "memory_type": "directive",
                "knowledge_type": "principle",
                "topic": "agent-behavior",
                "ring": "domain",
            },
            {
                "title": "Public release notes are part of the product surface",
                "content": "Directive: GitHub Releases are part of the public documentation surface, not optional garnish.",
                "concepts": ["public", "release", "notes", "product", "surface"],
                "memory_type": "directive",
                "knowledge_type": "law",
                "topic": "communication",
            },
            {
                "title": "Release automation links install, README, and debug entrypoints",
                "content": "Directive: release notes must link README, CHANGELOG, installation, and debug entrypoints.",
                "concepts": ["release", "automation", "install", "readme", "debug"],
                "memory_type": "directive",
                "knowledge_type": "method",
                "topic": "workflow",
                "ring": "domain",
            },
        ],
    )

    vector_titles = [
        "Passcode-after-restart is the 60-second proof",
        "Second-brain continuity is easiest to prove after restart",
        "Client Zero should hear the passcode proof before the architecture lecture",
        "The demo asks for the passcode after restart to prove continuity",
        "A remembered passcode turns memory into evidence",
        "The proof of memory is recall after context loss",
        "One-click install plus passcode recall is the customer moment",
        "Show continuity, then explain scoring",
        "The 60-second proof sells the outcome, not the internals",
        "Passcode recall is the smallest believable demo",
    ]
    vector_contents = [
        "What is my Elefante test passcode proof of memory retrieval and second brain continuity.",
        "The 60-second proof asks for the Elefante passcode after restart to demonstrate continuity, install success, and second-brain retrieval.",
        "Client Zero should hear the passcode proof before the architecture lecture because outcome beats internals on first contact.",
        "The demo asks for the passcode after restart because continuity is more believable than a slide about scoring.",
        "A remembered passcode turns memory from theory into evidence and makes continuity emotionally legible.",
        "The proof of memory is recall after context loss, not a paragraph about embeddings.",
        "One-click install plus passcode recall is the customer moment that proves value before theory.",
        "Show continuity, then explain scoring, because the customer buys the car before the hood diagram.",
        "The 60-second proof sells the outcome, not the internals, and it makes second-brain continuity feel real.",
        "Passcode recall is the smallest believable demo because it compresses memory, restart, retrieval, and trust into one moment.",
    ]
    vector_topics = [
        "general",
        "communication",
        "communication",
        "communication",
        "communication",
        "user-profile",
        "collaboration",
        "communication",
        "communication",
        "general",
    ]
    vector_types = ["note", "insight", "preference", "note", "insight", "preference", "decision", "decision", "preference", "conversation"]
    vector_rings = ["leaf", "topic", "domain", "topic", "topic", "domain", "domain", "domain", "core", "leaf"]
    vector_knowledge = ["fact", "insight", "preference", "method", "insight", "preference", "decision", "method", "principle", "fact"]
    vector_scores = [22, 86, 64, 82, 78, 72, 80, 76, 54, 48]
    vector_access = [1, 18, 0, 16, 12, 6, 10, 9, 0, 0]
    vector_created = [220, 4, 9, 4, 6, 18, 5, 7, 12, 25]
    vector_accessed = [220, 1, 9, 2, 3, 8, 2, 3, 12, 25]
    vector_processing = ["processed", "processed", "processing", "processed", "processed", "processed", "processed", "processed", "raw", "raw"]
    vector_status = ["new", "verified", "new", "new", "new", "related", "new", "new", "refined", "new"]
    for idx, title in enumerate(vector_titles):
        add_seed(
            title=title,
            cohort="vector_floor",
            content=vector_contents[idx],
            concepts=[] if idx == 0 else ["passcode", "proof", "restart", "continuity", "retrieval"],
            surfaces_when=["what is my elefante test passcode proof of memory retrieval and second brain continuity"],
            memory_type=vector_types[idx],
            domain="reference",
            topic=vector_topics[idx],
            ring=vector_rings[idx],
            knowledge_type=vector_knowledge[idx],
            score=vector_scores[idx],
            access_count=vector_access[idx],
            created_days_ago=vector_created[idx],
            accessed_days_ago=vector_accessed[idx],
            tags=["client-zero", "demo", "proof"],
            namespace="client-zero",
            processing_status=vector_processing[idx],
            status=vector_status[idx],
        )

    domain_payloads = [
        ("work", "Work continuity survives the meeting restart", "A working session can resume with the exact blocking issue still remembered.", "workflow"),
        ("personal", "Personal preferences return after context switch", "A personal preference can reappear on the first reply after a fresh session.", "user-profile"),
        ("learning", "Learning notes survive notebook restarts", "A learning thread can continue without re-explaining the same concept map.", "general"),
        ("project", "Project release rules return after IDE reboot", "A project workflow can recover the release rule immediately after restart.", "workflow"),
        ("reference", "Reference compendiums bring back the exact fix", "A reference memory can surface the exact bug fix without a new hunt.", "communication"),
        ("system", "System directives prevent the wrong release behavior", "A system rule can stop the wrong automation path before damage is done.", "agent-behavior"),
        ("work", "Work code review resumes with the blocking bug remembered", "A review can resume with the same blocking defect still in focus.", "collaboration"),
        ("personal", "Personal no-emoji preference returns on the first reply", "Response style can stay aligned with the user without being restated.", "user-profile"),
        ("learning", "Learning style stays concise after a new session", "Teaching style can stay concise and structured without a new prompt.", "communication"),
        ("project", "Project onboarding remembers the one-click promise", "The product story can restart at the customer value instead of the internals.", "general"),
    ]
    for domain, title, suffix, topic in domain_payloads:
        add_seed(
            title=title,
            cohort="domain_variants",
            content=(
                "Elefante is a local-first persistent memory engine that gives AI agents a second brain. "
                + suffix
            ),
            concepts=["elefante", "local-first", "persistent", "memory", "brain"],
            surfaces_when=["elefante local-first persistent memory second brain"],
            memory_type="note",
            domain=domain,
            topic=topic,
            ring="domain",
            knowledge_type="fact" if topic in {"general", "workflow"} else "preference" if topic == "user-profile" else "insight",
            score=66,
            access_count=6,
            created_days_ago=33,
            accessed_days_ago=9,
            tags=["second-brain", domain],
            namespace="client-zero",
            processing_status="raw" if title in {
                "Learning notes survive notebook restarts",
                "Project onboarding remembers the one-click promise",
            } else "processed",
        )

    cross_project_defaults = {
        "memory_type": "insight",
        "domain": "learning",
        "topic": "coding-standards",
        "ring": "leaf",
        "knowledge_type": "insight",
        "score": 58,
        "access_count": 0,
        "created_days_ago": 14,
        "accessed_days_ago": 14,
        "namespace": "field-notes",
        "tags": ["field-notes", "cross-project"],
    }
    add_group(
        "cross_project_lessons",
        cross_project_defaults,
        [
            {
                "title": "Safe file patching means read then rewrite, never stream overwrite",
                "content": "Safe file patching means reading the file fully into memory, applying the change, and writing it back; blind stream overwrites can truncate files on macOS.",
                "concepts": ["safe", "file", "patching", "rewrite", "truncate"],
                "topic": "coding-standards",
                "knowledge_type": "law",
                "memory_type": "directive",
                "ring": "core",
                "score": 74,
                "access_count": 7,
                "created_days_ago": 40,
                "accessed_days_ago": 6,
            },
            {
                "title": "Inner-wrapper backgrounds create real transparent spacers",
                "content": "Move a section background onto an inner wrapper when you need transparent spacer gaps; spacer divs inside the same background parent will never reveal what is behind them.",
                "concepts": ["background", "inner-wrapper", "transparent", "spacer", "section"],
                "topic": "coding-standards",
                "knowledge_type": "method",
                "memory_type": "decision",
                "processing_status": "processed",
            },
            {
                "title": "GGUF checkpoints need dedicated loaders",
                "content": "GGUF checkpoints cannot go through CheckpointLoaderSimple; they need dedicated loader nodes for the UNet, VAE, and text encoders.",
                "concepts": ["gguf", "checkpoint", "loader", "unet", "vae"],
                "topic": "tools-environment",
                "knowledge_type": "fact",
                "memory_type": "fact",
            },
            {
                "title": "API queuing beats browser automation for ComfyUI",
                "content": "ComfyUI automation is more stable through the prompt API than through headless browser clicks on Queue Prompt.",
                "concepts": ["api", "queue", "browser", "automation", "comfyui"],
                "topic": "tools-environment",
                "knowledge_type": "principle",
                "memory_type": "insight",
            },
            {
                "title": "MPS forbids float64 and complex tensor shortcuts",
                "content": "Apple Silicon MPS forbids float64 tensors and complex-tensor fallback paths, so custom nodes need float32 and sometimes CPU offload for rotary math.",
                "concepts": ["mps", "float64", "complex", "tensor", "cpu"],
                "topic": "tools-environment",
                "knowledge_type": "fact",
                "memory_type": "fact",
            },
            {
                "title": "Never test huge attention on MPS without a memory budget",
                "content": "Large attention on unified-memory Macs can crash the whole system, so calculate the tensor budget before running the experiment.",
                "concepts": ["attention", "mps", "memory", "budget", "crash"],
                "topic": "agent-behavior",
                "knowledge_type": "law",
                "memory_type": "directive",
                "ring": "core",
            },
            {
                "title": "Every simulator batch exports full conversation logs",
                "content": "Simulator runs are not complete until the full conversation logs are exported into tmp with a header, summary table, and turn-by-turn transcript.",
                "concepts": ["simulator", "batch", "export", "logs", "transcript"],
                "topic": "collaboration",
                "knowledge_type": "method",
                "memory_type": "decision",
                "score": 68,
                "access_count": 4,
                "created_days_ago": 30,
                "accessed_days_ago": 12,
            },
            {
                "title": "Diagrams show setup, not solutions",
                "content": "A teaching diagram should show what the student needs to look at, not the answer or the algebraic shortcut.",
                "concepts": ["diagram", "setup", "student", "answer", "teaching"],
                "topic": "general",
                "knowledge_type": "principle",
                "memory_type": "insight",
                "processing_status": "raw",
                "status": "new",
            },
            {
                "title": "Compute geometry; grep-based SVG verification is theater",
                "content": "SVG verification must use geometry and spatial relationships because string matching text in the markup proves nothing about visual correctness.",
                "concepts": ["geometry", "svg", "verification", "spatial", "markup"],
                "topic": "coding-standards",
                "knowledge_type": "insight",
                "memory_type": "insight",
                "processing_status": "processing",
                "status": "consolidated",
                "score": 62,
                "access_count": 2,
                "created_days_ago": 20,
                "accessed_days_ago": 20,
            },
            {
                "title": "Never blindly apply authority prefixes like spec- to old docs",
                "content": "Authority prefixes like spec- should never be applied blindly, because they can resurrect obsolete documents as active source of truth.",
                "concepts": ["authority", "prefix", "spec", "docs", "obsolete"],
                "topic": "collaboration",
                "knowledge_type": "law",
                "memory_type": "directive",
                "ring": "core",
                "score": 70,
                "access_count": 5,
                "created_days_ago": 15,
                "accessed_days_ago": 10,
            },
        ],
    )

    title_map = {seed.title: seed for seed in seeds}

    def connect(source_title: str, target_title: str, relationship: str = "RELATES_TO") -> None:
        title_map[source_title].graph_links.append((target_title, relationship))

    def supersede(newer_title: str, older_title: str) -> None:
        title_map[newer_title].supersedes_title = older_title
        title_map[older_title].superseded_by_title = newer_title

    supersede("GitHub release bodies render from CHANGELOG entries", "Draft release notes typed manually in workflow YAML")
    supersede("Version strings are owned by the bump script", "Branch-local version bump checklist from pre-script days")

    title_map["PyInstaller was blamed, but that was the wrong diagnosis"].conflict_titles.append(
        "Linux release asset exceeded GitHub's 2 GiB limit"
    )
    title_map["Live backend queries on every render keep the dashboard freshest"].conflict_titles.append(
        "Snapshot-first dashboard contract"
    )

    connect("Snapshot-first dashboard contract", "Dashboard serializer is the single source of truth", "REFERENCES")
    connect("Snapshot-first dashboard contract", "Blank dashboard triage starts with the snapshot file", "RELATES_TO")
    connect("Dashboard serializer is the single source of truth", "System intent decides when directives should dominate retrieval", "RELATES_TO")
    connect("Server readiness gate fixes the blank first launch", "Retry backoff heals early snapshot fetches", "DEPENDS_ON")
    connect("Server readiness gate fixes the blank first launch", "First-launch races are timing bugs, not dead dashboards", "RELATES_TO")
    connect("Blank dashboard triage starts with the snapshot file", "Snapshot-first dashboard contract", "REFERENCES")
    connect("Search-before-write is the compliance gate", "Blocked responses must say action required", "DEPENDS_ON")
    connect("Search-before-write is the compliance gate", "Search-before-write prevents silent memory mutation", "RELATES_TO")
    connect("Search proof protects the audit trail", "The audit trail starts with the search result", "RELATES_TO")
    connect("QueryResult lifetime leak can segfault FactorizedTable", "Materialize rows inside the worker thread", "DEPENDS_ON")
    connect("Materialize rows inside the worker thread", "Never return native QueryResult through asyncio futures", "REFERENCES")
    connect("Python rows are safe; QueryResult handles are not", "Asynchronous Kuzu code must fully materialize rows", "RELATES_TO")
    connect("Repo-local Python 3.11 is the installation authority", "The configured interpreter beats bare python", "REFERENCES")
    connect("Child-process temp HOME isolates live data safely", "Shared model cache may live outside the sandbox", "RELATES_TO")
    connect("Linux release asset exceeded GitHub's 2 GiB limit", "Preflight asset size before GitHub release publish", "DEPENDS_ON")
    connect("GitHub release bodies render from CHANGELOG entries", "Draft release notes typed manually in workflow YAML", "REFERENCES")
    connect("Version strings are owned by the bump script", "Branch-local version bump checklist from pre-script days", "REFERENCES")
    connect("Passcode-after-restart is the 60-second proof", "Second-brain continuity is easiest to prove after restart", "RELATES_TO")
    connect("Client Zero should hear the passcode proof before the architecture lecture", "The 60-second proof sells the outcome, not the internals", "RELATES_TO")
    connect("Safe file patching means read then rewrite, never stream overwrite", "Compute geometry; grep-based SVG verification is theater", "RELATES_TO")
    connect("Every simulator batch exports full conversation logs", "Never blindly apply authority prefixes like spec- to old docs", "RELATES_TO")

    fresh_activity_days = {
        "Linux release asset exceeded GitHub's 2 GiB limit": 2,
        "The release object existed while the Linux zip was too large": 2,
        "Preflight asset size before GitHub release publish": 1,
        "GitHub release bodies render from CHANGELOG entries": 1,
        "Version strings are owned by the bump script": 1,
        "Never ship an empty GitHub release page": 1,
        "Server readiness gate fixes the blank first launch": 2,
        "Retry backoff heals early snapshot fetches": 2,
        "Second-brain continuity is easiest to prove after restart": 3,
        "One-click install plus passcode recall is the customer moment": 3,
    }
    for title, days in fresh_activity_days.items():
        title_map[title].created_days_ago = days
        title_map[title].accessed_days_ago = min(title_map[title].accessed_days_ago, max(days, 1))

    coactivation_clusters = [
        [
            "Server readiness gate fixes the blank first launch",
            "Retry backoff heals early snapshot fetches",
            "First-launch races are timing bugs, not dead dashboards",
        ],
        [
            "Search-before-write is the compliance gate",
            "Blocked responses must say action required",
            "Search-before-write prevents silent memory mutation",
        ],
        [
            "Passcode-after-restart is the 60-second proof",
            "Second-brain continuity is easiest to prove after restart",
            "Show continuity, then explain scoring",
        ],
    ]

    if len(seeds) != 100:
        raise RuntimeError(f"Expected 100 seeds, got {len(seeds)}")

    return SeedPlan(seeds=seeds, coactivation_clusters=coactivation_clusters)


def _audit_snapshot(snapshot: dict[str, Any], required_topics: set[str]) -> list[dict[str, Any]]:
    memory_nodes = [
        node for node in snapshot.get("nodes", [])
        if isinstance(node, dict) and node.get("type") == "memory"
    ]
    memory_ids = {str(node.get("id")) for node in memory_nodes}
    props_list = [node.get("properties", {}) if isinstance(node.get("properties"), dict) else {} for node in memory_nodes]

    topic_counts = Counter(str(props.get("topic") or "general").lower() for props in props_list)
    memory_type_counts = Counter(str(props.get("memory_type") or "unknown").lower() for props in props_list)
    ring_counts = Counter(str(props.get("ring") or "missing").lower() for props in props_list)
    knowledge_counts = Counter(str(props.get("knowledge_type") or "missing").lower() for props in props_list)
    processing_counts = Counter(str(props.get("processing_status") or "missing").lower() for props in props_list)
    lifecycle_counts = Counter(str(props.get("status") or "missing").lower() for props in props_list)

    scores = [int(props.get("score")) for props in props_list if isinstance(props.get("score"), (int, float))]
    recent_14 = 0
    recent_3 = 0
    never_retrieved = 0
    heavy_use = 0
    now = datetime.utcnow()

    for node, props in zip(memory_nodes, props_list):
        created_at = node.get("created_at")
        access_count = int(props.get("access_count") or 0)
        if access_count == 0:
            never_retrieved += 1
        if access_count >= 10:
            heavy_use += 1
        if isinstance(created_at, str) and created_at:
            created_dt = datetime.fromisoformat(created_at.replace("Z", ""))
            age_days = (now - created_dt).total_seconds() / 86400
            if age_days <= 14:
                recent_14 += 1
            if age_days <= 3:
                recent_3 += 1

    memory_memory_edges = 0
    semantic_edges = 0
    graph_edges = 0
    adjacency = Counter()
    for edge in snapshot.get("edges", []):
        if not isinstance(edge, dict):
            continue
        src, dst = _edge_endpoints(edge)
        if not src or not dst:
            continue
        if src in memory_ids and dst in memory_ids:
            memory_memory_edges += 1
            adjacency[src] += 1
            adjacency[dst] += 1
            if str(edge.get("type") or "").lower() == "semantic":
                semantic_edges += 1
            else:
                graph_edges += 1

    spotlight = next((props for props in props_list if props.get("title") == "Snapshot-first dashboard contract"), {})
    spotlight_ok = all(
        bool(spotlight.get(field))
        for field in ["topic", "ring", "knowledge_type", "status", "processing_status", "namespace", "summary", "concepts", "surfaces_when"]
    )

    supersession_ok = False
    contradiction_ok = lifecycle_counts.get("contradictory", 0) >= 1
    for props in props_list:
        title = props.get("title")
        if title == "GitHub release bodies render from CHANGELOG entries":
            supersession_ok = bool(props.get("supersedes_id"))
            break

    checks = [
        {
            "name": "dashboard_snapshot_memory_count",
            "ok": len(memory_nodes) == 100,
            "detail": {"memory_nodes": len(memory_nodes)},
        },
        {
            "name": "dashboard_topic_coverage",
            "ok": required_topics.issubset(set(topic_counts.keys())),
            "detail": dict(topic_counts),
        },
        {
            "name": "dashboard_memory_type_coverage",
            "ok": {"fact", "decision", "preference", "insight", "note", "conversation", "specification", "directive"}.issubset(set(memory_type_counts.keys())),
            "detail": dict(memory_type_counts),
        },
        {
            "name": "dashboard_ring_coverage",
            "ok": {"core", "domain", "topic", "leaf"}.issubset(set(ring_counts.keys())),
            "detail": dict(ring_counts),
        },
        {
            "name": "dashboard_knowledge_type_coverage",
            "ok": {"law", "principle", "preference", "method", "fact", "decision", "insight"}.issubset(set(knowledge_counts.keys())),
            "detail": dict(knowledge_counts),
        },
        {
            "name": "dashboard_processing_states",
            "ok": {"processed", "raw", "processing", "failed"}.issubset(set(processing_counts.keys())),
            "detail": dict(processing_counts),
        },
        {
            "name": "dashboard_lifecycle_states",
            "ok": {"new", "verified", "related", "redundant", "contradictory", "deprecated", "archived", "refined", "consolidated"}.issubset(set(lifecycle_counts.keys())),
            "detail": dict(lifecycle_counts),
        },
        {
            "name": "dashboard_score_spread",
            "ok": bool(scores) and min(scores) <= 30 and max(scores) >= 85 and len({score // 10 for score in scores}) >= 5,
            "detail": {
                "min": min(scores) if scores else None,
                "max": max(scores) if scores else None,
                "buckets": sorted({score // 10 for score in scores}) if scores else [],
            },
        },
        {
            "name": "dashboard_activity_feed",
            "ok": recent_14 >= 18 and recent_3 >= 8,
            "detail": {"created_within_14_days": recent_14, "created_within_3_days": recent_3},
        },
        {
            "name": "dashboard_usage_mix",
            "ok": 8 <= never_retrieved <= 25 and heavy_use >= 18,
            "detail": {"never_retrieved": never_retrieved, "heavy_use": heavy_use},
        },
        {
            "name": "dashboard_graph_richness",
            "ok": memory_memory_edges >= 20 and semantic_edges >= 6 and graph_edges >= 10,
            "detail": {
                "memory_memory_edges": memory_memory_edges,
                "semantic_edges": semantic_edges,
                "graph_edges": graph_edges,
            },
        },
        {
            "name": "dashboard_detail_richness",
            "ok": spotlight_ok,
            "detail": {
                "title": spotlight.get("title"),
                "topic": spotlight.get("topic"),
                "ring": spotlight.get("ring"),
                "knowledge_type": spotlight.get("knowledge_type"),
                "status": spotlight.get("status"),
                "processing_status": spotlight.get("processing_status"),
            },
        },
        {
            "name": "dashboard_supersession_chain",
            "ok": supersession_ok,
            "detail": {"expected_title": "GitHub release bodies render from CHANGELOG entries"},
        },
        {
            "name": "dashboard_contradiction_marker",
            "ok": contradiction_ok,
            "detail": {"contradictory_count": lifecycle_counts.get("contradictory", 0)},
        },
    ]

    return checks


async def _worker_main(sandbox_root: Path) -> int:
    sys.path.insert(0, str(PROJECT_ROOT))

    from src.core.embeddings import get_embedding_service
    from src.core.graph_store import GraphStore
    from src.core.orchestrator import MemoryOrchestrator
    from src.core.vector_store import VectorStore
    from src.models.entity import Entity, EntityType, Relationship, RelationshipType
    from src.models.memory import DomainType, Memory, MemoryMetadata, MemoryStatus, MemoryType
    from src.models.query import QueryMode

    now = datetime.utcnow()

    embedding_service = get_embedding_service()
    vector_store = VectorStore()
    graph_store = GraphStore()
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_service=embedding_service,
    )

    plan = _build_seed_plan()
    seeds = plan.seeds
    embeddings = await embedding_service.generate_embeddings_batch([seed.content for seed in seeds])
    seed_id_map: dict[str, UUID] = {seed.title: seed.id for seed in seeds}

    id_map: dict[str, str] = {}
    for seed, embedding in zip(seeds, embeddings):
        related_ids = [seed_id_map[target_title] for target_title, _ in seed.graph_links if target_title in seed_id_map]
        metadata = MemoryMetadata(
            created_at=now - timedelta(days=seed.created_days_ago),
            created_by="sandbox",
            domain=DomainType(seed.domain),
            category=seed.topic,
            memory_type=MemoryType(seed.memory_type),
            score=seed.score,
            tags=seed.tags,
            concepts=seed.concepts,
            surfaces_when=seed.surfaces_when,
            authority_score=seed.authority_score or 0.5,
            status=MemoryStatus(seed.status),
            related_memory_ids=related_ids,
            conflict_ids=[seed_id_map[title] for title in seed.conflict_titles if title in seed_id_map],
            supersedes_id=seed_id_map.get(seed.supersedes_title),
            superseded_by_id=seed_id_map.get(seed.superseded_by_title),
            author="sandbox",
            last_accessed=now - timedelta(days=seed.accessed_days_ago),
            last_modified=now - timedelta(days=seed.accessed_days_ago),
            access_count=seed.access_count,
            deprecated=seed.deprecated,
            archived=seed.archived,
            summary=seed.summary,
            custom_metadata={
                "title": seed.title,
                "summary": seed.summary,
                "cohort": seed.cohort,
                "namespace": seed.namespace,
                "processing_status": seed.processing_status,
                "ring": seed.ring,
                "knowledge_type": seed.knowledge_type,
                "concepts": _list_string(seed.concepts),
                "surfaces_when": _list_string(seed.surfaces_when),
                "authority_score": seed.authority_score or 0.5,
            },
        )
        memory = Memory(id=seed.id, content=seed.content, metadata=metadata, embedding=embedding)
        await vector_store.add_memory(memory)

        entity = Entity(
            id=seed.id,
            name=seed.title,
            type=EntityType.MEMORY,
            description=seed.content[:180],
            created_at=metadata.created_at,
            updated_at=metadata.last_modified,
            properties={
                "content": seed.content[:200],
                "memory_type": seed.memory_type,
                "score": seed.score,
                "timestamp": metadata.created_at.isoformat(),
                "cohort": seed.cohort,
                "topic": seed.topic,
                "ring": seed.ring,
                "knowledge_type": seed.knowledge_type,
            },
            tags=seed.tags,
        )
        await graph_store.create_entity(entity)
        id_map[seed.title] = str(seed.id)

    for seed in seeds:
        for target_title, relationship_name in seed.graph_links:
            relationship_type = getattr(RelationshipType, relationship_name, RelationshipType.RELATES_TO)
            await graph_store.create_relationship(
                Relationship(
                    from_entity_id=seed.id,
                    to_entity_id=seed_id_map[target_title],
                    relationship_type=relationship_type,
                    strength=0.85,
                )
            )

    for _ in range(40):
        for cluster in plan.coactivation_clusters:
            await orchestrator.record_coactivation([id_map[title] for title in cluster])

    def _memory_title(result) -> str:
        return result.memory.metadata.custom_metadata.get("title", str(result.memory.id))

    def _memory_cohort(result) -> str:
        return result.memory.metadata.custom_metadata.get("cohort", "")

    def _memory_type(result) -> str:
        mem_type = result.memory.metadata.memory_type
        return mem_type.value if hasattr(mem_type, "value") else str(mem_type)

    def _memory_status(result) -> str:
        status = result.memory.metadata.status
        return status.value if hasattr(status, "value") else str(status)

    def _signal_map(result) -> dict[str, dict[str, Any]]:
        signals = result.explanation.get("signals", []) if result.explanation else []
        return {signal["name"]: signal for signal in signals}

    async def _search(query: str, recent_titles: list[str] | None = None, limit: int = 12):
        return await orchestrator.search_memories(
            query=query,
            mode=QueryMode.SEMANTIC,
            limit=limit,
            min_similarity=0.0,
            include_conversation=False,
            include_stored=True,
            apply_temporal_decay=False,
            recent_memory_ids=[id_map[title] for title in (recent_titles or [])],
        )

    def _find_rank(results, title: str) -> int:
        for idx, result in enumerate(results):
            if _memory_title(result) == title:
                return idx
        return 999

    def _scenario_detail(results) -> list[dict[str, Any]]:
        details: list[dict[str, Any]] = []
        for idx, result in enumerate(results[:5], start=1):
            signals = _signal_map(result)
            details.append(
                {
                    "rank": idx,
                    "title": _memory_title(result),
                    "cohort": _memory_cohort(result),
                    "memory_type": _memory_type(result),
                    "topic": result.memory.metadata.category,
                    "ring": result.memory.metadata.custom_metadata.get("ring", ""),
                    "knowledge_type": result.memory.metadata.custom_metadata.get("knowledge_type", ""),
                    "status": _memory_status(result),
                    "processing_status": result.memory.metadata.custom_metadata.get("processing_status", ""),
                    "score": round(result.score, 3),
                    "vector_score": round(result.vector_score or 0.0, 3),
                    "concept_score": round(signals.get("concept_overlap", {}).get("score", 0.0), 3),
                    "authority_score": round(signals.get("authority", {}).get("score", 0.0), 3),
                    "temporal_score": round(signals.get("temporal", {}).get("score", 0.0), 3),
                    "coactivation_score": round(signals.get("coactivation", {}).get("score", 0.0), 3),
                    "memory_score": result.memory.metadata.score,
                    "access_count": result.memory.metadata.access_count,
                }
            )
        return details

    scenarios: list[dict[str, Any]] = []

    semantic_results = await _search("Which pytest subset validates Kuzu lock and graph store close behavior?")
    semantic_ok = _memory_title(semantic_results[0]) == "Persistence tests prove the Kuzu lock contract"
    scenarios.append(
        {
            "name": "semantic_priority",
            "ok": semantic_ok,
            "detail": _scenario_detail(semantic_results),
        }
    )

    concept_results = await _search("kuzu queryresult factorizedtable lifetime segfault")
    concept_signals = _signal_map(concept_results[0])
    concept_ok = _memory_title(concept_results[0]) == "QueryResult lifetime leak can segfault FactorizedTable" and concept_signals.get("concept_overlap", {}).get("score", 0) > 0.35
    scenarios.append(
        {
            "name": "concept_overlap",
            "ok": concept_ok,
            "detail": _scenario_detail(concept_results),
        }
    )

    authority_results = await _search("compliance gate search before write blocked response action required")
    authority_high = next(result for result in authority_results if _memory_title(result) == "Blocked responses must say action required")
    authority_low = next(result for result in authority_results if _memory_title(result) == "The audit trail starts with the search result")
    authority_ok = (
        _find_rank(authority_results, "Blocked responses must say action required") < _find_rank(authority_results, "The audit trail starts with the search result")
        and _signal_map(authority_high).get("authority", {}).get("score", 0.0)
        > _signal_map(authority_low).get("authority", {}).get("score", 0.0)
        and authority_high.score > (authority_high.vector_score or 0.0) * 0.70
    )
    scenarios.append(
        {
            "name": "authority_ordering",
            "ok": authority_ok,
            "detail": _scenario_detail(authority_results),
        }
    )

    temporal_results = await _search("python virtual environment install verification repo local")
    temporal_recent = next(result for result in temporal_results if _memory_title(result) == "Repo-local Python 3.11 is the installation authority")
    temporal_stale = next(result for result in temporal_results if _memory_title(result) == "System Python is not the verification path")
    temporal_ok = (
        _find_rank(temporal_results, "Repo-local Python 3.11 is the installation authority") < _find_rank(temporal_results, "System Python is not the verification path")
        and _signal_map(temporal_recent).get("temporal", {}).get("score", 0.0)
        > _signal_map(temporal_stale).get("temporal", {}).get("score", 0.0)
        and temporal_recent.score > (temporal_recent.vector_score or 0.0) * 0.70
    )
    scenarios.append(
        {
            "name": "temporal_ordering",
            "ok": temporal_ok,
            "detail": _scenario_detail(temporal_results),
        }
    )

    coact_plain = await _search("dashboard blank launch retry backoff first launch")
    coact_context = await _search(
        "dashboard blank launch retry backoff first launch",
        recent_titles=["Server readiness gate fixes the blank first launch"],
    )
    coact_plain_rank = _find_rank(coact_plain, "Retry backoff heals early snapshot fetches")
    coact_context_rank = _find_rank(coact_context, "Retry backoff heals early snapshot fetches")
    coact_signals = _signal_map(next(result for result in coact_context if _memory_title(result) == "Retry backoff heals early snapshot fetches"))
    coact_ok = coact_context_rank < coact_plain_rank and coact_signals.get("coactivation", {}).get("score", 0) > 0.0
    scenarios.append(
        {
            "name": "coactivation_boost",
            "ok": coact_ok,
            "detail": {
                "without_context": _scenario_detail(coact_plain),
                "with_context": _scenario_detail(coact_context),
            },
        }
    )

    system_positive = await _search("What architecture directive governs release notes and specification retrieval?")
    system_positive_ok = _memory_type(system_positive[0]) in {"specification", "directive"}
    scenarios.append(
        {
            "name": "system_intent_positive",
            "ok": system_positive_ok,
            "detail": _scenario_detail(system_positive),
        }
    )

    system_negative = await _search("Why did create GitHub release fail for v2.6.0 Linux asset upload?")
    system_negative_ok = _memory_title(system_negative[0]) == "Linux release asset exceeded GitHub's 2 GiB limit" and _memory_type(system_negative[0]) not in {"specification", "directive"}
    scenarios.append(
        {
            "name": "system_intent_negative",
            "ok": system_negative_ok,
            "detail": _scenario_detail(system_negative),
        }
    )

    floor_results = await _search("What is my Elefante test passcode proof of memory retrieval and second brain continuity")
    floor_target = next(result for result in floor_results if _memory_title(result) == "Passcode-after-restart is the 60-second proof")
    floor_ok = _find_rank(floor_results, "Passcode-after-restart is the 60-second proof") <= 3 and floor_target.score >= (floor_target.vector_score or 0.0) * 0.70
    scenarios.append(
        {
            "name": "vector_floor_guard",
            "ok": floor_ok,
            "detail": _scenario_detail(floor_results),
        }
    )

    domain_results = await _search("Elefante local-first persistent memory second brain")
    domain_top = [result for result in domain_results if _memory_cohort(result) == "domain_variants"][:5]
    domain_scores = [result.score for result in domain_top]
    domain_signal_names = set()
    for result in domain_top:
        domain_signal_names.update(_signal_map(result).keys())
    domain_ok = len(domain_top) >= 3 and max(domain_scores) - min(domain_scores) < 0.005 and "domain" not in domain_signal_names
    scenarios.append(
        {
            "name": "domain_removed_noise",
            "ok": domain_ok,
            "detail": _scenario_detail(domain_top),
        }
    )

    graph_store.close()

    snapshot_path = Path(os.environ["ELEFANTE_DATA_DIR"]) / "dashboard_snapshot.json"
    pipeline_env = os.environ.copy()
    pipeline_env.update(
        {
            "ELEFANTE_SNAPSHOT_SEMANTIC_EDGES": "1",
            "ELEFANTE_SNAPSHOT_SEMANTIC_THRESHOLD": "0.72",
            "ELEFANTE_SNAPSHOT_SEMANTIC_TOPK": "4",
            "ELEFANTE_SNAPSHOT_SEMANTIC_MUTUAL": "1",
            "ELEFANTE_SNAPSHOT_CLUSTER": "0",
        }
    )
    pipeline_result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts/pipeline/update_dashboard_data.py")],
        cwd=str(PROJECT_ROOT),
        env=pipeline_env,
        capture_output=True,
        text=True,
    )

    dashboard_checks: list[dict[str, Any]] = []
    if pipeline_result.returncode != 0 or not snapshot_path.exists():
        dashboard_checks.append(
            {
                "name": "dashboard_snapshot_pipeline",
                "ok": False,
                "detail": {
                    "returncode": pipeline_result.returncode,
                    "stdout": pipeline_result.stdout,
                    "stderr": pipeline_result.stderr,
                    "snapshot_path": str(snapshot_path),
                },
            }
        )
    else:
        snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location(
            "verify_dashboard_snapshot",
            PROJECT_ROOT / "scripts/verify/verify_dashboard_snapshot.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load verify_dashboard_snapshot.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        validation = module.validate_snapshot(snapshot_payload, require_curation=True)
        dashboard_checks.append(
            {
                "name": "dashboard_snapshot_validation",
                "ok": validation.ok(strict=False),
                "detail": {
                    "info": validation.info,
                    "warnings": validation.warnings,
                    "errors": validation.errors,
                    "snapshot_path": str(snapshot_path),
                    "pipeline_stdout": pipeline_result.stdout,
                    "pipeline_stderr": pipeline_result.stderr,
                },
            }
        )
        dashboard_checks.extend(
            _audit_snapshot(
                snapshot_payload,
                required_topics={
                    "communication",
                    "workflow",
                    "agent-behavior",
                    "debugging",
                    "coding-standards",
                    "architecture",
                    "tools-environment",
                    "user-profile",
                    "collaboration",
                    "general",
                },
            )
        )

    summary = {
        "sandbox": str(sandbox_root),
        "memory_count": len(seeds),
        "cohorts": sorted({seed.cohort for seed in seeds}),
        "scenarios": scenarios,
        "dashboard": {
            "snapshot": str(snapshot_path),
            "checks": dashboard_checks,
        },
    }
    (sandbox_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n============================================================")
    print("  Elefante 100-memory scoring + dashboard sandbox")
    print("============================================================")
    print(f"  seeded memories: {len(seeds)}")
    print(f"  cohorts: {len(summary['cohorts'])}")
    print(f"  summary: {sandbox_root / 'summary.json'}")
    print(f"  snapshot: {snapshot_path}")
    print()

    all_ok = True
    for scenario in scenarios:
        tag = "PASS" if scenario["ok"] else "FAIL"
        print(f"  [{tag}] {scenario['name']}")
        all_ok = all_ok and scenario["ok"]

    if dashboard_checks:
        print()
        for check in dashboard_checks:
            tag = "PASS" if check["ok"] else "FAIL"
            print(f"  [{tag}] {check['name']}")
            all_ok = all_ok and check["ok"]

    return 0 if all_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed 100 crafted memories in an isolated sandbox and verify both 5-signal retrieval and dashboard demo coverage.")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--sandbox", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--keep-sandbox", action="store_true", help="Keep the temp HOME/data sandbox after the run for inspection.")
    args = parser.parse_args()

    if not args.worker:
        return _parent_main(keep_sandbox=args.keep_sandbox)

    if args.sandbox is None:
        raise SystemExit("--sandbox is required in worker mode")

    sys.path.insert(0, str(PROJECT_ROOT))
    from src.utils.logger import setup_logging
    from src.core.embeddings import get_embedding_service

    setup_logging(level="WARNING", console=True, format_type="text", log_file=None)
    get_embedding_service()._load_model()
    return asyncio.run(_worker_main(args.sandbox))


if __name__ == "__main__":
    raise SystemExit(main())