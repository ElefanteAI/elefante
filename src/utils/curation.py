# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/utils/curation.py
# PURPOSE : Deterministic (no LLM) curation helpers: generate title/summary
#           fields at ingestion time and during batch backfills.
# ROLE    : Utils — called by orchestrator.py and ETL pipeline at write time.
# TOUCHED : When changing title generation rules, summary truncation, or
#           the fields that get auto-populated on MemoryAdd.
# ─────────────────────────────────────────────────────────────────────────────
"""Deterministic curation helpers (no LLMs).

These utilities are used to ensure memories have reasonable `title` and `summary`
fields at ingestion time and during batch backfills.

Keep these functions cheap, stable, and side-effect free.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from src.models.memory import HealthStatus, Memory, MemoryStatus


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
    max_len: int = 90,
) -> str:
    cleaned = strip_codeblocks(content or "")
    cleaned = collapse_ws(cleaned)

    words = cleaned.split()
    core = " ".join(words[:10]) if words else "Memory"
    return truncate(core, max_len) or "Memory"


def generate_summary(*, content: str, max_len: int = 200) -> str:
    cleaned = strip_codeblocks(content or "")
    s = first_sentence(cleaned)
    if not s:
        s = collapse_ws(cleaned)
    return truncate(s, max_len) or ""


# ============================================================================
# COGNITIVE RETRIEVAL HELPERS
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
    Generate candidate query patterns for future proactive surfacing.

    The current retriever stores and displays these values but does not use
    them as a ranking signal.
    
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


def compute_authority_score(
    score: int,
    access_count: int,
    days_since_created: int,
    days_since_accessed: int,
    memory_type: str = "",
) -> float:
    """
    Compute authority score for retrieval ranking.
    
    Combines score, usage, and freshness.
    """
    if memory_type.lower() in ("specification", "directive"):
        return 1.0

    import math
    
    # Normalize score (0-100 → 0.0-1.0)
    score_factor = score / 100.0
    
    # Access factor (logarithmic, saturates around 50 accesses)
    access_factor = min(1.0, math.log(access_count + 1) / math.log(50))
    
    # Freshness decay (half-life of 90 days for creation)
    creation_decay = math.exp(-0.007 * days_since_created)
    
    # Recent access boost (half-life of 14 days)
    access_decay = math.exp(-0.05 * days_since_accessed)
    
    # Weighted combination
    score = (
        0.35 * score_factor +
        0.25 * access_factor +
        0.20 * creation_decay +
        0.20 * access_decay
    )
    
    return round(min(1.0, max(0.0, score)), 3)

HEALTH_STALE_AFTER_DAYS = 90


@dataclass(frozen=True)
class HealthAssessment:
    """Deterministic, explainable health result for one memory."""

    status: HealthStatus
    reason: str
    days_since_access: int
    connection_count: int


def _coerce_utc_naive(value: Any, fallback: datetime) -> datetime:
    """Normalize supported timestamps so aware and legacy-naive values compare safely."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            value = None
    if not isinstance(value, datetime):
        return fallback
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _safe_connection_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _has_value(value: Any) -> bool:
    """Treat empty persisted JSON/list representations as absent."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "none", "null", "[]", "{}"}
    try:
        return len(value) > 0
    except TypeError:
        return bool(value)


def assess_health_values(
    *,
    status: Any,
    conflict_ids: Any,
    superseded_by_id: Any,
    last_accessed: Any,
    connection_count: Any,
    now: Optional[datetime] = None,
) -> HealthAssessment:
    """Assess health from model or persisted values without mutating state.

    The priority is explicit: contradictory/superseded memories are at risk;
    otherwise memories not accessed for more than 90 days are stale; otherwise
    memories with no graph connection are orphans; all remaining memories are
    healthy.  This is an inspection signal, not an automatic repair decision.
    """
    current = _coerce_utc_naive(now, datetime.utcnow())
    accessed = _coerce_utc_naive(last_accessed, current)
    days_since_access = max(0, int((current - accessed).total_seconds() // 86400))
    connections = _safe_connection_count(connection_count)
    status_value = getattr(status, "value", status)
    status_value = str(status_value or "").strip().lower()

    if _has_value(superseded_by_id):
        return HealthAssessment(
            status=HealthStatus.AT_RISK,
            reason="superseded by a newer memory",
            days_since_access=days_since_access,
            connection_count=connections,
        )
    if status_value == MemoryStatus.CONTRADICTORY.value or _has_value(conflict_ids):
        return HealthAssessment(
            status=HealthStatus.AT_RISK,
            reason="has an unresolved contradiction",
            days_since_access=days_since_access,
            connection_count=connections,
        )
    if days_since_access > HEALTH_STALE_AFTER_DAYS:
        return HealthAssessment(
            status=HealthStatus.STALE,
            reason=f"not accessed for {days_since_access} days",
            days_since_access=days_since_access,
            connection_count=connections,
        )
    if connections == 0:
        return HealthAssessment(
            status=HealthStatus.ORPHAN,
            reason="has no graph connections",
            days_since_access=days_since_access,
            connection_count=connections,
        )
    return HealthAssessment(
        status=HealthStatus.HEALTHY,
        reason="current and connected",
        days_since_access=days_since_access,
        connection_count=connections,
    )


def assess_health(
    memory: Memory,
    connection_count: int,
    *,
    now: Optional[datetime] = None,
) -> HealthAssessment:
    """Assess one ``Memory`` using its canonical metadata fields."""
    metadata = memory.metadata
    return assess_health_values(
        status=metadata.status,
        conflict_ids=metadata.conflict_ids,
        superseded_by_id=metadata.superseded_by_id,
        last_accessed=metadata.last_accessed,
        connection_count=connection_count,
        now=now,
    )


def assess_health_from_raw(
    metadata: Mapping[str, Any],
    connection_count: int,
    *,
    now: Optional[datetime] = None,
) -> HealthAssessment:
    """Assess a raw vector-store metadata mapping with the same rules."""
    return assess_health_values(
        status=metadata.get("status"),
        conflict_ids=metadata.get("conflict_ids"),
        superseded_by_id=metadata.get("superseded_by_id"),
        last_accessed=metadata.get("last_accessed"),
        connection_count=connection_count,
        now=now,
    )


def compute_health(memory: Memory, connection_count: int) -> HealthStatus:
    """Backward-compatible status-only API backed by the canonical assessment."""
    return assess_health(memory, connection_count).status
