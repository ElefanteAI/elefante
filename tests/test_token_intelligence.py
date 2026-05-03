# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_token_intelligence.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : Token counting accuracy, density scoring, session ledger, and
#           TOKEN_STATS injection in MCP tool responses.
# RUN     : pytest tests/test_token_intelligence.py -v
# WHEN    : After any change to src/utils/token_counter.py or TOKEN_STATS
#           injection logic in server.py.
# ─────────────────────────────────────────────────────────────────────────────
"""
Tests for token intelligence: token counting, density scoring, session ledger,
and MCP server integration.

Run: pytest tests/test_token_intelligence.py -v
"""

import json
import pytest

from src.utils.token_counter import (
    estimate_tokens,
    estimate_tokens_json,
    token_density_score,
    TYPE_TOKEN_BUDGETS,
    CallTokenSnapshot,
    SessionTokenLedger,
)


# ============================================================================
# UNIT: estimate_tokens
# ============================================================================

class TestEstimateTokens:
    """Heuristic token counter: len(text) / 3.5, minimum 1."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        result = estimate_tokens("hello")
        assert result >= 1

    def test_typical_sentence(self):
        text = "Elefante is a local-first persistent memory engine for AI agents."
        tokens = estimate_tokens(text)
        # ~67 chars / 3.5 = ~19 tokens
        assert 15 <= tokens <= 25

    def test_json_payload(self):
        obj = {"success": True, "count": 5, "results": [{"id": "abc", "content": "test memory"}]}
        tokens = estimate_tokens_json(obj)
        assert tokens > 0
        # JSON string is longer than content alone
        assert tokens > estimate_tokens("test memory")

    def test_large_content(self):
        text = "x" * 10000
        tokens = estimate_tokens(text)
        # 10000 / 3.5 = ~2857
        assert 2800 <= tokens <= 2900

    def test_returns_int(self):
        assert isinstance(estimate_tokens("any text"), int)


# ============================================================================
# UNIT: token_density_score
# ============================================================================

class TestTokenDensity:
    """Token density = actual tokens / type budget. <=1.0 is within budget."""

    def test_specification_within_budget(self):
        # 800 budget, 400 tokens = 0.5
        score = token_density_score(400, "specification")
        assert score == 0.5

    def test_specification_at_budget(self):
        score = token_density_score(800, "specification")
        assert score == 1.0

    def test_note_over_budget(self):
        # 150 budget, 450 tokens = 3.0
        score = token_density_score(450, "note")
        assert score == 3.0

    def test_insight_generous_budget(self):
        # Insights earn their tokens (500 budget)
        score = token_density_score(500, "insight")
        assert score == 1.0

    def test_conversation_tight_budget(self):
        # Conversations should be compact (100 budget)
        score = token_density_score(300, "conversation")
        assert score == 3.0

    def test_unknown_type_uses_default(self):
        score = token_density_score(300, "nonexistent_type")
        # Default budget is 300
        assert score == 1.0

    def test_all_types_have_budgets(self):
        """Every known memory type has an explicit budget."""
        from src.models.memory import MemoryType
        for mt in MemoryType:
            assert mt.value in TYPE_TOKEN_BUDGETS, f"Missing budget for {mt.value}"


# ============================================================================
# UNIT: CallTokenSnapshot
# ============================================================================

class TestCallTokenSnapshot:

    def test_signal_ratio_with_overhead(self):
        snap = CallTokenSnapshot(
            tool_name="test", input_tokens=100,
            output_tokens=1000, overhead_tokens=600, context_tokens=400,
        )
        # signal_ratio = (1000 - 600) / 1000 = 0.4
        assert snap.signal_ratio == 0.4

    def test_signal_ratio_zero_output(self):
        snap = CallTokenSnapshot(
            tool_name="test", input_tokens=50,
            output_tokens=0, overhead_tokens=0, context_tokens=0,
        )
        assert snap.signal_ratio == 0.0

    def test_signal_ratio_all_overhead(self):
        snap = CallTokenSnapshot(
            tool_name="test", input_tokens=50,
            output_tokens=500, overhead_tokens=500, context_tokens=0,
        )
        # signal_ratio = (500 - 500) / 500 = 0.0
        assert snap.signal_ratio == 0.0

    def test_signal_ratio_no_overhead(self):
        snap = CallTokenSnapshot(
            tool_name="test", input_tokens=50,
            output_tokens=500, overhead_tokens=0, context_tokens=200,
        )
        assert snap.signal_ratio == 1.0

    def test_negative_tokens_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            CallTokenSnapshot(
                tool_name="test", input_tokens=-10,
                output_tokens=100, overhead_tokens=50, context_tokens=20,
            )


# ============================================================================
# UNIT: SessionTokenLedger
# ============================================================================

class TestSessionTokenLedger:

    def test_empty_ledger(self):
        ledger = SessionTokenLedger()
        assert ledger.call_count == 0
        assert ledger.avg_input_tokens == 0.0
        assert ledger.overhead_ratio == 0.0
        assert ledger.signal_ratio == 0.0

    def test_single_record(self):
        ledger = SessionTokenLedger()
        snap = CallTokenSnapshot(
            tool_name="elefante-Memory",
            input_tokens=100, output_tokens=2000,
            overhead_tokens=1200, context_tokens=800,
        )
        ledger.record(snap)
        assert ledger.call_count == 1
        assert ledger.avg_input_tokens == 100.0
        assert ledger.avg_output_tokens == 2000.0
        assert ledger.overhead_ratio == 0.6
        assert ledger.signal_ratio == 0.4

    def test_multiple_records(self):
        ledger = SessionTokenLedger()
        for i in range(10):
            ledger.record(CallTokenSnapshot(
                tool_name=f"tool-{i}",
                input_tokens=50, output_tokens=1000,
                overhead_tokens=600, context_tokens=400,
            ))
        assert ledger.call_count == 10
        assert ledger.total_input_tokens == 500
        assert ledger.total_output_tokens == 10000

    def test_record_count_survives_many(self):
        ledger = SessionTokenLedger()
        for i in range(60):
            ledger.record(CallTokenSnapshot(
                tool_name=f"tool-{i}",
                input_tokens=10, output_tokens=100,
                overhead_tokens=50, context_tokens=50,
            ))
        assert ledger.call_count == 60
        assert ledger.total_output_tokens == 6000

    def test_to_dict(self):
        ledger = SessionTokenLedger()
        ledger.record(CallTokenSnapshot(
            tool_name="test", input_tokens=100,
            output_tokens=500, overhead_tokens=300, context_tokens=200,
        ))
        d = ledger.to_dict()
        assert d["call_count"] == 1
        assert d["signal_ratio"] == 0.4
        assert "overhead_ratio" in d
        assert "avg_input_tokens" in d


# ============================================================================
# INTEGRATION: MCP Server token wiring
# ============================================================================

class TestMCPServerTokenIntegration:
    """Verify token intelligence is wired into the MCP server."""

    def test_server_has_token_ledger(self):
        from src.mcp.server import ElefanteMCPServer
        server = ElefanteMCPServer()
        assert hasattr(server, "_token_ledger")
        assert isinstance(server._token_ledger, SessionTokenLedger)

    def test_record_and_inject_produces_token_stats(self):
        from src.mcp.server import ElefanteMCPServer
        server = ElefanteMCPServer()
        result = {"success": True, "data": "test"}

        result = server._record_and_inject_token_stats(result, "test-tool", 50)
        assert "TOKEN_STATS" in result
        stats = result["TOKEN_STATS"]
        assert "output_tokens" in stats
        assert "overhead_tokens" in stats
        assert "signal_ratio" in stats
        assert stats["output_tokens"] > 0
        # ADV-006 + ADV-013: TOKEN_STATS own overhead is now dynamically measured
        assert stats["overhead_tokens"] >= 15, "TOKEN_STATS block itself must be counted"
        # Slim format: only 3 fields
        assert len(stats) == 3

    def test_overhead_measured_from_protocols(self):
        from src.mcp.server import ElefanteMCPServer
        server = ElefanteMCPServer()

        result = {"success": True}
        result = server._inject_pitfalls(result, "elefante-Memory")
        result = server._inject_entrypoint_protocol(result)
        result = server._inject_directives(result)

        overhead = server._measure_overhead_tokens(result)
        assert overhead > 0, "Protocol injection should produce measurable overhead"
        # Protocols + entrypoint + directives should be substantial
        assert overhead > 100, f"Expected significant overhead, got {overhead}"

    def test_context_measured_when_present(self):
        from src.mcp.server import ElefanteMCPServer
        server = ElefanteMCPServer()

        result = {
            "success": True,
            "RELEVANT_CONTEXT": {
                "note": "Auto-surfaced memories",
                "memories": ["[0.85] Some relevant memory content here..."],
            }
        }
        ctx_tokens = server._measure_context_tokens(result)
        assert ctx_tokens > 0

    def test_context_zero_when_absent(self):
        from src.mcp.server import ElefanteMCPServer
        server = ElefanteMCPServer()
        result = {"success": True}
        assert server._measure_context_tokens(result) == 0

    def test_ledger_accumulates_across_calls(self):
        from src.mcp.server import ElefanteMCPServer
        server = ElefanteMCPServer()

        for _ in range(3):
            result = {"success": True, "data": "x" * 100}
            server._record_and_inject_token_stats(result, "test", 50)

        assert server._token_ledger.call_count == 3
        assert server._token_ledger.total_input_tokens == 150


# ============================================================================
# ADV-004: Multilingual token estimation
# ============================================================================

class TestMultilingualTokens:
    """Non-ASCII text should produce higher token counts per character."""

    def test_chinese_text_higher_token_ratio(self):
        # Chinese: ~2 chars/token, so 100 chars should yield ~50 tokens
        chinese = "\u4f60\u597d" * 50  # 100 chars
        english = "hello" * 20         # 100 chars
        cn_tokens = estimate_tokens(chinese)
        en_tokens = estimate_tokens(english)
        assert cn_tokens > en_tokens, "CJK text should produce more tokens than English of same length"

    def test_arabic_text_higher_token_ratio(self):
        arabic = "\u0645\u0631\u062d\u0628\u0627" * 20  # 100 chars
        english = "hello" * 20
        ar_tokens = estimate_tokens(arabic)
        en_tokens = estimate_tokens(english)
        assert ar_tokens > en_tokens

    def test_mixed_content_blended(self):
        mixed = "Hello " + "\u4f60\u597d" * 47  # ~6 ASCII + 94 CJK = 100 chars
        tokens = estimate_tokens(mixed)
        # Should be between pure English and pure CJK rates
        assert tokens > 28  # above pure English rate (100/3.5)
        assert tokens < 55  # below worst case

    def test_pure_ascii_uses_base_ratio(self):
        text = "a" * 350
        tokens = estimate_tokens(text)
        assert tokens == 100  # 350 / 3.5 = 100

    def test_type_error_on_non_string(self):
        with pytest.raises(TypeError, match="expects str"):
            estimate_tokens(12345)

        with pytest.raises(TypeError, match="expects str"):
            estimate_tokens(None)


# ============================================================================
# ADV-008: system_metadata roundtrip (VectorStore persistence)
# ============================================================================

class TestSystemMetadataRoundtrip:
    """Verify system_metadata survives the VectorStore write/read cycle."""

    def test_parse_system_metadata_from_json_string(self):
        from src.core.vector_store import _parse_system_metadata
        metadata = {"system_metadata": '{"content_tokens": 42, "token_density": 0.95}'}
        result = _parse_system_metadata(metadata, {})
        assert result["content_tokens"] == 42
        assert result["token_density"] == 0.95

    def test_parse_system_metadata_from_dict(self):
        from src.core.vector_store import _parse_system_metadata
        metadata = {"system_metadata": {"content_tokens": 42}}
        result = _parse_system_metadata(metadata, {})
        assert result["content_tokens"] == 42

    def test_parse_system_metadata_from_custom_fallback(self):
        from src.core.vector_store import _parse_system_metadata
        custom = {"system_metadata": '{"content_tokens": 99}'}
        result = _parse_system_metadata({}, custom)
        assert result["content_tokens"] == 99

    def test_parse_system_metadata_missing(self):
        from src.core.vector_store import _parse_system_metadata
        result = _parse_system_metadata({}, {})
        assert result == {}

    def test_parse_system_metadata_invalid_json(self):
        from src.core.vector_store import _parse_system_metadata
        metadata = {"system_metadata": "not-json-{{}"}
        result = _parse_system_metadata(metadata, {})
        assert result == {}
