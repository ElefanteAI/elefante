# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_developer_routing.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : Self-protocol verifier routing and contract: dashboard snapshot path
#           resolution, large-payload stream sizing, and protocol verification.
# RUN     : pytest tests/test_developer_routing.py -v
# WHEN    : After changes to server.py routing, verify_e2e_tests.py, or the
#           self-protocol verification contract. Required before each release.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _mcp_surface_counts() -> tuple[int, int]:
    server = _read("src/mcp/server.py")
    return server.count("types.Tool("), server.count("Prompt(")


def _mcp_surface_names() -> tuple[set[str], set[str]]:
    server = _read("src/mcp/server.py")
    tool_names = set(re.findall(r'types\.Tool\(\s*name="(elefante-[^"]+)"', server, re.DOTALL))
    prompt_names = set(re.findall(r'Prompt\(\s*name="(elefante-[^"]+)"', server, re.DOTALL))
    return tool_names, prompt_names


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


def test_changelog_contract_is_synced_across_docs_and_embedded_rules() -> None:
    changelog = _read("CHANGELOG.md")
    dev_sdd = _read("docs/technical/dev-sdd.md")
    dev_etiquette = _read("docs/technical/dev-etiquette.md")
    directive_store = _read("src/core/directive_store.py")
    orchestrator = _read("src/core/orchestrator.py")

    for heading in ("### Added", "### Fixed", "### Changed"):
        assert heading in changelog
        assert heading in dev_sdd
        assert heading in dev_etiquette
        assert heading in directive_store
        assert heading in orchestrator

    assert "### The Problem Solved" not in dev_sdd
    assert "### The Solution" not in dev_sdd
    assert "### Changes" not in dev_sdd
    assert "Never use retired headings" in dev_etiquette
    assert "### The Problem Solved" in dev_etiquette
    assert "### The Solution" in dev_etiquette

    assert "scripts/ci/bump_version.py" in dev_sdd
    assert "scripts/ci/bump_version.py" in dev_etiquette
    assert "scripts/ci/bump_version.py" in directive_store
    assert "scripts/ci/bump_version.py" in orchestrator


def test_debug_feedback_loop_docs_are_linked() -> None:
    debug_index = _read("docs/debug/README.md")
    developer_agent = _read("docs/debug/dev-developer-agent.md")
    best_practices = _read("docs/debug/best_practices.md")

    assert "best_practices.md" in debug_index
    assert "best_practices.md" in developer_agent
    assert "dev-developer-agent.md" in best_practices
    assert "README.md" in best_practices
    assert "tests/README.md" in best_practices


def test_self_protocol_docs_are_linked() -> None:
    debug_index = _read("docs/debug/README.md")
    docs_index = _read("docs/README.md")
    scripts_readme = _read("scripts/README.md")
    tests_readme = _read("tests/README.md")
    protocol_doc = _read("docs/debug/self-elefante-protocol.md")

    assert "self-elefante-protocol.md" in debug_index
    assert "self-elefante-protocol.md" in docs_index
    assert "verify_e2e_tests.py" in protocol_doc
    assert "--with-dashboard-open" in protocol_doc
    assert "self-protocol" in scripts_readme
    assert "self-protocol" in tests_readme


def test_list_mcp_tools_script_reports_tools_and_prompts_separately() -> None:
    tool_names, prompt_names = _mcp_surface_names()
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ci" / "list_mcp_tools.py")],
        capture_output=True,
        text=True,
        check=True,
    )

    output = result.stdout
    assert f"Available MCP Tools: {len(tool_names)}" in output
    assert f"Available MCP Prompts: {len(prompt_names)}" in output

    for name in sorted(tool_names | prompt_names):
        assert name in output


def test_self_protocol_doc_lists_live_tools_and_prompts() -> None:
    protocol_doc = _read("docs/debug/self-elefante-protocol.md")
    tool_names, prompt_names = _mcp_surface_names()

    assert "Full-Surface Coverage Map" in protocol_doc
    for name in sorted(tool_names | prompt_names):
        assert name in protocol_doc


def test_spec_tools_documents_prompt_arguments_and_conditional_context_contract() -> None:
    spec_tools = _read("docs/technical/spec-tools.md")

    assert "`RELEVANT_CONTEXT` is conditional, not universal" in spec_tools
    assert "`topic` (required, string): What topic to retrieve context for." in spec_tools
    assert "This prompt performs a live hybrid memory search before returning content." in spec_tools


def test_scripts_readme_covers_live_script_inventory() -> None:
    scripts_readme = _read("scripts/README.md")
    scripts_root = ROOT / "scripts"

    live_scripts = sorted(
        path.relative_to(ROOT).as_posix()
        for pattern in ("**/*.py", "**/*.sh")
        for path in scripts_root.glob(pattern)
        if path.is_file()
    )

    for rel_path in live_scripts:
        assert Path(rel_path).name in scripts_readme, f"{rel_path} missing from scripts/README.md"

    for section in (
        "## `scripts/setup/`",
        "## `scripts/verify/`",
        "## `scripts/lifecycle/`",
        "## `scripts/ci/`",
        "## `scripts/pipeline/`",
        "## `scripts/debug/`",
        "## `scripts/privileged/`",
    ):
        assert section in scripts_readme


def test_privileged_script_docstrings_use_live_command_names() -> None:
    delete_script = _read("scripts/privileged/delete_memories_surgical.py")
    inspect_script = _read("scripts/privileged/inspect_memory_graph.py")

    assert "scripts/privileged/delete_memories_surgical.py" in delete_script
    assert "memory_surgeon.py" not in delete_script
    assert "scripts/privileged/inspect_memory_graph.py" in inspect_script
    assert "memory_workbench.py" not in inspect_script
    assert "delete_memories_surgical.py" in inspect_script


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
