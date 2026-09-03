"""Regression tests for the bounded literal-trigger surfacing path."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import math
from uuid import uuid4

import pytest

from src.core.governance import matching_triggers
from src.core.orchestrator import MemoryOrchestrator
from src.core.task_intelligence import TaskBriefCompiler, TaskBriefProfile, TaskBriefRequest
from src.mcp.server import ElefanteMCPServer
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, MemoryType, SourceType
from src.models.query import QueryMode, SearchFilters, SearchResult


def _memory(
    content: str,
    *,
    trigger: list[str] | None = None,
    policy: str = "ranked",
    project: str | None = None,
    workspace: str | None = None,
    recall_cues: list[str] | None = None,
    source_reliability: float = 0.9,
    status: MemoryStatus = MemoryStatus.VERIFIED,
    archived: bool = False,
    conflict_ids: list | None = None,
) -> Memory:
    return Memory(
        id=uuid4(),
        content=content,
        metadata=MemoryMetadata(
            created_at=datetime(2026, 1, 1),
            last_accessed=datetime(2026, 1, 1),
            memory_type=MemoryType.DIRECTIVE,
            source=SourceType.USER_INPUT,
            source_reliability=source_reliability,
            status=status,
            archived=archived,
            conflict_ids=conflict_ids or [],
            project=project,
            workspace=workspace,
            injection_policy=policy,
            trigger=trigger or [],
            surfaces_when=[],
            recall_cues=recall_cues or [],
        ),
    )


class _VectorStore:
    def __init__(self, memories: list[Memory]) -> None:
        self.memories = memories
        self.calls: list[tuple[int, int, object]] = []

    async def get_all(self, *, limit: int, offset: int, filters=None):
        self.calls.append((limit, offset, filters))
        return self.memories[offset : offset + limit]


def test_matching_triggers_is_literal_case_insensitive_and_deduplicated():
    memory = _memory(
        "A governed deployment note.",
        trigger=["Deploy Now", "deploy now"],
        policy="triggered",
    )
    memory.metadata.surfaces_when = ["release train"]

    assert matching_triggers(
        memory.metadata,
        "The RELEASE TRAIN is blocked; deploy now after review.",
    ) == ["Deploy Now", "release train"]


@pytest.mark.asyncio
async def test_surface_path_requires_explicit_trigger_policy_and_literal_match():
    triggered = _memory(
        "The deployment runbook is stored in the release handbook.",
        trigger=["open the deployment runbook"],
        policy="triggered",
    )
    ranked = _memory(
        "The ranked note also mentions the deployment runbook.",
        trigger=["open the deployment runbook"],
        policy="ranked",
    )
    unrelated = _memory(
        "A different operational note.",
        trigger=["rotate the staging key"],
        policy="triggered",
    )
    vector_store = _VectorStore([ranked, unrelated, triggered])
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=object(), embedding_service=object())

    before = [deepcopy(item.model_dump()) for item in vector_store.memories]
    results = await orchestrator._surface_triggered_memories(
        "Please open the deployment runbook before continuing.",
        filters=SearchFilters(project=None),
    )

    assert [result.memory.id for result in results] == [triggered.id]
    assert results[0].source == "triggered"
    assert results[0].score == 1.0
    assert results[0].surface_matches == ["open the deployment runbook"]
    assert [item.model_dump() for item in vector_store.memories] == before


@pytest.mark.asyncio
async def test_surface_path_preserves_scope_trust_lifecycle_and_conflict_gates():
    accepted = _memory(
        "Use the customer rollback runbook.",
        trigger=["customer rollback"],
        policy="triggered",
        project="elefante",
    )
    other_project = _memory(
        "Use the other project's rollback runbook.",
        trigger=["customer rollback"],
        policy="triggered",
        project="other",
    )
    low_trust = _memory(
        "Unverified rollback advice.",
        trigger=["customer rollback"],
        policy="triggered",
        source_reliability=0.49,
    )
    archived = _memory(
        "Archived rollback advice.",
        trigger=["customer rollback"],
        policy="triggered",
        archived=True,
    )
    conflicted = _memory(
        "Conflicted rollback advice.",
        trigger=["customer rollback"],
        policy="triggered",
        conflict_ids=[uuid4()],
    )
    vector_store = _VectorStore([other_project, low_trust, archived, conflicted, accepted])
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=object(), embedding_service=object())

    results = await orchestrator._surface_triggered_memories(
        "The customer rollback is required.",
        filters=SearchFilters(project="elefante"),
    )

    assert [result.memory.id for result in results] == [accepted.id]


@pytest.mark.asyncio
async def test_surface_path_is_bounded_to_three_matches():
    memories = [
        _memory(
            f"Operational note {index}.",
            trigger=["shared release trigger"],
            policy="triggered",
        )
        for index in range(4)
    ]
    vector_store = _VectorStore(memories)
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    results = await orchestrator._surface_triggered_memories(
        "The shared release trigger is active."
    )

    assert len(results) == 3
    assert len({result.memory.id for result in results}) == 3


@pytest.mark.asyncio
async def test_surface_path_blocks_digest_stale_source_without_mutating_store(tmp_path):
    source = tmp_path / "runtime.py"
    source.write_text("CURRENT = 'new'\n", encoding="utf-8")
    stale = _memory(
        "Use the old migration rollback contract.",
        trigger=["migration locked"],
        policy="triggered",
    )
    stale.metadata.file_path = "runtime.py"
    stale.metadata.custom_metadata = {
        "source_file_sha256": hashlib.sha256(b"CURRENT = 'old'\n").hexdigest()
    }
    vector_store = _VectorStore([stale])
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    results = await orchestrator._surface_triggered_memories(
        "terminal error: migration locked",
        filters=SearchFilters(workspace=str(tmp_path)),
    )

    assert results == []
    assert "current_source_state" not in stale.metadata.custom_metadata


@pytest.mark.asyncio
async def test_surface_path_accepts_context_separate_from_semantic_query(monkeypatch):
    triggered = _memory(
        "Keep the rollback note available.",
        trigger=["terminal error: migration locked"],
        policy="triggered",
    )
    vector_store = _VectorStore([triggered])
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    async def no_semantic_results(*_args, **_kwargs):
        return []

    monkeypatch.setattr(orchestrator, "_search_hybrid", no_semantic_results)
    results = await orchestrator.search_memories(
        query="What should I investigate next?",
        surface_context="terminal error: migration locked while applying the backup",
        mode=QueryMode.HYBRID,
        include_conversation=False,
        include_stored=True,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert [result.memory.id for result in results] == [triggered.id]
    assert results[0].surface_matches == ["terminal error: migration locked"]


@pytest.mark.asyncio
async def test_search_integrates_triggered_surface_without_access_or_graph_mutation(monkeypatch):
    triggered = _memory(
        "The exact deployment runbook is in the customer handbook.",
        trigger=["deployment emergency"],
        policy="triggered",
    )
    vector_store = _VectorStore([triggered])
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=object(), embedding_service=object())

    async def no_semantic_results(*_args, **_kwargs):
        return []

    monkeypatch.setattr(orchestrator, "_search_hybrid", no_semantic_results)
    before = deepcopy(triggered.model_dump())

    results = await orchestrator.search_memories(
        query="deployment emergency",
        mode=QueryMode.HYBRID,
        include_conversation=False,
        include_stored=True,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert len(results) == 1
    assert results[0].source == "triggered"
    assert results[0].surface_matches == ["deployment emergency"]
    assert results[0].explanation["signals"][0]["name"] == "explicit_trigger"
    assert triggered.model_dump() == before


def test_triggered_surface_is_deliverable_without_semantic_overlap():
    memory = _memory(
        "The deployment runbook is stored in the customer handbook.",
        trigger=["deployment emergency"],
        policy="triggered",
    )
    result = SearchResult(
        memory=memory,
        score=1.0,
        source="triggered",
        surface_matches=["deployment emergency"],
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="deployment emergency",
            profile=TaskBriefProfile.V2,
        ),
        [result],
    )

    assert brief.selected_memory_ids == [str(memory.id)]
    assert brief.packets[0].evidence[0].retrieval_signals["surface_match"] == 1.0


@pytest.mark.asyncio
async def test_recall_cue_is_exact_project_scoped_and_not_a_generic_trigger():
    question = "What is the conclusion after all this work? Explain it to me in STAC."
    accepted = _memory(
        'User likes answers in simple terms and concisely (STAC).',
        project="elefante",
        workspace="/work/elefante",
        recall_cues=[question],
    )
    other_project = _memory(
        "A different project preference.",
        project="other",
        workspace="/work/other",
        recall_cues=[question],
    )
    vector_store = _VectorStore([accepted, other_project])
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    results = await orchestrator._surface_recall_cue_memories(
        "what is the conclusion after all this work explain it to me in stac",
        filters=SearchFilters(project="elefante", workspace="/work/elefante"),
    )

    assert [result.memory.id for result in results] == [accepted.id]
    assert results[0].source == "recall-cue"
    assert results[0].recall_cue_match is True
    assert await orchestrator._surface_recall_cue_memories(
        "Explain STAC differently",
        filters=SearchFilters(project="elefante", workspace="/work/elefante"),
    ) == []
    assert await orchestrator._surface_recall_cue_memories(
        question,
        filters=None,
    ) == []


@pytest.mark.asyncio
async def test_search_preserves_recall_cue_as_explicit_non_vector_evidence(monkeypatch):
    question = "What is the conclusion after all this work? Explain it to me in STAC."
    memory = _memory(
        'User likes answers in simple terms and concisely (STAC).',
        project="elefante",
        workspace="/work/elefante",
        recall_cues=[question],
    )
    orchestrator = MemoryOrchestrator(
        vector_store=_VectorStore([memory]),
        graph_store=object(),
        embedding_service=object(),
    )

    async def no_semantic_results(*_args, **_kwargs):
        return []

    monkeypatch.setattr(orchestrator, "_search_hybrid", no_semantic_results)
    results = await orchestrator.search_memories(
        query=question,
        mode=QueryMode.HYBRID,
        filters=SearchFilters(
            project="elefante",
            workspace="/work/elefante",
            include_conversation=False,
            include_stored=True,
        ),
        include_conversation=False,
        include_stored=True,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert [result.memory.id for result in results] == [memory.id]
    assert results[0].score == 1.0
    assert results[0].vector_score is None
    assert results[0].recall_cue_match is True
    assert results[0].explanation["signals"][0]["name"] == "customer_recall_cue"


def test_recall_cue_is_deliverable_without_semantic_or_lexical_overlap():
    memory = _memory(
        'User likes answers in simple terms and concisely (STAC).',
        project="elefante",
        workspace="/work/elefante",
        recall_cues=["What is the conclusion after all this work?"],
    )
    result = SearchResult(
        memory=memory,
        score=1.0,
        source="recall-cue",
        recall_cue_match=True,
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="What is the conclusion after all this work?",
            project="elefante",
            workspace="/work/elefante",
            profile=TaskBriefProfile.V2,
        ),
        [result],
    )

    assert brief.selected_memory_ids == [str(memory.id)]
    assert brief.packets[0].evidence[0].retrieval_signals[
        "recall_cue_match"
    ] == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("similarities", "selected"),
    [((0.95, 0.89), True), ((0.92, 0.85), False), ((0.95, 0.94), False)],
    ids=["clear-paraphrase", "weak-match", "ambiguous-match"],
)
async def test_recall_cue_paraphrase_is_bounded_evidence(similarities, selected):
    """Question-to-question evidence must be strong and separated, not top-one."""
    question = "What is Elefante for?"
    purpose = _memory(
        "Elefante should turn relevant memories into useful advice that improves "
        "the current task. Judge its value by measurable task results and "
        "accepted task value per total token. Token savings and additional "
        "infrastructure are means, not the product goal.",
        project="elefante",
        workspace="/work/elefante",
        recall_cues=["What is Elefante's core purpose, and how should we judge its value?"],
    )
    dashboard = _memory(
        "Elefante's dashboard is an internal tool for advanced users to "
        "understand and manage memories, not a marketing page.",
        project="elefante",
        workspace="/work/elefante",
        recall_cues=["How should Elefante's dashboard help its users, and what should it avoid?"],
    )

    class CueEmbeddings:
        async def generate_embeddings_batch(self, texts):
            assert texts == [question, *purpose.metadata.recall_cues, *dashboard.metadata.recall_cues]
            return [[1.0, 0.0], *[[s, math.sqrt(1 - s * s)] for s in similarities]]

    orchestrator = MemoryOrchestrator(
        vector_store=_VectorStore([purpose, dashboard]),
        graph_store=object(),
        embedding_service=CueEmbeddings(),
    )
    candidates = [
        SearchResult(memory=purpose, score=0.63, vector_score=0.90, source="hybrid"),
        SearchResult(memory=dashboard, score=0.64, vector_score=0.92, source="hybrid"),
    ]
    before = [item.memory.model_dump() for item in candidates]
    await orchestrator._match_recall_cue_paraphrases(
        question,
        candidates,
        filters=SearchFilters(project="elefante", workspace="/work/elefante"),
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task=question, project="elefante", workspace="/work/elefante",
            profile=TaskBriefProfile.V2,
        ),
        candidates,
    )

    assert brief.selected_memory_ids == ([str(purpose.id)] if selected else [])
    assert [item.memory.model_dump() for item in candidates] == before
    assert all(item.recall_cue_match is False for item in candidates)
    assert all(item.vector_score == score for item, score in zip(candidates, [0.90, 0.92]))
    assert not orchestrator.vector_store.calls  # no extra corpus scan or store write
    if selected:
        assert candidates[0].recall_cue_similarity == pytest.approx(0.95)
        assert candidates[0].to_dict()["recall_cue_similarity"] == pytest.approx(0.95)


@pytest.mark.parametrize("blocked_by", ["archived", "conflict", "scope", "identifier", "partial_identifier", "privacy"])
def test_recall_cue_paraphrase_cannot_bypass_governance(blocked_by):
    memory = _memory(
        "The device stores settings across launches.",
        project="test-project", workspace="/work/test-project",
    )
    question = "Where are application preferences persisted?"
    if blocked_by == "archived":
        memory.metadata.archived = True
    elif blocked_by == "conflict":
        memory.metadata.conflict_ids = [uuid4()]
    elif blocked_by == "scope":
        memory.metadata.project = "other-project"
    elif blocked_by == "identifier":
        question = "Where are device R32's settings persisted?"
    elif blocked_by == "partial_identifier":
        question = "Where are device R32's Q87 settings persisted?"
        memory.content = "Device R32 stores settings across launches."
    elif blocked_by == "privacy":
        memory.metadata.source_detail = "api_key=" + ("a" * 32)
    candidate = SearchResult(
        memory=memory, source="vector", score=0.7, vector_score=0.85,
        recall_cue_similarity=0.98,
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task=question, project="test-project", workspace="/work/test-project",
            profile=TaskBriefProfile.V2,
        ),
        [candidate],
    )
    assert brief.abstained is True


@pytest.mark.asyncio
async def test_recall_cue_paraphrase_drops_stale_marks_and_skips_unscoped_work():
    memory = _memory("The spare batteries are in the hall cabinet.")
    candidate = SearchResult(
        memory=memory, source="vector", score=0.8, recall_cue_similarity=0.99,
        recall_focus_similarity=0.99,
    )
    orchestrator = MemoryOrchestrator(
        vector_store=object(), graph_store=object(), embedding_service=object(),
    )
    await orchestrator._match_recall_cue_paraphrases("A different question", [candidate])
    assert candidate.recall_cue_similarity is None
    assert candidate.recall_focus_similarity is None


@pytest.mark.parametrize(
    ("question", "focus"),
    [("Where is the toolbox?", "location"),
     ("When does the train depart?", "time"),
     ("For how many weeks are logs retained?", "duration"),
     ("Which supplier should I use?", "property:supplier"),
     ("Do I prefer paper or digital tickets?", "choice:paper or digital tickets"),
     ("What is the product for, and how should I use it?", None),
     ("Explain the latest design", None)],
)
def test_recall_question_focus_is_domain_independent(question, focus):
    assert TaskBriefCompiler._question_focus(question) == focus


def test_recall_cues_do_not_veto_broader_guidance_or_additional_body_facts():
    memory = _memory(
        "Use the bronze label. The supplier is Northwind.",
        recall_cues=["Which label should I use?"],
    )
    assert TaskBriefCompiler._recall_cue_focus("How should I prepare a shipment?", memory) == "unknown"
    assert TaskBriefCompiler._recall_cue_focus("Which supplier should I use?", memory) == "unknown"
    assert TaskBriefCompiler._recall_cue_focus("Which price should I pay?", memory) == "property"
    memory.metadata.recall_cues = [f"Which label should I use in case {index}?" for index in range(5)] + ["Which price should I pay?"]
    assert TaskBriefCompiler._recall_cue_focus("Which price should I pay?", memory) == "property"


@pytest.fixture(scope="module")
def cached_cue_embeddings():
    """Optional real-model proof; never download a model during unit tests."""
    from src.core.embeddings import EmbeddingService

    sentence_transformers = pytest.importorskip("sentence_transformers")
    try:
        model = sentence_transformers.SentenceTransformer(
            "thenlper/gte-base", device="cpu", local_files_only=True,
        )
    except OSError:
        pytest.skip("gte-base is not cached; real-model Recall proof was not run")
    service = EmbeddingService(model="thenlper/gte-base")
    service._model = model  # preloaded synchronously, before any async encoding
    return service


# Cold cases authored independently of the matcher and its thresholds. The
# unsupported past-meal question replaces an invalid negative: an allergy can
# legitimately inform a dinner recommendation. Expected IDs were fixed before
# running the model; do not rewrite the cues to make a failed question pass.
_CUE_PARAPHRASE_CASES = [
    (
        "cooking",
        [
            ("I prefer weeknight dinners that take 30 minutes or less.",
             "What is my usual weeknight dinner time limit?"),
            ("I avoid peanuts because of an allergy.",
             "Which ingredient must I keep out of my meals?"),
        ],
        [("How quickly do I want a weeknight dinner ready?", [0]),
         ("What did I eat for lunch last Tuesday?", [])],
    ),
    (
        "travel",
        [
            ("For my October city break, I chose the train instead of a rental car.",
             "How did I decide to travel on the October trip?"),
            ("I avoid flights departing before 8 a.m.",
             "What flight departure times do not work for me?"),
        ],
        [("Did I choose rail over hiring a car for October?", [0]),
         ("Where should I travel next?", [])],
    ),
    (
        "home",
        [
            ("The spare batteries are in the top drawer of the hall cabinet.",
             "Where did I put the spare batteries?"),
            ("I water the balcony herbs every Saturday morning.",
             "When do I water the balcony herbs?"),
        ],
        [("Where are the backup batteries kept?", [0]),
         ("Which houseplant needs repotting?", [])],
    ),
    # Independent near-miss holdout. Shared subject words do not establish
    # that a stored fact answers the property being asked about.
    (
        "pancakes",
        [("My pancake batter uses oat milk instead of dairy milk.",
          "What milk do I use when I make pancakes?"),
         ("I soak dried chickpeas overnight before cooking them.",
          "How do I prepare dried chickpeas before cooking?")],
        [("Which milk should I use for my pancakes?", [0]),
         ("Which oat-milk brand do I buy for pancakes?", []),
         ("How much oat milk should I measure for my pancake recipe?", [])],
    ),
    (
        "flights",
        [("I prefer an aisle seat on flights longer than three hours.",
          "Which seat do I prefer on a flight longer than three hours?"),
         ("I pack a compact power bank for weekend trips because my phone battery does not last a full day.",
          "What electronic item do I pack for weekend trips?")],
        [("For a flight lasting several hours, which seat do I usually choose?", [0]),
         ("Which airline do I usually choose for flights longer than three hours?", []),
         ("How much do I pay for my preferred aisle seat on long flights?", [])],
    ),
    (
        "laundry",
        [("I wash dark clothes in cold water to reduce fading.",
          "Do I wash dark clothes in warm or cold water?"),
         ("I air-dry wool sweaters flat instead of putting them in the dryer.",
          "How do I dry my wool sweaters?")],
        [("What water temperature should I use for dark laundry?", [0]),
         ("What detergent brand do I use for dark clothes?", []),
         ("How long is my cold-water cycle for dark clothes?", [])],
    ),
    (
        "communication",
        [("I prefer short answers with the conclusion first.",
          "How should you format answers for me?"),
         ("I prefer spoken explanations in Spanish.",
          "What language do I prefer for spoken explanations?")],
        [("How do I want you to structure your answer?", [0]),
         ("Which font should you use in my reports?", []),
         ("Which language should my spoken briefing use?", [1])],
    ),
    (
        "keys",
        [("The spare house keys are kept in the kitchen drawer.",
          "Where do I keep the spare house keys?"),
         ("The garage remote is on the hall shelf.",
          "Where is the garage remote?")],
        [("Where is my spare house key?", [0]),
         ("Who else has a copy of my house key?", []),
         ("How many spare house keys do I have?", [])],
    ),
    (
        "operations",
        [("Deployments require running the existing smoke tests first.",
          "What must I check before deploying a change?"),
         ("Database snapshots are retained for fourteen days.",
          "How long are database snapshots retained?")],
        [("How should I verify a change before deploying it?", [0]),
         ("At what time did the latest deployment finish?", []),
         ("For how many days are database snapshots kept?", [1])],
    ),
    (
        "planning",
        [("On Tuesdays the planning meeting starts at ten in the morning.",
          "When does the Tuesday planning meeting start?"),
         ("I disable app notifications during work hours.",
          "How should app notifications behave while I work?")],
        [("What time is the Tuesday planning meeting?", [0]),
         ("Which room is the Tuesday planning meeting in?", []),
         ("How should my app notifications behave while I am working?", [1])],
    ),
    (
        "elefante",
        [("Elefante should turn relevant memories into useful advice that improves "
          "the current task. Judge its value by measurable task results and accepted "
          "task value per total token. Token savings and additional infrastructure "
          "are means, not the product goal.",
          "What is Elefante's core purpose, and how should we judge its value?"),
         ("Elefante's dashboard is an internal tool for advanced users to understand "
          "and manage memories, not a marketing page. Keep it clean and concise. "
          "Explain each feature's use, behavior, and visible result in plain language, "
          "with grounded documentation and real examples. A 'ready' badge alone "
          "does not demonstrate value.",
          "How should Elefante's dashboard help its users, and what should it avoid?"),
         ("Elefante's founder is the sole operator across development, operations, "
          "marketing, the website, and business. Plan work that one person can "
          "maintain. Reuse completed work and existing documentation before adding "
          "scope; favor small, useful changes that reduce recurring effort.",
          "What staffing and maintenance constraints should shape Elefante's next feature?")],
        [("What is Elefante for?", [0]),
         ("How should Elefante's dashboard help its users, and what should it avoid?", [1]),
         ("What staffing and maintenance constraints should shape Elefante's next feature?", [2]),
         ("How much does Elefante's dashboard cost?", []),
         ("Where is Elefante's dashboard hosted?", []),
         ("How do I bake sourdough bread?", [])],
    ),
    (
        "tickets",
        [("I prefer digital tickets rather than paper tickets.",
          "Do I prefer paper or digital tickets?"),
         ("The concert starts at eight in the evening.",
          "When does the concert start?")],
        [("Which ticket format do I prefer?", [0]),
         ("What ticket price do I usually pay?", [])],
    ),
    (
        "vocabulary",
        [("Use SQLite for the event index.",
          "Which database should we use for the event index?"),
         ("We buy event badges from Northwind Print.",
          "Which supplier should we use for event badges?")],
        [("Which storage engine should the event index use?", [0]),
         ("Which vendor should we use for event badges?", [1]),
         ("Which license should the event index use?", []),
         ("Which colour should we use for event badges?", [])],
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain", "records", "question", "expected"),
    [
        pytest.param(domain, records, question, expected, id=f"{domain}-{index + 1}")
        for domain, records, questions in _CUE_PARAPHRASE_CASES
        for index, (question, expected) in enumerate(questions)
    ],
)
async def test_recall_cue_paraphrase_cold_domains(
    domain, records, question, expected, cached_cue_embeddings, monkeypatch,
):
    import numpy as np

    memories = [
        _memory(content, project=domain, workspace=f"/work/{domain}", recall_cues=[cue])
        for content, cue in records
    ]
    orchestrator = MemoryOrchestrator(
        vector_store=_VectorStore(memories), graph_store=object(),
        embedding_service=cached_cue_embeddings,
    )
    before = [memory.model_dump() for memory in memories]
    filters = SearchFilters(project=domain, workspace=f"/work/{domain}")

    async def semantic_results(query, *_args, **_kwargs):
        vectors = np.asarray(await cached_cue_embeddings.generate_embeddings_batch(
            [query, *[memory.content for memory in memories]],
        ))
        return [
            SearchResult(memory=memory, source="vector", score=float(score), vector_score=float(score))
            for memory, score in zip(memories, vectors[1:] @ vectors[0])
        ]

    monkeypatch.setattr(orchestrator, "_search_hybrid", semantic_results)
    results = await orchestrator.search_memories(
        query=question, mode=QueryMode.HYBRID, filters=filters,
        include_conversation=False, apply_temporal_decay=False, reinforce_access=False,
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(task=question, project=domain, workspace=f"/work/{domain}", profile=TaskBriefProfile.V2),
        results,
    )
    assert brief.selected_memory_ids == [str(memories[index].id) for index in expected], question
    assert [memory.model_dump() for memory in memories] == before


@pytest.mark.asyncio
async def test_live_price_month_query_does_not_select_existing_purpose_memory(
    cached_cue_embeddings,
    monkeypatch,
):
    """A real cue paraphrase must not answer an unrecorded price question."""
    import numpy as np

    purpose_content, purpose_cue = next(
        records[0]
        for domain, records, _questions in _CUE_PARAPHRASE_CASES
        if domain == "elefante"
    )
    purpose = _memory(
        purpose_content,
        project="elefante",
        workspace="/work/elefante",
        recall_cues=[purpose_cue],
    )
    question = "How much does Elefante cost per month?"
    orchestrator = MemoryOrchestrator(
        vector_store=_VectorStore([purpose]),
        graph_store=object(),
        embedding_service=cached_cue_embeddings,
    )
    before = purpose.model_dump()
    filters = SearchFilters(project="elefante", workspace="/work/elefante")

    async def semantic_results(query, *_args, **_kwargs):
        vectors = np.asarray(
            await cached_cue_embeddings.generate_embeddings_batch(
                [query, purpose.content],
            )
        )
        score = float(vectors[1] @ vectors[0])
        return [
            SearchResult(
                memory=purpose,
                source="vector",
                score=score,
                vector_score=score,
            )
        ]

    monkeypatch.setattr(orchestrator, "_search_hybrid", semantic_results)
    results = await orchestrator.search_memories(
        query=question,
        mode=QueryMode.HYBRID,
        filters=filters,
        include_conversation=False,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert len(results) == 1
    candidate = results[0]
    assert candidate.memory is purpose
    assert candidate.recall_cue_match is False
    assert purpose.metadata.recall_cues == [purpose_cue]
    assert purpose.model_dump() == before

    assert TaskBriefCompiler._question_focus(question) == "amount"
    assert TaskBriefCompiler._recall_cue_focus(question, purpose) == "different"
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task=question,
            project="elefante",
            workspace="/work/elefante",
            profile=TaskBriefProfile.V2,
        ),
        results,
    )

    assert brief.abstained is True
    assert brief.selected_memory_ids == []
    assert brief.omissions[0].reason == "insufficient-independent-relevance"


@pytest.mark.asyncio
async def test_memory_search_handler_forwards_surface_context_and_exposes_match(monkeypatch):
    memory = _memory(
        "The migration rollback note is in the customer handbook.",
        trigger=["terminal error: migration locked"],
        policy="triggered",
    )
    captured = {}

    class _Orchestrator:
        async def search_memories(self, **kwargs):
            captured.update(kwargs)
            return [
                SearchResult(
                    memory=memory,
                    score=1.0,
                    source="triggered",
                    surface_matches=["terminal error: migration locked"],
                )
            ]

    server = ElefanteMCPServer()

    async def get_orchestrator():
        return _Orchestrator()

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    response = await server._handle_search_memories(
        {
            "query": "What should I investigate next?",
            "surface_context": "terminal error: migration locked while applying the backup",
            "include_conversation": False,
            "include_stored": True,
        }
    )

    assert captured["surface_context"].startswith("terminal error")
    assert response["results"][0]["source"] == "triggered"
    assert response["results"][0]["surface_matches"] == [
        "terminal error: migration locked"
    ]
