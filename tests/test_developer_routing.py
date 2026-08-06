# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_developer_routing.py
# PROVES  : Self-protocol verifier routing and contract: dashboard snapshot path
#           resolution, large-payload stream sizing, protocol verification,
#           and developer-process token-discipline guidance.
# RUN     : pytest tests/test_developer_routing.py -v
# WHEN    : After changes to server.py routing, verify_e2e_tests.py, or the
#           self-protocol verification contract. Required before each release.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations
import ast
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _current_version() -> str:
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', _read("src/__init__.py"), re.MULTILINE)
    assert match is not None
    return match.group(1)


def _markdown_heading_slug(heading: str) -> str:
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"[`*_~]", "", heading).strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading)
    return re.sub(r" +", "-", heading)


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


def test_operational_docs_use_commands_supported_by_current_clis() -> None:
    operational_paths = [
        *sorted((ROOT / "docs/how-to").glob("*.md")),
        *sorted((ROOT / "agents").glob("*.md")),
        ROOT / "scripts/README.md",
    ]
    retired_forms = (
        "restart_elefante.py --stop",
        "restart_elefante.py --start",
        "manage_lock.py --dry-run",
        "manage_lock.py --release",
        "restore_elefante_data.py <backup-path>",
    )
    violations = [
        f"{path.relative_to(ROOT)}: {form}"
        for path in operational_paths
        for form in retired_forms
        if form in path.read_text(encoding="utf-8")
    ]
    assert not violations, "\n".join(violations)


def test_released_installer_record_is_not_active_task_context() -> None:
    planning = _read("workspace/PLANNING.md")
    proposals_index = _read("workspace/proposals/README.md")
    tasks = _read("benchmarks/task_intelligence/tasks.json")

    design_section = planning.split("### §4.2 In design", 1)[1].split("### §4.3", 1)[0]
    shipped_section = planning.split("### §4.4 Shipped", 1)[1].split("### §4.5", 1)[0]
    assert "installer-procedure.md" not in design_section
    assert "Customer-global installer" in shipped_section
    assert "RETAINED DESIGN RECORD" in proposals_index
    assert "workspace/proposals/installer-procedure.md" not in tasks


def test_four_laws_keep_retrieval_selective_and_project_grounded() -> None:
    planning = _read("workspace/PLANNING.md")
    vision = _read("docs/explanation/vision.md")
    for document in (planning, vision):
        assert "unrelated history" in document
        assert "before a memory write" in document
        assert "Project-specific claims" in document or "project-specific claims" in document
    assert "A session is never new" not in planning


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

    version = _current_version()
    assert f"## §2 Released Product: v{version} Customer-Global Memory Intelligence" in planning
    assert "### §3.1 v2.11.1 — Shipped baseline" in planning
    assert "### §3.2 v2.12.0 — Released" in planning
    assert f"### §3.3 Release Client Candidate 1.0 — released through v{version}" in planning
    assert "## §2 Active Release: v2.10.0" not in planning
    assert "## §2 Active Release: v2.12.0" not in planning
    assert "### §3.2 v2.12.0 — Active release candidate" not in planning
    assert "P1–P6 are open" not in planning
    assert "| OB4 |" not in planning
    assert "| OB5 |" not in planning
    assert "source-grounded" in planning
    assert f"**PUBLISHED_PRODUCT:** v{version}, public GitHub tag and checksummed platform assets." in planning
    assert "**PUBLICATION_AUTHORITY:** no unused authorization." in planning


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

    tool_names, prompt_names = _mcp_surface_names()
    for name in sorted(tool_names | prompt_names):
        assert name in spec_tools

    server = _read("src/mcp/server.py")
    assert '"min_similarity": {"type": "number", "default": 0.1' in server
    assert 'args.get("min_similarity", 0.1)' in server
    assert "default `0.1`" in spec_tools


def test_current_release_version_matches_active_entrypoints() -> None:
    version = _current_version()
    active_release_docs = (
        "AGENTS.md",
        "README.md",
        "docs/README.md",
        "docs/explanation/vision.md",
        "docs/reference/architecture.md",
        "docs/reference/tools.md",
        "workspace/PLANNING.md",
    )

    for path in active_release_docs:
        assert f"v{version}" in _read(path), f"{path} does not name current release v{version}"


def test_python_headers_do_not_claim_manual_product_versions() -> None:
    """Runtime, test, and script banners must not duplicate package version state."""
    violations: list[str] = []
    for root in (ROOT / "src", ROOT / "scripts", ROOT / "tests"):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for field in ("VERSION", "CHANGED", "LASTRUN"):
                if re.search(rf"^# {field}\s*:", text, re.MULTILINE):
                    violations.append(f"{path.relative_to(ROOT)}: manual {field} header")

    assert not violations, "\n".join(violations)


