"""Legacy behavioral-store benchmark for Elefante.

PURPOSE : Populate an isolated Elefante database with 100 deterministic memories
          drawn from Elefante's actual development history, plus realistic
          behavioral history for dashboard completeness.
INJECTION: Direct legacy Chroma VectorStore + Kuzu GraphStore writes. Zero LLM.
CURRENT : This is a store-mutation benchmark, not the current dashboard demo.
          Prefer generate_showcase_snapshot.py for a safe, source-grounded,
          read-only product showcase using the current snapshot contract.
SPEC    : scripts/demo/SPEC_behavioral_history.md

RUN:
    .venv/bin/python scripts/demo/generate_100_memories.py --db ./a0-data/demo_db --force
CLEAN:
    rm -rf ./a0-data/demo_db
"""
import asyncio
import argparse
import math
import random
import uuid
import os
import shutil
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())

from src.core.orchestrator import MemoryOrchestrator  # noqa: E402
from src.core.vector_store import VectorStore  # noqa: E402
from src.core.graph_store import GraphStore  # noqa: E402
from src.models.memory import Memory, MemoryMetadata, MemoryType, MemoryStatus, TYPE_DECAY_RATES  # noqa: E402
from src.models.entity import Entity, EntityType  # noqa: E402

random.seed(42)


def _memory_item(content, memory_type, category, tags=None, **extra):
    payload = {
        "content": content,
        "type": memory_type,
        "category": category,
        "tags": tags or [],
    }
    payload.update(extra)
    return payload


