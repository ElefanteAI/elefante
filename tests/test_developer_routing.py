# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_developer_routing.py
# VERSION : 2.5.2
# CHANGED : 2026-04-16
# PROVES  : Self-protocol verifier routing and contract: dashboard snapshot path
#           resolution, large-payload stream sizing, protocol verification,
#           and developer-process token-discipline guidance.
# RUN     : pytest tests/test_developer_routing.py -v
# WHEN    : After changes to server.py routing, verify_e2e_tests.py, or the
#           self-protocol verification contract. Required before each release.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations
import re
import subprocess
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
        "agents/orchestrator.md": _read("agents/orchestrator.md"),
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


def test_active_user_and_runtime_routes_do_not_reference_retired_debug_docs() -> None:
    active_paths = (
        "src/mcp/server.py",
        "agents/orchestrator.md",
        "docs/how-to/agent-handoff.md",
        "docs/how-to/install.md",
        "docs/how-to/rollback.md",
        "workspace/ISSUES.md",
        "workspace/lessons.md",
        "workspace/proposals/README.md",
        "workspace/proposals/ide-integration-surface.md",
        "workspace/proposals/session-intelligence.md",
        "workspace/proposals/tool-consolidation.md",
    )

    retired_routes = (
        "docs/debug/",
        "docs/technical/",
        "ops-memory-compendium.md",
        "spec-ide-integration-surface.md",
        "spec-session-intelligence.md",
    )
    violations = [
        f"{path}: {route}"
        for path in active_paths
        for route in retired_routes
        if route in _read(path)
    ]
    assert not violations, "\n".join(violations)

    lessons = _read("workspace/lessons.md")
    assert "../../" not in lessons
    assert not any(
        f"]({domain}.md" in lessons
        for domain in ("ai-behavior", "dashboard", "database", "installation", "memory")
    )


def test_active_developer_routing_points_to_current_sources() -> None:
    directive_store = _read("src/core/directive_store.py")
    orchestrator = _read("src/core/orchestrator.py")
    orchestrator_doc = _read("agents/orchestrator.md")

    assert "workspace/ISSUES.md" in directive_store
    assert "concrete assumption" in directive_store

    assert "workspace/ISSUES.md for issue routing" in orchestrator
    assert "docs/reference/architecture.md" in orchestrator
    assert "ci/bump_version.py" in orchestrator

    assert "workspace/ISSUES.md" in orchestrator_doc
    assert "confirm or falsify it" in orchestrator_doc
    assert "all 20 tools" not in orchestrator_doc or "20 tools" in orchestrator_doc


def test_living_plan_tracks_the_released_product_and_separate_client_candidate() -> None:
    planning = _read("workspace/PLANNING.md")

    assert "## §2 Released Product: v2.12.1 Memory Intelligence" in planning
    assert "### §3.1 v2.11.1 — Shipped baseline" in planning
    assert "### §3.2 v2.12.0 — Released" in planning
    assert "### §3.3 Release Client Candidate 1.0" in planning
    assert "## §2 Active Release: v2.10.0" not in planning
    assert "## §2 Active Release: v2.12.0" not in planning
    assert "### §3.2 v2.12.0 — Active release candidate" not in planning
    assert "P1–P6 are open" not in planning
    assert "| OB4 |" not in planning
    assert "| OB5 |" not in planning
    assert "source-grounded" in planning
    assert "**PUBLISHED_PRODUCT:** v2.12.1 remains live and unchanged." in planning
    assert "**PUBLICATION_AUTHORIZED:** YES" in planning


def test_active_tool_docs_match_current_mcp_surface() -> None:
    readme = _read("README.md")
    docs_index = _read("docs/README.md")
    spec_tools = _read("docs/reference/tools.md")
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

    startup_guide = _read("docs/how-to/run-mcp-server.md")
    self_protocol = _read("docs/reference/self-protocol.md")
    verifier = _read("scripts/verify/verify_e2e_tests.py")
    default_tool_count = tool_count - 1  # DashboardOpen is opt-in by design.
    assert f"Available MCP Tools: {tool_count}" in startup_guide
    assert "Available MCP Tools: 21" not in startup_guide
    assert f"{default_tool_count}/{tool_count} tools" in verifier
    assert f"{default_tool_count} of {tool_count} tools" in self_protocol

    assert "docs/technical/dashboard.md" not in readme
    assert "docs/how-to/view-dashboard.md" in readme


