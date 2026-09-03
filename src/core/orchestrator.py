# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/core/orchestrator.py
# PURPOSE : Central intelligence layer: routes queries to vector/graph stores,
#           applies intelligence-pipeline filters, enforces memory guards.
# ROLE    : Core — highest-traffic module; every MCP tool call passes through here.
# TOUCHED : When changing memory filtering logic, add/remove a memory type,
#           modify intelligence-pipeline guards, or adjust scoring weights.
#           BUG-011 rejection_reason field lives here.
# ─────────────────────────────────────────────────────────────────────────────
"""
Hybrid Query Orchestrator - Routes queries between Vector and Graph stores

This is the central intelligence layer that:
1. Analyzes queries to determine optimal routing strategy
2. Executes searches across both databases
3. Merges and ranks results with weighted scoring
4. Provides unified API for memory operations
"""

import asyncio
import hashlib
import inspect
import os
import re
import json
from difflib import SequenceMatcher
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from src.models.memory import (
    Memory, MemoryType, MemoryMetadata, MemoryStatus,
    DomainType, InjectionPolicy, RetentionPolicy, SourceType, TYPE_DECAY_RATES
)
from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.models.query import QueryMode, QueryPlan, SearchResult, SearchFilters
from src.core.vector_store import VectorStore, get_vector_store
from src.core.graph_store import GraphStore, get_graph_store
from src.core.embeddings import EmbeddingService, get_embedding_service
from src.core.retrieval import CognitiveRetriever, MemoryCandidate
from src.core.conflict_detection import ConflictOutcome, assess_conflict
from src.core.governance import governance_reason, matching_triggers
from src.utils.logger import get_logger
from src.utils.config import get_config
from src.utils.validators import validate_memory_content, validate_uuid
from src.utils.runtime_profile import is_client_runtime
from src.core.etl import ProcessingStatus  # Only need status, classification is agent-driven
from src.models.task import TaskStatus

logger = get_logger(__name__)

# Only reinforce memories that were genuinely relevant to the query.
# Below this threshold the hit is a keyword drag, not a true match.
# (Theoretical composite max without coactivation signal is ~0.65-0.70.)
REINFORCEMENT_THRESHOLD = 0.55
SURFACE_SCAN_MAX_MEMORIES = 5000
SURFACE_MAX_MEMORIES = 3
RECALL_CUE_MAX_CANDIDATES = 12
RECALL_CUE_MIN_MARGIN = 0.03

SYSTEM_SPECIFICATIONS = (
    {
        "title": "SDD Gate 2 Leakage Surface Scan",
        "category": "sdd",
        "canonical_key": "system:sdd:gate-2-leakage-surface-scan",
        "summary": "SDD Gate 2 leakage surface scan table for Elefante contributors.",
        "content": (
            "SDD Gate 2 leakage surface scan table specification for Elefante contributors. "
            "Every change must be checked against these leakage surfaces: MCP response contract, "
            "configured vector-store write/read roundtrip, Kuzu schema and DML split, stdout purity, "
            "compliance gate state machine, dashboard snapshot contract, co-activation history, "
            "and documentation links. Reference docs: agents/orchestrator.md "
            "for the gate definition and workspace/ISSUES.md for issue routing."
        ),
        "tags": ["system", "sdd", "gate-2", "leakage-scan", "specification"],
    },
    {
        "title": "SDD Gate 3 Scoring Formulas",
        "category": "sdd",
        "canonical_key": "system:sdd:gate-3-scoring-formulas",
        "summary": "SDD Gate 3 source-truth scoring formulas for behavioral relevance and cognitive retrieval.",
        "content": (
            "SDD Gate 3 scoring formulas specification for Elefante contributors. Verify the behavioral "
            "relevance formula and the cognitive retrieval composite from source code, not from remembered "
            "docs. Temporal vitality = exp(-effective_decay_rate * days_created) * "
            "exp(-0.005 * days_since_access), where effective_decay_rate = decay_rate / "
            "(1 + 0.25 * ln(access_count + 1)). Cognitive retrieval composite = 0.35 * "
            "vector_score + 0.30 * concept_score + 0.15 * coactivation_score + 0.10 * "
            "authority_score + 0.10 * temporal_score. Retrieval exposure is not verified task utility."
        ),
        "tags": ["system", "sdd", "gate-3", "scoring", "specification"],
    },
    {
        "title": "Elefante Developer Etiquette",
        "category": "developer-process",
        "canonical_key": "system:developer-etiquette:closure",
        "summary": "Completion protocol covering CLEAN, DOC_SYNC, changelog contract, and versioning for Elefante repo work.",
        "content": (
            "Elefante Developer Etiquette specification for versioning, CLEAN, and DOC_SYNC. Before claiming "
            "done: CLEAN_ENVIRONMENT removes leftovers, scratch files, and dead code. DOC_SYNC updates README.md, "
            "docs/README.md, docs/reference/architecture.md, and CHANGELOG.md. CHANGELOG.md must use the "
            "current Keep a Changelog headings `### Added`, `### Fixed`, or `### Changed` and document Why, What, "
            "and Impact in the matching section. STRICT_SEMVER uses scripts/ci/advise_version_bump.py to choose a "
            "version when needed and scripts/ci/bump_version.py instead of manual version edits. The working tree "
            "must be reviewed before finish."
        ),
        "tags": ["system", "developer-etiquette", "clean", "doc-sync", "changelog", "versioning", "specification"],
    },
)