def _foundation_memories():
    return [
        _memory_item("Elefante splits storage by purpose: embedded SQLite is the default semantic memory store and Kuzu holds entities and relationships. Legacy Chroma stores remain readable only when explicitly configured.", "fact", "architecture", ["sqlite", "kuzu", "architecture"], cluster="architecture"),
        _memory_item("The retrieval model in v2.7.0 uses five signals: vector 0.35, concept 0.30, coactivation 0.15, authority 0.10, temporal 0.10. Domain signal was removed after proving it contributed nothing.", "fact", "retrieval", ["v2.7.0", "scoring", "retrieval"], cluster="architecture"),
        _memory_item("Memory type half-lives are intentional product behavior: conversation about 28 days, note 46, insight 87, fact and decision 139, preference 347, specification and directive infinite.", "fact", "memory-model", ["decay", "memory-types", "product-behavior"], cluster="architecture"),
        _memory_item("Elefante exposes 16 MCP tools and 2 prompts across memory, directives, graph, tasks, ETL, context, sessions, dashboard, and system control.", "fact", "mcp", ["tools", "mcp", "surface-area"], cluster="architecture"),
        _memory_item("The tool response contract injects MANDATORY_PROTOCOLS, DIRECTIVES, RELEVANT_CONTEXT when available, and TOKEN_STATS.", "fact", "protocol", ["response-contract", "protocol", "mcp"]),
        _memory_item("Memory metadata is wide by design: 40 plus flattened fields covering classification, lifecycle, relationships, temporal state, and extensibility.", "fact", "memory-model", ["metadata", "schema", "memory-model"]),
        _memory_item("Token intelligence landed in v2.5.0. Every tool response reports output_tokens, overhead_tokens, and signal_ratio.", "fact", "token-intelligence", ["v2.5.0", "tokens", "telemetry"]),
        _memory_item("The runtime stack is Python 3.11, embedded SQLite vectors, Kuzu, sentence-transformers, FastAPI, and a React/Vite dashboard.", "fact", "stack", ["python", "dashboard", "stack"]),
        _memory_item("Co-activation is generated automatically from retrieval history. The server records memories retrieved together and writes CO_ACTIVATED edges to Kuzu.", "fact", "retrieval", ["coactivation", "graph", "retrieval"]),
        _memory_item("The dashboard must read dashboard_snapshot.json, not live database queries. Direct Kuzu calls caused the 11-nodes-vs-71-memories confusion.", "fact", "dashboard", ["dashboard", "snapshot", "known-issue"]),
        _memory_item("Dashboard composite score is weighted 50 percent temporal vitality, 25 percent memory-type weight, and 25 percent engagement.", "fact", "dashboard", ["dashboard", "scoring", "composite-score"]),
        _memory_item("Compliance is mechanical: search before write. elefante-Memory(action=add) must not bypass duplicate and contradiction checks.", "fact", "compliance", ["compliance", "memory-add", "search-first"]),
        _memory_item("ETL classification is agent-driven, not handled by an internal Elefante LLM. The agent enriches memories through ETLProcess and ETLClassify.", "fact", "etl", ["etl", "agent-driven", "classification"]),
        _memory_item("A pre-commit hook blocks commits by running health_check.py and verify_mcp_handshake.py.", "fact", "quality-gates", ["pre-commit", "health-check", "handshake"]),
        _memory_item("The project moved from v1.0.0 in December 2025 to v2.11.0 in July 2026, adding directives, token intelligence, five-signal retrieval, a shared loopback daemon, provenance, and an embedded SQLite default.", "fact", "project-history", ["versions", "timeline", "release-history"]),
        _memory_item("No emojis in source code or docs. The codebase treats decoration as signal loss and enforces that preference with tests.", "preference", "communication", ["no-emojis", "style", "tests"]),
        _memory_item("Use structured logging for normal diagnostics. Reserve raw stderr writes for probe-level debugging in threaded or async startup paths.", "preference", "debugging", ["logging", "stderr", "debugging"]),
        _memory_item("Keep Elefante local-first. Memory, backups, and reset paths must work on the user's machine without cloud dependency.", "preference", "product-direction", ["local-first", "privacy", "product"]),
        _memory_item("Never print to stdout from the MCP server. Stdout is JSON-RPC transport and any stray print corrupts the protocol.", "preference", "protocol", ["stdout", "json-rpc", "protocol"]),
        _memory_item("Keep commits scoped to one concern. Do not force-push and do not deploy without permission.", "preference", "workflow", ["commits", "workflow", "safety"]),
        _memory_item("Prefer maintained proof over scratch reproduction. Check tests/README.md and scripts/verify before inventing another debug script.", "preference", "debugging", ["tests", "verification", "proof"]),
        _memory_item("Python 3.11 is the floor because the codebase relies on modern typing, async, and current Kuzu and ChromaDB support.", "preference", "runtime", ["python-3.11", "runtime", "compatibility"]),
        _memory_item("Do not add new dependencies without explicit confirmation.", "preference", "workflow", ["dependencies", "approval", "constraints"]),
        _memory_item("Passive documentation does not make agents comply. The routing rules only started working when they were injected into every MCP response.", "insight", "agent-behavior", ["routing", "agents", "injection"]),
        _memory_item("Never let a Kuzu QueryResult escape the worker-thread helper. Materialize rows inside the lock or you will eventually hit native crashes.", "insight", "database", ["kuzu", "asyncio", "native-crash"]),
        _memory_item("If doubling the timeout still fails, stop calling it slow and treat it as a hang. BUG-010 only moved once that distinction was made.", "insight", "debugging", ["bug-010", "timeouts", "deadlock"]),
        _memory_item("Fix the whole live surface, not just the hurt file. Runtime messages, docs, tests, source strings, and stored memories drift together.", "insight", "maintenance", ["drift", "docs", "tests"]),
        _memory_item("Source-derived guards beat static prose. Tests that assert real paths, counts, and schemas fail loudly when reality changes.", "insight", "quality-gates", ["tests", "guards", "source-derived"]),
        _memory_item("Entry routing must appear at first contact. Agents skip instructions that are merely available somewhere else.", "insight", "agent-behavior", ["routing", "instructions", "first-contact"]),
        _memory_item("Analysis without action is entertainment. The correct pattern is state, do, verify in the same response.", "insight", "agent-behavior", ["execution", "verification", "workflow"]),
    ]


