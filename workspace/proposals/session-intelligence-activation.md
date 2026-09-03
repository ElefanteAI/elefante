---
status: released
owner: Elefante development
created: 2026-09-03
---

# PRD: Activate Session Intelligence on real work

Release follow-through: after local activation, the owner separately authorized
the coordinated v2.15.0 release on 2026-09-03; publication and installation are
verified. Its current version, publication,
installed build and website proofs are maintained in
[PLANNING §2.3](../PLANNING.md#23-current-release-state). The original bounded
implementation scope below remains the historical acceptance contract.

> **Question:** How do we make the existing Session Intelligence capability
> collect useful evidence automatically and explain it honestly in Home?
>
> **Consumer:** The owner and the developer/operator implementing this change.
> **Loading:** Route here from PLANNING §4.2 before implementation or activation.
> **Authority:** This file owns the bounded delivery requirements and acceptance
> gates, not claims about installed or released behavior. The
> [token reference](../../docs/reference/token-intelligence.md) and current
> source own implemented behavior. The [earlier PRD](session-intelligence.md)
> remains retained design rationale; this is not a replacement analytics design.

## 1. Objective and scope lock

Session Intelligence is a **required measurement capability** in the owner's
Elefante workflow, not an optional product afterthought. It should tell us what
Elefante did, what usage was observable, and whether there is evidence of value.
An enabled badge or a manually populated example is not delivery.

Required capability does not mean silent collection. Preserve local,
purpose-bound permission and revoke/export/delete controls. The intended rollout
is this owner's installation after tests, not a global change to other users'
consent or defaults. Implementation is tracked below; source tests are not
installed-activation evidence.

**Preserve:** the working six-tab dashboard, governed Recall, semantic memories,
graph relationships, installation rollback, and the existing ledger/CLI/API.
Semantic Memory owns meaning; Session Intelligence owns usage facts; Task
Intelligence owns outcome and causal evidence. Do not add a fourth authority.

**Excluded:** dashboard redesign, new tabs, provider-account scraping, transcript
ingestion, a new telemetry database/service, model calls to generate metrics,
automatic memory writes, general benchmarking, publication, and website changes.

## 2. Baseline: facts versus work still needed

Source baseline: `6e91034b567e2488c7ab28dc3e1f7b23a60d0746`, inspected
2026-09-03. Recheck source and installed identity before implementation; this
reference does not assert that a future installation still matches it.

| Evidence | What it establishes |
|---|---|
| [Ledger](../../src/session_intelligence/ledger.py), [runtime](../../src/session_intelligence/runtime.py), [CLI](../../scripts/pipeline/session_intelligence.py) | Consent, typed events, deduplication, rate cards, outcome records, retention, export/delete, aggregation and snapshot generation already exist. Reuse them. |
| [MCP server](../../src/mcp/server.py), [token counter](../../src/utils/token_counter.py), [daemon ingress](../../src/mcp/daemon.py) | MCP has an in-memory estimate ledger. Persistent usage ingress exists, but automatic MCP/provider collection is not connected to it. |
| [Home panel](../../src/dashboard/ui/src/components/SessionIntelligencePanel.tsx) | Six values and explanatory text already exist. The panel reads a snapshot; it does not activate collection. Its current zero/off states need evidence-aware handling. |
| Preceding read-only local inspection, 2026-09-03 | The configured Session Intelligence ledger and snapshot were absent; `/api/session-intelligence` returned disabled. This is the baseline, not proof of activation. |
| [Existing runtime tests](../../tests/test_session_intelligence_runtime.py) and [daemon tests](../../tests/test_session_intelligence_daemon.py) | Fixtures prove storage/math and ingress behavior; they do not prove automatic capture from a real host session. |

**UNKNOWN:** availability and completeness of actual token metadata from the
current host; real collection overhead; any task-quality or financial benefit.
Do not infer these from successful Recall, test counts, or a provider fixture.

## 3. What every existing feature must mean

All numbers must share a visible scope; covered source, time window and snapshot
time remain inspectable under **Usage details**. The current aggregate covers
retained events, not necessarily this chat. A transport connection is not
proof of a conversation identity; unknown host/task identity stays unknown.

| Existing feature | User value and required behavior | Acceptance |
|---|---|---|
| Usage events | Show observed activity, including failed/blocked results, with its measurement unit. Distinguish MCP invocations from provider/model-turn observations; page reloads are not AI usage. | N completed captured MCP calls yield N unique MCP events. Provider observations do not inflate that invocation count. Replaying one event adds zero; a genuine second invocation counts separately. |
| Actual input tokens | Show provider-reported input for the covered activity; tool-argument estimates stay separately labeled. Cached input is a subset, not extra input. | Reconcile a complete actual event to its source. Without actual events, show `UNKNOWN`, not a misleading zero. |
| Actual output tokens | Show provider-reported generation only where it is observable. An Elefante response-size estimate is not model output usage. | Reconcile source counts; estimates never populate the actual field. Partial coverage is explicit. |
| Verified cost | Explain rate-card-derived cost for covered actual usage, not the user's subscription bill or savings. | Exact model, complete counts, dated sourced rates and currency reconcile. Missing inputs/rates or incompatible totals show `UNKNOWN` with the reason. |
| Causal outcome | Say whether a valid comparable Task Intelligence evaluation supports the recorded outcome. | Tool success or user acceptance alone cannot produce a causal verdict. No qualifying evaluation means `UNKNOWN`; do not launch a new trial just to fill the card. |
| Training hypotheses | Surface aggregate suggestions for what to investigate, with their supporting groups/counts and unvalidated status. This is not model training. | Current generic per-group hypotheses remain explicitly provisional and inspectable. A missing report is not presented as zero proven opportunities. No employee ranking. |
| Explanation and unknowns | Explain what a number covers and why evidence is missing. | Distinguish disabled, enabled/no events, estimates-only, partially observed, current, stale/unavailable and permission-denied states. A failed refresh must not look current. |
| Privacy and data controls | Keep collection local, limited and reversible through the existing operator interface. | Consent, revoke, export, retention and deletion work in isolated tests; Home remains view-only and reads metric values from the snapshot. Revocation stops new writes without silently deleting retained evidence. |

Keep the six existing values, not six equally prominent cards. The owner's
preview feedback requires UX-first presentation: **Recorded events**, **Usage
cost**, and **Task result** lead; **Usage details** contains actual token counts,
estimates and provenance; **Suggestions** exposes provisional statements/counts.
Use readable text and native keyboard-accessible disclosures, closed by default.
The ordinary summary stays within 80 words; unavailable cost and outcome have
plain-language states, with exact `UNKNOWN` evidence retained in details. Errors,
pending writes and permission failures stay visible without opening details.
No collection, calculation, storage or control behavior changes. Zero is valid
only for a measured empty quantity, not for unavailable evidence.

## 4. Capture contract: small, shared and honest

1. Instrument the shared MCP invocation boundary once. Capture tool identity,
   stable invocation/event identity, transport-scoped session identity, time,
   duration, result status and observable token estimates. Include success,
   no-match, blocked and error paths; no-match is successful abstention, not an
   error. Do not count the same call again in its handler or response decorator.
2. Reuse the existing persistent event validation, consent and snapshot path.
   Persist only allowlisted metadata. No prompts, responses, arguments, raw
   errors, transcripts, secrets or hidden reasoning in events, logs or exports.
   No content fingerprint is needed for this activation.
3. Keep MCP-call estimates separate from provider/model-turn actual usage.
   Correlate only with supplied stable identity; never attach an entire model
   turn's tokens to each tool call or add overlapping observations together.
   Do not claim uninstrumented dashboard actions are observed MCP calls.
4. The common capture path must not depend on Codex, an IDE path or a project
   selection. A thin host adapter may supply documented actual metadata through
   the existing ingress. First verify that such metadata exists; if unavailable,
   record the limitation and retain estimates-only operation. No scraped or
   invented usage and no retrospective backfill of this conversation.
5. Collection must not change memory selection/content, tool results, stdout,
   error behavior or memory/graph writes. A locked/unwritable ledger or snapshot
   failure must not fail or replay the user's operation. Keep telemetry waits
   bounded off the critical operation path; do not inherit the ledger's
   five-second busy wait there. Surface sanitized collection failure and coverage
   loss; do not hide it behind a green card or an unbounded retry queue.
6. Measure overhead with the same isolated calls, capture off versus on; record
   the added latency before activation. Require zero added model calls, zero
   external uploads and no new service. Do not invent an efficiency improvement.

The existing event schema must be checked against each required observation
before changing it. Prefer mapping supported fields; any indispensable schema
extension needs a narrow compatibility test, not a replacement ledger.

## 5. Delivery order and gates

Status below is execution state, not a list of claimed completions. Enter the
next stage only after its preceding gate passes. Record evidence against these
IDs; do not create parallel checklists or session reports.

| ID | Work | Exit evidence | State |
|---|---|---|---|
| SI-1 | Add one fail-first isolated test: normal MCP call → automatic event → real temporary ledger → snapshot → dashboard API. Inspect available host usage metadata separately. | Missing capture reproduced (no snapshot); regression passes after the hook. Real in-memory MCP protocol also records two distinct blocked invocations with no mocked handlers. Transport/client identity is available; provider token metadata is not present on this boundary. | PASS — source candidate, 2026-09-03 |
| SI-2 | Connect the common capture path and minimum existing-panel evidence handling. | Bounded asynchronous persistence, consent/revocation, duplicate protection, capture health, safe error/interruption and mixed actual/estimated counts pass. Final combined regression: 340 passed / 13 deselected (slow/live paths outside this isolated gate); production UI build and scoped Ruff pass. | PASS — source candidate |
| SI-3 | Exercise the existing panel in an isolated browser using those real calls and controlled failure cases. | Both themes: enabled-empty/unknown, off, incomplete capture and broken-snapshot states are readable. Real MCP calls, provider/cost fixture, causal fixture, hypotheses, reload, snapshot recovery, revoke/regrant, export and test-data deletion reconcile as detailed below. Customer data is not the fixture. | PASS — isolated browser, 2026-09-03 |
| SI-4 | Prepare and activate the exact tested candidate in the owner's installation through the established install/operator workflow. | Exact-package rollback passed in isolation. Official installation completed; all 105 installed payload files match candidate `4b17c63`. Doctor is ready; all three intended purposes are enabled; six memories and three stored relationships are preserved. | PASS — owner's local installation, 2026-09-03; no public release |
| SI-5 | Use Elefante on one real development task, then inspect Home → Advanced → Session Intelligence. | The actual rollout-verification task captured two successful Codex MCP operations and three blocked diagnostic probes. The normal dashboard and ledger reconcile at five events; settled Reload remains five. Provider actuals, cost and task-value evidence remain unknown. | PASS — installed capture and visible readback, not task-quality or full-host accounting proof |

For SI-4, retain the existing permission purposes: `usage_analytics` for local
activity, `provider_usage` for actual provider metadata, and
`enterprise_training` for local aggregate hypotheses. The latter does not train
a model or upload anything. Apply only the owner's authorized purposes; do not
change other accounts or convert this plan into blanket collection permission.
Keep the existing 30-day event-retention default; verify the implemented pruning
triggers rather than promising an unbuilt continuous expiry service.

If installation or activation needs authority beyond the approved local scope,
stop at that boundary. Rollback uses the previous verified package and collection
revocation; it must preserve semantic data and retained usage unless deletion is
separately requested. Never test destructive controls against customer data.
Before SI-4, rehearse activation, revocation and package rollback in isolation
using the exact candidate and previous verified baseline. Read back preserved
memory/graph data and retained usage, confirm new usage writes stop after
revocation, and verify the prior dashboard still works. Reuse the existing
lifecycle runner where applicable. Missing rollback proof blocks activation;
a backup's existence alone does not pass this gate.

## 6. Acceptance and evidence discipline

Extend the existing Session Intelligence tests, not a new testing framework:

```bash
./.venv/bin/python -m pytest tests/test_session_intelligence.py tests/test_session_intelligence_runtime.py tests/test_session_intelligence_daemon.py tests/test_session_intelligence_dashboard.py tests/test_session_intelligence_cli.py tests/test_token_intelligence.py -q
```

These tests are necessary, not sufficient. SI-1 through SI-5 must also establish:

- One observed invocation per event; duplicate delivery adds none; a new real
  invocation/session is not accidentally deduplicated. Unknown identity is not
  attributed to another host, conversation, task or project.
- Successful, abstained, blocked and failed tool results remain identical with
  collection off/on; counts include observable failures. Interrupted/incomplete
  capture is identified as incomplete, not invented as a completed success.
- No consent creates no usage ledger/event. Wrong purpose, forbidden content
  and invalid usage are rejected without leaking the supplied content.
- Missing actual counts, missing rate card, mixed actual/estimated coverage,
  unvalidated outcomes and generic hypotheses retain honest labels. Controlled
  fixture math is labeled test evidence, never observed customer usage.
- One provider turn containing multiple MCP calls does not multiply actual
  tokens/cost or turn the combined observation count into an invocation count.
- Locked ledger, failed snapshot write and broken snapshot fetch preserve core
  operations and show unavailable/stale coverage. Reload cannot replay a call.
- Retention, export, revoke and deletion operate on isolated data and refresh
  the snapshot correctly. Existing user-data/loopback protections remain intact.

Each stage records only **source ref, test/command, expected versus observed,
PASS/FAIL/UNKNOWN, remaining limitation** in its row or linked existing test.
Put discovered defects in [ISSUES](../ISSUES.md), matching existing entries first;
do not reopen closed GAP-025 as a proxy for new capture work. Add a regression,
fix the cause, rerun the failed stage and its neighboring checks.

### Implementation evidence and bounded clarifications — 2026-09-03

- Implementation is sealed as `4b17c63e986ab093274473147301a865ae9cc23b`
  on baseline `6e91034`. The source/isolated evidence below is separate from
  the subsequent local-installation readbacks recorded after it.
- [Runtime regressions](../../tests/test_session_intelligence_runtime.py) exercise
  the real MCP protocol, automatic persistence, duplicate delivery, queue bound,
  revoked permission, simultaneous explicit ingress/capture, locked SQLite,
  snapshot failure, context failure, interruption and unchanged tool responses.
  [Existing ledger/CLI tests](../../tests/test_session_intelligence_cli.py) retain
  privacy, rate, outcome, retention, export and deletion proof in isolation.
- Asynchronous snapshot failure can happen after a successful tool response and
  even after an event is saved. Therefore the existing snapshot API adds a
  **content-free owning-process health overlay** (since/pending/failed/dropped),
  without opening SQLite in the dashboard or adding a database/service. The UI
  must say capture **or snapshot refresh** may be incomplete. Metrics remain
  snapshot-based; this deliberately clarifies the earlier snapshot-only wording.
- Bounded local timing: 20 warm real-protocol validation calls per condition,
  median 1.44 ms without capture versus 1.41 ms with capture; maxima 2.39/1.71 ms.
  No measurable added delay in this run, **not** a performance improvement or a
  host-wide overhead guarantee. Zero added model calls or external uploads.
- Known collection boundary: abrupt process loss can lose pending events; health
  is process-local, not a persistent loss audit. No complete-host accounting,
  automatic provider adapter, backfill or causal benefit is claimed.
- Final combined test set: the six SI/token suites above plus
  `tests/test_developer_routing.py`, `tests/test_mcp_daemon.py`,
  `tests/test_dashboard_ui.py`, `tests/test_dashboard_serializer.py`,
  `tests/test_dashboard_snapshot_verifier.py` and `tests/test_home_control.py`;
  `-k 'not live and not two_real and not bridge_reinitializes'` selected 340
  passing tests (17.85 seconds). The 13 deselected cases are not claimed as run.
- SI-3 readback: real DirectiveList success plus Recall's actual validation
  rejection produced two distinct estimated events; browser reload produced no
  extra event. One controlled provider observation (1M input, 500K cached subset,
  100K output at test-only rates 3/1/5 per million) produced USD 2.50 alone.
  Adding MCP estimates kept actual counts unchanged and aggregate cost UNKNOWN.
  A clearly synthetic comparable outcome tested `Accepted`; it is not task-value
  evidence. All three aggregate hypotheses exposed their actual statements and
  count basis. No provider adapter is proven by those fixtures.
- Forced refresh failure left 29 displayed observations versus 31 saved ones;
  the live partial warning showed two failures without changing tool responses.
  A broken snapshot cleared numbers and displayed unavailable; explicit refresh
  restored 31. Revocation retained 31 and two subsequent calls added none.
  Export returned 31 events and one fixture outcome; exact isolated deletion
  returned 31 and an empty card. Regrant plus two normal MCP calls resumed
  capture at two; repeated reload stayed at two. The data directory contained
  only the usage ledger and two snapshots, no semantic or graph database.
- Live iteration corrected a stale permission message: it now describes the
  last denied write instead of asserting permission is still missing after a
  new grant. Process failure counts remain historical until restart.
- [BUG-071](../ISSUES.md) was reproduced fail-first: the aggregate-report CLI
  advertised unsupported `status` grouping. Its choices now match the existing
  `tool`/`client`/`day` ledger; every advertised choice is tested. No new feature.
- Owner preview feedback refined SI-3's presentation, not capture: three plain
  summary cards, two closed disclosures, and readable text replace the dense
  six-card/report layout. The UI/routing/dashboard suites pass 96 checks; the
  production build and both-theme browser checks pass. Keyboard disclosure,
  preserved token/hypothesis evidence and reload staying at two real test events
  are verified. Errors/pending/permission remain outside disclosures; zero and
  unverified outcomes stay guarded. The owner subsequently approved committing
  and installing this candidate locally; approval does not establish installation.

### Local activation evidence — 2026-09-03

- The owner authorized local commit/install, not push, public release or website
  deployment. Implementation commit: `4b17c63e986ab093274473147301a865ae9cc23b`;
  installed version/channel: `2.14.0` / `candidate`. Later documentation-only
  commits do not change the installed implementation identity.
- The combined 340-test gate passed again (13 deselected), followed by 110
  routing/installer/customer-package tests. Both exact clean-source packages
  passed `verify_release_client.py`. Candidate archive SHA256:
  `9692b0fae073b7793abef19961c2086bcc58097a6c8466b557679f70ee691e36`.
- Isolated official payload swap/rollback preserved the full persisted fixture
  memory/graph hash; capture added one event, revocation stopped new writes,
  rollback retained that event, and both dashboard endpoints returned HTTP 200.
  This is exact-package rollback proof, **not full machine Scenario D**.
- The official installer completed at `2026-09-03T20:55:21.774612+00:00`.
  Its receipt is `/Users/jay/.elefante/app/current/.elefante-package-receipt.json`
  (`VERIFIED_COMPLETE`); all 105 payload files match the candidate. The installed
  Doctor reports `customer_ready=true`, `ready=true`, zero diagnostics.
- Existing consent controls enabled `usage_analytics`, `provider_usage` and
  `enterprise_training`. The actual Codex SystemStatusGet and DashboardOpen
  calls succeeded; three actual projectless Doctor Recall probes were blocked.
  These five events completed between 20:58:00 and 20:58:29 UTC. The dashboard
  displays five estimated events and zero provider-reported observations;
  Reload after the probes finished adds none. These are operations, not five
  completed tasks. Usage cost is unavailable; task result is not verified.
- Customer preservation: six SQLite memories are byte-identical to the verified
  preinstall backup; all six graph entities and three relationships match as
  stored records. Kuzu file bytes changed, but persisted graph content did not.
  Safety backup: `/Users/jay/.elefante/backups/elefante_data_backup_20260903_205348.zip`.
  Prior runtime: `/Users/jay/.elefante/app/current.backup.20260903_165349`.
- Exact candidate/baseline archives and content-free rollback/preservation
  receipts are retained under the ignored build-output directory
  `dist/local-rollouts/4b17c63/`; no new product-documentation surface was added.

**Completion criterion:** automatic collection and understandable evidence are verified in the
installed dashboard, with explicit coverage. Cost/outcome evidence may correctly
remain unknown. An unavailable actual-usage adapter must remain explicitly
unverified; operational capture is not proof of full host accounting or improved
task quality. Never report every capability as proven from the basic path alone.

## 7. One documentation trail

| Document | Owns | Update rule |
|---|---|---|
| This PRD | Activation requirements, stages and acceptance evidence | Follow it; change requirements explicitly, not through silent implementation drift. |
| [PLANNING §4.2 and §10](../PLANNING.md) | Status pointer and significant decision/history | Link here; do not duplicate this plan or test logs. |
| [Proposal index](README.md) and [retained PRD](session-intelligence.md) | Discovery and historical rationale | Link to this active delivery plan; preserve prior implemented boundaries. |
| [Token reference](../../docs/reference/token-intelligence.md), [architecture](../../docs/reference/architecture.md) and [HTML dashboard guide](../../docs/how-to/view-dashboard.html#session-intelligence) | Actual behavior and user instructions | Update with verified implementation, including activation/control usage and all six values. Describe it as shipped only after verified publication. |
| [ISSUES](../ISSUES.md) and its existing postmortems | Defects and regression ownership | Record real failures there, not in another backlog. |

### Official release follow-through — 2026-09-03

The original local-only acceptance above is retained as history. The separately
authorized v2.15.0 release is public and its official macOS package is installed
at source `2092916e30a3d46dc2e6190dceaed05653b769ed`, channel `release`.
The verified package receipt completed at `2026-09-03T23:44:53.758788+00:00`;
Doctor is ready with no diagnostics. Six memories, six graph entities and three
explicit memory relationships remain represented. Consent remains active.

Real MCP activity appeared in the installed dashboard's local estimate ledger;
the settled report showed 23 estimated events and zero supplied provider
observations. Another Reload left 23 events. This is capture/read-only reload
proof, not 23 completed tasks, complete host usage or measured task benefit.
The safety backup `elefante_data_backup_20260903_234320.zip` and previous runtime
`current.backup.20260903_194320` remain available. Publication and cross-surface
identities are indexed only in [PLANNING §2.3](../PLANNING.md#23-current-release-state).

**Delivery state:** SI-1–SI-5 pass within their recorded boundaries. The owner can
use Home → Advanced: Session Intelligence at `http://localhost:8000/`; normal MCP
activity is recorded automatically and Reload rereads the snapshot. Provider
actuals, billed cost, complete-host coverage and improved task quality remain
unverified. The separately authorized public release is complete; the original
local implementation scope was not silently expanded.