class MemoryOrchestrator:
    """
    Orchestrates memory operations across vector and graph databases
    
    This class provides the main API for:
    - Adding memories (stores in both databases)
    - Searching memories (hybrid search across both)
    - Managing entities and relationships
    - Retrieving context for sessions/tasks
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional[GraphStore] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize orchestrator with database connections
        
        Args:
            vector_store: configured vector-store instance
            graph_store: Kuzu graph store instance
            embedding_service: Embedding generation service
        """
        self.vector_store = vector_store or get_vector_store()
        self.graph_store = graph_store or get_graph_store()
        self.embedding_service = embedding_service or get_embedding_service()
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)

        # Cognitive Retriever - multi-signal scoring engine
        self.cognitive_retriever = CognitiveRetriever()
        self._system_baseline_ready = False
        self._last_rejection_reason: Optional[str] = None

        self.logger.info("Memory orchestrator initialized")

    async def ensure_system_baseline(self) -> Dict[str, Any]:
        """Ensure the runtime SDD specification baseline exists for every install."""
        if is_client_runtime():
            self._system_baseline_ready = True
            return {"success": True, "created": 0, "existing": 0, "titles": []}
        if self._system_baseline_ready:
            return {
                "success": True,
                "created": 0,
                "existing": len(SYSTEM_SPECIFICATIONS),
                "titles": [spec["title"] for spec in SYSTEM_SPECIFICATIONS],
            }

        created = []
        existing = []

        for specification in SYSTEM_SPECIFICATIONS:
            current = await self.vector_store.find_by_title(specification["title"])
            if current is not None:
                memory_type = current.metadata.memory_type
                if hasattr(memory_type, "value"):
                    memory_type = memory_type.value
                if str(memory_type).lower() == "specification":
                    existing.append(specification["title"])
                    continue

            await self.add_memory(
                content=specification["content"],
                memory_type="specification",
                tags=specification["tags"],
                metadata={
                    "domain": "system",
                    "category": specification["category"],
                    "title": specification["title"],
                    "summary": specification["summary"],
                    "namespace": "system",
                    "canonical_key": specification["canonical_key"],
                },
            )
            created.append(specification["title"])

        self._system_baseline_ready = True
        self.logger.info(
            "system_baseline_ready",
            created=len(created),
            existing=len(existing),
        )
        return {
            "success": True,
            "created": len(created),
            "existing": len(existing),
            "created_titles": created,
            "existing_titles": existing,
        }
    
    async def add_memory(
        self,
        content: str,
        memory_type: str = "conversation",
        tags: List[str] = None,
        entities: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None,
        force_new: bool = False,
        memory_id: UUID | None = None,
        conflict_ids: List[UUID] | None = None,
    ) -> Optional[Memory]:
        """
        Validate, enrich, deduplicate, persist, and graph-link a memory.
        
        Score is system-computed (starts at 100, decays with age).
        Decay rate is set automatically from memory_type.
        """


        explicit_conflict_ids = list(dict.fromkeys(conflict_ids or []))
        if any(not isinstance(item, UUID) for item in explicit_conflict_ids):
            raise ValueError("conflict_ids must contain UUID values")
        if memory_id is not None and memory_id in explicit_conflict_ids:
            raise ValueError("a memory cannot conflict with itself")
        if explicit_conflict_ids and not force_new:
            raise ValueError("explicit conflict links require a forced new memory")

        # ==================================================================================
        # STEP 1: PRIVACY + VALIDATE INPUT
        # ==================================================================================
        from src.modules.distiller.privacy import PrivacyFilter

        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        payload, privacy_redactions, privacy_types = PrivacyFilter().scrub_payload(
            {
                "content": content,
                "tags": tags or [],
                "entities": entities or [],
                "metadata": dict(metadata or {}),
            }
        )
        content = payload["content"]
        tags = payload["tags"]
        entities = payload["entities"]
        metadata = payload["metadata"]
        if privacy_redactions:
            system_metadata = dict(metadata.get("system_metadata") or {})
            system_metadata["privacy_redactions"] = privacy_redactions
            system_metadata["privacy_redacted_types"] = privacy_types
            metadata["system_metadata"] = system_metadata
        validate_memory_content(content)

        # Guardrail: block test-memory creation unless explicitly allowed.
        # Rationale: production memory graph should not accumulate E2E/persistence test artifacts.
        allow_test = os.getenv("ELEFANTE_ALLOW_TEST_MEMORIES", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }

        tags_list = tags or []
        tags_lower = {t.strip().lower() for t in tags_list if isinstance(t, str) and t.strip()}
        category_lower = str(metadata.get("category") or "").strip().lower()
        namespace_lower = str(metadata.get("namespace") or "").strip().lower()
        content_lower = (content or "").strip().lower()

        is_test_like = (
            namespace_lower == "test"
            or category_lower == "test"
            or category_lower.startswith("hybrid_test_")
            or "test" in tags_lower
            or "e2e" in tags_lower
            or any(t.startswith("hybrid_test_") for t in tags_lower)
            or content_lower.startswith("elefante e2e test memory")
            or content_lower.startswith("hybrid search test memory")
            or " test memory" in content_lower
        )

        if is_test_like and not allow_test:
            matched_conditions = []
            if namespace_lower == "test":
                matched_conditions.append("namespace='test'")
            if category_lower == "test":
                matched_conditions.append("category='test'")
            if category_lower.startswith("hybrid_test_"):
                matched_conditions.append(f"category='{category_lower}' starts with 'hybrid_test_'")
            if "test" in tags_lower:
                matched_conditions.append("tag 'test' present")
            if "e2e" in tags_lower:
                matched_conditions.append("tag 'e2e' present")
            hybrid_tags = [t for t in tags_lower if t.startswith("hybrid_test_")]
            if hybrid_tags:
                matched_conditions.append(f"tag '{hybrid_tags[0]}' starts with 'hybrid_test_'")
            if content_lower.startswith("elefante e2e test memory"):
                matched_conditions.append("content starts with 'elefante e2e test memory'")
            if content_lower.startswith("hybrid search test memory"):
                matched_conditions.append("content starts with 'hybrid search test memory'")
            if " test memory" in content_lower:
                matched_conditions.append("content contains ' test memory'")
            reason = (
                f"Test-memory guard blocked this submission. "
                f"Matched conditions: {'; '.join(matched_conditions)}. "
                f"Set ELEFANTE_ALLOW_TEST_MEMORIES=1 to override."
            )
            self._last_rejection_reason = reason
            self.logger.warning(
                "blocked_test_memory_submission",
                category=category_lower or None,
                namespace=namespace_lower or None,
                tags=sorted(tags_lower),
                reason=reason,
            )
            return None

        def _normalize_for_compare(text: str) -> str:
            text = text.lower().strip()
            return re.sub(r"\s+", " ", text)

        def _is_near_duplicate(a: str, b: str, threshold: float = 0.985) -> bool:
            na = _normalize_for_compare(a)
            nb = _normalize_for_compare(b)
            if na == nb:
                return True
            return SequenceMatcher(None, na, nb).ratio() >= threshold

        def _keywords(text: str) -> set[str]:
            words = re.findall(r"[a-zA-Z][a-zA-Z\-']+", text.lower())
            stop = {
                "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are",
                "be", "being", "been", "should", "must", "always", "please", "this", "that", "it",
                "i", "me", "my", "we", "you", "your", "they", "them", "he", "she", "as",
            }
            return {w for w in words if w not in stop and len(w) >= 3}

        def _has_meaningful_overlap(a: str, b: str) -> bool:
            ka = _keywords(a)
            kb = _keywords(b)
            if not ka or not kb:
                return False
            overlap = ka & kb
            # Guardrail: require at least a few shared keywords.
            return len(overlap) >= 3
            
        # Decay rate from memory type
        decay_rate = TYPE_DECAY_RATES.get(memory_type, 0.01)

        # Agent-driven enrichment (Elefante never calls an LLM).
        action = metadata.get("action")
        if isinstance(action, str) and action.strip().upper() == "IGNORE":
            self.logger.info(
                "Memory ignored by agent instruction",
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
            return None

        provided_title = metadata.get("title")
        if isinstance(provided_title, str) and provided_title.strip():
            title = provided_title.strip()
        else:
            from src.utils.curation import generate_title
            title = generate_title(content=content, max_len=120)
            metadata["title"] = title

        # ==================================================================================
        # STEP 1.5: LOGIC-LEVEL DEDUPLICATION (Pattern #5 Fix)
        # ==================================================================================
        # Check if this exact Concept Title already exists
        existing_memory = None
        if not force_new:
            existing_memory = await self.vector_store.find_by_title(title)

        if existing_memory:
            if _is_near_duplicate(content, existing_memory.content):
                self.logger.info(
                    f"LOGIC-LEVEL DEDUPLICATION: '{title}' already exists as {existing_memory.id}. Reinforcing."
                )

                # Reinforce existing memory (update timestamp, access count)
                existing_memory.metadata.last_accessed = datetime.utcnow()
                existing_memory.metadata.access_count += 1
                await self.vector_store.update_memory_access(existing_memory)
                return existing_memory

            # Title collision but materially different content.
            # Disambiguate title so we don't drop the new memory.
            digest = hashlib.sha256(_normalize_for_compare(content).encode("utf-8")).hexdigest()[:8]
            title = f"{title} [{digest}]"
            metadata["title"] = title

        # ==================================================================================
        # STEP 1.75: PREFERENCE RE-ASSERTION MERGE
        # ==================================================================================
        is_preference_like = str(memory_type).lower() == MemoryType.PREFERENCE.value

        if is_preference_like and not force_new:
            preference_candidates = await self.vector_store.search(
                query=content,
                limit=5,
                min_similarity=0.30,
                apply_temporal_decay=False,
                # where_override removed: collection.query() with where fails on ChromaDB 1.3.5
                # when the collection index is corrupted. The Python-side pref_like filter
                # below already handles memory_type filtering correctly. (BUG-022)
            )

            if preference_candidates:
                # Filter down to actual preferences after retrieval to avoid brittle
                # Chroma where-clauses. A close decision, constraint, or fact is
                # related evidence; it must never be rewritten as a preference
                # reassertion.
                pref_like = [
                    r
                    for r in preference_candidates
                    if str(r.memory.metadata.memory_type).lower() == MemoryType.PREFERENCE.value
                ]

                best_pref = pref_like[0] if pref_like else None

                # Merge only when we're confident it's the same preference.
                if (
                    best_pref is not None
                    and best_pref.score >= 0.40
                    and _has_meaningful_overlap(content, best_pref.memory.content)
                ):
                    existing = best_pref.memory
                    now = datetime.utcnow()

                    merged_tags: List[str] = []
                    seen = set()
                    for t in (existing.metadata.tags or []) + (tags or []):
                        if isinstance(t, str):
                            tt = t.strip()
                            if tt and tt not in seen:
                                seen.add(tt)
                                merged_tags.append(tt)

                    merged_score = int(existing.metadata.score or 100)

                    merged_content = existing.content
                    if not _is_near_duplicate(content, existing.content):
                        normalized_existing = _normalize_for_compare(existing.content)
                        normalized_incoming = _normalize_for_compare(content)
                        if normalized_incoming not in normalized_existing:
                            merged_content = (
                                f"{existing.content.rstrip()}\n\n"
                                f"Reasserted ({now.date().isoformat()}): {content.strip()}"
                            )

                    cm = dict(existing.metadata.custom_metadata or {})
                    reinforcements = cm.get("reinforcements")
                    if not isinstance(reinforcements, list):
                        reinforcements = []
                    reinforcements.append(
                        {
                            "at": now.isoformat(),
                            "content": content[:200],
                            "similarity": float(best_pref.score),
                        }
                    )
                    cm["reinforcements"] = reinforcements[-10:]

                    await self.vector_store.update_memory(
                        existing.id,
                        {
                            "content": merged_content,
                            "tags": merged_tags,
                            "score": merged_score,
                            "last_accessed": now,
                            "last_modified": now,
                            "access_count": int(existing.metadata.access_count or 1) + 1,
                            "custom_metadata": cm,
                        },
                    )

                    updated = await self.vector_store.get_memory(existing.id)
                    self.logger.info(
                        "preference_reassertion_merged",
                        existing_id=str(existing.id),
                        similarity=float(best_pref.score),
                    )
                    return updated or existing

        # ==================================================================================
        # STEP 2: INTEGRITY (Duplicate & Contradiction Check)
        # ==================================================================================
        embedding = await self.embedding_service.generate_embedding(content)
        
        similar_memories = []
        if not force_new:
            similar_memories = await self.vector_store.search(
                query=content,
                limit=3,
                min_similarity=0.65,  # Threshold
                # Integrity checks should use pure semantic similarity.
                # Temporal decay/reinforcement can inflate scores and cause false REDUNDANT.
                apply_temporal_decay=False
            )
        
        status = MemoryStatus.NEW
        related_id = None
        if similar_memories:
            best_match = similar_memories[0]

            # A contradiction is materially stronger than textual similarity.
            # Check it first so a one-word negation cannot be downgraded to a
            # near-duplicate simply because the rest of the sentence matches.
            conflict_assessment = assess_conflict(
                content,
                best_match.memory.content,
            )
            if (
                best_match.score >= 0.75
                and conflict_assessment.outcome is ConflictOutcome.CONFLICT
            ):
                status = MemoryStatus.CONTRADICTORY
                related_id = best_match.memory.id
                self.logger.warning(
                    "CONTRADICTORY memory detected",
                    conflicting_memory_id=str(best_match.memory.id),
                    reason=conflict_assessment.reason,
                )
            elif best_match.score >= 0.95:
                if _is_near_duplicate(content, best_match.memory.content):
                    status = MemoryStatus.REDUNDANT
                    related_id = best_match.memory.id
                    self.logger.info(f"Found redundant memory: {best_match.memory.id} (Score: {best_match.score})")
                else:
                    status = MemoryStatus.RELATED
                    related_id = best_match.memory.id
            elif best_match.score >= 0.75:
                status = MemoryStatus.RELATED
                related_id = best_match.memory.id

        # Verified Remember performs the customer-visible overlap inspection
        # before this write.  Preserve its exact conflict decision even though
        # force_new intentionally skips the legacy similarity/deduplication path.
        if explicit_conflict_ids:
            status = MemoryStatus.CONTRADICTORY
            related_id = explicit_conflict_ids[0]

        # ==================================================================================
        # STEP 3: WRITE (Construct Memory Object)
        # ==================================================================================
        try:
            # Map common V1 "custom" fields to V2 structured fields
            domain = metadata.get("domain", "reference")
            category = metadata.get("category", tags[0] if tags else "general")
            confidence = metadata.get("confidence", 0.7)
            source = metadata.get("source", "user_input")

            summary_text = metadata.get("summary")
            if not isinstance(summary_text, str) or not summary_text.strip():
                from src.utils.curation import generate_summary

                summary_text = generate_summary(content=content, max_len=220)
                metadata["summary"] = summary_text
            
            # ==================================================================================
            # STEP 3.25: V4 COGNITIVE RETRIEVAL FIELDS
            # Auto-populate concepts, surfaces_when for better retrieval
            # ==================================================================================
            from src.utils.curation import (
                extract_concepts,
                infer_surfaces_when,
                compute_authority_score,
                canonicalize_concepts,
                canonicalize_recall_cues,
                canonicalize_surfaces_when,
            )
            
            concepts = metadata.get("concepts")
            if not concepts or not isinstance(concepts, list):
                concepts = extract_concepts(content, max_concepts=5)

            concepts = canonicalize_concepts(concepts, max_concepts=5)
            metadata["concepts"] = concepts
            
            surfaces_when = metadata.get("surfaces_when")
            if not surfaces_when or not isinstance(surfaces_when, list):
                surfaces_when = infer_surfaces_when(content, concepts)

            surfaces_when = canonicalize_surfaces_when(surfaces_when)
            metadata["surfaces_when"] = surfaces_when

            recall_cues = canonicalize_recall_cues(
                metadata.get("recall_cues")
                if isinstance(metadata.get("recall_cues"), list)
                else []
            )
            metadata["recall_cues"] = recall_cues
            
            # Compute initial authority score
            authority_score = compute_authority_score(
                score=5,  # neutral start, system-computed
                access_count=1,
                days_since_created=0,
                days_since_accessed=0,
                memory_type=memory_type,
            )
            metadata["authority_score"] = authority_score
            
            # Extract system_metadata before building custom_metadata
            # (ADV-001: system_metadata must reach MemoryMetadata explicitly)
            system_metadata = metadata.pop("system_metadata", {})
            source_context = metadata.pop("elefante_source", {})
            if not isinstance(source_context, dict):
                source_context = {}
            source_context = {
                "tool": str(source_context.get("tool", "legacy")),
                "instance_id": str(source_context.get("instance_id", "legacy")),
                "session_id": str(source_context.get("session_id", "legacy")),
                "cwd": str(source_context.get("cwd", "")),
                "transport": str(source_context.get("transport", "stdio")),
                "timestamp_utc": datetime.utcnow().isoformat(),
            }
            
            custom_metadata = {
                k: v for k, v in metadata.items()
                if k not in [
                    "domain",
                    "category",
                    "confidence",
                    "source",
                    "project",
                    "workspace",
                    "retention_policy",
                    "injection_policy",
                    "scope",
                    "trigger",
                    "user_locked",
                ]
            }
            
            # ==================================================================================
            # STEP 3.5: RAW STORAGE (ETL tracking)
            # Store with processing_status=raw.
            # ==================================================================================
            custom_metadata["processing_status"] = ProcessingStatus.RAW
            custom_metadata["ingested_at"] = datetime.utcnow().isoformat()
            # Persist curated fields into custom_metadata for the configured vector
            # backend; title and summary are also used by the dashboard and deduplication.
            custom_metadata["title"] = title
            custom_metadata["summary"] = summary_text
            # Cognitive Retrieval Fields
            custom_metadata["concepts"] = concepts
            custom_metadata["surfaces_when"] = surfaces_when
            custom_metadata["recall_cues"] = recall_cues
            custom_metadata["authority_score"] = authority_score
            custom_metadata["elefante_source"] = source_context
            
            memory_metadata = MemoryMetadata(
                memory_type=MemoryType(memory_type),
                status=status,
                conflict_ids=(
                    explicit_conflict_ids
                    if explicit_conflict_ids
                    else [related_id]
                    if status == MemoryStatus.CONTRADICTORY and related_id
                    else []
                ),
                tags=tags or [],
                domain=DomainType(domain) if domain else DomainType.REFERENCE,
                category=category,
                confidence=confidence,
                source=SourceType(source),
                project=metadata.get("project") or None,
                workspace=metadata.get("workspace") or None,
                retention_policy=metadata.get(
                    "retention_policy", RetentionPolicy.MANAGED
                ),
                injection_policy=metadata.get(
                    "injection_policy", InjectionPolicy.RANKED
                ),
                scope=metadata.get("scope") or None,
                trigger=metadata.get("trigger") or [],
                user_locked=bool(metadata.get("user_locked", False)),
                # Cognitive retrieval fields
                concepts=concepts,
                surfaces_when=surfaces_when,
                recall_cues=recall_cues,
                authority_score=authority_score,
                custom_metadata=custom_metadata,
                system_metadata=system_metadata,
                summary=summary_text,
                # ==================================================================================
                # STEP 4: REINFORCE (Plasticity & Decay)
                # ==================================================================================
                access_count=1,          # Initialize 'used once' (creation counts as use)
                last_accessed=datetime.utcnow(),
                decay_rate=decay_rate    # From TYPE_DECAY_RATES
            )
            
            memory = Memory(
                id=memory_id or uuid4(),
                content=content,
                metadata=memory_metadata,
                embedding=embedding
            )
            
            # Persist to Vector DB
            await self.vector_store.add_memory(memory)
            
            # ==================================================================================
            # STEP 5: GRAPH LINKS (Entities & Relationships)
            # ==================================================================================
            
            # 5a. Create Memory Node
            entity_name = title if title and "Memory" not in title else f"memory_{memory.id}"
            
            memory_entity = Entity(
                id=memory.id,
                name=entity_name,
                type=EntityType.MEMORY,
                description=summary_text,
                created_at=memory.metadata.created_at,
                properties={
                    "content": content[:200],
                    "memory_type": memory_type,
                    "score": memory.metadata.score,
                    "status": status.value,
                    "timestamp": memory.metadata.created_at,
                    "processing_status": ProcessingStatus.RAW,
                }
            )
            await self.graph_store.create_entity(memory_entity)
            await self.graph_store.record_memory_source(memory.id, source_context)
            
            # 5b. Link to Contradiction/Redundancy
            relationship_targets = (
                explicit_conflict_ids if explicit_conflict_ids else [related_id] if related_id else []
            )
            for relationship_target in relationship_targets:
                rel_type = RelationshipType.RELATES_TO
                props = {
                    "similarity": (
                        float(similar_memories[0].score)
                        if similar_memories
                        else 1.0
                    )
                }
                
                if status == MemoryStatus.REDUNDANT:
                    rel_type = RelationshipType.SIMILAR_TO
                elif status == MemoryStatus.CONTRADICTORY:
                    rel_type = RelationshipType.CONTRADICTS
                    props["resolved"] = False
                
                await self.graph_store.create_relationship(Relationship(
                    from_entity_id=memory.id,
                    to_entity_id=relationship_target,
                    relationship_type=rel_type,
                    properties=props
                ))
            
            # 5c. Link to Provided Entities
            if entities:
                for entity_data in entities:
                    ent_name = entity_data.get("name")
                    ent_type = entity_data.get("type", "concept")
                    
                    if ent_name:
                         # Create/Get Entity
                        linked_entity = Entity(
                            name=ent_name,
                            type=EntityType(ent_type) if ent_type in EntityType.__members__ else EntityType.CONCEPT,
                            properties={}
                        )
                        await self.graph_store.create_or_get_entity(linked_entity)
                        
                        # Link Memory -> Entity
                        await self.graph_store.create_relationship(Relationship(
                            from_entity_id=memory.id,
                            to_entity_id=linked_entity.id,
                            relationship_type=RelationshipType.RELATES_TO
                        ))
            
            # 5d. Link to Concepts
            # Creates shared Concept nodes for memory clustering
            if concepts and isinstance(concepts, list) and len(concepts) > 0:
                try:
                    edges_created = await self.graph_store.link_memory_to_concepts(
                        memory_id=memory.id,
                        concepts=concepts
                    )
                    if edges_created > 0:
                        self.logger.debug(f"Linked memory {memory.id} to {edges_created} concepts")
                except Exception as e:
                    self.logger.warning(f"Failed to link concepts: {e}")
            
            if memory.metadata.session_id:
                session_id = str(memory.metadata.session_id)
                now_iso = datetime.utcnow().isoformat()
                
                # Use MERGE to create or update Session entity with stats
                session_cypher = f"""
                MERGE (s:Entity {{id: '{session_id}'}})
                ON CREATE SET 
                    s.name = 'Session {session_id[:8]}',
                    s.type = '{EntityType.SESSION.value}',
                    s.created_at = '{now_iso}',
                    s.last_active = '{now_iso}',
                    s.interaction_count = 1,
                    s.source = 'mcp'
                ON MATCH SET 
                    s.last_active = '{now_iso}',
                    s.interaction_count = s.interaction_count + 1
                RETURN s
                """
                try:
                    # We execute raw cypher here because create_entity doesn't support MERGE/ON MATCH yet
                    await self.graph_store.execute_query(session_cypher)
                    
                    # Link Memory -> Session (CREATED_IN)
                    session_rel = Relationship(
                        from_entity_id=memory_entity.id,
                        to_entity_id=UUID(session_id),
                        relationship_type=RelationshipType.CREATED_IN,
                        properties={"created_at": datetime.utcnow()}
                    )
                    await self.graph_store.create_relationship(session_rel)
                    self.logger.debug(f"Linked memory {memory.id} to Session {session_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to update Session entity: {e}") 

            self.logger.info(f"Memory stored successfully: {memory.id} [{memory_type}]")
            return memory
            
        except Exception as e:
            self.logger.error(f"Failed to store memory: {e}", exc_info=True)
            raise
    
    @staticmethod
    def _matches_explicit_scope(memory: Memory, filters: SearchFilters | None) -> bool:
        """Enforce explicit project filters after every retrieval branch.

        Vector backends already filter these fields, but structured graph and
        merged paths may not.  A hard post-merge gate prevents an unscoped or
        cross-project graph hit from bypassing strict project isolation.
        """
        if filters is None:
            return True
        metadata = memory.metadata
        if filters.project is not None and str(metadata.project or "") != str(
            filters.project
        ):
            return False
        if filters.workspace is not None and str(metadata.workspace or "") != str(
            filters.workspace
        ):
            return False
        return True

    async def search_memories(
        self,
        query: str,
        mode: QueryMode = QueryMode.HYBRID,
        limit: int = 10,
        filters: Optional[SearchFilters] = None,
        min_similarity: float = 0.3,
        # NEW: Conversation context parameters
        include_conversation: bool = True,
        include_stored: bool = True,
        session_id: Optional[UUID] = None,
        return_debug: bool = False,
        apply_temporal_decay: bool = True,
        reinforce_access: bool = False,
        recent_memory_ids: Optional[list[str]] = None,
        surface_context: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search memories using semantic, structured, and/or conversation context with temporal decay
        
        This implements enhanced hybrid search with conversation awareness and adaptive memory strength:
        - SEMANTIC: Vector similarity search only
        - STRUCTURED: Graph traversal only
        - HYBRID: Combined search with weighted scoring
        - CONVERSATION: Recent session messages (when session_id provided)
        - TEMPORAL DECAY: Adaptive memory strength based on recency and access patterns
        
        Args:
            query: Search query string
            mode: Search mode (semantic, structured, hybrid)
            limit: Maximum number of results
            filters: Optional search filters
            min_similarity: Minimum similarity threshold (0.0-1.0)
            include_conversation: Include conversation context in search
            include_stored: Include stored memories in search
            session_id: Session UUID for conversation context
            return_debug: Return debug statistics with results
            apply_temporal_decay: Apply temporal strength scoring (default: True)
            reinforce_access: Record explicit memory use after retrieval (default: False).
                Retrieval is exposure; callers must opt in only after confirming that
                returned memories informed a task.
            surface_context: Optional file, terminal-error, or conversation context
                used for explicit literal-trigger surfacing. When omitted, the query
                itself is used. This path is read-only and only considers memories
                explicitly marked ``injection_policy=triggered``.
            
        Returns:
            List[SearchResult]: Ranked search results
        """
        validate_memory_content(query, min_length=1, max_length=1000)
        if surface_context is not None:
            validate_memory_content(surface_context, min_length=1, max_length=1000)

        # Extract conversation settings from filters if provided
        if filters:
            include_conversation = filters.include_conversation if filters.include_conversation is not None else include_conversation
            include_stored = filters.include_stored if filters.include_stored is not None else include_stored
            session_id = filters.session_id if filters.session_id else session_id
        
        self.logger.info(
            "Searching memories (enhanced)",
            query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            mode=mode.value,
            limit=limit,
            include_conversation=include_conversation,
            include_stored=include_stored,
            has_session=session_id is not None
        )
        
        try:
            # Create query plan
            plan = self._create_query_plan(query, mode, limit, filters, min_similarity)
            
            # Execute searches based on flags
            results = []
            
            if include_stored:
                # Execute traditional search (semantic/structured/hybrid) with temporal decay
                if mode == QueryMode.SEMANTIC:
                    stored_results = await self._search_semantic(
                        query,
                        plan,
                        filters,
                        apply_temporal_decay,
                        reinforce_access,
                    )
                elif mode == QueryMode.STRUCTURED:
                    stored_results = await self._search_structured(
                        query,
                        plan,
                        apply_temporal_decay,
                        reinforce_access,
                    )
                else:  # HYBRID
                    stored_results = await self._search_hybrid(
                        query,
                        plan,
                        filters,
                        apply_temporal_decay,
                        reinforce_access,
                    )
                results.extend(stored_results)
            
            if include_conversation and session_id:
                # Execute conversation context search
                conversation_results = await self._search_conversation(query, session_id, limit)
                results.extend(conversation_results)
            
            # Merge, normalize, and deduplicate results
            if include_conversation and include_stored and session_id:
                results = await self._merge_and_deduplicate(results, query, session_id is not None, mode.value)

            # An explicitly triggered memory may be useful even when its body
            # is not semantically close enough to survive the vector threshold.
            # Scan only the bounded literal-trigger path, keep it read-only, and
            # merge the explanation into an existing hit instead of creating a
            # second result for the same memory.
            if include_stored:
                triggered_results = await self._surface_triggered_memories(
                    surface_context or query,
                    filters=filters,
                    limit=min(limit, SURFACE_MAX_MEMORIES),
                )
                by_memory_id = {str(result.memory.id): result for result in results}
                for triggered in triggered_results:
                    existing = by_memory_id.get(str(triggered.memory.id))
                    if existing is None:
                        results.append(triggered)
                        by_memory_id[str(triggered.memory.id)] = triggered
                    else:
                        existing.surface_matches = list(
                            dict.fromkeys(
                                [*existing.surface_matches, *triggered.surface_matches]
                            )
                        )

                # A verified customer Recall cue is a separate, project-only
                # route. It makes the question saved in Remember usable later
                # without converting the memory to literal-triggered delivery.
                cue_results = await self._surface_recall_cue_memories(
                    query,
                    filters=filters,
                    limit=min(limit, SURFACE_MAX_MEMORIES),
                )
                for cue_result in cue_results:
                    existing = by_memory_id.get(str(cue_result.memory.id))
                    if existing is None:
                        results.append(cue_result)
                        by_memory_id[str(cue_result.memory.id)] = cue_result
                    else:
                        existing.recall_cue_match = True

            # SearchFilters are a hard customer boundary, not merely a vector
            # optimization. Apply them after semantic, graph, conversation, and
            # triggered paths have merged so no branch can leak another project.
            if filters and (filters.project is not None or filters.workspace is not None):
                results = [
                    result
                    for result in results
                    if self._matches_explicit_scope(result.memory, filters)
                ]

            if include_stored:
                await self._match_recall_cue_paraphrases(query, results, filters=filters)
            
            # =============================================================
            # COGNITIVE SCORING - Multi-signal re-ranking
            # =============================================================
            if results and include_stored:
                # NEW: Pre-fetch co-activation matrix to avoid N+1 queries in sync code
                co_activation_matrix = {}
                if recent_memory_ids:
                    try:
                        for rid in recent_memory_ids[-10:]:
                            cypher = f"MATCH (a:Entity {{id: '{rid}'}})-[r:CO_ACTIVATED]-(b:Entity) RETURN b.id as target_id, r.strength as strength"
                            edges = await self.graph_store.execute_query(cypher)
                            for edge in edges:
                                target_id = str(edge.get("target_id", ""))
                                strength = float(edge.get("strength", 0.0))
                                if target_id:
                                    if target_id not in co_activation_matrix:
                                        co_activation_matrix[target_id] = {}
                                    co_activation_matrix[target_id][rid] = strength
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch co-activation matrix: {e}")
                        
                results = self._apply_cognitive_scoring(query, results, recent_memory_ids=recent_memory_ids, co_activation_matrix=co_activation_matrix)
            
            # Sort by score and limit
            results.sort(key=lambda r: r.score, reverse=True)
            results = results[:limit]
            
            self.logger.info(
                "Search completed (enhanced)",
                num_results=len(results),
                top_score=results[0].score if results else 0.0
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            raise

    async def _surface_triggered_memories(
        self,
        context: str,
        *,
        filters: Optional[SearchFilters] = None,
        limit: int = SURFACE_MAX_MEMORIES,
    ) -> List[SearchResult]:
        """Find explicitly opted-in literal-trigger memories without mutation.

        This is the narrow proactive-surfacing path.  It is deliberately not a
        second semantic retriever: only memories with
        ``injection_policy=triggered`` are considered, and a declared literal
        phrase must occur in the supplied file/error/conversation context.
        Lifecycle, scope, source-trust, and privacy gates still apply.
        """
        if not context or limit <= 0:
            return []

        from src.modules.distiller.privacy import PrivacyFilter

        matches: list[SearchResult] = []
        try:
            # The supported stores already implement bounded ``get_all``. One
            # read keeps this additive path from re-materializing the corpus on
            # every page while retaining a hard upper bound for large stores.
            memories = await self.vector_store.get_all(
                limit=SURFACE_SCAN_MAX_MEMORIES,
                offset=0,
                filters=filters,
            )
            for memory in memories[:SURFACE_SCAN_MAX_MEMORIES]:
                metadata = memory.metadata
                policy = getattr(
                    getattr(metadata, "injection_policy", None),
                    "value",
                    getattr(metadata, "injection_policy", "ranked"),
                )
                if str(policy).casefold() != InjectionPolicy.TRIGGERED.value:
                    continue
                matched = matching_triggers(metadata, context)
                if not matched:
                    continue
                status = str(
                    getattr(
                        getattr(metadata, "status", None),
                        "value",
                        getattr(metadata, "status", ""),
                    )
                ).casefold()
                if (
                    bool(getattr(metadata, "deprecated", False))
                    or bool(getattr(metadata, "archived", False))
                    or getattr(metadata, "superseded_by_id", None) is not None
                    or bool(getattr(metadata, "conflict_ids", []))
                    or status in {
                        MemoryStatus.DEPRECATED.value,
                        MemoryStatus.ARCHIVED.value,
                        MemoryStatus.CONTRADICTORY.value,
                    }
                ):
                    continue
                current_source_state = str(
                    (getattr(metadata, "custom_metadata", None) or {}).get(
                        "current_source_state", ""
                    )
                ).casefold()
                if current_source_state == "contradicted":
                    continue
                if getattr(metadata, "source_reliability", 0.0) < 0.5:
                    continue
                candidate = memory
                if filters and filters.workspace:
                    # Current-source validation mutates the inspected model
                    # with an ephemeral annotation. Keep the store-backed
                    # object untouched and share the Task Brief validator.
                    from src.core.task_intelligence import TaskBriefService

                    candidate = memory.model_copy(deep=True)
                    await asyncio.to_thread(
                        TaskBriefService._annotate_current_source,
                        candidate,
                        filters.workspace,
                    )
                    candidate_state = str(
                        (candidate.metadata.custom_metadata or {}).get(
                            "current_source_state", ""
                        )
                    ).casefold()
                    if candidate_state == "contradicted":
                        continue
                metadata = candidate.metadata
                if governance_reason(
                    metadata,
                    context,
                    project=filters.project if filters else None,
                    workspace=filters.workspace if filters else None,
                ):
                    continue
                _, redactions, _ = PrivacyFilter().scrub_payload(
                    {"content": candidate.content, "triggers": matched}
                )
                if redactions:
                    continue
                matches.append(
                    SearchResult(
                        memory=candidate,
                        score=1.0,
                        source="triggered",
                        vector_score=None,
                        surface_matches=matched,
                    )
                )
        except Exception as error:
            # Trigger surfacing is an additive enhancement.  A store that does
            # not support listing must retain its normal search behavior.
            self.logger.warning("Literal trigger surfacing unavailable: %s", error)
            return []

        matches.sort(
            key=lambda result: (
                -max((len(value) for value in result.surface_matches), default=0),
                -result.memory.metadata.source_reliability,
                -int(result.memory.metadata.verified),
                str(result.memory.id),
            )
        )
        return matches[:limit]

    async def _surface_recall_cue_memories(
        self,
        question: str,
        *,
        filters: Optional[SearchFilters] = None,
        limit: int = SURFACE_MAX_MEMORIES,
    ) -> List[SearchResult]:
        """Find an exact customer-authored Recall cue inside one project.

        This path is intentionally narrower than semantic or proactive
        retrieval: both project and workspace must be explicit, the complete
        normalized question must match, and all lifecycle, governance,
        current-source, trust, and privacy gates remain active.
        """
        if (
            not question
            or limit <= 0
            or filters is None
            or not filters.project
            or not filters.workspace
        ):
            return []

        from src.core.task_intelligence import TaskBriefService
        from src.modules.distiller.privacy import PrivacyFilter
        from src.utils.curation import matching_recall_cue

        matches: list[SearchResult] = []
        try:
            memories = await self.vector_store.get_all(
                limit=SURFACE_SCAN_MAX_MEMORIES,
                offset=0,
                filters=filters,
            )
            for stored in memories[:SURFACE_SCAN_MAX_MEMORIES]:
                if not self._matches_explicit_scope(stored, filters):
                    continue
                metadata = stored.metadata
                if not matching_recall_cue(metadata.recall_cues, question):
                    continue
                status = str(
                    getattr(
                        getattr(metadata, "status", None),
                        "value",
                        getattr(metadata, "status", ""),
                    )
                ).casefold()
                if (
                    bool(metadata.deprecated)
                    or bool(metadata.archived)
                    or metadata.superseded_by_id is not None
                    or bool(metadata.conflict_ids)
                    or status
                    in {
                        MemoryStatus.DEPRECATED.value,
                        MemoryStatus.ARCHIVED.value,
                        MemoryStatus.CONTRADICTORY.value,
                    }
                    or float(metadata.source_reliability) < 0.5
                ):
                    continue
                candidate = stored.model_copy(deep=True)
                await asyncio.to_thread(
                    TaskBriefService._annotate_current_source,
                    candidate,
                    filters.workspace,
                )
                if str(
                    (candidate.metadata.custom_metadata or {}).get(
                        "current_source_state", ""
                    )
                ).casefold() == "contradicted":
                    continue
                if governance_reason(
                    candidate.metadata,
                    question,
                    project=filters.project,
                    workspace=filters.workspace,
                ):
                    continue
                _, redactions, _ = PrivacyFilter().scrub_payload(
                    {
                        "content": candidate.content,
                        "recall_cues": candidate.metadata.recall_cues,
                    }
                )
                if redactions:
                    continue
                matches.append(
                    SearchResult(
                        memory=candidate,
                        score=1.0,
                        source="recall-cue",
                        vector_score=None,
                        recall_cue_match=True,
                    )
                )
        except Exception as error:
            self.logger.warning("Recall cue surfacing unavailable: %s", error)
            return []

        matches.sort(
            key=lambda result: (
                -result.memory.metadata.source_reliability,
                -int(result.memory.metadata.verified),
                str(result.memory.id),
            )
        )
        return matches[:limit]
    
    async def _match_recall_cue_paraphrases(
        self,
        question: str,
        candidates: List[SearchResult],
        *,
        filters: Optional[SearchFilters] = None,
    ) -> None:
        """Mark one clear paraphrase of an existing scoped Recall cue, read-only.

        Reuses the loaded local model and at most twelve retrieved memories;
        does not scan, reindex, or change the durable corpus. Exact cues keep
        their existing path. Weak or competing cue matches add no evidence.
        """
        for candidate in candidates:
            candidate.recall_cue_similarity = None
            candidate.recall_focus_similarity = None
        if (
            not question or not filters or not filters.project or not filters.workspace
            or any(item.recall_cue_match for item in candidates)
        ):
            return

        import numpy as np
        from src.core.task_intelligence import TaskBriefCompiler, TaskBriefProfile, TaskBriefRequest
        from src.modules.distiller.privacy import PrivacyFilter
        from src.utils.curation import canonicalize_recall_cues

        compiler = TaskBriefCompiler()
        request = TaskBriefRequest(
            task=question, project=filters.project, workspace=filters.workspace,
            profile=TaskBriefProfile.V2,
        )
        cue_owners: list[SearchResult] = []
        texts = [question]
        for result in candidates[:RECALL_CUE_MAX_CANDIDATES]:
            metadata = result.memory.metadata
            if (
                not self._matches_explicit_scope(result.memory, filters)
                or str(metadata.injection_policy).casefold() != InjectionPolicy.RANKED.value
                or compiler._exclusion_reason(request, result)
                or compiler._conflict(result.memory) is not None
            ):
                continue
            cues = canonicalize_recall_cues(metadata.recall_cues)
            if PrivacyFilter().scrub_payload(cues)[1]:
                continue
            texts.extend(cues)
            cue_owners.extend([result] * len(cues))
        if not cue_owners:
            return
        try:
            vectors = np.asarray(
                await self.embedding_service.generate_embeddings_batch(texts), dtype=float,
            )
            if vectors.ndim != 2 or len(vectors) != len(texts) or not np.isfinite(vectors).all():
                return
            norms = np.linalg.norm(vectors, axis=1)
            if np.any(norms == 0):
                return
            similarities = (vectors[1:] @ vectors[0]) / (norms[1:] * norms[0])
            by_memory: dict[str, tuple[float, SearchResult]] = {}
            for result, score in zip(cue_owners, similarities):
                key = str(result.memory.id)
                if key not in by_memory or score > by_memory[key][0]:
                    by_memory[key] = (float(score), result)
            ranked = sorted(by_memory.values(), key=lambda item: item[0], reverse=True)
            # A closed choice declares alternatives, not a brand, price, count
            # or other unstated property. Compare just that focused phrase.
            target = compiler._question_focus(question)
            if target and target.startswith("property:"):
                options: list[str] = []
                owners: list[SearchResult] = []
                for _, candidate in ranked:
                    if compiler._recall_cue_focus(question, candidate.memory) != "choice":
                        continue
                    for cue in canonicalize_recall_cues(candidate.memory.metadata.recall_cues):
                        focus = compiler._question_focus(cue)
                        if focus and focus.startswith("choice:"):
                            options.append(focus.partition(":")[2])
                            owners.append(candidate)
                if options:
                    focused = np.asarray(await self.embedding_service.generate_embeddings_batch(
                        [target.partition(":")[2], *options],
                    ), dtype=float)
                    if focused.ndim != 2 or len(focused) != len(options) + 1 or not np.isfinite(focused).all():
                        return
                    lengths = np.linalg.norm(focused, axis=1)
                    if np.any(lengths == 0):
                        return
                    scores = (focused[1:] @ focused[0]) / (lengths[1:] * lengths[0])
                    for owner, score in zip(owners, scores):
                        owner.recall_focus_similarity = max(owner.recall_focus_similarity or 0.0, min(1.0, float(score)))
            best, result = ranked[0]
            runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
            floor = (
                compiler.MIN_FOCUSED_CUE_SIMILARITY
                if (
                    compiler._recall_cue_focus(question, result.memory) == "same"
                    or (result.recall_focus_similarity or 0.0) >= compiler.MIN_FOCUSED_CUE_SIMILARITY
                )
                else compiler.MIN_RECALL_CUE_SIMILARITY
            )
            if best >= floor and best - runner_up >= RECALL_CUE_MIN_MARGIN:
                result.recall_cue_similarity = min(1.0, best)
        except Exception:
            # Additive evidence only. Do not log question/cue content or turn
            # an embedding failure into a different memory selection policy.
            self.logger.warning("Recall cue paraphrase comparison unavailable")

    def _create_query_plan(
        self,
        query: str,
        mode: QueryMode,
        limit: int,
        filters: Optional[SearchFilters],
        min_similarity: float
    ) -> QueryPlan:
        """
        Create execution plan for query
        
        Analyzes query to determine optimal weights and parameters
        """
        # Determine weights based on query characteristics
        if mode == QueryMode.SEMANTIC:
            vector_weight, graph_weight = 1.0, 0.0
        elif mode == QueryMode.STRUCTURED:
            vector_weight, graph_weight = 0.0, 1.0
        else:  # HYBRID
            # Analyze query to determine weights
            # Questions/concepts favor semantic, facts favor structured
            has_question = any(q in query.lower() for q in ["what", "how", "why", "when", "where", "who"])
            has_specific = any(s in query.lower() for s in ["named", "called", "id", "uuid"])
            
            if has_specific:
                vector_weight, graph_weight = 0.3, 0.7
            elif has_question:
                vector_weight, graph_weight = 0.7, 0.3
            else:
                vector_weight, graph_weight = 0.5, 0.5
        
        return QueryPlan(
            mode=mode,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            limit=limit,
            min_similarity=min_similarity,
            memory_types=[filters.memory_type] if filters and filters.memory_type else None,
            tags=filters.tags if filters else None,
            min_score=filters.min_score if filters else None,
            date_range={
                "start": filters.start_date if filters.start_date else datetime.min,
                "end": filters.end_date if filters.end_date else datetime.max
            } if filters and (filters.start_date or filters.end_date) else None
        )
    
    def _apply_cognitive_scoring(
        self,
        query: str,
        results: List[SearchResult],
        recent_memory_ids: Optional[list[str]] = None,
        co_activation_matrix: Optional[dict] = None
    ) -> List[SearchResult]:
        """
        Apply current cognitive multi-signal scoring and attach its explanation.

        Formula authority is src/core/retrieval.py; the human contract is
        docs/reference/scoring.md. Do not duplicate weights here.
        """
        if not results:
            return results
        
        # Analyze query to extract concepts, domain, intent
        query_analysis = self.cognitive_retriever.analyze_query(query)
        
        self.logger.debug(
            "Cognitive scoring",
            query_concepts=query_analysis.concepts,
            inferred_domain=query_analysis.inferred_domain,
            inferred_intent=query_analysis.inferred_intent,
            num_results=len(results)
        )
        
        # Convert each SearchResult to MemoryCandidate, score, update
        scored_results = []
        for result in results:
            memory = result.memory
            metadata = memory.metadata if memory.metadata else {}

            # Literal-trigger matches are an explicit governance signal, not a
            # vector score. Preserve that distinction in both ranking and the
            # explanation shown to the caller.
            if result.recall_cue_match:
                result.score = 1.0
                result.vector_score = None
                result.explanation = {
                    "composite_score": 1.0,
                    "signals": [
                        {
                            "name": "customer_recall_cue",
                            "score": 1.0,
                            "weight": 1.0,
                            "weighted": 1.0,
                            "reason": (
                                "Complete project-scoped customer Recall cue matched"
                            ),
                            "details": {"project_scoped": True},
                        }
                    ],
                }
                scored_results.append(result)
                continue
            if result.surface_matches:
                result.score = 1.0
                result.vector_score = None
                result.explanation = {
                    "composite_score": 1.0,
                    "signals": [
                        {
                            "name": "explicit_trigger",
                            "score": 1.0,
                            "weight": 1.0,
                            "weighted": 1.0,
                            "reason": "Configured literal surface trigger matched",
                            "details": {
                                "matched_triggers": list(result.surface_matches),
                            },
                        }
                    ],
                }
                scored_results.append(result)
                continue
            
            # Build MemoryCandidate from Memory object
            candidate = MemoryCandidate(
                id=str(memory.id),
                content=memory.content,
                title=metadata.title if hasattr(metadata, 'title') else str(memory.id)[:8],
                summary=metadata.summary if hasattr(metadata, 'summary') else memory.content[:100],
                concepts=metadata.concepts if hasattr(metadata, 'concepts') and metadata.concepts else [],
                domain=metadata.domain.value if hasattr(metadata, 'domain') and metadata.domain and hasattr(metadata.domain, 'value') else (metadata.domain if hasattr(metadata, 'domain') and isinstance(metadata.domain, str) else "general"),
                score=metadata.score if hasattr(metadata, 'score') else 100,
                access_count=metadata.access_count if hasattr(metadata, 'access_count') else 1,
                created_at=metadata.created_at if hasattr(metadata, 'created_at') and metadata.created_at else datetime.utcnow(),
                last_accessed=metadata.last_accessed if hasattr(metadata, 'last_accessed') and metadata.last_accessed else datetime.utcnow(),
                vector_score=result.score,  # Original vector similarity score
                memory_type=metadata.memory_type.value if hasattr(metadata, 'memory_type') and hasattr(metadata.memory_type, "value") else getattr(metadata, "memory_type", "fact"),
            )
            
            # Score candidate and get explanation
            scored_candidate, explanation = self.cognitive_retriever.score_candidate(
                candidate,
                query_analysis,
                recent_memory_ids=recent_memory_ids or [],
                include_explanation=True,
                co_activation_matrix=co_activation_matrix
            )
            
            # Preserve original vector_score, update score with composite
            result.vector_score = result.score
            result.score = scored_candidate.composite_score
            
            # Attach explanation to result
            if explanation:
                result.explanation = explanation.to_dict()
            
            # Log score breakdown for debugging
            self.logger.debug(
                "Scored memory",
                memory_id=str(memory.id)[:8],
                vector=f"{scored_candidate.vector_score:.3f}",
                concept=f"{scored_candidate.concept_score:.3f}",
                domain=f"{scored_candidate.domain_score:.3f}",
                authority=f"{scored_candidate.authority_score:.3f}",
                composite=f"{scored_candidate.composite_score:.3f}"
            )
            
            scored_results.append(result)
        
        return scored_results
    
    async def record_coactivation(self, memory_ids: list[str]) -> None:
        """
        Record co-activations for an explicitly acknowledged use event.

        Retrieval results alone must never call this method.  The caller must
        first establish that the selected memories informed the task.
        """
        if not memory_ids or len(memory_ids) < 2:
            return
            
        try:
            # Validate that IDs still exist in the configured vector store before
            # burning O(n^2) graph co-activation work.
            # graph queries.  Deleted/stale IDs are silently dropped.
            valid_ids = []
            for mid in set(memory_ids):
                try:
                    mem = await self.vector_store.get_memory(UUID(mid))
                    if mem is not None:
                        valid_ids.append(mid)
                except Exception:
                    pass  # skip invalid/missing

            if len(valid_ids) < 2:
                return

            import itertools
            pairs = list(itertools.combinations(valid_ids, 2))
            
            for m1, m2 in pairs:
                # Merge the undirected (or bidirectional) relationship
                cypher = f"""
                MATCH (a:Entity {{id: '{m1}'}}), (b:Entity {{id: '{m2}'}})
                MERGE (a)-[r:CO_ACTIVATED]->(b)
                ON CREATE SET r.strength = 1.0, r.last_coactivated = '{datetime.utcnow().isoformat()}'
                ON MATCH SET r.strength = r.strength + 0.1, r.last_coactivated = '{datetime.utcnow().isoformat()}'
                """
                await self.graph_store.execute_query(cypher)
                
            self.logger.debug(f"Recorded co-activations for {len(pairs)} memory pairs.")
        except Exception as e:
            self.logger.warning(f"Failed to record explicit-use graph co-activations: {e}")
    
    async def _search_semantic(
        self,
        query: str,
        plan: QueryPlan,
        filters: Optional[SearchFilters] = None,
        apply_temporal_decay: bool = True,
        reinforce_access: bool = True,
    ) -> List[SearchResult]:
        """Execute semantic search via vector store with optional temporal decay.

        Uses metadata-filtered federated search to prevent core/domain memories from being
        drowned out by leaf noise.
        """
        # Build metadata filters
        metadata_filter = {}
        if plan.memory_types:
            metadata_filter["memory_type"] = plan.memory_types
        if plan.tags:
            metadata_filter["tags"] = {"$in": plan.tags}
        if plan.min_score:
            metadata_filter["score"] = {"$gte": plan.min_score}

        # Standard search (no federated anchor split — behavioral relevance
        # handles ranking via temporal decay + reinforcement).
        general_fetch = max(plan.limit * 3, 10)

        results = await self.vector_store.search(
            query=query,
            limit=general_fetch,
            filters=filters,
            min_similarity=plan.min_similarity,
            apply_temporal_decay=apply_temporal_decay,
        )

        merged = results[:plan.limit]

        if apply_temporal_decay and reinforce_access:
            for result in merged:
                result.memory.record_access()
                await self.vector_store.update_memory_access(result.memory)

        return merged
    
    async def _search_structured(
        self,
        query: str,
        plan: QueryPlan,
        apply_temporal_decay: bool = True,
        reinforce_access: bool = True,
    ) -> List[SearchResult]:
        """Execute structured search via graph store with optional temporal decay"""
        # Build Cypher query based on filters
        # Note: Entity node stores score in JSON 'props', not as a direct column
        cypher_parts = ["MATCH (m:Entity {type: 'memory'})"]
        where_clauses = []
        
        if plan.memory_types:
            where_clauses.append(f"m.memory_type IN {plan.memory_types}")
        
        if where_clauses:
            cypher_parts.append("WHERE " + " AND ".join(where_clauses))
        
        cypher_parts.append(f"RETURN m LIMIT {plan.limit}")
        cypher_query = " ".join(cypher_parts)
        
        # Execute query
        graph_results = await self.graph_store.execute_query(cypher_query)
        
        # Convert to SearchResult objects
        # Note: Graph results don't have similarity scores, so we use score as a proxy.
        import json

        results: List[SearchResult] = []
        for row in graph_results:
            entity = row.get("m")
            if not entity:
                continue

            # Kuzu may return a Node-like object (with `.properties`) or a plain dict.
            entity_props: Dict[str, Any]
            if hasattr(entity, "properties"):
                entity_props = getattr(entity, "properties")
            elif isinstance(entity, dict):
                entity_props = entity
            else:
                entity_props = {}

            raw_props = entity_props.get("props")
            extra: Dict[str, Any] = {}
            if isinstance(raw_props, str) and raw_props.strip():
                try:
                    extra = json.loads(raw_props)
                except Exception:
                    extra = {}

            memory_id_value = entity_props.get("id") or extra.get("memory_id")
            memory_id: Optional[UUID] = None
            try:
                if isinstance(memory_id_value, str) and memory_id_value:
                    memory_id = UUID(memory_id_value)
            except Exception:
                memory_id = None

            # Try to load the authoritative Memory from the vector store when possible.
            memory: Optional[Memory] = None
            vector_backed = False
            if memory_id is not None:
                memory = await self.vector_store.get_memory(memory_id)
                vector_backed = memory is not None

            score_val = extra.get("score")
            if score_val is None:
                score_val = extra.get("importance")  # Backward compat
            if score_val is None:
                score_val = entity_props.get("score") or entity_props.get("importance")
            try:
                score_int = int(score_val) if score_val is not None else 100
            except Exception:
                score_int = 100

            score = max(0.0, min(1.0, score_int / 100.0))

            if memory is None:
                # Fallback: construct a minimal Memory object from graph metadata.
                memory_type_str = extra.get("memory_type") or entity_props.get("memory_type") or "conversation"
                try:
                    mem_type = MemoryType(memory_type_str)
                except Exception:
                    mem_type = MemoryType.CONVERSATION

                memory_metadata = MemoryMetadata(
                    memory_type=mem_type,
                    score=score_int,
                )

                memory = Memory(
                    id=memory_id or uuid4(),
                    content=extra.get("content") or entity_props.get("description") or "",
                    metadata=memory_metadata,
                )

            # Mark whether this result is backed by an actual vector-store record.
            try:
                memory.metadata.custom_metadata["_vector_backed"] = vector_backed
            except Exception:
                pass

            results.append(
                SearchResult(
                    memory=memory,
                    score=score,
                    source="graph",
                    vector_score=None,
                    graph_score=score,
                )
            )
        
        # Apply Temporal Decay & Reinforcement (Read-Side Plasticity)
        if apply_temporal_decay:
            for result in results:
                # Calculate temporal score (even if just based on current time for graph results)
                current_time = datetime.utcnow()
                temporal_score = result.memory.calculate_relevance_score(current_time)
                
                # Blend with graph score
                # Config defaults: semantic=0.7, temporal=0.3
                # For graph, we treat score as the "semantic" signal
                semantic_weight = 0.7 
                temporal_weight = 0.3
                
                # Re-calculate score
                result.score = (semantic_weight * result.score) + (temporal_weight * temporal_score)
                result.score = max(0.0, min(1.0, result.score))
                
                if reinforce_access and getattr(result.memory.metadata, "custom_metadata", {}).get("_vector_backed"):
                    result.memory.record_access()
                    await self.vector_store.update_memory_access(result.memory)
                
            # Re-sort after decay application
            results.sort(key=lambda r: r.score, reverse=True)

        return results
    
    async def _search_hybrid(
        self,
        query: str,
        plan: QueryPlan,
        filters: Optional[SearchFilters] = None,
        apply_temporal_decay: bool = True,
        reinforce_access: bool = True,
    ) -> List[SearchResult]:
        """
        Execute hybrid search combining vector and graph results with temporal decay
        
        This is the most powerful search mode:
        1. Run semantic and structured searches in parallel
        2. Merge results by memory ID
        3. Calculate weighted scores (including temporal strength)
        4. Deduplicate and rank
        """
        # Execute both searches in parallel with temporal decay.
        # Reinforcement is deferred until after merge to avoid double increments.
        semantic_task = self._search_semantic(
            query,
            plan,
            filters,
            apply_temporal_decay,
            reinforce_access=False,
        )
        structured_task = self._search_structured(
            query,
            plan,
            apply_temporal_decay,
            reinforce_access=False,
        )
        
        semantic_results, structured_results = await asyncio.gather(
            semantic_task,
            structured_task,
            return_exceptions=True
        )
        
        # Handle exceptions and ensure we have lists
        if isinstance(semantic_results, Exception):
            self.logger.warning(f"Semantic search failed: {semantic_results}")
            semantic_results = []
        elif not isinstance(semantic_results, list):
            semantic_results = []
            
        if isinstance(structured_results, Exception):
            self.logger.warning(f"Structured search failed: {structured_results}")
            structured_results = []
        elif not isinstance(structured_results, list):
            structured_results = []
        
        # Merge results by memory ID
        merged: Dict[UUID, SearchResult] = {}
        
        # Add semantic results
        for result in semantic_results:
            merged[result.memory.id] = result
        
        # Merge with structured results
        for result in structured_results:
            memory_id = result.memory.id
            if memory_id in merged:
                # Combine scores with weights
                existing = merged[memory_id]
                combined_score = (
                    (existing.vector_score or 0) * plan.vector_weight +
                    (result.graph_score or 0) * plan.graph_weight
                )
                
                # Update result
                existing.score = combined_score
                existing.source = "hybrid"
                existing.graph_score = result.graph_score
            else:
                # Add new result with weighted score
                result.score = (result.graph_score or 0) * plan.graph_weight
                result.source = "hybrid"
                merged[memory_id] = result
        
        merged_results = list(merged.values())

        if apply_temporal_decay and reinforce_access:
            for result in merged_results:
                is_vector_backed_graph = (
                    result.source == "graph"
                    and getattr(result.memory.metadata, "custom_metadata", {}).get("_vector_backed")
                )
                if result.source in {"semantic", "hybrid"} or is_vector_backed_graph:
                    result.memory.record_access()
                    await self.vector_store.update_memory_access(result.memory)

        return merged_results
    
    async def _search_conversation(
        self,
        query: str,
        session_id: UUID,
        limit: int
    ) -> List[SearchResult]:
        """
        Search conversation context for relevant messages
        
        Args:
            query: Search query
            session_id: Session UUID
            limit: Maximum results
            
        Returns:
            List of SearchResult objects from conversation
        """
        from src.core.conversation_context import get_conversation_searcher
        try:
            searcher = get_conversation_searcher()
            candidates = await searcher.collect_candidates(query, session_id, limit)
            
            # Convert SearchCandidates to SearchResults
            results = []
            for candidate in candidates:
                # Create a minimal Memory object for the result
                from src.models.memory import Memory, MemoryMetadata, MemoryType
                
                memory_metadata = MemoryMetadata(
                    memory_type=MemoryType.CONVERSATION,
                    source=SourceType.CONVERSATION,
                    session_id=session_id
                )
                
                memory = Memory(
                    id=candidate.memory_id if candidate.memory_id else uuid4(),
                    content=candidate.text,
                    metadata=memory_metadata
                )
                
                result = SearchResult(
                    memory=memory,
                    score=candidate.score,
                    source="conversation",
                    vector_score=None,
                    graph_score=None
                )
                
                results.append(result)
            
            self.logger.debug(
                "Conversation search completed",
                session_id=str(session_id),
                count=len(results)
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Conversation search failed: {e}", exc_info=True)
            return []
    
    async def _merge_and_deduplicate(
        self,
        results: List[SearchResult],
        query: str,
        has_session: bool,
        mode: str
    ) -> List[SearchResult]:
        """
        Merge results from multiple sources and remove duplicates
        
        Args:
            results: Combined results from all sources
            query: Original search query
            has_session: Whether session context was used
            mode: Search mode
            
        Returns:
            Deduplicated and normalized results
        """
        from src.core.scoring import ScoreNormalizer
        from src.core.deduplication import get_deduplicator
        from src.models.conversation import SearchCandidate
        
        try:
            # Convert SearchResults to SearchCandidates for processing
            candidates = []
            for result in results:
                candidate = SearchCandidate(
                    text=result.memory.content,
                    score=result.score,
                    source=result.source,
                    metadata={
                        "memory_id": str(result.memory.id),
                        "timestamp": result.memory.metadata.created_at.isoformat(),
                        "memory_type": result.memory.metadata.memory_type.value
                    },
                    embedding=result.memory.embedding,
                    memory_id=result.memory.id
                )
                candidates.append(candidate)
            
            # Calculate adaptive weights
            weights = ScoreNormalizer.adaptive_weights(query, has_session, mode)
            
            # Normalize scores
            candidates = ScoreNormalizer.normalize_scores(candidates, weights)
            
            # Deduplicate
            deduplicator = get_deduplicator(threshold=0.95)
            candidates = await deduplicator.deduplicate(candidates)
            
            # Convert back to SearchResults
            final_results = []
            for candidate in candidates:
                # Find original result to preserve full memory object
                original = next(
                    (r for r in results if r.memory.id == candidate.memory_id),
                    None
                )
                
                if original:
                    # Update score with normalized value
                    original.score = candidate.score
                    # Update source if merged
                    if "sources" in candidate.metadata:
                        original.source = "hybrid"
                    final_results.append(original)
            
            self.logger.debug(
                "Merge and deduplication completed",
                original_count=len(results),
                final_count=len(final_results),
                weights=weights
            )
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"Merge and deduplication failed: {e}", exc_info=True)
            # Return original results if processing fails
            return results
    
    async def get_context(
        self,
        session_id: Optional[UUID] = None,
        depth: int = 2,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieve full context for a session or task
        
        This assembles a comprehensive context by:
        1. Finding all memories in the session
        2. Traversing relationships to depth N
        3. Collecting related entities and facts
        
        Args:
            session_id: Optional session UUID to filter by
            depth: Relationship traversal depth (1-5)
            limit: Maximum memories to retrieve
            
        Returns:
            Dict containing memories, entities, and relationships
        """
        self.logger.info(
            "Retrieving context",
            session_id=str(session_id) if session_id else None,
            depth=depth,
            limit=limit
        )
        
        try:
            context = {
                "memories": [],
                "entities": [],
                "relationships": [],
                "stats": {}
            }
            
            # Build query for session memories
            memory_ids = []
            if session_id:
                validate_uuid(str(session_id))
                    
            else:
                # AUTHORITATIVE: Use recursive traversal based on depth
                # Determine anchor points. If no session, rely on recency (flat) or relevant entities
                
                if session_id:
                     # Start from Session entity and traverse out
                     cypher = f"""
                     MATCH (s:Entity {{id: '{session_id}'}})-[r*1..{depth}]-(m:Entity)
                     WHERE m.type = 'memory' OR m.type = 'fact' OR m.type = 'person'
                     RETURN m, r
                     LIMIT {limit}
                     """
                else:
                    # Fallback to recent memories if no session anchor
                    # But we can still find their related entities up to depth
                    cypher = f"""
                    MATCH (m:Entity {{type: 'memory'}})
                    WITH m
                    ORDER BY m.created_at DESC
                    LIMIT 10
                    MATCH (m)-[r*1..{depth}]-(related:Entity)
                    RETURN m, related, r
                    LIMIT {limit}
                    """
            
                # Get memories/entities from graph
                try:
                    results = await self.graph_store.execute_query(cypher)
                    
                    for row in results:
                         # Handle Kuzu results which can be complex with var-length paths
                         # We'll flatten the results
                        
                        entities_to_process = []
                        if session_id:
                            # pattern: m, r (where r is list of rels, m is node)
                            # Actually Kuzu might return individual rows for paths
                            if "m" in row:
                                entities_to_process.append(row["m"])
                        else:
                            if "m" in row:
                                entities_to_process.append(row["m"])
                            if "related" in row:
                                entities_to_process.append(row["related"])
                            
                        for entity in entities_to_process:
                            # Skip if already added
                            e_id = entity.get('id') if isinstance(entity, dict) else getattr(entity, 'id', None)
                            if not e_id or str(e_id) in [e["id"] for e in context["entities"]]:
                                continue
                                
                            # Safe property extraction
                            props = {}
                            if hasattr(entity, 'get') and entity.get('properties'):
                                try:
                                    props = json.loads(entity.get('properties'))
                                except (TypeError, ValueError):
                                    props = {}
                            elif isinstance(entity, dict) and 'properties' in entity and isinstance(entity['properties'], str):
                                try:
                                    props = json.loads(entity['properties'])
                                except (TypeError, ValueError):
                                    pass
                            
                            # Add to context
                            context["entities"].append({
                                "id": str(e_id),
                                "name": entity.get('name'),
                                "type": entity.get('type'),
                                "properties": props
                            })
                            
                            if entity.get('type') == 'memory':
                                memory_ids.append(e_id)
                                
                except Exception as e:
                     self.logger.warning(f"Recursive graph traversal failed: {e}. Falling back to flat search.")
                     # Fallback code
                     fallback_cypher = f"MATCH (m:Entity {{type: 'memory'}}) RETURN m ORDER BY m.created_at DESC LIMIT {limit}"
                     results = await self.graph_store.execute_query(fallback_cypher)
                     # (Simple processing for fallback - minimal implementation to prevent crash)
                     for row in results:
                         m = row.get("m")
                         if m:
                             memory_ids.append(m.get("id"))
                             context["entities"].append({"id": str(m.get("id")), "type": "memory", "name": m.get("name")})

            
            # [NEW] Fetch User Profile Context
            # Always try to find the "User" entity and its direct facts (location, role, preferences)
            try:
                user_name = self.config.elefante.user_profile.user_name
                user_cypher = f"""
                MATCH (u:Entity {{name: '{user_name}'}})-[r]-(fact:Entity)
                RETURN u, r, fact
                LIMIT 20
                """
                user_results = await self.graph_store.execute_query(user_cypher)
                for row in user_results:
                    # GraphStore returns {"values": [u, r, fact]}
                    u_entity = row["values"][0]
                    rel = row["values"][1]
                    fact = row["values"][2]
                    
                    # Handle Kuzu dictionary results
                    u_id = u_entity.get('id')
                    if u_id and u_id not in [e["id"] for e in context["entities"]]:
                        u_props = {k: v for k, v in u_entity.items() 
                                 if k not in ['id', 'name', 'type', '_id', '_label']}
                        context["entities"].append({
                            "id": str(u_id),
                            "name": u_entity.get('name'),
                            "type": u_entity.get('type'),
                            "properties": u_props,
                            "is_user_profile": True
                        })

                    fact_id = fact.get('id')
                    if fact_id and fact_id not in [e["id"] for e in context["entities"]]:
                        # Extract properties (exclude internal/standard fields)
                        fact_props = {k: v for k, v in fact.items() 
                                    if k not in ['id', 'name', 'type', '_id', '_label']}
                        
                        context["entities"].append({
                            "id": str(fact_id),
                            "name": fact.get('name'),
                            "type": fact.get('type'),
                            "properties": fact_props,
                            "is_user_fact": True  # Flag for client to prioritize
                        })
                        
                        rel_props = {k: v for k, v in rel.items() 
                                   if k not in ['_id', '_src', '_dst', '_label']}
                        
                        context["relationships"].append({
                            "from": str(u_entity.get('id')),
                            "to": str(fact_id),
                            "type": rel.get('_label'), # Kuzu uses _label for relationship type
                            "properties": rel_props
                        })
            except Exception as e:
                self.logger.warning(f"Failed to fetch User Profile context: {e}")

            # Get full memory content from vector store
            for memory_id in memory_ids:
                try:
                    memory = await self.vector_store.get_memory(memory_id)
                    if memory:
                        context["memories"].append(memory.to_dict())
                except Exception as e:
                    self.logger.warning(f"Failed to fetch memory {memory_id}: {e}")
            
                    # Traverse relationships to specified depth
            if memory_ids and depth > 0:
                for memory_id in memory_ids:
                    # Build Cypher query to find related entities
                    cypher = f"""
                    MATCH (m:Entity {{id: '{memory_id}'}})-[*1..{depth}]-(related:Entity)
                    WHERE related.id <> '{memory_id}'
                    RETURN DISTINCT related
                    LIMIT 50
                    """
                    try:
                        related_results = await self.graph_store.execute_query(cypher)
                        for row in related_results:
                            entity = row.get("related")
                            if entity:
                                # Handle dict vs object for ID
                                e_id = entity.get('id') if isinstance(entity, dict) else getattr(entity, 'id', None)
                                e_name = entity.get('name') if isinstance(entity, dict) else getattr(entity, 'name', None)
                                e_type = entity.get('type') if isinstance(entity, dict) else getattr(entity, 'type', None)
                                
                                # Handle properties
                                props = {}
                                if isinstance(entity, dict):
                                    p_str = entity.get('properties')
                                    if isinstance(p_str, str):
                                        try:
                                            props = json.loads(p_str)
                                        except (TypeError, ValueError):
                                            pass
                                else:
                                    p_str = getattr(entity, 'properties', None)
                                    if isinstance(p_str, str):
                                        try:
                                            props = json.loads(p_str)
                                        except (TypeError, ValueError):
                                            pass
                                            
                                if e_id and str(e_id) not in [e["id"] for e in context["entities"]]:
                                    context["entities"].append({
                                        "id": str(e_id),
                                        "name": e_name,
                                        "type": e_type,
                                        "properties": props
                                    })
                    except Exception as e:
                        self.logger.warning(f"Failed to traverse relationships for {memory_id}: {e}")
            
            # Add stats
            context["stats"] = {
                "num_memories": len(context["memories"]),
                "num_entities": len(context["entities"]),
                "depth": depth,
                "session_id": str(session_id) if session_id else None
            }
            
            self.logger.info(
                "Context retrieved",
                num_memories=context["stats"]["num_memories"],
                num_entities=context["stats"]["num_entities"]
            )
            
            return context
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve context: {e}", exc_info=True)
            raise

    def _detect_contradiction(self, new_content: str, existing_content: str) -> bool:
        """
        Backward-compatible boolean facade over the pure conflict assessment.

        Callers that need an explanation should use ``assess_conflict``
        directly.  This method intentionally cannot mutate either memory.
        """
        return assess_conflict(
            new_content,
            existing_content,
        ).outcome is ConflictOutcome.CONFLICT

    def _is_first_person_statement(self, content: str) -> bool:
        """
        Check if content contains first-person statements using robust regex.
        Avoids false positives from code (e.g., 'i = 0', 'my_var').
        """
        if not self.config.elefante.user_profile.auto_link_first_person:
            return False
            
        # 1. Check if it looks like code (simple heuristic)
        if self.config.elefante.user_profile.detect_code_blocks:
            # Strong heuristic: Starts with code keyword
            if any(content.strip().startswith(k) for k in ['return ', 'import ', 'def ', 'class ', 'for ', 'if ', 'async ', 'await ', 'try:', 'except', 'else', 'elif']):
                return False

            # If it has many code-like symbols, skip
            code_symbols = [
                '{', '}', 'def ', 'class ', 'return ', 'import ', ' = ', '(', ')', 
                'for ', 'if ', 'else', 'elif', 'try:', 'except', 'in ', 'range', 
                'print', '->', '[', ']', ':', 'await ', 'async '
            ]
            if sum(1 for s in code_symbols if s in content) >= 2:  # Lowered threshold to 2 for safety
                return False
        
        # 2. Regex for natural language first-person pronouns
        # \b ensures word boundaries
        # Case insensitive
        # Negative lookahead/behind to avoid variable names like my_var, i_index
        
        # Patterns:
        # "I " (but not "i =")
        # "my " (but not "my_")
        # "me", "we", "our", "mine"
        
        patterns = [
            r'\bI\b(?!\s*=)',  # "I" but not followed by "="
            r'\b(my|me|we|our|mine)\b(?!_)'  # pronouns not followed by underscore
        ]
        
        combined_pattern = '|'.join(patterns)
        return bool(re.search(combined_pattern, content, re.IGNORECASE))
    
    async def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Entity:
        """
        Create a new entity in the knowledge graph
        
        Args:
            name: Entity name
            entity_type: Entity type (person, project, file, concept, etc.)
            properties: Additional properties
            
        Returns:
            Entity: Created entity
        """
        # Parse entity type (STRICT)
        parsed_type = EntityType(entity_type)
        
        entity = Entity(
            name=name,
            type=parsed_type,
            properties=properties or {}
        )
        
        # Use idempotent creation (MERGE behavior)
        await self.graph_store.create_or_get_entity(entity)
        self.logger.info(f"Entity created/retrieved: {name} ({entity_type})")
        
        return entity
    
    async def create_relationship(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Relationship:
        """
        Create a relationship between entities
        
        Args:
            from_entity_id: Source entity UUID
            to_entity_id: Target entity UUID
            relationship_type: Type of relationship
            properties: Additional properties
            
        Returns:
            Relationship: Created relationship
        """
        # Parse relationship type (STRICT)
        parsed_rel_type = RelationshipType(relationship_type)
        
        relationship = Relationship(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relationship_type=parsed_rel_type,
            properties=properties or {}
        )
        
        await self.graph_store.create_relationship(relationship)
        self.logger.info(
            f"Relationship created: {relationship_type}",
            from_id=str(from_entity_id),
            to_id=str(to_entity_id)
        )
        
        return relationship
    
    async def consolidate_memories(self, force: bool = False) -> Dict[str, Any]:
        """
        Trigger memory cleanup/consolidation process.

        Note: Elefante does not perform internal LLM synthesis. This endpoint is used
        for deterministic cleanup (canonicalization, duplicate marking, test quarantine)
        using the existing tool surface.
        """
        from src.core.refinery import MemoryRefinery

        refinery = MemoryRefinery(self.vector_store)
        result = await refinery.run(apply=bool(force))

        # Backward-compatible envelope keys
        return {
            "success": True,
            "consolidated_count": 0,
            "new_memory_ids": [],
            "refinery": result,
        }
    
    async def list_all_memories(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[SearchFilters] = None
    ) -> List[Memory]:
        """
        List all memories without semantic search filtering
        
        This method retrieves memories directly from the vector store without
        applying semantic similarity filtering. Useful for:
        - Database inspection and debugging
        - Exporting all memories
        - Browsing complete memory collection
        - Administrative tasks
        
        Args:
            limit: Maximum number of memories to return (default: 100)
            offset: Number of memories to skip for pagination (default: 0)
            filters: Optional filters (memory_type, score, etc.)
            
        Returns:
            List[Memory]: List of memory objects
            
        Example:
            # Get first 50 memories
            memories = await orchestrator.list_all_memories(limit=50)
            
            # Get next 50 memories (pagination)
            memories = await orchestrator.list_all_memories(limit=50, offset=50)
            
            # Filter by type
            filters = SearchFilters(memory_type="decision")
            memories = await orchestrator.list_all_memories(filters=filters)
        """
        self.logger.info(
            "Listing all memories",
            limit=limit,
            offset=offset,
            has_filters=filters is not None
        )
        
        try:
            memories = await self.vector_store.get_all(
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            self.logger.info(
                "Listed all memories",
                count=len(memories),
                offset=offset
            )
            
            return memories
            
        except Exception as e:
            self.logger.error(f"Failed to list all memories: {e}", exc_info=True)
            raise
    
    # --------------------------------------------------------------------------
    # Task Orchestration
    # --------------------------------------------------------------------------

    async def create_task(
        self,
        description: str,
        parent_id: Optional[str] = None,
        blocked_by: Optional[List[str]] = None,
        priority: int = 1,
        status: TaskStatus = TaskStatus.PENDING,
        assigned_agent: Optional[str] = None
    ) -> str:
        """Create a new task, optionally linked to a parent and/or blocked by other tasks."""
        # Input validation
        if not description or not description.strip():
            raise ValueError("Task description cannot be empty")
        priority = max(1, min(10, priority))  # Clamp to 1-10
        if not isinstance(status, TaskStatus):
            raise ValueError(f"Invalid status: {status}. Must be a TaskStatus enum value.")

        task_id = str(uuid4())
        now = datetime.utcnow()
        
        cypher = """
            CREATE (t:Task {
                id: $id,
                description: $description,
                status: $status,
                created_at: $created_at,
                updated_at: $updated_at,
                priority: $priority,
                assigned_agent: $assigned_agent
            })
            RETURN t.id
        """
        params = {
            "id": task_id,
            "description": description.strip(),
            "status": status.value,
            "created_at": now,
            "updated_at": now,
            "priority": priority,
            "assigned_agent": assigned_agent or "unassigned"
        }
        
        await self.graph_store.execute_query(cypher, params)
        
        # Link to parent if provided
        if parent_id:
            rel_cypher = """
                MATCH (child:Task), (parent:Task)
                WHERE child.id = $child_id AND parent.id = $parent_id
                CREATE (child)-[:TASK_PARENT]->(parent)
            """
            await self.graph_store.execute_query(rel_cypher, {"child_id": task_id, "parent_id": parent_id})

        # Create TASK_BLOCKED_BY edges
        if blocked_by:
            for blocker_id in blocked_by:
                block_cypher = """
                    MATCH (blocked:Task), (blocker:Task)
                    WHERE blocked.id = $blocked_id AND blocker.id = $blocker_id
                    CREATE (blocked)-[:TASK_BLOCKED_BY]->(blocker)
                """
                await self.graph_store.execute_query(block_cypher, {"blocked_id": task_id, "blocker_id": blocker_id})

        return task_id

    async def decompose_task(self, parent_task_id: str, subtasks: List[Dict[str, Any]]) -> List[str]:
        """
        Break a task into subtasks.
        subtasks list expects dicts with: description, priority (optional), assigned_agent (optional)
        """
        created_ids = []
        for st in subtasks:
            # Inherit priority if not set? Or default to 1.
            # Create subtask linked to parent
            tid = await self.create_task(
                description=st["description"],
                parent_id=parent_task_id,
                priority=st.get("priority", 1),
                assigned_agent=st.get("assigned_agent")
            )
            created_ids.append(tid)
        return created_ids

    async def update_task(self, task_id: str, status: Optional[str] = None, output: Optional[str] = None) -> bool:
        """Update task status and output."""
        # Validate status against enum if provided
        valid_statuses = {s.value for s in TaskStatus}
        if status and status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

        set_clauses = ["t.updated_at = $updated_at"]
        params = {"id": task_id, "updated_at": datetime.utcnow()}
        
        if status:
            set_clauses.append("t.status = $status")
            params["status"] = status
        if output is not None:
            set_clauses.append("t.output = $output")
            params["output"] = output
            
        cypher = f"""
            MATCH (t:Task)
            WHERE t.id = $id
            SET {", ".join(set_clauses)}
            RETURN t.id
        """
        results = await self.graph_store.execute_query(cypher, params)
        return len(results) > 0

    async def get_task_graph(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get task hierarchy.
        If task_id is None, returns all root tasks (no parents).
        If task_id provided, returns that task, its children, and blockers.
        """
        if task_id:
            # Get task details
            task_details = await self.graph_store.execute_query(
                "MATCH (t:Task) WHERE t.id = $id RETURN t.id, t.description, t.status, t.output, t.priority, t.assigned_agent",
                {"id": task_id}
            )
            if not task_details:
                return None

            # Get children
            children = await self.graph_store.execute_query(
                "MATCH (child:Task)-[:TASK_PARENT]->(parent:Task) WHERE parent.id = $id RETURN child.id, child.description, child.status, child.priority",
                {"id": task_id}
            )

            # Get blockers
            blockers = await self.graph_store.execute_query(
                "MATCH (t:Task)-[:TASK_BLOCKED_BY]->(blocker:Task) WHERE t.id = $id RETURN blocker.id, blocker.description, blocker.status",
                {"id": task_id}
            )

            return {
                "task": task_details[0],
                "subtasks": children,
                "blocked_by": blockers
            }
        else:
            cypher = """
                MATCH (t:Task)
                WHERE NOT (t)-[:TASK_PARENT]->(:Task)
                RETURN t.id, t.description, t.status, t.priority
                ORDER BY t.created_at DESC
                LIMIT 50
            """
            return await self.graph_store.execute_query(cypher)

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task and its edges. Children are NOT deleted — they become orphans (roots)."""
        return await self.graph_store.delete_task(task_id)

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics from both databases
        
        Returns:
            Dict with stats from vector and graph stores
        """
        vector_stats = await self.vector_store.get_stats()
        graph_stats = await self.graph_store.get_stats()
        
        return {
            "vector_store": vector_stats,
            "graph_store": graph_stats,
            "orchestrator": {
                "status": "operational",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    async def close(self) -> None:
        """Release owned persistence handles during controlled shutdown.

        Stores may expose either synchronous or asynchronous ``close`` methods.
        Supporting both keeps the orchestrator compatible with the existing
        Kuzu and the configured vector store (SQLite by default).
        """
        self.logger.info("closing_orchestrator_connections")
        failures: list[Exception] = []

        for name, resource in (("vector_store", self.vector_store), ("graph_store", self.graph_store)):
            close = getattr(resource, "close", None)
            if not callable(close):
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except Exception as error:
                failures.append(error)
                self.logger.exception("failed_to_close_store", store=name, error=str(error))

        if failures:
            raise failures[0]


# Global singleton instance
_orchestrator: Optional[MemoryOrchestrator] = None


def get_orchestrator() -> MemoryOrchestrator:
    """
    Get or create global orchestrator instance
    
    Returns:
        MemoryOrchestrator: Singleton orchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator


async def reset_orchestrator(
    extra_orchestrator: MemoryOrchestrator | None = None,
) -> None:
    """Close persistence handles and force the next request to open fresh stores."""
    global _orchestrator

    current = _orchestrator
    _orchestrator = None
    instances = []
    for candidate in (current, extra_orchestrator):
        if candidate is not None and all(candidate is not item for item in instances):
            instances.append(candidate)
    failures: list[Exception] = []
    for instance in instances:
        try:
            await instance.close()
        except Exception as error:
            failures.append(error)

    from src.core.graph_store import reset_graph_store
    from src.core.vector_store import reset_vector_store

    reset_vector_store()
    reset_graph_store()
    if failures:
        raise failures[0]