def _conversations():
    return [
        _memory_item("Boot failed with 'Database path cannot be a directory'. First guess was leftover Kuzu files or a corrupted test database.", "conversation", "database-debugging", ["kuzu", "startup", "path"], session_group=0),
        _memory_item("We spent time in graph_store.py before noticing the failure was happening earlier in startup. The hypothesis shifted from storage corruption to path setup.", "conversation", "database-debugging", ["kuzu", "debugging", "path"], session_group=0),
        _memory_item("A search for mkdir calls found config.py pre-creating KUZU_DIR. That was the exact thing Kuzu 0.11.x no longer tolerates.", "conversation", "database-debugging", ["kuzu", "config", "mkdir"], session_group=0),
        _memory_item("Removed the eager mkdir and let Kuzu own the path. The error vanished; the bug was in our bootstrap, not the database.", "conversation", "database-debugging", ["kuzu", "fix", "bootstrap"], session_group=0),
        _memory_item("Migration reported 78 memories migrated with 0 errors, but the dashboard still showed empty V3 layer metadata. We assumed the migration logic was broken.", "conversation", "metadata-debugging", ["v3", "migration", "metadata"], session_group=1),
        _memory_item("The classifier only had five regex patterns, so many memories were never labeled. Fixing that exposed a second gap in add_memory.", "conversation", "metadata-debugging", ["v3", "classifier", "metadata"], session_group=1),
        _memory_item("layer and sublayer were also missing in _reconstruct_memory, and a long-lived server cache hid the code changes.", "conversation", "metadata-debugging", ["v3", "reconstruct", "cache"], session_group=1),
        _memory_item("The frontend then failed again because it read the wrong property path in two places. The issue spanned six layers, not one file.", "conversation", "metadata-debugging", ["v3", "frontend", "six-layers"], session_group=1),
        _memory_item("Windows startup kept hanging near sentence-transformers. First assumption was a slow cold start, so we doubled the timeout.", "conversation", "startup-debugging", ["bug-010", "windows", "startup"], session_group=2, cluster="deadlock-investigation"),
        _memory_item("Timeout increases changed nothing. We moved the import into asyncio.to_thread, which only relocated the hang.", "conversation", "startup-debugging", ["bug-010", "asyncio", "deadlock"], session_group=2, cluster="deadlock-investigation"),
        _memory_item("Added raw stderr probes around startup because structured logs were too late. The freeze point was exactly import SentenceTransformer.", "conversation", "startup-debugging", ["bug-010", "stderr", "import"], session_group=2, cluster="deadlock-investigation"),
        _memory_item("Fixed startup by pre-loading the embedding model before asyncio.run(). Lesson: stop calling a deadlock slow after the second timeout.", "conversation", "startup-debugging", ["bug-010", "fix", "sentence-transformers"], session_group=2, cluster="deadlock-investigation"),
        _memory_item("Agent said the dashboard opened on localhost:8000 with nodes and edges, but the user only saw a blank page. Initial focus went to React rendering.", "conversation", "dashboard-debugging", ["dashboard", "blank-screen", "ui"], session_group=3),
        _memory_item("We checked frontend hooks and snapshot generation, but the blank page reproduced before the app could fully boot. Browser launch timing looked suspicious.", "conversation", "dashboard-debugging", ["dashboard", "race-condition", "startup"], session_group=3),
        _memory_item("The real issue was process lifetime: the dashboard was started as a daemon thread inside the MCP server. When the client closed stdio, the thread died immediately.", "conversation", "dashboard-debugging", ["dashboard", "daemon-thread", "stdio"], session_group=3),
        _memory_item("Switched to subprocess.Popen with start_new_session=True and waited for readiness before opening the browser. The blank page was lifecycle, not UI.", "conversation", "dashboard-debugging", ["dashboard", "subprocess", "readiness"], session_group=3),
        _memory_item("A proposed fix for memory-search behavior was adding BOB/.github/copilot-instructions.md. That looked acceptable until the audit considered opening subfolders.", "conversation", "agent-behavior", ["bug-012", "instructions", "scope"], session_group=4),
        _memory_item("ARAA rejected the workspace-only fix because behavior would regress outside that exact root. The scope of the bug was broader than the patch.", "conversation", "agent-behavior", ["bug-012", "audit", "scope"], session_group=4),
        _memory_item("We separated MCP registration scope from instruction delivery scope. Registering the server does not make the agent use it.", "conversation", "agent-behavior", ["bug-012", "mcp", "instructions"], session_group=4),
        _memory_item("Final fix moved codeGeneration.instructions to VS Code user settings so every workspace and folder inherits the routing rules.", "conversation", "agent-behavior", ["bug-012", "settings-json", "routing"], session_group=4),
    ]


