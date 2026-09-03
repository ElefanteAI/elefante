"""Regression checks for the dashboard retrieval-evidence presentation."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "src" / "dashboard" / "ui" / "src"


def _read(relative_path: str) -> str:
    return (UI_SRC / relative_path).read_text(encoding="utf-8")


def test_memory_keyboard_controls_share_the_visible_state_and_respect_dialogs() -> None:
    memories = _read("components/MemoriesTab.tsx")
    app = _read("App.tsx")
    assert "const query = useDashboardStore((s) => s.searchQuery)" in memories
    assert "const selectedId = useDashboardStore((s) => s.inspectedMemoryId)" in memories
    assert "[selectedId, setSelectedId] = useState" not in memories
    assert "[query, setQuery] = useState" not in memories
    assert "document.querySelector('[role=\"dialog\"]')" in app
    assert app.index("if (e.key === 'Escape')") < app.index("target.tagName === 'INPUT'")
    assert "searchError && mode === 'search'" in memories
    detail = _read("components/MemoryDetailPanel.tsx")
    assert 'className="absolute right-0 top-0' in detail
    assert 'className="fixed right-0 top-0' not in detail
    assert '!e.defaultPrevented' in detail


def test_real_dashboard_store_preserves_recall_and_reconnects_without_replay() -> None:
    node = shutil.which("node")
    if not node or not (UI_SRC.parent / "node_modules/zustand").is_dir():
        pytest.skip("Requires the dashboard's installed Node dependencies")
    script = f"const storeUrl = {(UI_SRC / 'store.ts').as_uri()!r};\n" + r'''
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const compiled = ts.transpileModule(readFileSync(new URL(storeUrl), 'utf8'), {
  compilerOptions: {module:ts.ModuleKind.ESNext, target:ts.ScriptTarget.ES2022},
}).outputText.replace("from 'zustand'", 'from ' + JSON.stringify(import.meta.resolve('zustand')));
const {useDashboardStore:store} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const project = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const other = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const reply = (body, status = 200) => new Response(JSON.stringify(body), {status});
const ready = () => store.setState({controlEnabled:true, controlAvailability:'available', controlToken:'test-capability-123', controlBaseUrl:'http://127.0.0.1:18765', activeProjectId:project});
const result = {success:true, recall_status:'supplied', selected_memory_ids:['memory-a'], selected_count:1, conflict_count:0, memory_content_returned:false, project:{project_id:project,name:'Atlas'}};
ready();
store.getState().setRecallQuestion('Which database?');
globalThis.fetch = async () => reply(result);
await store.getState().testRecall('Which database?');
store.getState().setActiveTab('memories');
store.getState().setActiveTab('recall');
assert.equal(store.getState().recallQuestion, 'Which database?');
assert.deepEqual(store.getState().recallResult.selected_memory_ids, ['memory-a']);

let calls = 0;
globalThis.fetch = async () => { calls++; return reply({error:'Session expired'},401); };
await store.getState().testRecall('Which database?');
assert.equal(calls,1); // A failed operation is never replayed.
assert.equal(store.getState().controlEnabled,false);
assert.equal(store.getState().controlToken,null);
assert.equal(store.getState().controlAvailability,'unavailable');
assert.match(store.getState().controlSessionError,/expired/);
assert.equal(store.getState().recallQuestion,'Which database?');

globalThis.fetch = async (url) => {
  calls++;
  return reply(url === '/api/control-config'
    ? {available:true,daemon_port:18765}
    : {success:true,token:'renewed-capability-123',project_id:project});
};
await store.getState().initializeControlSession(project);
assert.equal(calls,3); // Discovery + grant only, not a repeated Recall/write.
assert.equal(store.getState().controlEnabled,true);
assert.equal(store.getState().controlSessionError,null);
assert.equal(store.getState().recallQuestion,'Which database?');

globalThis.fetch = async () => reply({error:'Session request limit reached'},429);
await store.getState().requestRecoveryPlan('backup');
assert.equal(store.getState().controlEnabled,false);
assert.match(store.getState().controlSessionError,/limit/);

ready();
let release;
globalThis.fetch = () => new Promise(resolve => { release=resolve; });
store.getState().setRecallQuestion('Old question');
const pending = store.getState().testRecall('Old question');
store.getState().setRecallQuestion('Different question');
release(reply(result));
await pending;
assert.equal(store.getState().recallResult,null); // No stale answer under new input.

globalThis.fetch = async (url) => reply(url === '/api/control-config'
  ? {available:true,daemon_port:18765}
  : {success:true,token:'other-capability-123',project_id:other});
await store.getState().initializeControlSession(other);
assert.equal(store.getState().recallQuestion,'');
assert.equal(store.getState().recallResult,null);
console.log('PASS: continuity, expiry, request limit, explicit reconnect, no replay, input race, project boundary');
'''
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=UI_SRC.parent, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: continuity" in result.stdout


def test_real_dashboard_store_surfaces_stats_and_session_errors_and_clears_on_retry() -> None:
    node = shutil.which("node")
    if not node or not (UI_SRC.parent / "node_modules/zustand").is_dir():
        pytest.skip("Requires the dashboard's installed Node dependencies")
    script = f"const storeUrl = {(UI_SRC / 'store.ts').as_uri()!r};\n" + r'''
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const compiled = ts.transpileModule(readFileSync(new URL(storeUrl), 'utf8'), {
  compilerOptions: {module:ts.ModuleKind.ESNext, target:ts.ScriptTarget.ES2022},
}).outputText.replace("from 'zustand'", 'from ' + JSON.stringify(import.meta.resolve('zustand')));
const {useDashboardStore:store} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const oldStats = {elefante:{package_version:'old'}, vector_store:{total_memories:17}, graph_store:{total_entities:4, total_relationships:3}, snapshot:{generated_at:'old'}};
const oldSession = {consent:{enabled:true}, signal_card:{hypothesis:'old signal'}};
store.setState({stats:oldStats, sessionIntelligence:oldSession, statsError:null, sessionIntelligenceError:null});
const realSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = callback => { callback(); return 0; };
let statsAttempts = 0;
try {
  globalThis.fetch = async url => {
    if (url === '/api/stats') {
      statsAttempts++;
      return new Response(JSON.stringify({error:'Snapshot unavailable'}));
    }
    return new Response(JSON.stringify({error:'Session snapshot unavailable'}), {status:503});
  };
  await store.getState().fetchStats();
  assert.equal(statsAttempts, 5);
  assert.equal(store.getState().stats, null);
  assert.equal(store.getState().statsError, 'Snapshot unavailable');
  await store.getState().fetchSessionIntelligence();
  assert.equal(store.getState().sessionIntelligence, null);
  assert.equal(store.getState().sessionIntelligenceError, 'HTTP 503');

  const nextStats = {elefante:{package_version:'new'}, vector_store:{total_memories:18}, graph_store:{total_entities:5, total_relationships:4}, snapshot:{generated_at:'new'}};
  const nextSession = {consent:{enabled:false}, signal_card:null};
  globalThis.fetch = async url => new Response(JSON.stringify(url === '/api/stats' ? nextStats : nextSession));
  await store.getState().fetchStats();
  await store.getState().fetchSessionIntelligence();
  assert.deepEqual(store.getState().stats, nextStats);
  assert.equal(store.getState().statsError, null);
  assert.deepEqual(store.getState().sessionIntelligence, nextSession);
  assert.equal(store.getState().sessionIntelligenceError, null);
} finally {
  globalThis.setTimeout = realSetTimeout;
}
console.log('PASS: dashboard surface errors clear after successful retry');
'''
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=UI_SRC.parent, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: dashboard surface errors" in result.stdout


def test_dashboard_error_surfaces_render_honest_states() -> None:
    node = shutil.which("node")
    if not node or not (UI_SRC.parent / "node_modules/react-dom").is_dir():
        pytest.skip("Requires the dashboard's installed Node dependencies")
    script = (
        f"const headerUrl = {(UI_SRC / 'components/HeaderBar.tsx').as_uri()!r};\n"
        f"const sessionUrl = {(UI_SRC / 'components/SessionIntelligencePanel.tsx').as_uri()!r};\n"
    ) + r'''
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const moduleUrl = code => 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
const compile = url => ts.transpileModule(readFileSync(new URL(url), 'utf8'), {
  compilerOptions: {module:ts.ModuleKind.ESNext, target:ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX},
}).outputText;
const replaceImport = (code, name, target) => {
  const replacement = 'from ' + JSON.stringify(target);
  return code.replaceAll(`from '${name}'`, replacement).replaceAll(`from "${name}"`, replacement);
};
const storeUrl = moduleUrl('export const useDashboardStore = pick => pick(globalThis.dashboardState);');
const iconsUrl = moduleUrl('export const Moon=()=>null; export const RefreshCw=()=>null; export const Sun=()=>null;');
const runtimeUrl = import.meta.resolve('react/jsx-runtime');
const headerCode = replaceImport(replaceImport(compile(headerUrl), '@/store', storeUrl), 'lucide-react', iconsUrl)
  .replaceAll('from "react/jsx-runtime"', 'from ' + JSON.stringify(runtimeUrl))
  .replaceAll("from 'react/jsx-runtime'", 'from ' + JSON.stringify(runtimeUrl));
const sessionCode = replaceImport(compile(sessionUrl), '@/store', storeUrl)
  .replaceAll('from "react/jsx-runtime"', 'from ' + JSON.stringify(runtimeUrl))
  .replaceAll("from 'react/jsx-runtime'", 'from ' + JSON.stringify(runtimeUrl));
const {HeaderBar} = await import(moduleUrl(headerCode));
const {SessionIntelligencePanel} = await import(moduleUrl(sessionCode));

globalThis.dashboardState = {
  stats:{vector_store:{total_memories:17}, graph_store:{total_entities:4, total_relationships:3}, snapshot:{generated_at:'old'}},
  statsError:'HTTP 503', snapshot:null, isRefreshing:false, refreshSnapshot:()=>{},
};
const headerHtml = renderToStaticMarkup(React.createElement(HeaderBar, {theme:'dark', onToggleTheme:()=>{}}));
assert.match(headerHtml, /Stats unavailable/);
assert.ok(!headerHtml.includes('17 memories'));
assert.ok(!headerHtml.includes('4 entities'));
assert.ok(!headerHtml.includes('3 links'));

globalThis.dashboardState = {
  sessionIntelligence:{consent:{enabled:true}, signal_card:{hypothesis:'old signal'}},
  sessionIntelligenceError:'HTTP 503',
};
const failedSessionHtml = renderToStaticMarkup(React.createElement(SessionIntelligencePanel));
assert.match(failedSessionHtml, /Session Intelligence snapshot unavailable/);
assert.ok(!failedSessionHtml.includes('Off by default.'));

globalThis.dashboardState = {
  sessionIntelligence:{consent:{enabled:false}, signal_card:null},
  sessionIntelligenceError:null,
};
const disabledSessionHtml = renderToStaticMarkup(React.createElement(SessionIntelligencePanel));
assert.match(disabledSessionHtml, /Off by default\./);
console.log('PASS: honest stats and Session Intelligence render states');
'''
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=UI_SRC.parent, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: honest stats" in result.stdout


def test_memory_detail_related_memories_render_as_named_buttons() -> None:
    node = shutil.which("node")
    if not node or not (UI_SRC.parent / "node_modules/react-dom").is_dir():
        pytest.skip("Requires the dashboard's installed Node dependencies")
    script = f"const detailUrl = {(UI_SRC / 'components/MemoryDetailPanel.tsx').as_uri()!r};\n" + r'''
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const moduleUrl = code => 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
const compile = url => ts.transpileModule(readFileSync(new URL(url), 'utf8'), {
  compilerOptions: {module:ts.ModuleKind.ESNext, target:ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX},
}).outputText;
const replaceImport = (code, name, target) => {
  const replacement = 'from ' + JSON.stringify(target);
  return code.replaceAll(`from '${name}'`, replacement).replaceAll(`from "${name}"`, replacement);
};
const iconsUrl = moduleUrl('export const X=()=>null; export const Clock=()=>null; export const Tag=()=>null; export const Layers=()=>null; export const Brain=()=>null; export const Star=()=>null; export const Hash=()=>null; export const Globe=()=>null; export const User=()=>null; export const Check=()=>null;');
const emptyComponentUrl = moduleUrl('export const RetrievalExplanation=()=>null; export const ResolveMemoryDialog=()=>null; export const CorrectionDialog=()=>null;');
const runtimeUrl = import.meta.resolve('react/jsx-runtime');
let detailCode = compile(detailUrl);
detailCode = replaceImport(detailCode, 'lucide-react', iconsUrl);
detailCode = replaceImport(detailCode, '@/components/RetrievalExplanation', emptyComponentUrl);
detailCode = replaceImport(detailCode, '@/components/ResolveMemoryDialog', emptyComponentUrl);
detailCode = replaceImport(detailCode, '@/components/CorrectionDialog', emptyComponentUrl);
detailCode = detailCode.replaceAll('from "react"', 'from ' + JSON.stringify(import.meta.resolve('react')))
  .replaceAll("from 'react'", 'from ' + JSON.stringify(import.meta.resolve('react')))
  .replaceAll('from "react/jsx-runtime"', 'from ' + JSON.stringify(runtimeUrl))
  .replaceAll("from 'react/jsx-runtime'", 'from ' + JSON.stringify(runtimeUrl));
const {MemoryDetailPanel} = await import(moduleUrl(detailCode));
const makeMemory = (id, title) => ({
  id, name:title, type:'memory', description:'Content ' + title, created_at:'2026-09-03T12:00:00Z',
  properties:{content:'Content ' + title, memory_type:'fact', score:80, tags:'', status:'active', archived:false, deprecated:false,
    processing_status:'ready', namespace:'default', title, topic:'testing', summary:title, source:'test', access_count:0,
    last_accessed:'2026-09-03T12:00:00Z'},
});
const html = renderToStaticMarkup(React.createElement(MemoryDetailPanel, {
  memory:makeMemory('memory-a', 'Current memory'),
  relatedMemories:[makeMemory('memory-b', 'Related memory')],
  conflictMemories:[], onClose:()=>{}, onNavigateToMemory:()=>{},
}));
assert.match(html, /<button[^>]*type="button"/);
assert.ok(html.includes('aria-label="Open related memory Related memory"'));
console.log('PASS: related memories render as named native buttons');
'''
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=UI_SRC.parent, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: related memories" in result.stdout


def test_retrieval_explanation_uses_only_dashboard_search_evidence() -> None:
    explanation = _read("components/RetrievalExplanation.tsx")

    assert "result.similarity" in explanation
    assert "metadata.storage_backend" in explanation
    assert "metadata.health_status" in explanation
    assert "metadata.health_reason" in explanation
    assert "metadata.connection_count" in explanation
    assert "edgeEndpoints(edge)" in explanation
    assert "Snapshot search ratio" in explanation
    assert "The dashboard API does not expose the MCP retriever" in explanation
    assert "result.vector_score" not in explanation
    assert "result.concept_score" not in explanation


def test_retrieval_storage_source_never_substitutes_content_provenance() -> None:
    explanation = _read("components/RetrievalExplanation.tsx")

    assert "metadata.storage_backend ?? memory.properties?.storage_backend" in explanation
    assert "metadata.source ?? memory.properties?.source" not in explanation
    assert "'Not reported'" in explanation


def test_recovery_disconnect_keeps_error_and_explicit_reconnect_visible() -> None:
    recover = _read("components/RecoverTab.tsx")
    app = _read("App.tsx")
    locked_start = recover.index("  if (!controlEnabled) {")
    locked_view = recover[locked_start:recover.index("\n  return (", locked_start)]

    assert "recoveryError" in locked_view
    assert "'alert'" in locked_view
    assert "Reconnect Home" in locked_view
    assert "!controlSessionError" in locked_view
    assert "window.location.reload()" in locked_view
    assert "No operation is retried automatically" in locked_view
    assert "No recovery check ran in this environment" not in locked_view
    assert "applyPlan(" not in locked_view
    # The shell is an isolated stacking context; z-index alone cannot beat portals.
    assert 'controlSessionError && !controlEnabled && (' in app
    assert 'relative z-[80] flex shrink-0' in app
    assert app.index('role="alert"') < app.index('className="elefante-shell')


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
    assert "Question that must not return this memory" in correction
    assert "Recall question that currently finds this memory" not in correction
    assert "The temporary safety backup is destroyed after success" in correction
    assert "Older backups are not deleted and may still contain this memory." in correction
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


def test_home_routes_review_recommendations_to_review_and_refreshes_verified_writes() -> None:
    home = _read("components/HomeStatePanel.tsx")
    memories = _read("components/MemoriesTab.tsx")
    store = _read("store.ts")
    header = _read("components/HeaderBar.tsx")

    assert "memoryView: 'review'" in home
    assert "setMemoryWorkspaceView(nextAction.memoryView)" in home
    continue_start = home.index("const continueToNext =")
    continue_body = home[continue_start : home.index("\n\n  return (", continue_start)]
    assert "setSearchQuery('');" in continue_body
    assert "setInspectedMemoryId(null);" in continue_body
    assert continue_body.index("setSearchQuery('');") < continue_body.index(
        "setMemoryWorkspaceView(nextAction.memoryView);"
    )
    assert continue_body.index("setInspectedMemoryId(null);") < continue_body.index(
        "setMemoryWorkspaceView(nextAction.memoryView);"
    )
    workspace_start = home.index("const openMemoryWorkspace =")
    workspace_end = home.index("\n\n  const continueToNext =", workspace_start)
    workspace_body = home[workspace_start:workspace_end]
    assert "setSearchQuery('');" in workspace_body
    assert "setInspectedMemoryId(null);" in workspace_body
    assert workspace_body.index("setSearchQuery('');") < workspace_body.index(
        "setMemoryWorkspaceView(view);"
    )
    assert workspace_body.index("setInspectedMemoryId(null);") < workspace_body.index(
        "setMemoryWorkspaceView(view);"
    )
    assert "memoryWorkspaceView" in memories
    assert "useState<'library' | 'review'>('library')" not in memories
    assert "await get().refreshSnapshot();" in store[
        store.index("remember: async"):store.index("isRecallTesting: false")
    ]
    assert "Reload snapshot" in header
    assert "this does not regenerate memory data" in header
    assert "Operational session verified" not in home


def test_snapshot_search_keeps_zero_matches_empty_until_query_is_cleared() -> None:
    memories = _read("components/MemoriesTab.tsx")

    assert "const searchMemories: MemoryNode[] = mode === 'search'\n" in memories
    assert "mode === 'search' && results.length > 0" not in memories
    assert "if (query.trim().length >= 2)" in memories
    assert "const mode = query.trim().length >= 2 ? 'search' : 'browse';" in memories
    assert "const currentResults = searchPending ? [] : results;" in memories
    assert "setSelectedId(null);\n                setQuery(e.target.value);" in memories


def test_inactive_memories_keep_a_verified_permanent_delete_route() -> None:
    correction = _read("components/CorrectionDialog.tsx")

    assert "candidate.action === 'restore' || candidate.action === 'permanent_delete'" in correction
    assert "candidate.action === 'permanent_delete'" in correction


def test_status_only_surfaces_are_named_as_status_only() -> None:
    connections = _read("components/ExploreTab.tsx")
    session = _read("components/SessionIntelligencePanel.tsx")
    recover = _read("components/RecoverTab.tsx")

    assert "Read-only snapshot" in connections
    assert "View only" in session
    assert "Installer actions — status only here." in recover


def test_memory_controls_have_names_and_do_not_render_an_empty_sort_button() -> None:
    memories = _read("components/MemoriesTab.tsx")
    table = _read("components/MemoryTable.tsx")

    assert 'aria-label="Search the current memory snapshot"' in memories
    assert 'aria-label="Clear snapshot search"' in memories
    assert 'aria-label="Filter displayed memories"' in table
    assert 'aria-label="Clear memory filter"' in table
    assert "aria-label={`${row.getIsExpanded() ? 'Collapse' : 'Expand'}" in table
    assert "header.column.getCanSort()" in table


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
    assert "1 · Memory scope" in recall
    assert "2 · Ask one question" in recall
    assert "3 · Inspect the receipt" in recall
    result_block = recall[recall.index("{result && copy && ("):]
    assert "What this proves" in result_block
    assert result_block.index("What this proves") < result_block.index("What it does not prove")


def test_empty_recall_reports_observation_not_correctness() -> None:
    recall = _read("components/RecallTab.tsx")

    assert "No memories selected" in recall
    assert "A relevant memory may still exist" in recall
    assert "No match · safe abstention" not in recall
    assert "supplied no unrelated or ineligible memory" not in recall
    assert "Your question" in recall
    dialog = _read("components/HomeMemoryDialog.tsx")
    assert "No memories selected" in dialog
    assert "Elefante returned no unrelated history" not in dialog


def test_recall_inspection_clears_stale_library_scope() -> None:
    recall = _read("components/RecallTab.tsx")
    inspect = recall[recall.index("const inspectMemory ="):recall.index("const copy =")]
    assert "setSearchQuery('')" in inspect
    assert "setMemoryWorkspaceView('library')" in inspect
    assert "setInspectedMemoryId(memoryId)" in inspect
    assert "onClick={() => setActiveTab('memories')}" not in recall


def test_projects_and_recover_explain_value_without_dead_controls_or_address_handoffs() -> None:
    projects = _read("components/ProjectsTab.tsx")
    recover = _read("components/RecoverTab.tsx")

    assert "Example project boundary" in projects
    assert "Projects prevent unrelated work from sharing Recall context" in projects
    assert "Overall memory inspection does not require a project" in projects
    assert "Protect Elefante before changing durable state." in recover
    assert "Recovery controls are disconnected" in recover
    assert "No active local session" in recover
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


def test_decision_graph_renders_exact_stored_edges_not_card_adjacency() -> None:
    node = shutil.which("node")
    if not node or not (UI_SRC.parent / "node_modules/react-dom").is_dir():
        pytest.skip("Requires the dashboard's installed Node dependencies")
    script = (
        f"const graphUrl = {(UI_SRC / 'components/KnowledgeGraph.tsx').as_uri()!r};\n"
        f"const typesUrl = {(UI_SRC / 'types.ts').as_uri()!r};\n"
    ) + r'''
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const moduleUrl = code => 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
const compile = url => ts.transpileModule(readFileSync(new URL(url), 'utf8'), {
  compilerOptions: {module:ts.ModuleKind.ESNext, target:ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX},
}).outputText;
const storeUrl = moduleUrl('export const useDashboardStore = pick => pick(globalThis.graphState);');
const graphCode = compile(graphUrl)
  .replace("from '@/store'", 'from ' + JSON.stringify(storeUrl))
  .replace("from '@/types'", 'from ' + JSON.stringify(moduleUrl(compile(typesUrl))))
  .replace("from 'react'", 'from ' + JSON.stringify(import.meta.resolve('react')))
  .replace('from "react/jsx-runtime"', 'from ' + JSON.stringify(import.meta.resolve('react/jsx-runtime')));
const {KnowledgeGraph} = await import(moduleUrl(graphCode));
const memories = ['a','b','c','d','unlinked'].map(id => ({
  id, type:'memory', name:id, description:'Requirement ' + id,
  properties:{title:id, score:80, memory_type:id === 'c' ? 'decision' : 'specification'},
}));
const render = edges => {
  globalThis.graphState = {
    getMemoryNodes:() => memories, snapshot:{edges},
    setInspectedMemoryId:() => {}, setActiveTab:() => {},
  };
  return renderToStaticMarkup(React.createElement(KnowledgeGraph));
};
const drawnEdges = html => [...html.matchAll(/data-source="([^"]+)" data-target="([^"]+)" data-relationship="([^"]+)"/g)]
  .map(match => match.slice(1).join(':')).sort();
const typedMemories = [
  ['decision', 'Decision node', 'decision', 90],
  ['specification', 'Specification node', 'specification', 80],
  ['directive', 'Directive node', 'directive', 70],
].map(([id, title, memoryType, score]) => ({
  id, type:'memory', name:id, description:title,
  properties:{title, score, memory_type:memoryType},
}));
const renderTyped = edges => {
  globalThis.graphState = {
    getMemoryNodes:() => typedMemories, snapshot:{edges},
    setInspectedMemoryId:() => {}, setActiveTab:() => {},
  };
  return renderToStaticMarkup(React.createElement(KnowledgeGraph));
};
const typedHtml = renderTyped([
  {from:'decision', to:'specification', label:'GOVERNS', type:'graph'},
  {from:'decision', to:'directive', label:'GUARDED_BY', type:'graph'},
  {from:'specification', to:'directive', label:'DEPENDS_ON', type:'graph'},
]);
assert.match(typedHtml, /· Specification/);
assert.match(typedHtml, /· Directive/);
assert.match(typedHtml, /<strong[^>]*>2<\/strong><span[^>]*>safeguard links<\/span>/);
assert.ok(typedHtml.includes('3 explicit relationships'));
assert.ok(typedHtml.includes('stored links'));
assert.ok(!typedHtml.includes('source grounded'));
const branches = [
  {from:'a', to:'c', label:'DEPENDS_ON', type:'graph'},
  {from:'b', to:'c', label:'DEPENDS_ON', type:'graph'},
  {from:'a', to:'d', label:'DEPENDS_ON', type:'graph'},
];
const branchHtml = render(branches);
assert.deepEqual(drawnEdges(branchHtml), ['a:c:DEPENDS_ON','a:d:DEPENDS_ON','b:c:DEPENDS_ON']);
assert.ok(!branchHtml.includes('>connected<')); // Neighbours are not edges.
assert.ok(!branchHtml.includes('>unlinked<'));
const cycleAndParallel = [...branches,
  {source:'c', target:'a', label:'GOVERNS', type:'graph'},
  {source:'a', target:'c', label:'GUARDED_BY', type:'graph'},
];
assert.deepEqual(drawnEdges(render(cycleAndParallel)), [
  'a:c:DEPENDS_ON','a:c:GUARDED_BY','a:d:DEPENDS_ON','b:c:DEPENDS_ON','c:a:GOVERNS',
]);
assert.deepEqual(drawnEdges(render([...branches].reverse())), drawnEdges(branchHtml));
const nonTrailEdges = [
  {from:'a', to:'topic', label:'HAS_TOPIC', type:'signal'},
  {from:'a', to:'b', label:'DEPENDS_ON', type:'semantic'},
  {from:'a', to:'missing', label:'DEPENDS_ON', type:'graph'},
];
assert.deepEqual(drawnEdges(render([...branches, ...nonTrailEdges])), drawnEdges(branchHtml));
assert.deepEqual(drawnEdges(render(nonTrailEdges)), []);
assert.ok(render(nonTrailEdges).includes('No decision trails yet'));
console.log('PASS: exact branches, direction, cycles, parallel labels, reordered input, excluded edges');
'''
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=UI_SRC.parent, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: exact branches" in result.stdout


def test_decision_graph_scrolls_as_one_surface_in_narrow_panels() -> None:
    graph = _read("components/KnowledgeGraph.tsx")
    assert 'className="h-full min-h-0 overflow-y-auto' in graph
    assert "min-h-[460px]" not in graph
    assert 'className="lg:grid lg:min-h-0 lg:flex-1' in graph
    assert '<section className="lg:min-h-0 lg:overflow-y-auto">' in graph


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

    assert "source prototype checked 2026-09-02" in guide
    assert "Installing a local candidate does not publish a release" in guide
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
