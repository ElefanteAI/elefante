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


def test_home_opens_with_one_product_state_and_four_customer_actions() -> None:
    home = _read("components/HomeStatePanel.tsx")
    overview = _read("components/OverviewTab.tsx")
    store = _read("store.ts")
    types = _read("types.ts")
    tabs = _read("components/TabNav.tsx")

    for state in (
        "Ready",
        "Setup required",
        "Needs attention",
        "Recovery required",
        "Unsupported",
    ):
        assert state in home
    for action in ("Remember", "Test Recall", "Correct", "Recover"):
        assert f'title="{action}"' in home

    assert "Current product state" in home
    assert "One safe next action" in home
    assert "Connected agent" in home
    assert "Active project" in home
    assert "Last verified Recall" in home
    assert "Last verified backup" in home
    assert "requestRecoveryPlan('health')" in home
    assert "activeProjectId" in home
    assert "{project.root}" not in home
    assert "HomeStatePanel" in overview
    assert "active_project_id" in store
    assert "window.history.replaceState" in store
    assert "connected_agents: string[]" in types
    assert "{ id: 'overview', label: 'Home' }" in tabs


def test_home_remember_and_manual_recall_are_project_safe_verified_actions() -> None:
    home = _read("components/HomeStatePanel.tsx")
    dialog = _read("components/HomeMemoryDialog.tsx")
    store = _read("store.ts")
    types = _read("types.ts")

    assert "Remember here" in home
    assert "Ask a Recall question" in home
    assert "<HomeMemoryDialog" in home
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
