"""
Cognitive Retrieval Engine - V4 Schema

Returns memory constellations, not flat lists.
Multi-signal scoring: vector + concepts + domain + co-activation + authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

import numpy as np


@dataclass
class MemoryCandidate:
    """A memory with its multi-signal scores."""
    id: str
    content: str
    title: str
    summary: str
    concepts: list[str]
    domain: str
    importance: int
    access_count: int
    created_at: datetime
    last_accessed: datetime
    embedding: Optional[list[float]] = None
    
    # Computed scores
    vector_score: float = 0.0
    concept_score: float = 0.0
    domain_score: float = 0.0
    coactivation_score: float = 0.0
    authority_score: float = 0.0
    composite_score: float = 0.0
    
    # Role in constellation
    role: str = "candidate"  # primary, supporting, contradicting, context


@dataclass
class QueryAnalysis:
    """Analyzed query with extracted signals."""
    raw_query: str
    concepts: list[str]
    inferred_domain: Optional[str] = None
    inferred_intent: Optional[str] = None  # troubleshoot, learn, decide, remember
    embedding: Optional[list[float]] = None


@dataclass
class MemoryConstellation:
    """Structured retrieval result - not a flat list."""
    primary: Optional[MemoryCandidate] = None
    supporting: list[MemoryCandidate] = field(default_factory=list)
    contradicting: list[MemoryCandidate] = field(default_factory=list)
    context: list[MemoryCandidate] = field(default_factory=list)
    synthesis: str = ""
    
    def to_dict(self) -> dict:
        def mem_to_dict(m: MemoryCandidate) -> dict:
            return {
                "id": m.id,
                "title": m.title,
                "summary": m.summary,
                "score": round(m.composite_score, 3),
                "role": m.role,
                "concepts": m.concepts,
            }
        
        return {
            "primary": mem_to_dict(self.primary) if self.primary else None,
            "supporting": [mem_to_dict(m) for m in self.supporting],
            "contradicting": [mem_to_dict(m) for m in self.contradicting],
            "context": [mem_to_dict(m) for m in self.context],
            "synthesis": self.synthesis,
            "total_memories": 1 + len(self.supporting) + len(self.contradicting) + len(self.context) if self.primary else 0,
        }


class CognitiveRetriever:
    """
    Multi-signal retrieval engine.
    
    Weights:
    - vector_similarity: 0.30
    - concept_overlap: 0.20
    - domain_match: 0.15
    - co_activation: 0.15
    - authority: 0.10
    - temporal: 0.10
    """
    
    WEIGHTS = {
        "vector": 0.30,
        "concept": 0.20,
        "domain": 0.15,
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
    ) -> float:
        """Score based on co-retrieval history."""
        if not recent_memory_ids or memory_id not in self.co_activation_matrix:
            return 0.0
        
        memory_coacts = self.co_activation_matrix.get(memory_id, {})
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
    
    def compute_authority(self, importance: int, access_count: int) -> float:
        """Authority from importance and usage."""
        importance_factor = importance / 10.0
        access_factor = min(1.0, math.log(access_count + 1) / math.log(50))
        
        return 0.6 * importance_factor + 0.4 * access_factor
    
    def score_candidate(
        self,
        candidate: MemoryCandidate,
        query: QueryAnalysis,
        recent_memory_ids: list[str],
    ) -> MemoryCandidate:
        """Compute all scores for a candidate."""
        
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
        )
        
        # Authority
        candidate.authority_score = self.compute_authority(
            candidate.importance,
            candidate.access_count,
        )
        
        # Temporal
        temporal_score = self.compute_temporal_score(
            candidate.last_accessed,
            candidate.created_at,
        )
        
        # Composite score
        candidate.composite_score = (
            self.WEIGHTS["vector"] * candidate.vector_score +
            self.WEIGHTS["concept"] * candidate.concept_score +
            self.WEIGHTS["domain"] * candidate.domain_score +
            self.WEIGHTS["coactivation"] * candidate.coactivation_score +
            self.WEIGHTS["authority"] * candidate.authority_score +
            self.WEIGHTS["temporal"] * temporal_score
        )
        
        return candidate
    
    def build_constellation(
        self,
        candidates: list[MemoryCandidate],
        query: QueryAnalysis,
        contradictions: Optional[dict[str, list[str]]] = None,
        supports: Optional[dict[str, list[str]]] = None,
    ) -> MemoryConstellation:
        """
        Build structured constellation from scored candidates.
        
        Args:
            candidates: Scored candidates, sorted by composite_score descending
            contradictions: {memory_id: [contradicting_ids]}
            supports: {memory_id: [supporting_ids]}
        """
        if not candidates:
            return MemoryConstellation(synthesis="No relevant memories found.")
        
        contradictions = contradictions or {}
        supports = supports or {}
        
        # Primary = highest score
        primary = candidates[0]
        primary.role = "primary"
        
        constellation = MemoryConstellation(primary=primary)
        
        # Categorize remaining candidates
        primary_contradicts = set(contradictions.get(primary.id, []))
        primary_supports = set(supports.get(primary.id, []))
        
        for candidate in candidates[1:10]:  # Limit to top 10
            if candidate.id in primary_contradicts:
                candidate.role = "contradicting"
                constellation.contradicting.append(candidate)
            elif candidate.id in primary_supports:
                candidate.role = "supporting"
                constellation.supporting.append(candidate)
            elif candidate.concept_score > 0.3:  # Shares concepts
                candidate.role = "context"
                constellation.context.append(candidate)
            elif candidate.composite_score > 0.5:  # High enough to include
                candidate.role = "supporting"
                constellation.supporting.append(candidate)
        
        # Limit each category
        constellation.supporting = constellation.supporting[:3]
        constellation.contradicting = constellation.contradicting[:2]
        constellation.context = constellation.context[:2]
        
        # Generate synthesis
        constellation.synthesis = self._generate_synthesis(constellation, query)
        
        return constellation
    
    def _generate_synthesis(self, constellation: MemoryConstellation, query: QueryAnalysis) -> str:
        """Generate human-readable synthesis."""
        parts = []
        
        if constellation.primary:
            parts.append(f"Primary: {constellation.primary.title} (confidence: {constellation.primary.composite_score:.2f})")
        
        if constellation.supporting:
            support_titles = [m.title for m in constellation.supporting[:2]]
            parts.append(f"Supported by: {', '.join(support_titles)}")
        
        if constellation.contradicting:
            contra_titles = [m.title for m in constellation.contradicting[:2]]
            parts.append(f"Note: Conflicting info in: {', '.join(contra_titles)}")
        
        if constellation.context:
            context_titles = [m.title for m in constellation.context[:2]]
            parts.append(f"Related: {', '.join(context_titles)}")
        
        return " | ".join(parts) if parts else "No synthesis available."