def _decisions():
    return [
        _memory_item("Chose ChromaDB plus Kuzu dual-store architecture because semantic retrieval and relationship queries are different workloads.", "decision", "architecture", ["v2.0.0", "architecture", "storage"]),
        _memory_item("Pinned embeddings to thenlper/gte-base and store vectors explicitly. Mixing ChromaDB defaults with project embeddings silently corrupts search.", "decision", "retrieval", ["embeddings", "gte-base", "retrieval"]),
        _memory_item("Adopted behavioral scoring instead of user-assigned importance. Score should emerge from recency, freshness, access frequency, and memory type.", "decision", "scoring", ["v2.0.0", "scoring", "behavioral"], cluster="scoring"),
        _memory_item("Created a directive system outside normal memories so hard rules are injected unconditionally and cannot be outcompeted by similarity.", "decision", "directives", ["v2.1.0", "directives", "mcp"]),
        _memory_item("Promoted specification and directive to first-class memory types with authority 1.0 and zero decay.", "decision", "memory-model", ["v2.2.0", "authority", "memory-types"]),
        _memory_item("Moved sentence-transformers preload before asyncio.run() because import SentenceTransformer deadlocks in worker threads under anyio plus piped stdio.", "decision", "startup", ["v2.5.1", "bug-010", "startup"]),
        _memory_item("Removed the domain signal from ranking and redistributed its weight to vector and concept signals after proving the value spaces never intersected.", "decision", "scoring", ["v2.7.0", "bug-016", "scoring"], cluster="scoring"),
        _memory_item("Gated the specification override on system intent only. The unconditional boost created a ranking monopoly.", "decision", "scoring", ["v2.7.0", "bug-017", "specifications"], cluster="scoring"),
        _memory_item("Committed to MCP stdio instead of a REST-first architecture. Core memory operations should work as an IDE-connected server, not an HTTP app.", "decision", "protocol", ["mcp", "stdio", "architecture"]),
        _memory_item("Renamed importance to score across the codebase to match behavioral scoring semantics.", "decision", "scoring", ["v2.1.1", "naming", "scoring"], cluster="scoring"),
        _memory_item("Curated the stored memories from 19 down to 13 by deleting duplicates, generic checklists, and unimplemented concepts.", "decision", "curation", ["v2.0.0", "curation", "quality"]),
        _memory_item("Merged four maintenance scripts into two to remove duplicated lock-handling and export logic.", "decision", "tooling", ["v2.5.2", "scripts", "maintenance"]),
        _memory_item("Changed the installer to ask what to do with an existing .venv instead of silently reusing it.", "decision", "installation", ["v2.6.0", "installer", "venv"]),
        _memory_item("Standardized the dashboard on React, Vite, and SVG with a snapshot file as the only data source.", "decision", "dashboard", ["dashboard", "react", "vite"]),
        _memory_item("Persisted session retrieval history to disk with 7-day expiry so co-activation does not reset to zero on every restart.", "decision", "retrieval", ["v2.7.0", "bug-018", "coactivation"]),
    ]


def _supersessions():
    pairs = [
        ("The dashboard server can run as a daemon thread inside the MCP process.", "The dashboard server must run as a detached subprocess with a readiness check before the browser opens.", "dashboard-runtime", ["dashboard", "lifecycle", "supersession"]),
        ("Dashboard node payloads can be serialized inline wherever they are needed.", "All dashboard nodes must be built through dashboard_serializer.py with live score computation.", "dashboard-serialization", ["dashboard", "serializer", "supersession"]),
        ("Workspace-scoped copilot-instructions files are enough to make agents call Elefante.", "Instruction delivery must be system-scoped through VS Code user settings so every workspace inherits the routing.", "instruction-delivery", ["instructions", "scope", "supersession"]),
        ("The ranking model should keep a 15 percent domain signal.", "The ranking model removes the broken domain signal and reallocates that weight to vector and concept signals.", "scoring", ["scoring", "domain-signal", "supersession"]),
        ("Specification memories always receive a 0.30 override boost.", "Specification boost only applies when inferred intent is system.", "scoring", ["scoring", "specification", "supersession"]),
    ]
    items = []
    for pair_id, (old_content, new_content, category, tags) in enumerate(pairs):
        items.append(_memory_item(old_content, "fact", category, tags, is_old=True, pair_id=pair_id))
        items.append(_memory_item(new_content, "decision", category, tags, is_new=True, pair_id=pair_id, cluster="tooling-evolution"))
    return items


def _contradictions():
    pairs = [
        ("The 'Database path cannot be a directory' failure means the Kuzu database files are corrupted.", "The 'Database path cannot be a directory' failure came from config.py pre-creating the database directory before Kuzu opened it.", "database-debugging", ["kuzu", "path", "assumption"]),
        ("import SentenceTransformer is just slow on Windows cold start.", "import SentenceTransformer deadlocks in worker threads under anyio plus piped stdio and must be pre-loaded.", "startup-debugging", ["bug-010", "windows", "deadlock"]),
        ("The blank dashboard after launch is a React rendering bug.", "The blank dashboard after launch is a process-lifecycle bug caused by daemon-thread shutdown and browser timing.", "dashboard-debugging", ["dashboard", "blank-screen", "assumption"]),
        ("JSON export from export_memories.py is sufficient backup coverage.", "JSON export is read-only analysis output because embeddings are excluded and there is no import path.", "backup", ["export", "backup", "assumption"]),
        ("MCP registration scope and instruction delivery scope are basically the same thing.", "MCP registration and instruction delivery are orthogonal; the agent still needs explicit system-scoped routing.", "instruction-delivery", ["mcp", "instructions", "scope"]),
    ]
    items = []
    for pair_id, (left, right, category, tags) in enumerate(pairs):
        items.append(_memory_item(left, "note", category, tags + ["contradiction-a"], pair_id=pair_id, conflict_side="a"))
        items.append(_memory_item(right, "note", category, tags + ["contradiction-b"], pair_id=pair_id, conflict_side="b"))
    return items


