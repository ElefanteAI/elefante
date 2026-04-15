# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/utils/token_counter.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Heuristic token counting and TOKEN_STATS injection for all MCP
#           tool responses; negligible CPU cost; multilingual support.
# ROLE    : Utils — called by server.py to inject TOKEN_STATS on every response.
# TOUCHED : When changing token budget constants (per memory type), heuristic
#           counting formula, CJK/Arabic ratio blending, or the TOKEN_STATS
#           field names exposed in tool responses.
# ─────────────────────────────────────────────────────────────────────────────
"""
Token counting and intelligence for Elefante.

Power-aware design: default heuristic has negligible CPU cost.
The accurate tokenizer path is opt-in and piggybacks on the
sentence-transformers model already loaded by EmbeddingService.

Token budget philosophy:
  Tokens should be proportional to insight value.
  A specification that saves hours is worth 500 tokens.
  A note that decays in 46 days should be compact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ============================================================================
# EXPECTED TOKEN DENSITY BY MEMORY TYPE
# Higher = more tokens acceptable for that type.
# Used to compute proportionality score (actual / expected_max).
#
# Rationale (linked to memory type half-lives in spec-memory-schema.md):
#   specification (800): Immutable authority (authority=1.0), rarely accessed
#       but immensely valuable. Specs justify length because they prevent
#       re-derivation of architecture decisions.
#   directive (200): Injected into EVERY response. Must be concise to avoid
#       compounding overhead across hundreds of calls.
#   insight (500): Variable-length patterns with high reuse (access_count > 5
#       typical). Worth the tokens because they transfer learning across tasks.
#   decision (400): Need enough context to explain WHY, not just WHAT.
#   preference (300): Stable over ~347 days. Moderate length.
#   fact (250): Atomic truths. Should not need paragraphs.
#   note (150): Decays in ~46 days. Keep lean — if it needs more tokens,
#       it should probably be an insight or decision.
#   conversation (100): Ephemeral (~28 days). Minimal footprint.
# ============================================================================

TYPE_TOKEN_BUDGETS: Dict[str, int] = {
    "specification": 800,
    "directive": 200,
    "preference": 300,
    "decision": 400,
    "fact": 250,
    "insight": 500,
    "note": 150,
    "conversation": 100,
}

DEFAULT_TOKEN_BUDGET = 300


def _non_ascii_ratio(text: str) -> float:
    """Fraction of characters that are non-ASCII (CJK, Arabic, etc.)."""
    if not text:
        return 0.0
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return non_ascii / len(text)


def estimate_tokens(text: str) -> int:
    """Fast heuristic token count. Negligible CPU cost.

    Base ratio: ~3.5 chars/token for English/JSON blended content.
    For text with significant non-ASCII content (CJK, Arabic, Cyrillic),
    the ratio drops toward ~2 chars/token because tokenizers split
    multi-byte characters into more subword tokens.
    """
    if not isinstance(text, str):
        raise TypeError(f"estimate_tokens expects str, got {type(text).__name__}")
    if not text:
        return 0
    ratio = 3.5
    na_ratio = _non_ascii_ratio(text)
    if na_ratio > 0.1:
        # Blend: mostly non-ASCII → ~2.0 chars/token
        ratio = 3.5 - (1.5 * min(na_ratio, 1.0))
    return max(1, int(len(text) / ratio))


def estimate_tokens_json(obj: Any) -> int:
    """Estimate tokens for a JSON-serializable object."""
    try:
        text = json.dumps(obj, default=str)
    except (TypeError, ValueError):
        text = str(obj)
    return estimate_tokens(text)


def token_density_score(token_count: int, memory_type: str) -> float:
    """How proportional is this memory's token count to its type budget?

    Returns a ratio where:
      <= 1.0 means within budget (good)
      > 1.0 means over budget (may need trimming)

    This is NOT a quality judgment. An insight at 1.3x is fine.
    A conversation at 3.0x is a signal to consolidate.
    """
    budget = TYPE_TOKEN_BUDGETS.get(memory_type, DEFAULT_TOKEN_BUDGET)
    if budget == 0:
        return 0.0
    return round(token_count / budget, 3)


# ============================================================================
# SESSION TOKEN LEDGER
# In-memory accumulator, lives on the MCP server instance.
# Resets per server lifecycle. No persistence needed.
# ============================================================================

@dataclass
class CallTokenSnapshot:
    """Token breakdown for a single tool call."""
    tool_name: str
    input_tokens: int
    output_tokens: int
    overhead_tokens: int
    context_tokens: int

    def __post_init__(self):
        for name in ("input_tokens", "output_tokens", "overhead_tokens", "context_tokens"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative, got {getattr(self, name)}")

    @property
    def signal_ratio(self) -> float:
        """Fraction of output that is actual payload (not protocol overhead).
        Higher = more of the response is useful content.
        1.0 = zero overhead. 0.0 = all overhead.
        """
        if self.output_tokens == 0:
            return 0.0
        return round(max(0.0, (self.output_tokens - self.overhead_tokens) / self.output_tokens), 3)


@dataclass
class SessionTokenLedger:
    """Accumulates token stats across a server session."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_overhead_tokens: int = 0
    total_context_tokens: int = 0
    call_count: int = 0

    def record(self, snapshot: CallTokenSnapshot) -> None:
        self.total_input_tokens += snapshot.input_tokens
        self.total_output_tokens += snapshot.output_tokens
        self.total_overhead_tokens += snapshot.overhead_tokens
        self.total_context_tokens += snapshot.context_tokens
        self.call_count += 1

    @property
    def avg_input_tokens(self) -> float:
        if self.call_count == 0:
            return 0.0
        return round(self.total_input_tokens / self.call_count, 1)

    @property
    def avg_output_tokens(self) -> float:
        if self.call_count == 0:
            return 0.0
        return round(self.total_output_tokens / self.call_count, 1)

    @property
    def overhead_ratio(self) -> float:
        """What fraction of all output is static overhead?"""
        if self.total_output_tokens == 0:
            return 0.0
        return round(self.total_overhead_tokens / self.total_output_tokens, 3)

    @property
    def signal_ratio(self) -> float:
        """Session-level signal ratio: fraction of output that is payload."""
        if self.total_output_tokens == 0:
            return 0.0
        return round(max(0.0, (self.total_output_tokens - self.total_overhead_tokens) / self.total_output_tokens), 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_count": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_overhead_tokens": self.total_overhead_tokens,
            "total_context_tokens": self.total_context_tokens,
            "avg_input_tokens": self.avg_input_tokens,
            "avg_output_tokens": self.avg_output_tokens,
            "overhead_ratio": self.overhead_ratio,
            "signal_ratio": self.signal_ratio,
        }
