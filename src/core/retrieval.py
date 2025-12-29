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


# =============================================================================
# V5: RETRIEVAL EXPLANATION
# =============================================================================

@dataclass
class RetrievalExplanation:
    """
    Complete explanation for why a memory was retrieved.
    
    V5 Feature: Every search result includes WHY it surfaced.
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
        include_explanation: bool = True,
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
        
        # V5: Build explanation if requested
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
        
        V5 Feature: Req-1 - Retrieval Explanation
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
        if candidate.importance >= 8:
            authority_reason = "High importance, frequently used"
        elif candidate.importance >= 5:
            authority_reason = "Medium importance"
        else:
            authority_reason = "Lower importance"
        
        # Build domain reason
        if candidate.domain_score >= 1.0:
            domain_reason = f"Exact domain match: {candidate.domain}"
        elif candidate.domain_score >= 0.5:
            domain_reason = "Neutral (no domain inferred from query)"
        else:
            domain_reason = f"Different domain: {candidate.domain}"
        
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
                "name": "domain_match",
                "score": candidate.domain_score,
                "weight": self.WEIGHTS["domain"],
                "weighted": candidate.domain_score * self.WEIGHTS["domain"],
                "reason": domain_reason,
                "details": {"domain": candidate.domain}
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
                "details": {"importance": candidate.importance, "access_count": candidate.access_count}
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


# =============================================================================
# V5: PROACTIVE SURFACING
# =============================================================================

@dataclass
class ProactiveSuggestion:
    """
    A memory that SHOULD surface based on context triggers.
    
    V5 Feature: Req-4 - Proactive Surfacing
    """
    memory_id: str
    memory_title: str
    trigger: str       # "temporal" | "domain" | "recurring_concept"
    confidence: float  # 0.0 - 1.0
    reason: str        # Human-readable explanation


class ProactiveSurfacer:
    """
    Suggests memories that SHOULD surface based on:
    1. Temporal triggers (surfaces_when matches current time/context)
    2. Domain triggers (domain matches current conversation)
    3. Recurring concepts (same concepts appearing repeatedly)
    
    V5 Feature: Req-4 - Proactive Surfacing (soft suggestions only)
    """
    
    def __init__(
        self,
        temporal_confidence: float = 0.7,
        domain_confidence: float = 0.6,
        concept_confidence: float = 0.5,
    ):
        """
        Configurable confidence thresholds.
        
        Args:
            temporal_confidence: Base confidence for time-based triggers
            domain_confidence: Base confidence for domain matches
            concept_confidence: Base confidence for recurring concepts
        """
        self.temporal_confidence = temporal_confidence
        self.domain_confidence = domain_confidence
        self.concept_confidence = concept_confidence
    
    def check_temporal_trigger(
        self,
        memory_id: str,
        memory_title: str,
        surfaces_when: Optional[str],
        current_context: str,
    ) -> Optional[ProactiveSuggestion]:
        """
        Check if memory's surfaces_when matches current context.
        
        Examples of surfaces_when values:
        - "at standup meetings"
        - "when discussing Python projects"
        - "during code reviews"
        """
        if not surfaces_when:
            return None
        
        # Normalize for comparison
        surfaces_lower = surfaces_when.lower()
        context_lower = current_context.lower()
        
        # Extract key phrases from surfaces_when
        trigger_phrases = []
        
        # Common temporal patterns
        if "standup" in surfaces_lower:
            trigger_phrases.extend(["standup", "daily", "morning meeting"])
        if "code review" in surfaces_lower:
            trigger_phrases.extend(["review", "pr", "pull request"])
        if "debug" in surfaces_lower:
            trigger_phrases.extend(["debug", "error", "bug", "fix"])
        if "planning" in surfaces_lower:
            trigger_phrases.extend(["plan", "sprint", "roadmap"])
        
        # Also use raw words from surfaces_when
        raw_words = [w.strip() for w in surfaces_lower.replace(",", " ").split() if len(w) > 3]
        trigger_phrases.extend(raw_words)
        
        # Check for matches
        matches = [p for p in trigger_phrases if p in context_lower]
        
        if not matches:
            return None
        
        return ProactiveSuggestion(
            memory_id=memory_id,
            memory_title=memory_title,
            trigger="temporal",
            confidence=self.temporal_confidence,
            reason=f"Scheduled to surface: '{surfaces_when}' matches current context"
        )
    
    def check_domain_trigger(
        self,
        memory_id: str,
        memory_title: str,
        memory_domain: str,
        conversation_domain: Optional[str],
    ) -> Optional[ProactiveSuggestion]:
        """
        Check if memory's domain matches current conversation domain.
        """
        if not conversation_domain:
            return None
        
        if memory_domain == conversation_domain:
            return ProactiveSuggestion(
                memory_id=memory_id,
                memory_title=memory_title,
                trigger="domain",
                confidence=self.domain_confidence,
                reason=f"Relevant to current domain: {memory_domain}"
            )
        
        return None
    
    def check_concept_trigger(
        self,
        memory_id: str,
        memory_title: str,
        memory_concepts: list[str],
        recent_concepts: list[str],
        min_overlap: int = 2,
    ) -> Optional[ProactiveSuggestion]:
        """
        Check if memory shares multiple concepts with recent conversation.
        """
        if not memory_concepts or not recent_concepts:
            return None
        
        shared = set(memory_concepts) & set(recent_concepts)
        
        if len(shared) >= min_overlap:
            return ProactiveSuggestion(
                memory_id=memory_id,
                memory_title=memory_title,
                trigger="recurring_concept",
                confidence=self.concept_confidence,
                reason=f"Shares concepts: {', '.join(list(shared)[:3])}"
            )
        
        return None
    
    def get_proactive_surfaces(
        self,
        memories: list[dict],
        current_context: str,
        conversation_domain: Optional[str] = None,
        recent_concepts: Optional[list[str]] = None,
    ) -> list[ProactiveSuggestion]:
        """
        Scan memories for proactive surfacing candidates.
        
        Args:
            memories: List of dicts with keys:
                - id: str
                - title: str
                - domain: str
                - concepts: list[str]
                - surfaces_when: Optional[str]
            current_context: Current conversation/query context
            conversation_domain: Inferred domain of conversation
            recent_concepts: Concepts from recent conversation
        
        Returns:
            List of ProactiveSuggestion, sorted by confidence descending
        """
        recent_concepts = recent_concepts or []
        suggestions: list[ProactiveSuggestion] = []
        seen_ids: set[str] = set()  # Dedupe
        
        for mem in memories:
            mem_id = mem["id"]
            mem_title = mem.get("title", "Untitled")
            
            # Skip if already suggested
            if mem_id in seen_ids:
                continue
            
            # Check temporal trigger (highest priority)
            temporal = self.check_temporal_trigger(
                mem_id, mem_title,
                mem.get("surfaces_when"),
                current_context
            )
            if temporal:
                suggestions.append(temporal)
                seen_ids.add(mem_id)
                continue
            
            # Check domain trigger
            domain_sug = self.check_domain_trigger(
                mem_id, mem_title,
                mem.get("domain", "general"),
                conversation_domain
            )
            if domain_sug:
                suggestions.append(domain_sug)
                seen_ids.add(mem_id)
                continue
            
            # Check concept trigger
            concept_sug = self.check_concept_trigger(
                mem_id, mem_title,
                mem.get("concepts", []),
                recent_concepts
            )
            if concept_sug:
                suggestions.append(concept_sug)
                seen_ids.add(mem_id)
        
        # Sort by confidence descending
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        return suggestions[:5]  # Limit to top 5