def _specifications():
    return [
        _memory_item("The Four Laws govern the system: continuity, compliance, grounding, and efficiency. Sessions continue, search precedes claims, unknown stays unknown, and every token must earn its place.", "specification", "system-law", ["four-laws", "system", "sdd"]),
        _memory_item("Search before assert: when the user asks about preferences, past decisions, or project conventions, call elefante-Memory(action=search) with an explicit standalone query before answering.", "specification", "retrieval-rule", ["search-first", "retrieval", "compliance"]),
        _memory_item("Stdout Purity Law: never print to stdout from the MCP server because stdout is the JSON-RPC transport.", "specification", "protocol-law", ["stdout", "protocol", "json-rpc"]),
        _memory_item("Memory type selection is deliberate: specification for architecture, preference for user preferences, conversation for ephemeral dialogue, and never note for architectural decisions.", "specification", "memory-model", ["memory-types", "classification", "lifespan"]),
        _memory_item("Critical database laws: properties cannot be a column name, Kuzu is single-writer, let Kuzu own its path, and never let database work outlive GraphStore.close().", "specification", "database-law", ["kuzu", "database", "safety"]),
    ]


def _ephemera():
    return [
        _memory_item("Windows crashed on import because fcntl was imported unconditionally. The immediate fix was a sys.platform != 'win32' guard.", "note", "platform-bug", ["windows", "fcntl", "bug"], delete_candidate=True),
        _memory_item("Dashboard topic kept showing General because two code paths read topic instead of category.", "note", "dashboard-bug", ["dashboard", "topic", "category"], delete_candidate=True),
        _memory_item("Deleting a memory left stale UUIDs inside session retrieval history and created orphan co-activation edges.", "note", "graph-bug", ["coactivation", "delete", "graph"], delete_candidate=True),
        _memory_item("A cleanup pass removed 200 test memories like entity_target_0 through entity_target_99 from ChromaDB and added a guard to detect that artifact pattern.", "note", "data-hygiene", ["cleanup", "test-data", "chromadb"], delete_candidate=True),
        _memory_item("Using properties as a Kuzu column name works in schema DDL but collides with Cypher parsing. Renaming the field to props fixed the binder error.", "note", "database-bug", ["kuzu", "cypher", "schema"], delete_candidate=True),
        _memory_item("A write-only export is not a backup. If there is no import path, the tool must say read-only analysis output.", "insight", "backup", ["backup", "export", "product-safety"]),
        _memory_item("CI must build every artifact it packages. Gitignored dashboard assets made the first binary release pipeline fail.", "insight", "release", ["ci", "release", "assets"]),
        _memory_item("A green build matrix is not release proof. Publication can still fail later on asset size limits or release assembly.", "insight", "release", ["release", "ci", "proof"]),
        _memory_item("GitHub releases cap assets at 2 GiB. The Linux artifact exceeded 4 GiB, so release automation had to filter oversized assets.", "fact", "release", ["github-release", "asset-cap", "v2.7.1"]),
        _memory_item("API working does not prove dashboard working. The frontend can still bind to the wrong response shape and render blank rows.", "insight", "dashboard", ["dashboard", "frontend", "contract"]),
    ]


def build_corpus():
    corpus = []
    corpus.extend(_foundation_memories())
    corpus.extend(_conversations())
    corpus.extend(_decisions())
    corpus.extend(_supersessions())
    corpus.extend(_contradictions())
    corpus.extend(_specifications())
    corpus.extend(_ephemera())
    assert len(corpus) == 100, f"Expected 100, got {len(corpus)}"
    return corpus