def test_changelog_contract_is_synced_across_docs_and_embedded_rules() -> None:
    changelog = _read("CHANGELOG.md")
    orchestrator_doc = _read("agents/orchestrator.md")
    dev_etiquette = _read("docs/how-to/close-a-feature.md")
    directive_store = _read("src/core/directive_store.py")
    orchestrator = _read("src/core/orchestrator.py")

    for heading in ("### Added", "### Fixed", "### Changed"):
        assert heading in changelog
        assert heading in orchestrator_doc
        assert heading in dev_etiquette
        assert heading in directive_store
        assert heading in orchestrator

    assert "### The Problem Solved" not in orchestrator_doc
    assert "### The Solution" not in orchestrator_doc
    assert "Never use retired headings" in dev_etiquette
    assert "### The Problem Solved" in dev_etiquette
    assert "### The Solution" in dev_etiquette

    assert "scripts/ci/bump_version.py" in orchestrator_doc
    assert "scripts/ci/bump_version.py" in dev_etiquette
    assert "scripts/ci/bump_version.py" in directive_store
    assert "scripts/ci/bump_version.py" in orchestrator


def test_debug_feedback_loop_docs_are_linked() -> None:
    issues = _read("workspace/ISSUES.md")
    orchestrator_doc = _read("agents/orchestrator.md")
    lessons = _read("workspace/lessons.md")
    docs_index = _read("docs/README.md")

    assert "best_practices.md" in issues or "lessons.md" in issues
    assert "best_practices.md" in orchestrator_doc or "lessons.md" in orchestrator_doc
    assert "agents/orchestrator.md" in lessons or "../agents/orchestrator.md" in lessons
    assert "README.md" in lessons
    assert "tests/README.md" in lessons
    assert "workspace/" not in docs_index
    assert "postmortems/" not in docs_index


def test_readme_and_planning_docs_capture_installer_recovery_and_learning_boundaries() -> None:
    readme = _read("README.md")
    proposals_readme = _read("workspace/proposals/README.md")
    docs_index = _read("docs/README.md")

    assert "Install Elefante.command" in readme
    assert "Signed and notarized native macOS packaging is Upcoming." in readme
    assert "native AppKit installer surface" not in readme
    assert "If installation fails:" in readme
    assert ".elefante-install-summary.txt" in readme
    assert ".elefante-install-status.txt" in readme
    assert ".elefante-install.log" in readme

    assert "installer-procedure.md" in proposals_readme

    assert "workspace/proposals" not in docs_index
    assert "memory-identity.md" not in docs_index
    assert "close-a-feature.md" not in docs_index


def test_active_release_claims_avoid_stale_version_promises() -> None:
    """Active entrypoints must not present completed release targets as future."""
    active_paths = (
        "AGENTS.md",
        "README.md",
        "docs/README.md",
        "docs/explanation/vision.md",
        "docs/reference/architecture.md",
        "docs/reference/tools.md",
        "agents/manifests/ide-integration.yaml",
    )
    stale_patterns = (
        r"currently at \*\*v2\.(?:9|10)",
        r"current:\s*\*\*v2\.(?:9|10)",
        r"v2\.10(?:\.0)? is in design",
        r"v2\.11\.0 plan",
        r"planned-v2\.(?:11|12)",
        r"planned for v2\.(?:11|12)",
        r"latest published release:\s*\**v2\.11\.1",
        r"current published release:\s*\**v2\.11\.1",
        r"active release candidate:\s*\**v2\.12\.0",
        r"v2\.12\.0\*{0,2}\s*(?:—|-)\s*release candidate",
        r"v2\.12\.0\*{0,2}\s+release candidate",
    )

    violations = []
    for path in active_paths:
        text = _read(path)
        for pattern in stale_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"{path}: {pattern}")

    assert not violations, "\n".join(violations)


def test_developer_process_docs_enforce_question_first_token_discipline() -> None:
    orchestrator_doc = _read("agents/orchestrator.md")
    best_practices = _read("workspace/lessons.md")
    spec_vision = _read("docs/explanation/vision.md")

    assert "State the concrete diagnostic question before opening more files" in orchestrator_doc
    assert "smallest maintained proof" in orchestrator_doc
    assert "decision-bearing facts" in orchestrator_doc
    assert "maximum decision value per token" in orchestrator_doc.lower() or "Maximum decision value per token" in orchestrator_doc
    assert "Required Progress Update Template" in orchestrator_doc
    assert "Question: What exact uncertainty is being resolved right now?" in orchestrator_doc
    assert "Proof: What smallest maintained proof is being run or read?" in orchestrator_doc
    assert "Result: What changed because of that proof?" in orchestrator_doc
    assert "Next: What is the immediate next move?" in orchestrator_doc

    assert "Question-First" in orchestrator_doc
    assert "repeated summaries are noise" in orchestrator_doc

    assert "Question-First Routing Maximizes Quality Per Token" in best_practices
    assert "smallest maintained proof" in best_practices
    assert "quality per token" in best_practices.lower()

    assert "Full Signal Injection" in spec_vision


