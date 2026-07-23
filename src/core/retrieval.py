# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/core/retrieval.py
# VERSION : 2.7.0
# CHANGED : 2026-04-15
# PURPOSE : Cognitive retrieval engine: ranked memory results with multi-signal
#           scoring (semantic, temporal, access reinforcement).
# ROLE    : Core query path — called by orchestrator for all MemorySearch ops.
# TOUCHED : When changing ranking signals, score weights, or retrieval filters.
#           Works with scoring.py for normalization.
# ─────────────────────────────────────────────────────────────────────────────
"""
Cognitive Retrieval Engine

Returns ranked memory results with multi-signal scoring.
Multi-signal scoring: vector + concepts + co-activation + authority + temporal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MemoryCandidate:
    """A memory with its multi-signal scores."""
    id: str
    content: str
    title: str
    summary: str
    concepts: list[str]
    domain: str
    score: int  # 0-100 behavioral vitality score
    access_count: int
    created_at: datetime
    last_accessed: datetime
    embedding: Optional[list[float]] = None
    memory_type: str = "fact"
    
    # Computed scores
    vector_score: float = 0.0
    concept_score: float = 0.0
    domain_score: float = 0.0
    coactivation_score: float = 0.0
    authority_score: float = 0.0
    composite_score: float = 0.0
    
    role: str = "candidate"  # primary, supporting, contradicting, context


@dataclass
class QueryAnalysis:
    """Analyzed query with extracted signals."""
    raw_query: str
    concepts: list[str]
    inferred_domain: Optional[str] = None
    inferred_intent: Optional[str] = None  # troubleshoot, learn, decide, remember
    embedding: Optional[list[float]] = None


# =============================================================================
# RETRIEVAL EXPLANATION
# =============================================================================

@dataclass
class RetrievalExplanation:
    """
    Complete explanation for why a memory was retrieved.
    Every search result includes WHY it surfaced.
    """
    composite_score: float
    signals: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Serialize for MCP response."""
        return {
            "composite_score": round(self.composite_score, 3),
            "signals": [
                {
                    "name": s["name"],
                    "score": round(s["score"], 3),
                    "weight": s["weight"],
                    "weighted": round(s["weighted"], 3),
                    "reason": s["reason"],
                    "details": s["details"]
                }
                for s in self.signals
            ]
        }