async def run_injection(db_path, *, force=False):
    abs_db = os.path.abspath(db_path)
    print(f"Target DB: {abs_db}")

    if os.path.exists(abs_db) and not force:
        raise FileExistsError(f"{abs_db} already exists; pass --force to replace this isolated demo path")
    if os.path.exists(abs_db):
        shutil.rmtree(abs_db)
    os.makedirs(abs_db, exist_ok=True)

    chroma_dir = os.path.join(abs_db, "chroma")
    kuzu_dir = os.path.join(abs_db, "kuzu_db")

    vector_store = VectorStore(persist_directory=chroma_dir)
    graph_store = GraphStore(database_path=kuzu_dir)
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=graph_store)
    corpus = build_corpus()
    now = datetime.utcnow()

    print(f"Injecting {len(corpus)} memories (direct DB, zero LLM)...")

    all_ids = []
    supersession_old_ids = {}
    conversation_groups = {}
    contradiction_pairs = {}
    cluster_members = {}
    delete_candidates = []

    for idx, payload in enumerate(corpus):
        days_ago = 180 - int((idx / len(corpus)) * 180)
        spoofed = now - timedelta(days=days_ago)

        m_type = payload["type"]
        decay = TYPE_DECAY_RATES.get(m_type, 0.01)

        mem_id = uuid.uuid4()
        metadata = MemoryMetadata(
            created_at=spoofed,
            last_modified=spoofed,
            last_accessed=spoofed,
            category=payload.get("category", "general"),
            tags=payload.get("tags", []),
            domain="work",
            memory_type=MemoryType(m_type),
            status=MemoryStatus.NEW,
            score=100,
            decay_rate=decay,
        )

        memory = Memory(id=mem_id, content=payload["content"], metadata=metadata)

        # ChromaDB
        await orchestrator.vector_store.add_memory(memory)

        # Kuzu
        entity = Entity(
            id=mem_id,
            name=f"memory_{mem_id}",
            type=EntityType.MEMORY,
            description=payload["content"][:80],
            properties={
                "content": payload["content"][:200],
                "memory_type": m_type,
                "score": 100,
                "status": "new",
                "timestamp": spoofed.isoformat(),
            },
        )
        await orchestrator.graph_store.create_entity(entity)

        all_ids.append(str(mem_id))

        # Track grouped conversation memories
        if payload["type"] == "conversation":
            conversation_groups.setdefault(payload.get("session_group", 0), []).append(str(mem_id))

        # Track contradiction pairs by explicit pair_id
        if payload.get("conflict_side") == "a":
            contradiction_pairs.setdefault(payload["pair_id"], {})["a"] = str(mem_id)
        elif payload.get("conflict_side") == "b":
            contradiction_pairs.setdefault(payload["pair_id"], {})["b"] = str(mem_id)

        # Track related-memory clusters explicitly
        if payload.get("cluster"):
            cluster_members.setdefault(payload["cluster"], []).append(str(mem_id))

        # Track low-signal memories for purposeful deletion later
        if payload.get("delete_candidate"):
            delete_candidates.append(str(mem_id))

        # Track supersession pairs
        if payload.get("is_old"):
            supersession_old_ids[payload["pair_id"]] = str(mem_id)
        elif payload.get("is_new"):
            old_id = supersession_old_ids.get(payload["pair_id"])
            if old_id:
                await orchestrator.vector_store.update_memory(
                    uuid.UUID(old_id),
                    {"superseded_by_id": str(mem_id), "deprecated": True},
                )
                print(f"  Supersession: {old_id[:8]}... -> {str(mem_id)[:8]}...")

        if (idx + 1) % 20 == 0:
            print(f"  {idx + 1}/100 injected")

    # Co-Activation Graph Edges - 10 simulated sessions
    print("Forging co-activation graph edges...")
    for _ in range(10):
        session_ids = random.sample(all_ids, k=min(4, len(all_ids)))
        await orchestrator.record_coactivation(session_ids)

    contradiction_pair_ids = []
    for pair in sorted(contradiction_pairs):
        sides = contradiction_pairs[pair]
        if "a" in sides and "b" in sides:
            contradiction_pair_ids.append((sides["a"], sides["b"]))

    # Purposeful Deletions - 5 low-signal notes marked for pruning
    print("Executing 5 purposeful deletions...")
    delete_targets = delete_candidates[:5]
    deleted_set = set(delete_targets)
    for del_id in delete_targets:
        await orchestrator.vector_store.delete_memory(uuid.UUID(del_id))
        await orchestrator.graph_store.delete_entity(uuid.UUID(del_id))

    # Remove deleted IDs from tracking lists
    surviving_ids = [mid for mid in all_ids if mid not in deleted_set]
    surviving_conversation_groups = {
        group: [mid for mid in mids if mid not in deleted_set]
        for group, mids in conversation_groups.items()
    }
    surviving_clusters = {
        name: [mid for mid in mids if mid not in deleted_set]
        for name, mids in cluster_members.items()
    }

    # =========================================================================
    # BEHAVIORAL HISTORY PASS (Spec: scripts/demo/SPEC_behavioral_history.md)
    # =========================================================================
    await _behavioral_history_pass(
        orchestrator,
        surviving_ids,
        surviving_conversation_groups,
        contradiction_pair_ids,
        surviving_clusters,
        now,
    )

    # Final stats
    surviving = await asyncio.to_thread(orchestrator.vector_store._collection.get)
    total = len(surviving["ids"])
    print(f"\nDone. {total} memories in DB.")
    print("This legacy benchmark does not directly drive the snapshot-only dashboard.")
    print("Use generate_showcase_snapshot.py for the current product showcase.")