def test_integration_manifest_matches_released_host_selection_contract() -> None:
    """Every installer host must have one explicit, honest manifest tier."""
    manifest = yaml.safe_load(_read("agents/manifests/ide-integration.yaml"))
    surfaces = manifest["surfaces"]
    ids = [surface["id"] for surface in surfaces]
    assert len(ids) == len(set(ids))

    allowed_statuses = {"compatible", "partial", "community", "planned", "deprecated"}
    invalid = [
        f"{surface.get('id')}: {surface.get('status')}"
        for surface in surfaces
        if surface.get("status") not in allowed_statuses
    ]
    assert not invalid, "\n".join(invalid)

    path_statuses = {"configured", "planned", "deprecated"}
    nested_violations: list[str] = []
    for surface in surfaces:
        for group in ("in_repo", "user_home"):
            for item in surface.get(group, []) or []:
                if "installer_writes" in item and not isinstance(item["installer_writes"], bool):
                    nested_violations.append(
                        f"{surface['id']}:{group}:{item.get('path')}: installer_writes must be boolean"
                    )
                if group == "in_repo" and item.get("status") not in path_statuses:
                    nested_violations.append(
                        f"{surface['id']}:{group}:{item.get('path')}: invalid status {item.get('status')}"
                    )
    assert not nested_violations, "\n".join(nested_violations)

    selection_module = ast.parse(_read("scripts/setup/host_selection.py"))
    supported_hosts: tuple[str, ...] | None = None
    for node in selection_module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SUPPORTED_HOSTS"
            for target in node.targets
        ):
            supported_hosts = ast.literal_eval(node.value)
            break
    assert supported_hosts is not None

    by_id = {surface["id"]: surface for surface in surfaces}
    missing = set(supported_hosts).difference(by_id)
    assert not missing, f"installer hosts absent from manifest: {sorted(missing)}"
    for host in supported_hosts:
        assert by_id[host]["status"] in {"compatible", "partial"}, host


def test_released_docs_do_not_use_retired_memory_tool_names() -> None:
    retired = re.compile(r"elefante-Memory(?:Add|Search|Update|Delete|Consolidate)\b")
    violations: list[str] = []
    paths = [ROOT / "README.md", ROOT / ".github" / "copilot-instructions.md"]
    paths.extend(
        path for path in (ROOT / "docs").rglob("*.md")
        if "_archive" not in path.parts
    )
    paths.extend((ROOT / "agents").glob("*.md"))
    for path in paths:
        if retired.search(path.read_text(encoding="utf-8")):
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, "\n".join(violations)


def test_active_bug_guidance_uses_the_consolidated_memory_tool() -> None:
    paths = (
        "workspace/ISSUES.md",
        "workspace/lessons.md",
        "workspace/postmortems/ai-behavior.md",
        "workspace/postmortems/dashboard.md",
        "workspace/postmortems/database.md",
        "workspace/postmortems/installation.md",
        "workspace/postmortems/memory.md",
    )
    retired_names = (
        "MemoryAdd",
        "MemorySearch",
        "MemoryGet",
        "MemoryUpdate",
        "MemoryDelete",
        "MemoryConsolidate",
    )
    violations = [
        f"{path}: {name}"
        for path in paths
        for name in retired_names
        if name in _read(path)
    ]
    assert not violations, "\n".join(violations)


def test_active_markdown_relative_links_resolve() -> None:
    skip_parts = {"_archive", ".git", ".venv", "node_modules"}
    violations: list[str] = []

    for path in ROOT.rglob("*.md"):
        if any(part in skip_parts for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = raw_target.split("#", 1)[0].split(" ", 1)[0].strip("<>")
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.exists():
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{path.relative_to(ROOT)}:{line}: {raw_target}")

    assert not violations, "\n".join(violations)


def test_active_markdown_internal_anchors_resolve() -> None:
    skip_parts = {"_archive", ".git", ".venv", "node_modules"}
    violations: list[str] = []

    for path in ROOT.rglob("*.md"):
        if any(part in skip_parts for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            raw_target = match.group(1).strip()
            if raw_target.startswith(("http://", "https://", "mailto:")) or "#" not in raw_target:
                continue
            target, fragment = raw_target.split("#", 1)
            resolved = (path.parent / unquote(target or path.name)).resolve()
            if not resolved.exists() or resolved.suffix.lower() != ".md":
                continue
            target_text = resolved.read_text(encoding="utf-8")
            anchors = set(re.findall(r'<a\s+id=["\']([^"\']+)', target_text, re.IGNORECASE))
            anchors.update(
                _markdown_heading_slug(heading)
                for heading in re.findall(r"^#{1,6}\s+(.+?)\s*$", target_text, re.MULTILINE)
            )
            if unquote(fragment).lower() not in anchors:
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{path.relative_to(ROOT)}:{line}: {raw_target}")

    assert not violations, "\n".join(violations)


def test_current_instruction_docs_do_not_reference_missing_repo_files() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "CONTRIBUTING.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "agents").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.md")),
        ROOT / "scripts/README.md",
    ]
    path_pattern = re.compile(
        r"`((?:src|scripts|tests|docs|agents|workspace|examples|benchmarks)/"
        r"[^`\s#]+?\.(?:py|md|yaml|yml|json|sh|bat|ts|tsx))(?:#[^`]*)?`"
    )
    violations: list[str] = []
    for document in paths:
        if "_archive" in document.parts:
            continue
        text = document.read_text(encoding="utf-8")
        for match in path_pattern.finditer(text):
            reference = match.group(1).split("::", 1)[0]
            if any(marker in reference for marker in ("<", ">", "*")):
                continue
            if not (ROOT / reference).exists():
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{document.relative_to(ROOT)}:{line}: {reference}")
    assert not violations, "\n".join(violations)


def test_scoring_reference_matches_runtime_contract() -> None:
    scoring_doc = _read("docs/reference/scoring.md")
    memory_model = _read("src/models/memory.py")
    cognitive_scoring = _read("src/core/retrieval.py")

    for rate in ("0.002", "0.005", "0.008", "0.015", "0.025", "0.000"):
        assert rate in scoring_doc
    for weight in ("0.35 * vector", "0.30 * concept", "0.15 * coactivation", "0.10 * authority", "0.10 * temporal"):
        assert weight in scoring_doc

    assert "TYPE_DECAY_RATES" in memory_model
    assert '"vector": 0.35' in cognitive_scoring
    assert "automatic archive" not in scoring_doc.lower()
    assert "5-10ms" not in scoring_doc


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
