"""
generate_100_memories.py - Self-Contained 6-Month Demo Dataset Injector

PURPOSE : Populate an isolated Elefante database with 100 deterministic memories
          that exercise every dashboard metric, with realistic behavioral history.
INJECTION: Direct VectorStore + GraphStore writes. Zero LLM. Instant.
SPEC    : scripts/demo/SPEC_behavioral_history.md

RUN:
    .venv/bin/python scripts/demo/generate_100_memories.py --db ./a0-data/demo_db
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

from src.core.orchestrator import MemoryOrchestrator
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.models.memory import Memory, MemoryMetadata, MemoryType, MemoryStatus, TYPE_DECAY_RATES
from src.models.entity import Entity, EntityType

random.seed(42)


def _facts(n=35):
    services = ["AuthService", "PaymentGateway", "SearchIndexer", "NotificationHub",
                "UserProfileAPI", "AnalyticsPipeline", "BillingEngine"]
    techs = ["Redis cluster", "Kafka topic", "RabbitMQ exchange", "SQS queue",
             "gRPC endpoint", "REST API", "GraphQL resolver"]
    langs = ["Python 3.12", "Java 21", "TypeScript 5.4", "Go 1.22", "Rust 1.77"]
    return [{"content": f"{services[i % len(services)]} communicates via {techs[i % len(techs)]} and is written in {langs[i % len(langs)]}.",
             "type": "fact", "category": "infrastructure", "tags": ["backend", "architecture"]}
            for i in range(n)]


def _conversations(n=20):
    topics = [
        "Debugged CORS preflight failures on the Vite dev proxy.",
        "Discussed migrating from Webpack to esbuild for faster builds.",
        "Reviewed PR #247: refactored the retry logic in PaymentGateway.",
        "Investigated OOM kills in the Kubernetes staging cluster.",
        "Paired on fixing flaky Playwright E2E tests in CI.",
        "Triaged a customer report about duplicate invoice emails.",
        "Reviewed Java 21 virtual threads adoption for the BillingEngine.",
        "Debugged a race condition in the Redis pub/sub consumer.",
        "Discussed adding OpenTelemetry tracing to all Python services.",
        "Sprint retro: agreed to reduce WIP limit from 5 to 3.",
        "Investigated slow PostgreSQL queries on the analytics dashboard.",
        "Reviewed security audit findings for the AuthService.",
        "Discussed API versioning strategy for the public REST endpoints.",
        "Debugged TypeScript strict-mode errors after upgrading to 5.4.",
        "Paired on writing integration tests for the Kafka consumer.",
        "Reviewed deployment runbook for the new blue-green strategy.",
        "Discussed monorepo vs polyrepo tradeoffs for the frontend.",
        "Investigated memory leaks in the long-running Go worker.",
        "Sprint planning: prioritized the search relevance improvements.",
        "Debugged a certificate rotation failure in the staging environment.",
    ]
    return [{"content": topics[i], "type": "conversation", "category": "troubleshooting",
             "tags": ["ci-cd", "debugging"]} for i in range(n)]


def _decisions(n=15):
    rules = [
        "All React components must use Zustand for state management, not Redux.",
        "Python services must target 90% test coverage before merge.",
        "Java modules require Checkstyle + SpotBugs in the CI gate.",
        "Frontend bundle size budget is 200KB gzipped, enforced by CI.",
        "All database migrations must be backward-compatible (expand-contract).",
        "API response times must stay below p99 = 200ms in staging.",
        "Secrets are stored in AWS Secrets Manager, never in env vars.",
        "All public endpoints require rate limiting at the API gateway.",
        "Error responses must follow RFC 7807 Problem Details format.",
        "Logging must use structured JSON, never printf-style strings.",
        "Docker images must be based on distroless, not Alpine.",
        "All async Python code must use structured concurrency (TaskGroups).",
        "GraphQL mutations must be idempotent with client-generated IDs.",
        "Feature flags are managed via LaunchDarkly, no homegrown toggles.",
        "Dependency updates are automated via Renovate with auto-merge for patch.",
    ]
    return [{"content": rules[i], "type": "preference", "category": "standards",
             "tags": ["rules", "engineering"]} for i in range(n)]


def _supersessions(n=5):
    pairs = [
        ("Formatting uses Prettier with default config.", "Migrated from Prettier to Biome for 10x faster formatting."),
        ("CI runs on GitHub Actions with Ubuntu 22.04.", "CI migrated to Buildkite with self-hosted ARM runners."),
        ("Frontend tests use Jest + React Testing Library.", "Frontend tests migrated to Vitest for Vite-native speed."),
        ("Python linting uses flake8 + isort.", "Python linting consolidated to Ruff (replaces flake8, isort, black)."),
        ("Deployments use Helm charts on EKS.", "Deployments migrated to ArgoCD GitOps on EKS."),
    ]
    items = []
    for i in range(n):
        items.append({"content": pairs[i][0], "type": "fact", "category": "tooling",
                       "tags": ["migration"], "is_old": True, "pair_id": i})
        items.append({"content": pairs[i][1], "type": "decision", "category": "tooling",
                       "tags": ["migration"], "is_new": True, "pair_id": i})
    return items


def _contradictions(n=5):
    pairs = [
        ("Production database timezone is set to UTC.", "Production database timezone is set to America/New_York."),
        ("The default branch is main.", "The default branch is master."),
        ("API authentication uses JWT with RS256.", "API authentication uses opaque OAuth2 tokens."),
        ("Search uses Elasticsearch 8.", "Search uses OpenSearch 2."),
        ("Cache TTL for user sessions is 30 minutes.", "Cache TTL for user sessions is 24 hours."),
    ]
    items = []
    for i in range(n):
        items.append({"content": pairs[i][0], "type": "fact", "category": "config", "tags": ["contradiction-a"]})
        items.append({"content": pairs[i][1], "type": "fact", "category": "config", "tags": ["contradiction-b"]})
    return items


def _specifications(n=5):
    specs = [
        "NEVER commit plaintext secrets to the repository. Enforced by pre-commit hook.",
        "All production data access requires an approved IAM role with MFA.",
        "PII must be encrypted at rest (AES-256) and in transit (TLS 1.3).",
        "Incident response SLA: P1 acknowledged within 15 minutes.",
        "All third-party dependencies must pass license compliance (no GPL in proprietary code).",
    ]
    return [{"content": specs[i], "type": "specification", "category": "security",
             "tags": ["critical", "compliance"]} for i in range(n)]


def build_corpus():
    # 30 + 20 + 15 + 10(5 pairs) + 10(5 pairs) + 5 = 90 + 10 = 100
    corpus = []
    corpus.extend(_facts(30))
    corpus.extend(_conversations(20))
    corpus.extend(_decisions(15))
    corpus.extend(_supersessions(5))   # yields 10
    corpus.extend(_contradictions(5))  # yields 10
    corpus.extend(_specifications(5))
    # Pad to exactly 100 with 5 extra diverse facts
    while len(corpus) < 100:
        corpus.append({"content": f"Extra fact: deployment region {len(corpus)} uses multi-AZ.",
                        "type": "fact", "category": "infrastructure", "tags": ["cloud"]})
    assert len(corpus) == 100, f"Expected 100, got {len(corpus)}"
    return corpus


async def run_injection(db_path):
    abs_db = os.path.abspath(db_path)
    print(f"Target DB: {abs_db}")

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
    # Track indices by role for behavioral history pass
    conversation_ids = []
    contradiction_pair_ids = []  # list of (id_a, id_b)
    _contradiction_buffer = {}   # pair_id -> first id

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

        # Track conversation memories
        if payload["type"] == "conversation":
            conversation_ids.append(str(mem_id))

        # Track contradiction pairs
        if "contradiction-a" in payload.get("tags", []):
            _contradiction_buffer[idx] = str(mem_id)
        elif "contradiction-b" in payload.get("tags", []):
            # The previous index was the "a" side
            a_id = _contradiction_buffer.get(idx - 1)
            if a_id:
                contradiction_pair_ids.append((a_id, str(mem_id)))

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

    # Purposeful Deletions - 5 extra-fact-range memories (indices 90-94)
    print("Executing 5 purposeful deletions...")
    delete_targets = all_ids[90:95]
    deleted_set = set(delete_targets)
    for del_id in delete_targets:
        await orchestrator.vector_store.delete_memory(uuid.UUID(del_id))
        await orchestrator.graph_store.delete_entity(uuid.UUID(del_id))

    # Remove deleted IDs from tracking lists
    surviving_ids = [mid for mid in all_ids if mid not in deleted_set]
    conversation_ids = [mid for mid in conversation_ids if mid not in deleted_set]

    # =========================================================================
    # BEHAVIORAL HISTORY PASS (Spec: scripts/demo/SPEC_behavioral_history.md)
    # =========================================================================
    await _behavioral_history_pass(orchestrator, surviving_ids, conversation_ids,
                                   contradiction_pair_ids, now)

    # Final stats
    surviving = await asyncio.to_thread(orchestrator.vector_store._collection.get)
    total = len(surviving["ids"])
    print(f"\nDone. {total} memories in DB.")
    print(f"Launch dashboard:")
    print(f"  ELEFANTE_DB_PATH={abs_db} python -m src.dashboard")


async def _behavioral_history_pass(orchestrator, surviving_ids, conversation_ids,
                                    contradiction_pair_ids, now):
    """Simulate 6 months of realistic usage patterns. Spec-driven."""
    vs = orchestrator.vector_store

    # ------------------------------------------------------------------
    # Phase 1: Session IDs on Conversations (20 → 5 sessions of 4)
    # ------------------------------------------------------------------
    print("\n[Phase 1] Assigning session IDs to conversations...")
    session_uuids = [uuid.UUID(int=random.getrandbits(128)) for _ in range(5)]
    for i, cid in enumerate(conversation_ids):
        session_idx = i // 4  # 0-3 → session 0, 4-7 → session 1, ...
        if session_idx >= len(session_uuids):
            session_idx = len(session_uuids) - 1
        mem = await vs.get_memory(uuid.UUID(cid))
        if mem:
            mem.metadata.session_id = session_uuids[session_idx]
            await vs.replace_memory(mem)
    print(f"  {len(conversation_ids)} conversations across {len(session_uuids)} sessions")

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
    # Phase 3: Related Memory Links (4 topical clusters)
    # ------------------------------------------------------------------
    print("[Phase 3] Building topical clusters...")
    # Cluster by index ranges in surviving_ids
    # Facts (0-29) → infra cluster, Conversations (30-49) → CI/CD cluster
    # Decisions (50-64) → standards cluster, Specs (85-89) → security cluster
    clusters = [
        surviving_ids[0:4],     # Backend infrastructure facts
        surviving_ids[30:34],   # CI/CD conversations
        surviving_ids[50:53],   # Standards decisions + security
        surviving_ids[60:64],   # Tooling supersession area
    ]
    linked_count = 0
    for cluster in clusters:
        valid = [mid for mid in cluster if mid in set(surviving_ids)]
        for mid in valid:
            mem = await vs.get_memory(uuid.UUID(mid))
            if mem:
                mem.metadata.related_memory_ids = [uuid.UUID(other) for other in valid if other != mid]
                await vs.replace_memory(mem)
                linked_count += 1
    print(f"  {linked_count} memories linked across {len(clusters)} clusters")

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
    parser = argparse.ArgumentParser(description="Generate 100-memory demo dataset")
    parser.add_argument("--db", default="./a0-data/demo_db", help="Isolated DB path (will be wiped)")
    args = parser.parse_args()
    asyncio.run(run_injection(args.db))