class CognitiveRetriever:
    """
    Multi-signal retrieval engine.
    
    Weights (v2.7.0 — domain removed, see CHANGELOG):
    - vector_similarity: 0.35
    - concept_overlap: 0.30
    - co_activation: 0.15
    - authority: 0.10
    - temporal: 0.10
    """
    
    WEIGHTS = {
        "vector": 0.35,
        "concept": 0.30,
        "coactivation": 0.15,
        "authority": 0.10,
        "temporal": 0.10,
    }
    
    def __init__(
        self,
        co_activation_matrix: Optional[dict[str, dict[str, int]]] = None,
    ):
        """
        Args:
            co_activation_matrix: {memory_id: {other_id: co_retrieval_count}}
        """
        self.co_activation_matrix = co_activation_matrix or {}
    
    def analyze_query(self, query: str, query_embedding: Optional[list[float]] = None) -> QueryAnalysis:
        """Extract signals from query."""
        from src.utils.curation import extract_concepts
        
        concepts = extract_concepts(query, max_concepts=5)
        
        # Infer domain from keywords
        query_lower = query.lower()
        domain = None
        if "elefante" in query_lower:
            domain = "project:elefante"
        elif any(w in query_lower for w in ["work", "job", "meeting", "deadline"]):
            domain = "work"
        elif any(w in query_lower for w in ["personal", "home", "family"]):
            domain = "personal"
        
        # Infer intent
        intent = "remember"  # default
        if any(w in query_lower for w in ["error", "bug", "fix", "problem", "issue"]):
            intent = "troubleshoot"
        elif any(w in query_lower for w in ["spec", "directive", "rule", "requirement", "architecture", "constraint", "sdd", "compliance"]):
            intent = "system"
        elif any(w in query_lower for w in ["how", "learn", "what is", "explain"]):
            intent = "learn"
        elif any(w in query_lower for w in ["decide", "choose", "should i", "which"]):
            intent = "decide"
        
        return QueryAnalysis(
            raw_query=query,
            concepts=concepts,
            inferred_domain=domain,
            inferred_intent=intent,
            embedding=query_embedding,
        )
    
    def compute_concept_overlap(self, query_concepts: list[str], memory_concepts: list[str]) -> float:
        """Jaccard-like overlap with position weighting."""
        if not query_concepts or not memory_concepts:
            return 0.0
        
        query_set = set(query_concepts)
        memory_set = set(memory_concepts)
        
        intersection = len(query_set & memory_set)
        union = len(query_set | memory_set)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def compute_domain_match(self, query_domain: Optional[str], memory_domain: str) -> float:
        """Domain matching score."""
        if not query_domain:
            return 0.5  # Neutral if no domain inferred
        
        if query_domain == memory_domain:
            return 1.0
        
        # Partial match for project domains
        if query_domain.startswith("project:") and memory_domain.startswith("project:"):
            return 0.3  # Both are projects but different
        
        return 0.0
    
    def compute_coactivation(
        self,
        memory_id: str,
        recent_memory_ids: list[str],
        co_activation_matrix: dict | None = None,
    ) -> float:
        """Score based on co-retrieval history."""
        matrix = co_activation_matrix if co_activation_matrix is not None else self.co_activation_matrix
        if not recent_memory_ids or memory_id not in matrix:
            return 0.0
        
        memory_coacts = matrix.get(memory_id, {})
        total_coact = sum(memory_coacts.get(rid, 0) for rid in recent_memory_ids)
        
        # Normalize (saturates around 10 co-activations)
        return min(1.0, total_coact / 10.0)
    
    def compute_temporal_score(self, last_accessed: datetime, created_at: datetime) -> float:
        """Recency and freshness score."""
        now = datetime.utcnow()
        
        days_since_access = (now - last_accessed).days if last_accessed else 365
        days_since_created = (now - created_at).days if created_at else 365
        
        # Recent access boost (half-life 14 days)
        access_score = math.exp(-0.05 * days_since_access)
        
        # Creation freshness (half-life 90 days)
        freshness_score = math.exp(-0.007 * days_since_created)
        
        return 0.6 * access_score + 0.4 * freshness_score
    
    def compute_authority(self, score: int, access_count: int) -> float:
        """Authority from score (0-100) and usage."""
        score_factor = score / 100.0
        access_factor = min(1.0, math.log(access_count + 1) / math.log(50))
        
        return 0.6 * score_factor + 0.4 * access_factor
    
    def score_candidate(
        self,
        candidate: MemoryCandidate,
        query: QueryAnalysis,
        recent_memory_ids: list[str],
        include_explanation: bool = True,
        co_activation_matrix: dict | None = None,
    ) -> tuple[MemoryCandidate, Optional[RetrievalExplanation]]:
        """
        Compute all scores for a candidate.
        
        V5: Now returns (candidate, explanation) tuple.
        """
        
        # Vector score (already computed externally, passed in)
        # candidate.vector_score is set before calling this
        
        # Concept overlap
        candidate.concept_score = self.compute_concept_overlap(
            query.concepts,
            candidate.concepts,
        )
        
        # Domain match
        candidate.domain_score = self.compute_domain_match(
            query.inferred_domain,
            candidate.domain,
        )
        
        # Co-activation
        candidate.coactivation_score = self.compute_coactivation(
            candidate.id,
            recent_memory_ids,
            co_activation_matrix
        )
        
        # Authority
        candidate.authority_score = self.compute_authority(
            candidate.score,
            candidate.access_count,
        )
        
        # Temporal
        temporal_score = self.compute_temporal_score(
            candidate.last_accessed,
            candidate.created_at,
        )
        
        # Base composite score (v2.7.0: domain signal removed).
        # Keep the co-activation contribution separate from the vector floor
        # below: otherwise a positive co-activation signal can be hidden when
        # the metadata-derived score remains below that floor.
        cognitive_score_without_coactivation = (
            self.WEIGHTS["vector"] * candidate.vector_score +
            self.WEIGHTS["concept"] * candidate.concept_score +
            self.WEIGHTS["authority"] * candidate.authority_score +
            self.WEIGHTS["temporal"] * temporal_score
        )

        # Dynamic Floor (Fixes Issue #8 Low Similarity)
        # Vector score is the semantic ground truth. Cognitive heuristics should boost 
        # semantic matches, not suppress them into oblivion if metadata is sparse.
        # Floor lowered from 0.85 to 0.70 in v2.7.0 (domain removal reduces noise).
        vector_baseline = candidate.vector_score * 0.70
        candidate.composite_score = max(vector_baseline, cognitive_score_without_coactivation)
        candidate.composite_score += (
            self.WEIGHTS["coactivation"] * candidate.coactivation_score
        )
        candidate.composite_score = min(1.0, candidate.composite_score)
            
        # Intent-Gated SDD Authority Override (v2.7.0)
        # Specifications and directives get a boost ONLY when the query intent
        # is system/architecture related. Prevents specs from dominating
        # unrelated queries (e.g., "what should I remember about debugging").
        if candidate.memory_type in ("specification", "directive") and query.inferred_intent == "system":
            candidate.composite_score = min(1.0, candidate.composite_score + 0.30)
        
        # Build explanation if requested
        explanation = None
        if include_explanation:
            explanation = self._build_explanation(
                candidate, query, temporal_score
            )
        
        return candidate, explanation
    
    def _build_explanation(
        self,
        candidate: MemoryCandidate,
        query: QueryAnalysis,
        temporal_score: float,
    ) -> RetrievalExplanation:
        """
        Build human-readable explanation from scored candidate.
        """
        # Compute matched concepts for details
        query_set = set(query.concepts) if query.concepts else set()
        memory_set = set(candidate.concepts) if candidate.concepts else set()
        matched_concepts = list(query_set & memory_set)
        
        # Build temporal reason
        now = datetime.utcnow()
        days_since_access = (now - candidate.last_accessed).days if candidate.last_accessed else 0
        temporal_reason = f"Accessed {days_since_access} days ago" if days_since_access > 0 else "Recently accessed"
        
        # Build authority reason
        if candidate.score >= 80:
            authority_reason = "High score, frequently used"
        elif candidate.score >= 50:
            authority_reason = "Medium score"
        else:
            authority_reason = "Lower score"
        
        signals = [
            {
                "name": "vector_similarity",
                "score": candidate.vector_score,
                "weight": self.WEIGHTS["vector"],
                "weighted": candidate.vector_score * self.WEIGHTS["vector"],
                "reason": "Semantic match",
                "details": {}
            },
            {
                "name": "concept_overlap",
                "score": candidate.concept_score,
                "weight": self.WEIGHTS["concept"],
                "weighted": candidate.concept_score * self.WEIGHTS["concept"],
                "reason": f"Shared {len(matched_concepts)} concept(s)" if matched_concepts else "No concept overlap",
                "details": {"matched": matched_concepts}
            },
            {
                "name": "coactivation",
                "score": candidate.coactivation_score,
                "weight": self.WEIGHTS["coactivation"],
                "weighted": candidate.coactivation_score * self.WEIGHTS["coactivation"],
                "reason": "Co-retrieved with recent memories" if candidate.coactivation_score > 0 else "No co-activation history",
                "details": {}
            },
            {
                "name": "authority",
                "score": candidate.authority_score,
                "weight": self.WEIGHTS["authority"],
                "weighted": candidate.authority_score * self.WEIGHTS["authority"],
                "reason": authority_reason,
                "details": {"score": candidate.score, "access_count": candidate.access_count}
            },
            {
                "name": "temporal",
                "score": temporal_score,
                "weight": self.WEIGHTS["temporal"],
                "weighted": temporal_score * self.WEIGHTS["temporal"],
                "reason": temporal_reason,
                "details": {"days_since_access": days_since_access}
            },
        ]
        
        return RetrievalExplanation(
            composite_score=candidate.composite_score,
            signals=signals
        )
    