async def _behavioral_history_pass(orchestrator, surviving_ids, conversation_groups,
                                    contradiction_pair_ids, cluster_members, now):
    """Simulate 6 months of realistic usage patterns. Spec-driven."""
    vs = orchestrator.vector_store

    # ------------------------------------------------------------------
    # Phase 1: Session IDs on Conversations (20 → 5 sessions of 4)
    # ------------------------------------------------------------------
    print("\n[Phase 1] Assigning session IDs to conversations...")
    session_uuids = {
        group: uuid.UUID(int=random.getrandbits(128))
        for group in sorted(conversation_groups)
    }
    conversation_count = 0
    for group, ids in conversation_groups.items():
        for cid in ids:
            mem = await vs.get_memory(uuid.UUID(cid))
            if mem:
                mem.metadata.session_id = session_uuids[group]
                await vs.replace_memory(mem)
                conversation_count += 1
    print(f"  {conversation_count} conversations across {len(session_uuids)} sessions")

    # ------------------------------------------------------------------
    # Phase 2: Conflict Cross-Links (5 contradiction pairs → 10 memories)
    # ------------------------------------------------------------------
    print("[Phase 2] Cross-linking contradiction pairs...")
    for a_id, b_id in contradiction_pair_ids:
        mem_a = await vs.get_memory(uuid.UUID(a_id))
        mem_b = await vs.get_memory(uuid.UUID(b_id))
        if mem_a and mem_b:
            mem_a.metadata.conflict_ids = [uuid.UUID(b_id)]
            mem_a.metadata.status = MemoryStatus.CONTRADICTORY
            await vs.replace_memory(mem_a)
            mem_b.metadata.conflict_ids = [uuid.UUID(a_id)]
            mem_b.metadata.status = MemoryStatus.CONTRADICTORY
            await vs.replace_memory(mem_b)
    print(f"  {len(contradiction_pair_ids)} pairs cross-linked")

    # ------------------------------------------------------------------
    # Phase 3: Related Memory Links (explicit topical clusters)
    # ------------------------------------------------------------------
    print("[Phase 3] Building topical clusters...")
    surviving_set = set(surviving_ids)
    linked_count = 0
    active_cluster_count = 0
    for cluster in cluster_members.values():
        valid = [mid for mid in cluster if mid in surviving_set]
        if len(valid) < 2:
            continue
        active_cluster_count += 1
        for mid in valid:
            mem = await vs.get_memory(uuid.UUID(mid))
            if mem:
                mem.metadata.related_memory_ids = [uuid.UUID(other) for other in valid if other != mid]
                await vs.replace_memory(mem)
                linked_count += 1
    print(f"  {linked_count} memories linked across {active_cluster_count} clusters")

    # ------------------------------------------------------------------
    # Phase 4: Access Pattern Simulation (power law / Zipf)
    # ------------------------------------------------------------------
    print("[Phase 4] Simulating access patterns...")
    # Shuffle deterministically to pick hot/warm/cool/cold
    shuffled = surviving_ids[:]
    random.shuffle(shuffled)
    hot = shuffled[:10]
    warm = shuffled[10:30]
    cool = shuffled[30:60]
    cold = shuffled[60:]

    access_map = {}
    for mid in hot:
        access_map[mid] = {"count": random.randint(15, 30), "recency_days": random.randint(0, 3)}
    for mid in warm:
        access_map[mid] = {"count": random.randint(5, 14), "recency_days": random.randint(1, 14)}
    for mid in cool:
        access_map[mid] = {"count": random.randint(1, 4), "recency_days": random.randint(14, 60)}
    # cold: no access updates

    accessed_count = 0
    for mid, access in access_map.items():
        last_acc = now - timedelta(days=access["recency_days"])
        result = await vs.update_memory(uuid.UUID(mid), {
            "access_count": access["count"],
            "last_accessed": last_acc,
            "status": MemoryStatus.VERIFIED,
        })
        if result:
            accessed_count += 1
    print(f"  {accessed_count} memories given access history (10 hot, 20 warm, 30 cool, {len(cold)} cold)")

    # ------------------------------------------------------------------
    # Phase 5: Authority Score Computation
    # ------------------------------------------------------------------
    print("[Phase 5] Computing authority scores...")
    authority_count = 0
    for mid in surviving_ids:
        mem = await vs.get_memory(uuid.UUID(mid))
        if mem:
            _strip_tz(mem)
            score_norm = mem.metadata.score / 100.0
            ac = max(0, mem.metadata.access_count)
            days_since_access = max(0, (now - mem.metadata.last_accessed).total_seconds() / 86400)
            freshness = math.exp(-0.005 * days_since_access)
            authority = max(0.0, min(1.0, score_norm * math.log(ac + 1) * freshness))
            mem.metadata.authority_score = round(authority, 3)
            await vs.replace_memory(mem)
            authority_count += 1
    print(f"  {authority_count} authority scores computed")

    # ------------------------------------------------------------------
    # Phase 6: Final Rescore with Behavioral Signals
    # ------------------------------------------------------------------
    print("[Phase 6] Final rescore with behavioral signals...")
    rescored = 0
    scores = []
    for mid in surviving_ids:
        mem = await vs.get_memory(uuid.UUID(mid))
        if mem:
            _strip_tz(mem)
            new_score = min(100, max(0, round(mem.calculate_relevance_score(now) * 100)))
            await vs.update_memory(mem.id, {"score": new_score})
            scores.append(new_score)
            rescored += 1
    print(f"  {rescored} memories rescored")
    if scores:
        print(f"  Score range: {min(scores)} - {max(scores)} (variance: {max(scores) - min(scores)})")

    # ------------------------------------------------------------------
    # Verification (Spec criteria)
    # ------------------------------------------------------------------
    await _verify(orchestrator, surviving_ids, now)


