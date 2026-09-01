"""Regression checks for the dashboard retrieval-evidence presentation."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "src" / "dashboard" / "ui" / "src"


def _read(relative_path: str) -> str:
    return (UI_SRC / relative_path).read_text(encoding="utf-8")


def test_retrieval_explanation_uses_only_dashboard_search_evidence() -> None:
    explanation = _read("components/RetrievalExplanation.tsx")

    assert "result.similarity" in explanation
    assert "metadata.source" in explanation
    assert "metadata.health_status" in explanation
    assert "metadata.health_reason" in explanation
    assert "metadata.connection_count" in explanation
    assert "edgeEndpoints(edge)" in explanation
    assert "Snapshot search ratio" in explanation
    assert "The dashboard API does not expose the MCP retriever" in explanation
    assert "result.vector_score" not in explanation
    assert "result.concept_score" not in explanation


def test_search_selection_wires_rank_and_snapshot_relationships_to_detail_panel() -> None:
    memories = _read("components/MemoriesTab.tsx")
    detail_panel = _read("components/MemoryDetailPanel.tsx")

    assert "selectedSearchResultIndex" in memories
    assert "rank: selectedSearchResultIndex + 1" in memories
    assert "total: results.length" in memories
    assert "edges: snapshot?.edges || []" in memories
    assert "retrievalEvidence={selectedSearchResult ?" in memories
    assert "retrievalEvidence?: RetrievalEvidence" in detail_panel
    assert "<RetrievalExplanation memory={memory} evidence={retrievalEvidence}" in detail_panel


def test_search_rows_keep_snapshot_vitality_separate_from_lexical_match() -> None:
    memories = _read("components/MemoriesTab.tsx")

    assert "score: Number.isFinite(Number(r.metadata?.score))" in memories
    assert "score: r.similarity" not in memories


def test_home_correct_uses_named_verified_routes_and_customer_safe_lifecycle() -> None:
    correction = _read("components/CorrectionDialog.tsx")
    detail_panel = _read("components/MemoryDetailPanel.tsx")
    store = _read("store.ts")

    assert "/control/corrections/plan" in store
    assert "/control/corrections/apply" in store
    assert "window.history.replaceState" in store
    assert "CORRECTION_ACTIONS" in store
    assert "'permanent_delete'" in store
    assert "createPortal" in correction
    assert 'role="dialog"' in correction
    assert 'aria-modal="true"' in correction
    assert "single-use plan ticket" in correction
    assert "temporary verified safety backup" in correction
    assert "Failure restores it; success destroys it" in correction
    assert "Type DELETE to continue" in correction
    assert "This cannot be recovered after success" in correction
    assert "confirm_permanent: confirmPermanent" in store
    assert "verified_correction_history" in detail_panel


def test_home_remember_explains_saved_recall_cue_and_safe_rollback() -> None:
    dialog = _read("components/HomeMemoryDialog.tsx")
    store = _read("store.ts")

    assert "project-only Recall cue" in dialog
    assert "Remember did not complete" in dialog
    assert "Rollback verified · the attempted memory was removed." in dialog
    assert "<ReceiptChecks result={rememberResult} />" in dialog
    assert "RECALL_POSTCONDITION_FAILED" in store
    assert "Nothing was saved." in store


def test_memory_detail_accepts_list_or_text_metadata_without_crashing() -> None:
    detail_panel = _read("components/MemoryDetailPanel.tsx")

    assert "const tags = parseListValue(p.tags);" in detail_panel
    assert "const concepts = parseListValue(p.concepts);" in detail_panel
    assert "const recallCues = parseListValue(p.recall_cues);" in detail_panel
    assert "Recall questions" in detail_panel
    assert 'label="Source verified"' in detail_panel
    assert 'label="Verified"' not in detail_panel
    assert "p.tags.split" not in detail_panel


def test_home_recover_exposes_verified_backup_and_restore_without_path_override() -> None:
    recover = _read("components/RecoverTab.tsx")
    store = _read("store.ts")
    types = _read("types.ts")
    app = _read("App.tsx")
    tabs = _read("components/TabNav.tsx")

    assert "/control/recovery/plan" in store
    assert "/control/recovery/apply" in store
    assert "Inspect backup" in recover
    assert "Check health" in recover
    assert "Check product readiness" in recover
    assert "One safe next action" in recover
    assert "runtime, agent connection, Recall, and verified backup evidence" in recover
    assert "useState<RecoveryAction>('health')" in recover
    assert "normalizeRecoveryHealth" in store
    assert "const requiresHealth = action === 'health';" in store
    assert "health.diagnostic_codes" not in recover
    assert "Create verified backup" in recover
    assert "briefly pause memory writes" in recover
    assert "Find verified backups" in recover
    assert "Managed backup location" in recover
    assert "backup_directory: string" in types
    assert "Inspect selected backup" in recover
    assert "Private Recall check" in recover
    assert "Restore with rollback protection" in recover
    assert "question is not written to the recovery receipt" in recover
    assert "Recover receipt" in recover
    assert "Verified data restore" in recover
    assert "Preview support report" in recover
    assert "Report preview" in recover
    assert "Never included" in recover
    assert "Create and download report" in recover
    assert "Nothing was transmitted" in recover
    assert "Privacy-safe support report" in recover
    assert "/control/recovery/support-report/download" in store
    assert "downloadSupportReport" in store
    assert "action === 'support_report'" in recover
    assert "Product maintenance" in recover
    assert "One safe package handoff" in recover
    assert "Repair recommended" in recover
    assert "Roll back code" in recover
    assert "matching this installed build" in recover
    assert "running app never replaces or removes itself" in recover
    assert "Return and verify" in recover
    assert "Permanent memory deletion" in recover
    assert "Correct · verified gate" in recover
    assert "package_maintenance" in store
    assert "rawReceipt.status !== 'RUNNING'" in store
    assert "status: RecoveryTerminalStatus | 'RUNNING';" in types
    assert 'type="text"' not in recover
    assert "archive_name" in store
    assert "verification_question" in store
    assert "<RecoverTab />" in app
    assert "{ id: 'recover', label: 'Recover' }" in tabs

    execute_recovery = re.search(
        r"const executeRecovery = async \(\) => \{(?P<body>.*?)\n  \};",
        recover,
        re.DOTALL,
    )
    assert execute_recovery is not None
    execute_body = execute_recovery.group("body")
    assert "setVerificationQuestion('');" in execute_body
    assert execute_body.index("setVerificationQuestion('');") < execute_body.index(
        "setReceipt(result.receipt ?? null);"
    )

    apply_recovery = store[
        store.index("applyRecoveryPlan: async"):
        store.index("downloadSupportReport: async")
    ]
    assert "action === 'restore'" in apply_recovery
    assert "rawStatus === 'VERIFIED_COMPLETE'" in apply_recovery
    assert "await get().refreshSnapshot();" in apply_recovery
    assert "selectedMemoryIds: []" in apply_recovery
    assert "inspectedMemoryId: null" in apply_recovery


def test_home_leads_with_one_elefante_product_model_and_three_operator_jobs() -> None:
    home = _read("components/HomeStatePanel.tsx")
    overview = _read("components/OverviewTab.tsx")
    store = _read("store.ts")
    types = _read("types.ts")
    tabs = _read("components/TabNav.tsx")

    assert "Elefante control room" in home
    assert "Make memory useful for the next task." in home
    assert "selects governed decisions, constraints, preferences, facts, and lessons" in home
    assert "Understand the memory system" in home
    assert "Improve what Elefante supplies" in home
    assert "Protect and recover" in home
    assert "No project is required" in home
    assert "Required for task-scoped Recall and changes—not global inspection" in home
    assert "Recommended next" in home
    assert "Memory corpus" in home
    assert "Review queue" in home
    assert "Task boundary" in home
    assert "Recovery evidence" in home
    assert "requestRecoveryPlan('health')" in home
    assert "activeProjectId" in home
    assert "{project.root}" not in home
    assert "HomeStatePanel" in overview
    assert "active_project_id" in store
    assert "window.history.replaceState" in store
    assert "connected_agents: string[]" in types
    assert "{ id: 'overview', label: 'Home' }" in tabs


def test_dashboard_keeps_environment_state_as_evidence_not_a_second_product() -> None:
    home = _read("components/HomeStatePanel.tsx")
    store = _read("store.ts")
    types = _read("types.ts")
    header = _read("components/HeaderBar.tsx")
    app = _read("App.tsx")

    assert "Example workspace" in home
    assert "No operational receipt in this environment" in home
    assert "CONTROL_ORIGIN_UNAVAILABLE" in store
    assert "controlAvailability: ControlAvailability" in store
    assert "snapshot_context?: SnapshotContext" in types
    assert "Example workspace" in header
    assert "example workspace" in app
    combined = home + app + header
    assert "installed Elefante Home" not in combined
    assert "Dashboard preview" not in combined
    assert "8000" not in combined
    assert "8001" not in combined


def test_home_summary_is_compact_snapshot_evidence_not_a_random_memory_story() -> None:
    home = _read("components/HomeStatePanel.tsx")
    overview = _read("components/OverviewTab.tsx")

    assert "Current evidence" in home
    assert "Memory corpus" in home
    assert "Review queue" in home
    assert "Health or lifecycle evidence; not a truth grade" in home
    assert "Advanced: Session Intelligence" in overview
    assert "chooseMaintenanceFocus" not in overview
    assert "Memory Maintenance Briefing" not in overview
    assert "Snapshot evidence" not in overview


def test_recall_never_claims_proof_before_a_live_result_exists() -> None:
    recall = _read("components/RecallTab.tsx")

    assert "Prove what memory Elefante would supply." in recall
    assert "No Recall evidence yet" in recall
    assert "1 · Confirm project" in recall
    assert "2 · Ask one question" in recall
    assert "3 · Inspect the receipt" in recall
    result_block = recall[recall.index("{result && copy && ("):]
    assert "What this proves" in result_block
    assert result_block.index("What this proves") < result_block.index("What it does not prove")


def test_projects_and_recover_explain_value_without_dead_controls_or_address_handoffs() -> None:
    projects = _read("components/ProjectsTab.tsx")
    recover = _read("components/RecoverTab.tsx")

    assert "Example project boundary" in projects
    assert "Projects prevent unrelated work from sharing Recall context" in projects
    assert "Overall memory inspection does not require a project" in projects
    assert "Protect Elefante before changing durable state." in recover
    assert "No recovery evidence yet" in recover
    assert "Capability is not presented as readiness" in recover
    assert "Live control" in recover
    assert "Requires verified plan" in recover
    assert "Advanced: product maintenance" in recover
    assert "Available now" not in recover
    assert "installed Home" not in projects + recover


def test_connections_names_snapshot_metrics_without_truth_claims() -> None:
    connections = _read("components/ExploreTab.tsx")
    vitality = _read("components/CalendarHeatmap.tsx")
    graph = _read("components/KnowledgeGraph.tsx")
    topics = _read("components/TopicTreemap.tsx")

    assert "label: 'Vitality'" in connections
    assert "Stored vitality & type breakdown" in connections
    assert "Stored vitality distribution" in vitality
    assert "Highest vitality memories" in vitality
    assert "avg vitality" in topics
    assert "avg score" not in topics
    assert "Trace one represented decision" in graph
    assert "current truth won" not in graph


def test_dashboard_uses_the_preservation_first_six_workspace_navigation() -> None:
    app = _read("App.tsx")
    tabs = _read("components/TabNav.tsx")
    types = _read("types.ts")
    recall = _read("components/RecallTab.tsx")

    for entry in (
        "{ id: 'overview', label: 'Home' }",
        "{ id: 'recall', label: 'Recall' }",
        "{ id: 'memories', label: 'Memory Intelligence' }",
        "{ id: 'explore', label: 'Connections' }",
        "{ id: 'projects', label: 'Projects' }",
        "{ id: 'recover', label: 'Recover' }",
    ):
        assert entry in tabs

    assert "'overview' | 'recall' | 'memories' | 'explore' | 'projects' | 'recover'" in types
    assert "import { RecallTab }" in app
    assert "case 'recall':" in app
    assert "return <RecallTab />;" in app
    assert "'6': 'recover'" in app
    assert "1/2/3/4/5/6 to switch views" in app
    assert "Recall Inspector" in recall
    assert "Run Recall Check" in recall
    assert "result.selected_count" in recall
    assert "result?.selected_memory_ids" in recall
    assert "result.conflict_count" in recall
    assert "result.project?.name" in recall
    assert "formatVerifiedAt(result.verified_at)" in recall
    assert "no memory content is returned to Home" in recall
    assert "What it does not prove" in recall


def test_dashboard_defaults_to_clear_light_and_preserves_dark_theme() -> None:
    app = _read("App.tsx")
    header = _read("components/HeaderBar.tsx")
    styles = _read("index.css")
    tailwind = (ROOT / "src" / "dashboard" / "ui" / "tailwind.config.js").read_text(encoding="utf-8")

    assert "=== 'dark' ? 'dark' : 'light'" in app
    assert "document.documentElement.dataset.theme = theme" in app
    assert "elefante-dashboard-theme" in app
    assert "onToggleTheme" in header
    assert "Switch to ${theme === 'light' ? 'dark' : 'light'} theme" in header
    assert "grid min-h-[104px] grid-cols-1" in header
    assert "sm:min-h-[72px] sm:flex" in header
    assert "flex w-full min-w-0 items-center justify-between" in header
    assert '<span className="sm:hidden">' in header
    assert 'color-scheme: light' in styles
    assert ':root[data-theme="dark"]' in styles
    assert 'color-scheme: dark' in styles
    assert "token('slate-950')" in tailwind
    assert "100: token('cyan-100')" in tailwind
    assert "200: token('violet-200')" in tailwind


def test_dashboard_html_guide_matches_the_source_prototype_boundary() -> None:
    guide = (ROOT / "docs" / "how-to" / "view-dashboard.html").read_text(encoding="utf-8")

    assert "source prototype checked 2026-09-01" in guide
    assert "This work did not replace the installed runtime or publish a package" in guide
    assert "Home has six top-level workspaces" in guide
    assert "Recall: test governed selection" in guide
    assert "Make memory useful for the next task" in guide
    assert "Global understanding" in guide
    assert "Task intelligence" in guide
    assert "Continuity" in guide
    assert "Memory Intelligence: inspect and review" in guide
    assert "New browser profiles start in high-contrast light" in guide
    assert "Home has five top-level views" not in guide
    assert "Continuity briefing" not in guide


def test_home_summary_is_evidence_not_unbound_recall_claims() -> None:
    home = _read("components/HomeStatePanel.tsx")
    overview = _read("components/OverviewTab.tsx")

    assert "Health or lifecycle evidence; not a truth grade" in home
    assert "Missing relationships and task relevance are never inferred" in home
    assert "correction is not implied" in home
    assert "chooseMaintenanceFocus" not in overview
    assert "shaping your next answer" not in overview
    assert "What compatible agents carry forward" not in overview
    assert "retrieved by agents" not in overview
    assert "Why this memory endures" not in overview


def test_memory_intelligence_and_connections_preserve_distinct_operator_jobs() -> None:
    memories = _read("components/MemoriesTab.tsx")
    connections = _read("components/ExploreTab.tsx")
    insights = _read("components/CalendarHeatmap.tsx")

    assert "Memory Intelligence" in memories
    assert "Library · {memories.length}" in memories
    assert "Review · {reviewCount}" in memories
    assert "View scope: all memories, read only" in memories
    assert "does not grade truth, usefulness" in memories
    assert "visibleMemories" in memories
    assert "Connections" in connections
    assert "Decision Graph" in connections
    assert "Missing links and causal claims are not inferred" in connections
    assert "Number(score) >= 80" in insights
    assert "Number(score) >= 60" in insights
    assert "Number(score) >= 8 ?" not in insights


def test_home_first_run_explains_project_boundary_and_memory_policy() -> None:
    home = _read("components/HomeStatePanel.tsx")

    assert "No project is required" in home
    assert "project is required only for task-scoped Recall and changes" in home
    assert "Remember durable guidance" in home
    assert "never secrets or full transcripts" in home
    assert "Capability is not readiness until a check returns a receipt" in home


def test_direct_localhost_home_establishes_its_own_bounded_session() -> None:
    home = _read("components/HomeStatePanel.tsx")
    store = _read("store.ts")
    app = _read("App.tsx")

    assert "fetch('/api/control-config'" in store
    assert "/control/session" in store
    assert "cache: 'no-store'" in store
    assert "credentials: 'omit'" in store
    assert "live local session" in app
    assert "Open Home through Elefante first." not in home
    assert "manually typed localhost URL" not in home
    assert "browser connector" not in (home + store + app).casefold()
    assert "8000" not in home + app
    assert "8001" not in home + app


def test_home_remember_and_manual_recall_are_project_safe_verified_actions() -> None:
    home = _read("components/HomeStatePanel.tsx")
    dialog = _read("components/HomeMemoryDialog.tsx")
    recall = _read("components/RecallTab.tsx")
    store = _read("store.ts")
    types = _read("types.ts")

    assert "setMemoryDialog('remember')" in home
    assert "Improve what Elefante supplies" in home
    assert "setActiveTab('recall')" in home
    assert "<HomeMemoryDialog" in home
    assert "testRecall(question.trim())" in recall
    assert "/control/remember" in store
    assert "/control/remember/apply" in store
    assert "/control/recall/test" in store
    assert "memory_content_returned !== false" in store
    assert "Remember did not return one complete verification receipt" in store
    assert "isLoading: get().snapshot === null" in store
    for kind in ("Decision", "Constraint", "Preference", "Lesson"):
        assert f"label: '{kind}'" in dialog
    for choice in ("Update existing", "Supersede existing", "Keep both", "Cancel"):
        assert choice in dialog
    assert "Remember and verify" in dialog
    assert "Remember verified" in dialog
    assert "Recall passed" in dialog
    assert "Their private content stayed in the agent path" in dialog
    assert 'role="dialog"' in dialog
    assert 'aria-modal="true"' in dialog
    assert "export type KnowledgeKind" in types
    assert "export interface RememberReceipt" in types
    assert "export interface RecallTestResponse" in types


def test_projects_review_and_verify_legacy_unassigned_memories() -> None:
    projects = _read("components/ProjectsTab.tsx")
    review = _read("components/ProjectReviewPanel.tsx")
    store = _read("store.ts")
    types = _read("types.ts")

    assert "<ProjectReviewPanel />" in projects
    assert "Cross-project delivery is disabled" in projects
    assert "Isolated projects · Sharing off" in projects
    assert "shared_across_projects?: false" in types
    assert "projectReview.total_unscoped === 0" in projects
    assert "Review every unassigned legacy memory" in projects
    assert "Elefante never guesses from their text" in review
    assert "Assign and verify" in review
    assert "Project assignment verified" in review
    assert "Its protection remains unchanged" in review
    assert "/control/projects/unscoped/list" in store
    assert "/control/projects/unscoped/plan" in store
    assert "/control/projects/unscoped/apply" in store
    assert "normalizeProjectAssignmentReceipt" in store
    assert "export interface ProjectReviewResponse" in types
    assert "export interface ProjectAssignmentReceipt" in types
