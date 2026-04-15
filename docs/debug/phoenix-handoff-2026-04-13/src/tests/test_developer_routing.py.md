# Annotated Excerpt: tests/test_developer_routing.py

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _mcp_surface_counts() -> tuple[int, int]:
    server = _read("src/mcp/server.py")
    return server.count("types.Tool("), server.count("Prompt(")


def test_active_developer_routing_avoids_retired_paths() -> None:
    files = {
        "src/core/directive_store.py": _read("src/core/directive_store.py"),
        "src/core/orchestrator.py": _read("src/core/orchestrator.py"),
        "docs/technical/dev-sdd.md": _read("docs/technical/dev-sdd.md"),
    }

    stale_paths = {
        "docs/pitfall-index.md",
        "docs/technical/sdd-development-protocol.md",
        "docs/technical/developer-etiquette.md",
        "docs/technical/architecture.md",
        "scripts/bump_version.py",
    }

    violations: list[str] = []
    for rel_path, text in files.items():
        for stale_path in stale_paths:
            if stale_path in text:
                violations.append(f"{rel_path}: stale reference -> {stale_path}")

    assert not violations, "\n".join(violations)


def test_active_developer_routing_points_to_current_sources() -> None:
    # Supposed to do:
    # keep the live developer-process contract pointed at current sources.
    #
    # Current failure for the next session:
    # this test checks routing strings and tool-count wording, but it does not
    # assert the live CHANGELOG heading contract. Because of that gap,
    # docs/technical/dev-sdd.md can still contain the obsolete
    # "The Problem Solved / The Solution / Changes" wording while this test stays green.
    #
    # Debugging already done:
    # - compared dev-sdd.md against CHANGELOG.md and confirmed the mismatch is real
    # - verified pytest tests/test_developer_routing.py -v still passes because this assertion is missing
    directive_store = _read("src/core/directive_store.py")
    orchestrator = _read("src/core/orchestrator.py")
    dev_sdd = _read("docs/technical/dev-sdd.md")

    assert "docs/debug/README.md" in directive_store
    assert "concrete assumption" in directive_store

    assert "docs/debug/README.md for issue routing" in orchestrator
    assert "docs/technical/spec-architecture.md" in orchestrator
    assert "ci/bump_version.py" in orchestrator

    assert "docs/debug/README.md" in dev_sdd
    assert "confirm or falsify it" in dev_sdd
    assert "all 20 tools present" in dev_sdd


def test_active_tool_docs_match_current_mcp_surface() -> None:
    # Supposed to do:
    # guard the active MCP-surface docs against count drift and stale dashboard references.
    #
    # Current status:
    # this test already closed the recent 13-item spec-tools audit. If it stays green,
    # spec-tools count drift is not the blocker.
    readme = _read("README.md")
    docs_index = _read("docs/README.md")
    spec_tools = _read("docs/technical/spec-tools.md")
    tool_count, prompt_count = _mcp_surface_counts()

    assert f"{tool_count} tools · {prompt_count} prompts" in readme
    assert f"{tool_count} tools + {prompt_count} prompts" in readme
    assert f"({tool_count} tools, {prompt_count} prompts)" in docs_index
    assert f"**{tool_count} tools**" in spec_tools
    assert f"**{prompt_count} prompts**" in spec_tools

    assert "21 tools" not in readme
    assert "21 tools" not in docs_index
    assert "MCP Surface (v2.3.0)" not in spec_tools
    assert "active v2.3.0 fields" not in spec_tools

    assert "docs/technical/dashboard.md" not in readme
    assert "docs/technical/ops-dashboard.md" in readme


class TestSelfProtocolContract:
    def test_self_protocol_client_allows_large_tool_payloads(self) -> None:
        harness = _read("scripts/verify/verify_e2e_tests.py")

        assert "STREAM_LIMIT_BYTES = 1024 * 1024" in harness
        assert "limit=STREAM_LIMIT_BYTES" in harness

    def test_self_protocol_dashboard_phase_tracks_runtime_snapshot_path(self) -> None:
        harness = _read("scripts/verify/verify_e2e_tests.py")
        protocol_doc = _read("docs/debug/self-elefante-protocol.md")

        assert 'temp_home / ".elefante" / "data" / "dashboard_snapshot.json"' in harness
        assert 'temp_data_dir / "dashboard_snapshot.json"' in harness
        assert "candidate_snapshot_paths" in harness
        assert "Snapshot verification must follow the live runtime path" in protocol_doc
```