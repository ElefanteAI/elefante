#!/usr/bin/env python3
"""Build Elefante's deterministic, source-grounded dashboard showcase.

The output is a redacted dashboard snapshot. It never opens or mutates an
Elefante vector or graph store. Access counts and timestamps are synthetic and
declared as such in the snapshot's curation metadata.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


GENERATED_AT = "2026-07-26T18:00:00.000Z"
PRODUCT_BASELINE = "v2.12.0"

# id, title, description, type, topic, score, access_count, status, evidence
MEMORIES = [
    ("daemon-assumption", "Multiple agent hosts can each own a memory process", "Independent stdio servers appear simple, but every process can become a competing database owner.", "note", "Runtime authority", 42, 2, "superseded", "workspace/ISSUES.md · GAP-025"),
    ("kuzu-evidence", "Kuzu is a single-writer graph store", "Concurrent database-owning clients create lock contention and make write origin impossible to trust.", "fact", "Runtime authority", 86, 19, "verified", "workspace/postmortems/memory.md · Issue 15"),
    ("daemon-decision", "One loopback daemon owns memory", "A single local daemon owns storage, concurrency, migrations, and provenance for every compatible agent host.", "decision", "Runtime authority", 94, 28, "verified", "workspace/PLANNING.md · §1.3"),
    ("bridge-guard", "The stdio bridge carries provenance, not storage", "Stdio-only clients connect through a storage-free bridge; two concurrent bridges retain distinct Codex and Claude origins.", "specification", "Runtime authority", 97, 24, "verified", "tests/test_mcp_daemon.py · slow two-bridge proof"),
    ("dashboard-live-assumption", "A dashboard can query live stores for convenience", "Live hydration looked convenient but quietly gave the browser a second path into private memory state.", "note", "Trust boundary", 38, 1, "superseded", "workspace/postmortems/dashboard.md · Issue 11"),
    ("snapshot-evidence", "Browser convenience bypassed the read-only boundary", "Live graph hydration, semantic search, and browser refresh all crossed the snapshot contract.", "insight", "Trust boundary", 83, 12, "verified", "workspace/ISSUES.md · BUG-031"),
    ("snapshot-decision", "The dashboard reads one redacted snapshot", "Every dashboard data route reads dashboard_snapshot.json; live regeneration remains an explicit MCP or operator action.", "decision", "Trust boundary", 93, 20, "verified", "docs/reference/dashboard-snapshot.md"),
    ("loopback-guard", "Private memory stays loopback-bound", "Dashboard and daemon bind to 127.0.0.1 with explicit local origins. Public exposure is never a default.", "specification", "Trust boundary", 96, 22, "verified", "workspace/ISSUES.md · BUG-028"),
    ("signal-thesis", "Every injected token must earn its place", "Elefante maximizes signal-per-token in the agent context window; feature count is not the product metric.", "specification", "Retrieval intelligence", 98, 31, "verified", "workspace/PLANNING.md · §1"),
    ("vector-signal", "Semantic similarity anchors retrieval", "Vector similarity carries 35 percent of the cognitive score and establishes a 70 percent semantic floor.", "fact", "Retrieval intelligence", 91, 17, "verified", "src/core/retrieval.py"),
    ("concept-signal", "Concept overlap recovers shared meaning", "Concept overlap contributes 30 percent, so related ideas can reinforce a result even when wording changes.", "fact", "Retrieval intelligence", 89, 15, "verified", "src/core/retrieval.py"),
    ("coactivation-signal", "Memories retrieved together learn together", "Co-activation contributes 15 percent and persists across restarts, allowing repeated working context to become easier to recover.", "insight", "Retrieval intelligence", 92, 21, "verified", "src/core/retrieval.py · BUG-018"),
    ("authority-signal", "Authority is earned, not manually declared", "Authority contributes 10 percent and reflects memory type, reinforcement, and actual use rather than a user-assigned importance slider.", "decision", "Retrieval intelligence", 88, 14, "verified", "src/core/retrieval.py"),
    ("temporal-signal", "Fresh context receives a measured advantage", "Temporal freshness contributes 10 percent while durable specifications and directives retain their authority without generic score inflation.", "fact", "Retrieval intelligence", 84, 11, "verified", "src/core/retrieval.py"),
    ("search-first", "Search before every write", "Elefante retrieves related knowledge before adding, updating, or deleting memory. Duplicate growth is blocked mechanically.", "directive", "Memory governance", 99, 34, "verified", "src/mcp/server.py · Compliance Gate"),
    ("update-over-duplicate", "Update the existing truth instead of cloning it", "A near-match should be amended or superseded so future retrieval has one authoritative answer.", "preference", "Memory governance", 90, 18, "verified", "agents/memory-janitor.md"),
    ("contradiction-policy", "Contradictions remain visible until resolved", "Conflicting memories are linked and surfaced; the newest grounded decision wins without erasing the path that produced it.", "specification", "Memory governance", 87, 13, "verified", "agents/memory-janitor.md"),
    ("unknown-law", "If it is not grounded, the answer is UNKNOWN", "Grounding prevents confident invention when neither the memory system nor the workspace contains the requested fact.", "directive", "Memory governance", 98, 29, "verified", "workspace/PLANNING.md · Four Laws"),
    ("stdout-law", "Stdout is reserved for JSON-RPC", "Any diagnostic text from an MCP-reachable code path goes to structured logs or stderr, never stdout.", "directive", "Memory governance", 95, 25, "verified", "agents/orchestrator.md · Five Gates"),
    ("sqlite-default", "Fresh stores use embedded SQLite vectors", "SQLite is the configured vector-store default for fresh installations; Kuzu remains the relationship graph.", "decision", "Storage", 92, 16, "verified", "src/utils/config.py"),
    ("migration-parity", "Storage migration must prove parity before apply", "Dry-run migration verifies UUIDs, reconstructed metadata, float32 embeddings, and representative top-10 search overlap.", "specification", "Storage", 93, 18, "verified", "workspace/PLANNING.md · GAP-029"),
    ("chroma-blocker", "The release lock still contains one ChromaDB advisory", "The embedded endpoint is not exposed, but the unresolved advisory keeps the Trust Release blocked until an authorized transition and clean audit.", "fact", "Storage", 80, 9, "active", "workspace/ISSUES.md · GAP-029"),
    ("no-live-migration", "Never migrate a live store without explicit authority", "Apply requires a stopped system, an exact checksum-manifested backup, a new destination, and user authorization.", "directive", "Storage", 97, 26, "verified", "workspace/PLANNING.md · §2.4"),
    ("source-provenance", "Every durable write records where it came from", "Source tuples distinguish host, transport, and installation so one shared memory authority remains auditable across agents.", "decision", "Host continuity", 94, 23, "verified", "workspace/PLANNING.md · GAP-025"),
    ("host-tiers", "Compatibility is not certification", "Every host is labeled certified, compatible, or community. Elefante does not claim an integration that has not completed its lifecycle proof.", "specification", "Host continuity", 91, 17, "verified", "workspace/PLANNING.md · §1.3"),
    ("manifest-ownership", "Installers own exact entries, not whole files", "The install manifest records only Elefante-owned configuration so unrelated servers and later user edits survive upgrades and uninstall.", "decision", "Host continuity", 90, 15, "verified", "workspace/PLANNING.md · §2.2"),
    ("safe-uninstall", "User-modified configuration is preserved", "Uninstall removes only manifest-recorded entries whose hashes still match the emitted state.", "specification", "Host continuity", 93, 19, "verified", "workspace/PLANNING.md · §10.1"),
    ("one-memory-many-hosts", "Tools can change while project memory continues", "The daemon-and-bridge architecture separates durable project context from any one editor or agent host.", "insight", "Host continuity", 88, 14, "verified", "workspace/PLANNING.md · §1.3"),
    ("agent-zero-tier", "Agent Zero remains a community path", "Community documentation exists, but the product does not promote Agent Zero to a certified integration without host-driven evidence.", "fact", "Host continuity", 75, 7, "verified", "workspace/PLANNING.md · §2.2"),
    ("backup-contract", "A JSON export is not a backup", "Portable exports omit embeddings and have no restore path; real backup uses checksummed archives and dry-run-first restore.", "insight", "Recovery", 92, 21, "verified", "workspace/ISSUES.md · GAP-013"),
    ("recoverable-reset", "Factory reset begins with a recoverable move", "Configured vector and graph stores are moved into a timestamped recovery area rather than destroyed in place.", "specification", "Recovery", 91, 15, "verified", "workspace/PLANNING.md · SQLite operator-surface repair"),
    ("safe-extraction", "Restore rejects unsafe archive paths", "Restore validates checksums and path safety before replacing current state.", "specification", "Recovery", 89, 12, "verified", "tests/test_backup_restore.py"),
    ("test-isolation", "Verification never pollutes durable memory", "The self-protocol creates a temporary Elefante home and explicitly allows test memories only inside that isolated store.", "directive", "Recovery", 96, 27, "verified", "scripts/verify/verify_e2e_tests.py"),
    ("source-first", "Read source before trusting remembered documentation", "The source-first gate exists because specifications and stored memories can lag behind the shipped implementation.", "directive", "Development process", 99, 36, "verified", "agents/orchestrator.md · Five Gates"),
    ("issue-first", "Match a BUG or GAP before changing code", "Every development session checks the issue ledger and runs the maintained proof before selecting a fix.", "directive", "Development process", 98, 33, "verified", "agents/orchestrator.md · Lifecycle"),
    ("proof-not-promise", "A green API is not a green user experience", "Dashboard bugs repeatedly passed backend checks while the visible interface was blank, mislabeled, or stale.", "insight", "Development process", 90, 20, "verified", "workspace/postmortems/dashboard.md"),
    ("journal-compounds", "Every completed cycle leaves a retrievable deposit", "Ingest, journal, and commit turn a debugging session into context the next agent can actually recover.", "insight", "Development process", 95, 25, "verified", "workspace/PLANNING.md · §10"),
]

SOURCE_IDS = ("source:codex", "source:claude", "source:system")
FEATURED_CHAIN = (
    "demo:daemon-assumption",
    "demo:kuzu-evidence",
    "demo:daemon-decision",
    "demo:bridge-guard",
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_showcase_snapshot() -> dict[str, Any]:
    """Return a deterministic snapshot that exercises every dashboard view."""
    nodes: list[dict[str, Any]] = []
    for index, (key, title, description, memory_type, topic, score, access_count, status, evidence) in enumerate(MEMORIES):
        created_hour = (16 - index) % 24
        nodes.append(
            {
                "id": f"demo:{key}",
                "name": title,
                "type": "memory",
                "description": description,
                "created_at": f"2026-07-{25 - (index % 4):02d}T{created_hour:02d}:00:00.000Z",
                "properties": {
                    "content": description,
                    "title": title,
                    "summary": description,
                    "memory_type": memory_type,
                    "topic": topic,
                    "score": score,
                    "access_count": access_count,
                    "last_accessed": f"2026-07-26T{index % 18:02d}:00:00.000Z",
                    "last_modified": f"2026-07-{25 - (index % 4):02d}T{created_hour:02d}:00:00.000Z",
                    "status": status,
                    "archived": False,
                    "deprecated": status == "superseded",
                    "tags": _slug(topic),
                    "source": "sqlite",
                    "evidence": evidence,
                    "namespace": "showcase",
                    "canonical_key": key,
                    "processing_status": "processed",
                },
            }
        )

    topics = list(dict.fromkeys(item[4] for item in MEMORIES))
    nodes.extend(
        {
            "id": f"topic:{_slug(topic)}",
            "name": topic,
            "type": "signal",
            "description": "Source-grounded product knowledge area.",
            "properties": {"kind": "topic"},
        }
        for topic in topics
    )
    nodes.extend(
        [
            {"id": "source:codex", "name": "Codex", "type": "entity", "description": "Agent provenance", "properties": {"kind": "agent"}},
            {"id": "source:claude", "name": "Claude Code", "type": "entity", "description": "Agent provenance", "properties": {"kind": "agent"}},
            {"id": "source:system", "name": "Elefante", "type": "entity", "description": "System provenance", "properties": {"kind": "system"}},
        ]
    )

    edges: list[dict[str, Any]] = []
    for index, (key, _title, _description, _memory_type, topic, *_rest) in enumerate(MEMORIES):
        memory_id = f"demo:{key}"
        edges.append({"from": memory_id, "to": f"topic:{_slug(topic)}", "label": "ABOUT", "type": "graph"})
        edges.append({"from": memory_id, "to": SOURCE_IDS[index % len(SOURCE_IDS)], "label": "WRITTEN_BY", "type": "provenance"})

    edges.extend(
        [
            {"from": FEATURED_CHAIN[0], "to": FEATURED_CHAIN[1], "label": "CHALLENGED_BY", "type": "graph"},
            {"from": FEATURED_CHAIN[1], "to": FEATURED_CHAIN[2], "label": "LED_TO", "type": "graph"},
            {"from": FEATURED_CHAIN[2], "to": FEATURED_CHAIN[3], "label": "GUARDED_BY", "type": "graph"},
        ]
    )
    memory_ids = [f"demo:{item[0]}" for item in MEMORIES]
    edges.extend(
        {
            "from": memory_ids[index],
            "to": memory_ids[index + 1],
            "label": "RELATED_TO",
            "type": "semantic",
            "similarity": round(0.91 - index * 0.004, 3),
        }
        for index in range(18)
    )

    return {
        "generated_at": GENERATED_AT,
        "curation": {
            "purpose": "Elefante Memory Intelligence dashboard showcase",
            "product_baseline": PRODUCT_BASELINE,
            "deterministic": True,
            "synthetic_behavioral_metadata": True,
            "source_grounded_content": True,
            "contains_user_data": False,
            "disclaimer": "Counts and access history demonstrate product behavior; they are not customer or performance claims.",
        },
        "stats": {
            "total_nodes": len(nodes),
            "memories": len(MEMORIES),
            "entities": len(nodes) - len(MEMORIES),
            "edges": len(edges),
        },
        "nodes": nodes,
        "edges": edges,
        "featured_chain": list(FEATURED_CHAIN),
    }


def write_showcase_snapshot(output: Path, *, force: bool = False) -> Path:
    """Write the snapshot without overwriting an existing file by default."""
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_showcase_snapshot(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Destination dashboard_snapshot.json")
    parser.add_argument("--force", action="store_true", help="Replace only the explicit output path if it exists")
    args = parser.parse_args()
    written = write_showcase_snapshot(args.output.resolve(), force=args.force)
    print(f"Wrote source-grounded showcase snapshot: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