def _strip_tz(mem):
    """Ensure naive datetimes for calculate_relevance_score compatibility."""
    if mem.metadata.created_at.tzinfo is not None:
        mem.metadata.created_at = mem.metadata.created_at.replace(tzinfo=None)
    if mem.metadata.last_accessed.tzinfo is not None:
        mem.metadata.last_accessed = mem.metadata.last_accessed.replace(tzinfo=None)


async def _verify(orchestrator, surviving_ids, now):
    """Run spec verification criteria."""
    vs = orchestrator.vector_store
    print("\n[Verify] Running spec assertions...")

    accessed = 0
    last_acc_diff = 0
    with_session = 0
    with_conflicts = 0
    with_related = 0
    active_count = 0
    scores = []
    authorities = []

    for mid in surviving_ids:
        mem = await vs.get_memory(uuid.UUID(mid))
        if not mem:
            continue
        if mem.metadata.access_count > 0:
            accessed += 1
        _strip_tz(mem)
        if abs((mem.metadata.last_accessed - mem.metadata.created_at).total_seconds()) > 60:
            last_acc_diff += 1
        if mem.metadata.session_id is not None:
            with_session += 1
        if mem.metadata.conflict_ids:
            with_conflicts += 1
        if mem.metadata.related_memory_ids:
            with_related += 1
        status_val = mem.metadata.status.value if hasattr(mem.metadata.status, 'value') else str(mem.metadata.status)
        if status_val not in ("new",):
            active_count += 1
        scores.append(mem.metadata.score)
        authorities.append(mem.metadata.authority_score)

    checks = [
        ("access_count > 0 for >= 60", accessed >= 60, f"{accessed}/60"),
        ("last_accessed != created_at for >= 60", last_acc_diff >= 60, f"{last_acc_diff}/60"),
        ("session_id set for == 20 conversations", with_session == 20, f"{with_session}/20"),
        ("conflict_ids non-empty for == 10", with_conflicts == 10, f"{with_conflicts}/10"),
        ("related_memory_ids non-empty for >= 15", with_related >= 15, f"{with_related}/15"),
        ("status != NEW for >= 60", active_count >= 60, f"{active_count}/60"),
        ("score variance >= 40", (max(scores) - min(scores)) >= 40 if scores else False,
         f"{max(scores) - min(scores)}" if scores else "N/A"),
        ("authority variance >= 0.3", (max(authorities) - min(authorities)) >= 0.3 if authorities else False,
         f"{round(max(authorities) - min(authorities), 3)}" if authorities else "N/A"),
    ]

    all_pass = True
    for label, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {label} ({detail})")

    if all_pass:
        print("\n  All 8 spec criteria passed.")
    else:
        print("\n  WARNING: Some criteria failed. Review output above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a legacy 100-memory behavioral store benchmark")
    parser.add_argument("--db", default="./a0-data/demo_db", help="Isolated legacy database path")
    parser.add_argument("--force", action="store_true", help="Replace only the explicit isolated database path")
    args = parser.parse_args()
    asyncio.run(run_injection(args.db, force=args.force))
