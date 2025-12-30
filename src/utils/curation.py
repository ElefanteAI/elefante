"""Deterministic curation helpers (no LLMs).

These utilities are used to ensure memories have reasonable `title` and `summary`
fields at ingestion time and during batch backfills.

Keep these functions cheap, stable, and side-effect free.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


_CODEBLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


def collapse_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def strip_codeblocks(text: str) -> str:
    return _CODEBLOCK_RE.sub(" ", text or "")


def first_sentence(text: str) -> str:
    text = collapse_ws(text)
    if not text:
        return ""
    text = text.replace("- ", "").replace("* ", "")
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return (parts[0] if parts else text).strip()


def truncate(text: str, max_len: int) -> str:
    text = collapse_ws(text)
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rstrip()
    return cut + "…"


def generate_title(
    *,
    content: str,
    layer: Optional[str],
    sublayer: Optional[str],
    max_len: int = 90,
) -> str:
    cleaned = strip_codeblocks(content or "")
    cleaned = collapse_ws(cleaned)

    words = cleaned.split()
    core = " ".join(words[:10]) if words else "Memory"
    core = truncate(core, 70)

    l = (layer or "world").strip() or "world"
    s = (sublayer or "fact").strip() or "fact"

    title = f"{l}.{s}: {core}" if core else f"{l}.{s}: Memory"
    return truncate(title, max_len) or "Memory"


def generate_summary(*, content: str, max_len: int = 200) -> str:
    cleaned = strip_codeblocks(content or "")
    s = first_sentence(cleaned)
    if not s:
        s = collapse_ws(cleaned)
    return truncate(s, max_len) or ""


# ============================================================================
# V4 COGNITIVE RETRIEVAL HELPERS
# ============================================================================

# Common stop words to exclude from concepts
_STOP_WORDS = frozenset([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "also", "now", "i", "me",
    "my", "myself", "we", "our", "ours", "you", "your", "he", "him", "his",
    "she", "her", "it", "its", "they", "them", "their", "what", "which",
    "who", "whom", "this", "that", "these", "those", "am", "and", "but",
    "if", "or", "because", "until", "while", "although", "though", "even",
    "like", "use", "using", "used", "make", "made", "get", "got", "set",
])

# Technical terms that should be preserved as-is
_TECH_TERMS = frozenset([
    "api", "ui", "ux", "sql", "css", "html", "json", "yaml", "xml",
    "http", "https", "rest", "graphql", "oauth", "jwt", "aws", "gcp",
    "azure", "docker", "kubernetes", "k8s", "ci", "cd", "git", "github",
    "vscode", "ide", "cli", "sdk", "npm", "pip", "conda", "venv",
    "python", "javascript", "typescript", "react", "vue", "angular",
    "node", "express", "fastapi", "django", "flask", "postgresql",
    "mongodb", "redis", "elasticsearch", "chromadb", "kuzu", "llm",
    "gpt", "claude", "openai", "anthropic", "mcp", "elefante",
])


# Optional synonym/alias registry for concept normalization.
# Keep this small and deterministic; expand intentionally as UX evidence accumulates.
_DEFAULT_CONCEPT_ALIASES: dict[str, str] = {}


def _strip_accents(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_label(text: str) -> str:
    """Normalize a label for consistent matching (deterministic, language-agnostic).

    - casefold
    - strip accents
    - keep alphanumerics, dash, underscore, and spaces
    - collapse whitespace
    """
    text = collapse_ws(_strip_accents(text).casefold())
    text = re.sub(r"[^a-z0-9_\-\s]+", " ", text)
    return collapse_ws(text)


def canonicalize_concepts(
    concepts: list[str],
    *,
    aliases: Optional[dict[str, str]] = None,
    max_concepts: int = 5,
) -> list[str]:
    """Canonicalize concept labels.

    Goal: stable labeling for concept-overlap scoring and graph edges.
    Does NOT change memory content.
    """
    aliases = aliases or _DEFAULT_CONCEPT_ALIASES
    out: list[str] = []
    seen: set[str] = set()
    for raw in concepts or []:
        if not isinstance(raw, str):
            continue
        label = normalize_label(raw)
        if not label:
            continue

        # Normalize via alias map (keys are normalized labels).
        label = normalize_label(aliases.get(label, label))

        if label in _STOP_WORDS or len(label) < 2:
            continue
        if label in seen:
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= max_concepts:
            break
    return out


def canonicalize_surfaces_when(
    surfaces_when: list[str],
    *,
    aliases: Optional[dict[str, str]] = None,
    max_surfaces: int = 12,
) -> list[str]:
    """Canonicalize surface triggers.

    These are short query patterns; we normalize tokens for consistency.
    """
    aliases = aliases or _DEFAULT_CONCEPT_ALIASES
    out: list[str] = []
    seen: set[str] = set()

    for raw in surfaces_when or []:
        if not isinstance(raw, str):
            continue
        phrase = normalize_label(raw)
        if not phrase:
            continue

        # Apply aliases token-by-token to preserve the phrase structure.
        tokens = []
        for tok in phrase.split():
            tok_norm = normalize_label(tok)
            tok_norm = normalize_label(aliases.get(tok_norm, tok_norm))
            if tok_norm:
                tokens.append(tok_norm)
        phrase = " ".join(tokens)

        if not phrase or phrase in seen:
            continue
        seen.add(phrase)
        out.append(phrase)
        if len(out) >= max_surfaces:
            break

    return out


def extract_concepts(content: str, max_concepts: int = 5) -> list[str]:
    """
    Extract 3-5 key concepts from content for graph edges.
    
    Deterministic, no LLM. Uses frequency + position + technical term detection.
    """
    if not content:
        return []
    
    # Clean and tokenize
    cleaned = strip_codeblocks(content)
    cleaned = re.sub(r"[^\w\s-]", " ", cleaned.lower())
    words = cleaned.split()
    
    if not words:
        return []
    
    # Score each word
    word_scores: dict[str, float] = {}
    total_words = len(words)
    
    for i, word in enumerate(words):
        # Skip short words and stop words
        if len(word) < 3 or word in _STOP_WORDS:
            continue
        
        # Normalize
        word = word.strip("-")
        if not word:
            continue
        
        # Base score: frequency
        if word not in word_scores:
            word_scores[word] = 0.0
        word_scores[word] += 1.0
        
        # Position boost: words near start are more important
        position_boost = 1.0 - (i / total_words) * 0.5
        word_scores[word] += position_boost * 0.3
        
        # Technical term boost
        if word in _TECH_TERMS:
            word_scores[word] += 2.0
    
    # Sort by score and take top concepts
    sorted_concepts = sorted(word_scores.items(), key=lambda x: -x[1])
    concepts = [word for word, score in sorted_concepts[:max_concepts]]
    
    return concepts


def infer_surfaces_when(content: str, concepts: list[str]) -> list[str]:
    """
    Generate query patterns that should surface this memory.
    
    Based on content structure and extracted concepts.
    """
    surfaces = []
    content_lower = content.lower()
    
    # Pattern 1: Question-based (if content answers a question)
    if any(q in content_lower for q in ["how to", "why", "what is", "when to"]):
        # Extract the question pattern
        for pattern in ["how to", "why do", "why is", "what is", "when to", "where to"]:
            if pattern in content_lower:
                surfaces.append(pattern)
    
    # Pattern 2: Error/problem patterns
    if any(e in content_lower for e in ["error", "fail", "issue", "problem", "bug", "fix"]):
        for concept in concepts[:2]:
            surfaces.append(f"{concept} error")
            surfaces.append(f"{concept} problem")
    
    # Pattern 3: Concept combinations
    if len(concepts) >= 2:
        surfaces.append(f"{concepts[0]} {concepts[1]}")
    
    # Pattern 4: Action patterns (if content is instructional)
    if any(a in content_lower for a in ["always", "never", "must", "should", "use", "avoid"]):
        for concept in concepts[:2]:
            surfaces.append(f"{concept} best practice")
            surfaces.append(f"how to {concept}")
    
    # Pattern 5: Configuration/setup patterns
    if any(c in content_lower for c in ["config", "setup", "install", "configure"]):
        for concept in concepts[:2]:
            surfaces.append(f"{concept} setup")
            surfaces.append(f"{concept} configuration")
    
    # Deduplicate and limit
    seen = set()
    unique_surfaces = []
    for s in surfaces:
        if s not in seen:
            seen.add(s)
            unique_surfaces.append(s)
    
    return unique_surfaces[:8]


def classify_memory_type(content: str) -> str:
    """
    Classify memory as fact/rule/preference/decision.
    
    Simple keyword heuristics, no LLM.
    """
    content_lower = content.lower()
    
    # Rule patterns
    if any(p in content_lower for p in [
        "always", "never", "must", "should not", "do not", "don't",
        "rule:", "convention:", "standard:", "policy:"
    ]):
        return "rule"
    
    # Decision patterns
    if any(p in content_lower for p in [
        "decided", "chose", "will use", "going with", "selected",
        "decision:", "chose to", "opted for"
    ]):
        return "decision"
    
    # Preference patterns
    if any(p in content_lower for p in [
        "prefer", "like", "favorite", "i want", "i need",
        "preference:", "rather", "instead of"
    ]):
        return "preference"
    
    # Default to fact
    return "fact"


def compute_authority_score(
    importance: int,
    access_count: int,
    days_since_created: int,
    days_since_accessed: int,
) -> float:
    """
    Compute authority score for retrieval ranking.
    
    Combines importance, usage, and freshness.
    """
    import math
    
    # Normalize importance (1-10 → 0.1-1.0)
    importance_factor = importance / 10.0
    
    # Access factor (logarithmic, saturates around 50 accesses)
    access_factor = min(1.0, math.log(access_count + 1) / math.log(50))
    
    # Freshness decay (half-life of 90 days for creation)
    creation_decay = math.exp(-0.007 * days_since_created)
    
    # Recent access boost (half-life of 14 days)
    access_decay = math.exp(-0.05 * days_since_accessed)
    
    # Weighted combination
    score = (
        0.35 * importance_factor +
        0.25 * access_factor +
        0.20 * creation_decay +
        0.20 * access_decay
    )
    
    return round(min(1.0, max(0.0, score)), 3)


# ============================================================================
# V5 MEMORY HEALTH ANALYZER
# ============================================================================

from enum import Enum
from dataclasses import dataclass


class HealthStatus(str, Enum):
    """Memory health status (V5 Req-2)."""
    HEALTHY = "healthy"   #  Active, connected, recently used
    STALE = "stale"       #  Not accessed in 90+ days
    AT_RISK = "at_risk"   #  Superseded or has unresolved conflicts
    ORPHAN = "orphan"     #  No graph connections


@dataclass
class HealthReport:
    """Health analysis result for a memory."""
    status: HealthStatus
    icon: str
    reasons: list[str]


@dataclass
class ConflictReport:
    """Potential conflict between two memories (V5 Req-3)."""
    memory_a_id: str
    memory_b_id: str
    overlap: float
    shared_concepts: list[str]
    reason: str


class MemoryHealthAnalyzer:
    """
    Analyzes memory health and detects potential conflicts.
    
    V5 Features: Req-2 (Health), Req-3 (Conflicts)
    
    Used by: update_dashboard_data.py (snapshot generation)
    """
    
    ICONS = {
        HealthStatus.HEALTHY: "",
        HealthStatus.STALE: "",
        HealthStatus.AT_RISK: "",
        HealthStatus.ORPHAN: "",
    }
    
    def __init__(self, stale_days: int = 90, conflict_threshold: float = 0.6):
        """
        Args:
            stale_days: Days without access before memory is STALE
            conflict_threshold: Jaccard overlap threshold for conflict detection
        """
        self.stale_days = stale_days
        self.conflict_threshold = conflict_threshold
    
    def compute_health(
        self,
        *,
        superseded_by_id: Optional[str] = None,
        potential_conflicts: Optional[list[str]] = None,
        days_since_access: int = 0,
        connection_count: int = 0,
    ) -> HealthReport:
        """
        Compute health status for a single memory.
        
        Priority order:
        1. AT_RISK if superseded
        2. AT_RISK if has unresolved conflicts
        3. STALE if not accessed in 90+ days
        4. ORPHAN if no connections
        5. HEALTHY otherwise
        """
        potential_conflicts = potential_conflicts or []
        
        if superseded_by_id:
            return HealthReport(
                status=HealthStatus.AT_RISK,
                icon=self.ICONS[HealthStatus.AT_RISK],
                reasons=["Superseded by newer memory"]
            )
        
        if potential_conflicts:
            return HealthReport(
                status=HealthStatus.AT_RISK,
                icon=self.ICONS[HealthStatus.AT_RISK],
                reasons=[f"Has {len(potential_conflicts)} unresolved conflict(s)"]
            )
        
        if days_since_access > self.stale_days:
            return HealthReport(
                status=HealthStatus.STALE,
                icon=self.ICONS[HealthStatus.STALE],
                reasons=[f"Not accessed in {days_since_access} days"]
            )
        
        if connection_count == 0:
            return HealthReport(
                status=HealthStatus.ORPHAN,
                icon=self.ICONS[HealthStatus.ORPHAN],
                reasons=["No connections to other memories"]
            )
        
        return HealthReport(
            status=HealthStatus.HEALTHY,
            icon=self.ICONS[HealthStatus.HEALTHY],
            reasons=["Active and connected"]
        )
    
    def detect_potential_conflict(
        self,
        memory_a_id: str,
        memory_a_concepts: list[str],
        memory_a_domain: str,
        memory_b_id: str,
        memory_b_concepts: list[str],
        memory_b_domain: str,
    ) -> Optional[ConflictReport]:
        """
        Check if two memories MIGHT conflict.
        
        Returns ConflictReport if:
        - Same domain AND
        - Concept overlap > threshold (default 60%)
        
        Soft detection only - flags for user review, never auto-asserts.
        """
        # Different domains can't conflict (different contexts)
        if memory_a_domain != memory_b_domain:
            return None
        
        set_a = set(memory_a_concepts) if memory_a_concepts else set()
        set_b = set(memory_b_concepts) if memory_b_concepts else set()
        
        # Need concepts to detect conflict
        if not set_a or not set_b:
            return None
        
        # Jaccard similarity
        intersection = set_a & set_b
        union = set_a | set_b
        overlap = len(intersection) / len(union)
        
        if overlap < self.conflict_threshold:
            return None
        
        shared = list(intersection)[:3]
        return ConflictReport(
            memory_a_id=memory_a_id,
            memory_b_id=memory_b_id,
            overlap=overlap,
            shared_concepts=shared,
            reason=f"High concept overlap ({overlap:.0%}): {', '.join(shared)}"
        )
    
    def analyze_all(
        self,
        memories: list[dict],
    ) -> tuple[dict[str, HealthReport], list[ConflictReport]]:
        """
        Batch analyze: compute health for all + detect all conflicts.
        
        Args:
            memories: List of dicts with keys:
                - id: str
                - concepts: list[str]
                - domain: str
                - days_since_access: int
                - connection_count: int
                - superseded_by_id: Optional[str]
                - potential_conflicts: Optional[list[str]]
        
        Returns:
            - health_map: {memory_id: HealthReport}
            - conflicts: list of ConflictReport
        """
        health_map: dict[str, HealthReport] = {}
        conflicts: list[ConflictReport] = []
        
        # First pass: compute health for each memory
        for mem in memories:
            health = self.compute_health(
                superseded_by_id=mem.get("superseded_by_id"),
                potential_conflicts=mem.get("potential_conflicts"),
                days_since_access=mem.get("days_since_access", 0),
                connection_count=mem.get("connection_count", 0),
            )
            health_map[mem["id"]] = health
        
        # Second pass: detect conflicts between pairs (O(n²) but n is small)
        n = len(memories)
        for i in range(n):
            for j in range(i + 1, n):
                mem_a = memories[i]
                mem_b = memories[j]
                
                conflict = self.detect_potential_conflict(
                    memory_a_id=mem_a["id"],
                    memory_a_concepts=mem_a.get("concepts", []),
                    memory_a_domain=mem_a.get("domain", "general"),
                    memory_b_id=mem_b["id"],
                    memory_b_concepts=mem_b.get("concepts", []),
                    memory_b_domain=mem_b.get("domain", "general"),
                )
                
                if conflict:
                    conflicts.append(conflict)
        
        return health_map, conflicts