def test_installer_docs_route_bug_020_through_screenshot_first_verification() -> None:
    debug_index = _read("workspace/ISSUES.md")
    install_compendium = _read("workspace/postmortems/installation.md")

    assert "Screenshot first → native compile → install smoke; widget-tree inspection only if screenshot fails" in debug_index
    assert "Question-First Verification Path" in install_compendium
    assert "start with the narrowest customer-visible question" in install_compendium
    assert "Only if the screenshot is still broken, inspect widget existence separately" in install_compendium
    assert "quality-per-token path for installer UX bugs" in install_compendium


def test_best_practices_capture_installer_failure_file_routing() -> None:
    best_practices = _read("workspace/lessons.md")

    assert "Installer Failures Must End With Persisted File Routing" in best_practices
    assert "Installer UI Must Expose Recovery Files Before Failure" in best_practices
    assert "summary file first, status file second, log file third" in best_practices
    assert "Show the persisted summary, status, and log file paths directly in the installer UI" in best_practices
    assert "persisted installer files survive" in best_practices or "persisted installer files survive a closed terminal" in best_practices
    assert "check the logs above" in best_practices


def test_self_protocol_docs_are_linked() -> None:
    docs_index = _read("docs/README.md")
    scripts_readme = _read("scripts/README.md")
    tests_readme = _read("tests/README.md")
    protocol_doc = _read("docs/reference/self-protocol.md")

    assert "self-protocol.md" in docs_index
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
    protocol_doc = _read("docs/reference/self-protocol.md")
    tool_names, prompt_names = _mcp_surface_names()

    assert "Full-Surface Coverage Map" in protocol_doc
    for name in sorted(tool_names | prompt_names):
        assert name in protocol_doc


def test_spec_tools_documents_prompt_arguments_and_conditional_context_contract() -> None:
    spec_tools = _read("docs/reference/tools.md")

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
        protocol_doc = _read("docs/reference/self-protocol.md")

        assert 'temp_home / ".elefante" / "data" / "dashboard_snapshot.json"' in harness
        assert 'temp_data_dir / "dashboard_snapshot.json"' in harness
        assert "candidate_snapshot_paths" in harness
        assert "Snapshot verification must follow the live runtime path" in protocol_doc


def test_no_forbidden_filename_patterns_in_active_docs_or_agents() -> None:
    """BUG-026 active guard: fail on date-stamped, version-stamped, or generic-dump filenames
    in `docs/`, `agents/`, or `workspace/`. Source-of-truth: `agents/orchestrator.md`
    Documentation Skill § Forbidden Patterns. Pre-guard recurrence count: 3x in a single session
    (2026-05-02), demonstrating the passive-protocol failure class. Guard fires on FILENAMES only;
    historical text references inside docs and `CHANGELOG.md` historical prose are deliberate
    anchors and are NOT scanned.

    Scope expanded 2026-05-02 to include `workspace/` (developer-workspace surface created same day).
    """
    import fnmatch

    forbidden_patterns = [
        "HANDOFF-*",
        "spec-v[0-9]*-*",
        "NOTES*",
        "scratch*",
        "todo*",
        "ideas-new*",
        "CURRENT_STATE*",
        "IDEA-[0-9]*",
        "session-summary*",
    ]

    violations: list[str] = []
    for surface in ("docs", "agents", "workspace"):
        surface_root = ROOT / surface
        if not surface_root.exists():
            continue
        for path in surface_root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            for pattern in forbidden_patterns:
                if fnmatch.fnmatchcase(name, pattern):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}: matches forbidden pattern '{pattern}'"
                    )
                    break

    assert not violations, "\n".join([
        "BUG-026 active guard fired: forbidden filename patterns found in active docs/, agents/, or workspace/.",
        *violations,
        "",
        "These patterns are forbidden per agents/orchestrator.md Documentation Skill § Forbidden Patterns.",
        "Historical text references inside docs and CHANGELOG.md prose are deliberate anchors; this guard scans filenames only.",
        "See: workspace/ISSUES.md BUG-026 row + workspace/postmortems/ai-behavior.md Issue #12.",
    ])
