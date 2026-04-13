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
