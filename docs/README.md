# Elefante User Guide

> **v2.15.2** · Published user documentation.

Elefante gives your AI agent relevant memories for the task at hand: decisions,
preferences, constraints, facts, and lessons you chose to keep. Your agent still
does the work and writes the answer. Elefante supplies context; it does not answer
questions itself or automatically save every conversation.

Use your connected agent for everyday work. Use the **local dashboard** to inspect,
correct, and protect the memory behind that work. You do not need to keep the
dashboard open for your agent to use Elefante.

**Start with the [five-minute real-memory demo](../examples/README.md).** Then use
this guide for [first use](#first-use), [everyday use](#everyday-use), the
[dashboard](#dashboard), [all released features](#all-released-features),
[troubleshooting](#troubleshooting), and the [advanced reference](#advanced-reference).

For the product purpose and boundaries, read [Why Elefante exists](explanation/vision.md).

## First use

### 1. Install and connect your agent

Follow [Install Elefante](how-to/install.md) for your operating system. Use the
published installer ZIP, not GitHub's **Code → Download ZIP**. The installer
includes the dashboard; a source checkout, Git, and Node.js are not required.

During setup, select the project folder used for your work. Then restart your
agent host and ask it to check Elefante's status. Elefante connects through MCP,
the protocol between the agent and the local memory service. See
[Configure a host](how-to/configure-ide.md) for compatible hosts and their limits.

Released compatible adapters cover VS Code, Cursor, Kiro, Gemini CLI, Claude
Code, Codex, OpenClaw, Zed, and Continue. Compatibility is contract-tested; it
does not mean vendor certification. Preview and community tiers are listed in
the host guide.

**What does “project” mean here?** It is a memory-isolation boundary, not a task
manager. Registering a folder does not scan its files or import its conversations.
You can browse memories across projects in the dashboard. Recall and memory
changes require one active project; there is no shared-across-project Recall
scope in this release.

### 2. Remember one useful decision

Choose a real rule or decision you will need again. The
[five-minute demo](../examples/README.md) walks through the complete loop. For
example, **only if this is your actual rule**, ask your connected agent:

> Remember for this project: every customer-facing change must be checked on
> desktop and mobile before release.

Check the returned result: was a record saved, was an existing record found, or
was the write blocked? Do not assume a request to remember succeeded. If you
already have a suitable memory, reuse it instead of adding this example.

In the dashboard, **Home → Remember** runs the same verified workflow. An empty
Home recommends saving one useful decision before testing Recall.

### 3. Check that the memory helps a task

In a later conversation or task, ask your agent to use Elefante Recall for a
question that needs the decision:

> What must I verify before releasing this customer-facing change?

Inspect the selected memory and the agent's answer. The answer should include
desktop and mobile checking. A selected record or a green status alone does not
prove that the agent used the memory well.

For a direct inspection, open the dashboard's **Recall** tab, enter the question,
and select **Run Recall Check**. Open a returned record to read it. If a known
relevant memory is missing, use the troubleshooting steps below; do not treat
every empty result as correct abstention.

### 4. Open the dashboard and protect your work

On the computer where Elefante is installed, open
[localhost:8000](http://localhost:8000/). No Chrome extension or browser connector
is required. If the page is unavailable, ask your connected agent to
**Open Elefante Home** and follow the address it returns.

Open **Memory Intelligence → Library** to inspect what was stored. After you
have useful memories, use **Recover → Back up now** and inspect the verification
receipt. Opening the page or seeing **Ready** does not replace these checks.

## Everyday use

| Your need | What to do | What should happen |
|---|---|---|
| Keep something useful for later | Ask your agent to **Remember** one durable decision, preference, constraint, or lesson | Elefante checks for existing knowledge before writing; inspect the result |
| Use prior knowledge now | Ask a real task question and have your agent use **Recall** | It receives relevant, eligible context or an explicit no-match/blocked result |
| Fix outdated knowledge | Open the record in **Memory Intelligence** and choose the appropriate correction | Review the proposed change, confirm it, and inspect its verified result |
| Protect or recover data | Use **Recover** | A backup or restore is complete only when its checks pass |

Keep memories concise and independently useful. Do not store passwords, API
keys, access tokens, hidden reasoning, or full transcripts as durable memories.
Read-only Recall does not edit memories; consented usage capture can separately
record metadata about the call. Relevant memory sent to your agent is subject
to that agent provider's policies.

## Dashboard

The dashboard is a maintenance tool, not a chat window. Most browsing reads a
**snapshot**: an inspection copy of the stored data. Named actions such as Recall
and correction use a short-lived local control session.

An **operation receipt** is the result card: it reports what happened and which
checks passed. A managed change, backup, or restore should finish with
`VERIFIED_COMPLETE`; otherwise read the failure and next-step information.

**Reload snapshot** rereads the existing snapshot; it does not rebuild it from
the live stores. **Current** describes snapshot age, not memory accuracy.
**Light / Dark** changes appearance only. If controls expire,
use **Reconnect Home**, then explicitly retry the check or review a fresh change
plan. Elefante does not automatically repeat an interrupted operation.

### Home

See memory counts, review signals, the active memory boundary, and recovery
evidence. **Recommended next → Continue** opens the relevant task: for example,
**Review** opens the counted Review queue; **Test Recall** opens Recall.

“Review 10 direct signals” means ten records have health or lifecycle information
worth inspecting. It does not mean ten memories are false, or that you must
change them. A connected or ready state describes availability, not task quality.

### Recall

Confirm the displayed memory scope, enter one real question, and select
**Run Recall Check**. Recall selects supporting memories; it does not write an
answer or save your question as a memory. The check needs connected controls,
an active project with an available folder, and a nonblank question.

| Result | Meaning | Your next step |
|---|---|---|
| Bundle supplied | One or more memories were selected | Open the records and judge whether they help the task |
| No memories selected | Nothing passed the matching rules | Use **Inspect available memories** if you expected a match |
| Blocked | A conflict or governance rule prevented delivery | Inspect the reason and affected knowledge before changing it |
| Unavailable | The check could not complete | Check the connection or session; this is not a successful no-match result |

Unavailable checks do not prove that Recall ran. Missing counts are not zero,
and a missing or invalid verification time remains **Not verified**.

The current question and result survive switching dashboard tabs, but they are
not saved history. Reloading the page or changing project clears them.

### Memory Intelligence

**Library** browses the memories represented in the loaded snapshot across
projects. **Review** shows records with direct health or lifecycle signals.
Select a row to read its content, source, scope, lifecycle, and relationships.
On narrow screens, the detail fills this tab so its content and actions remain
scrollable. **Close panel** returns to the list; main navigation stays available.

- **Snapshot search** finds text matches in the snapshot after two characters.
  It is not governed Recall. Zero matches must leave zero rows.
- **Filter memories** narrows the currently displayed rows. Clear it when a
  record seems missing.
- **Edit** fixes wording without changing meaning; **Replace** records newer
  knowledge while preserving the old version.
- **Archive** removes a record from Recall eligibility without deleting it.
  **Restore** is available for a manually archived record that was not superseded
  (replaced by a newer record).
- **Verified Resolve** is available for a represented conflict pair. You choose
  the authoritative memory; Elefante does not decide truth for you.
- **Delete permanently** erases the record after explicit confirmation and
  verification. It is not an archive action. Existing older backups can still
  contain that memory.

Available correction actions depend on the record and active project. Read the
health reason before acting: **At risk** is a review signal, not an instruction
to delete. Leave a correct record unchanged.

### Connections

- **Topics:** see how represented memories are grouped by subject.
- **Vitality:** inspect stored maintenance scores. A high score is not proof
  of truth, usefulness, or relevance to the current question.
- **Decision Graph:** follow explicit stored relationships between memories.
  Similar wording does not create a connection. An empty graph can mean that
  no qualifying relationships are represented, even when memories exist.

Use this view to understand the collection. It does not edit relationships or
prove that one memory caused a better result. The detailed guide explains the
graph controls and score ranges.

### Projects

Manage registered projects and their folder boundaries. Review older unassigned
memories before assigning them; do not guess ownership. Check the active project
before Recall or a memory change. Global browsing does not authorize global
Recall, and choosing a folder does not import its contents. In a read-only view,
management buttons can remain visible but disabled; read their stated reason.

After registration and strict-mode setup, select **Use for actions** beside the
intended project. **Current scope** confirms this session's boundary. Selecting
another project clears the old Recall question and receipt; it does not move
memories or replay an operation.

### Recover

**Check health** diagnoses without repairing. **Back up now** creates and verifies
a local backup. Restore first inspects the selected backup and asks you to
confirm a plan; it replaces stored state and must not be used as a casual test
on your real memories.

**Support report** creates a local, privacy-safe ZIP after showing its contents.
It does not send the ZIP anywhere. Inspect the final receipt for each operation;
a failed or unsafe result is not completion. Repair, update, product rollback,
and uninstall use the matching official package, not dashboard action buttons.

### Session Intelligence

Open **Home → Advanced**. This is a report, not a control for starting collection.
After explicit permission, Elefante automatically records local MCP activity and
token estimates without saving prompts, transcripts, or response content.

- **Recorded events** counts observed activity, including failed and blocked
  calls—not completed tasks. Refreshing the report adds no usage event.
- **Usage cost** needs complete provider-reported usage and matching rates.
  Estimates are kept separate; **Unavailable** does not mean free.
- **Task result** needs outcome evidence. **Not verified** means a useful result
  has not been demonstrated by that evidence.
- **Usage details** expands counts, coverage, timestamps, and limitations.
  **Suggestions** contains provisional observations, not verified improvements.

For permission, export, retention, and deletion, use the
[existing local controls](reference/token-intelligence.md#existing-local-controls).
Do not confuse activity recorded by Session Intelligence with durable memories
in the Library.

## All released features

Every released feature belongs to the same purpose: preserve useful knowledge,
select it safely for a later task, or let the user inspect and protect that
process. Optional and advanced features do not run merely because they exist.

| Feature | How you use it | What it does |
|---|---|---|
| Remember and Library | Ask the connected agent to remember durable knowledge, or use **Home → Remember**; inspect it in **Memory Intelligence** | Searches before writing, stores an attributable record, and shows the explicit result |
| Bounded Recall | Ask one real task question through the agent, or run the dashboard Recall check | Supplies a small eligible memory bundle, or returns no match, blocked, or unavailable |
| Project isolation | Choose a specific registered folder for actions | Keeps new memory and Recall inside that boundary; it does not scan the folder or make Elefante a project manager |
| Verified correction | Use Edit, Replace, Archive, Restore, Resolve, or permanent deletion from a record | Plans the change, asks for confirmation, and verifies its postconditions |
| Conflict safety | Inspect a represented conflict before Resolve or Smart Merge | Can withhold conflicting records; the user chooses authority when no protected winner is unambiguous |
| Connections | Open Topics, Vitality, or Decision Graph | Shows represented subjects, maintenance scores, and explicit stored relationships without editing them |
| Recover | Check health, back up, preview/confirm restore, or create a support report | Performs bounded local recovery operations and returns a verification receipt |
| Elefante Home | Open `http://localhost:8000` on the installed computer | Provides the local maintenance dashboard; it is not the everyday chat surface |
| Session Intelligence | Give purpose-specific permission with the installed local controls; inspect **Home → Advanced** | Records metadata-only MCP activity and usage evidence without prompts, transcripts, or response content |
| Session Distiller | Run the foreground distiller or opt-in watch mode | Processes supported session files serially; it stores nothing unless storage is explicitly enabled |
| Team Sync | Use the advanced local CLI with an explicit memory-ID allowlist and user-chosen transport | Creates or imports signed, scope-bound bundles; Elefante does not provide cloud synchronization |
| Local media | Attach a bounded local image, audio, or video file through a memory operation | Stores and integrity-checks the file locally; it does not perform OCR, transcription, model analysis, or upload |
| Private host events | Send a typed file, terminal-error, or conversation envelope to the local event endpoint | Requests literal-trigger retrieval after privacy scrubbing; Elefante does not silently intercept activity or retain the event body |
| Context and sessions | Use the advanced Context and Sessions MCP tools | Retrieves a broader graph-connected bundle or lists time-based work sessions |
| Persistent task graph | Use Task Create, Update, and Graph from an orchestrating agent | Preserves structured task hierarchy, dependencies, status, and output; it is separate from project memory isolation |
| ETL enrichment | Use the advanced Process/Classify pair | Adds bounded summaries, concepts, and trigger metadata to stored memories |
| Directives | Add, list, or remove an explicit persistent directive | Keeps always-on behavioral constraints separate from relevance-ranked memories |

The published interface exposes 18 tools and 2 prompts. Most customers use
natural language through their connected agent; exact parameters, response
contracts, permissions, and limits are in the [advanced tool reference](reference/tools.md).

## Troubleshooting

| What you see | What to check first |
|---|---|
| The local page will not open | Confirm Elefante is installed on this computer; ask your connected agent to open Home. Use the [installation checks](how-to/install.md#4-verify-the-installation) if it cannot |
| Setup required or controls unavailable | Read the stated reason. Reconnect an expired local session; use Projects when a memory boundary is missing. Do not reinstall just because a snapshot is read-only |
| Recall misses a memory you know exists | Inspect the Library; check the active project, archive/supersession state, conflicts, and the actual question. A text-search match does not guarantee Recall eligibility |
| At risk, but the content is correct | Read the health and lifecycle reason. No correction may be needed |
| Empty graph | Check whether explicit relationships exist; topic similarity and a nonzero memory count are not enough |
| Snapshot is old after Reload | Reload rereads the same file. Ask your connected agent to refresh/open Home; do not delete storage or remove lock files |
| Usage cost or task result is unavailable | Check **Usage details** for missing evidence. Do not substitute an estimate for a measured result |

For persistent failures, use **Recover → Support report**. Do not reset your
memories, edit database files, or remove locks as a first response.

## Detailed dashboard guide

The [first-party website guide](https://elefante.ai/docs#dashboard) explains the
dashboard in a normal browser. The [complete offline dashboard reference](how-to/view-dashboard.html)
covers every section, control, score, confirmation, receipt, and safety boundary.
**GitHub displays HTML source**, not the rendered guide. Choose **Download raw file**
and open it locally when you need the standalone reference. It loads no
external scripts, fonts, or trackers.

If you stay on GitHub, this page is the readable starting guide. Technical
references below also render directly as Markdown.

<a id="advanced-reference"></a>

## Reference — advanced and operator

<details>
<summary>Advanced, operator, and technical guides</summary>

The published MCP interface exposes 18 tools, 2 prompts. You do not need to learn
their API names to begin using Elefante through your connected agent.

| Guide | Use it when you need… |
|---|---|
| [Install Elefante](how-to/install.md) | Requirements, checksums, setup, repair, upgrade, or uninstall |
| [Configure a host](how-to/configure-ide.md) | Compatible adapters, preview/community tiers, or manual connection |
| [Run the MCP server — developer](how-to/run-mcp-server.md) | Source-checkout startup and full-surface proof |
| [Restart](how-to/restart.md) | Graceful service restart |
| [Backup and rollback](how-to/rollback.md) | Detailed backup and recovery procedures |
| [Docker and Agent Zero — advanced community setup](how-to/docker.md) | Container or Agent Zero operation outside the normal installer path |
| [Kuzu troubleshooting](how-to/kuzu-troubleshooting.md) | Graph ownership or locking problems |
| [Agent handoff](how-to/agent-handoff.md) | Connecting an existing MCP-capable agent |
| [Tools and prompts](reference/tools.md) | Exact parameters, results, and safety rules |
| [Memory schema](reference/memory-schema.md) | Types, provenance, governance, lifecycle, and attachments |
| [Scoring](reference/scoring.md) | Vitality and retrieval formulas |
| [Ingestion](reference/ingestion.md) | Validation, storage, and graph-link processing |
| [Dashboard snapshot](reference/dashboard-snapshot.md) | Snapshot and local-control contracts |
| [Token Intelligence](reference/token-intelligence.md) | Estimates, provider-reported usage, and local controls |
| [Architecture](reference/architecture.md) | Local daemon, MCP, SQLite vectors, and Kuzu |
| [Product vision](explanation/vision.md) | Product purpose and boundaries |
| [Agent integration examples](../examples/AGENT_TUTORIAL.md) | Exact Recall, write, correction, and host-instruction behavior |

</details>

## Documentation boundary

This guide describes released behavior, not planned features or a promise of
better answers on every task. A version-tagged URL is a fixed release snapshot;
later documentation corrections do not rewrite that tag. Check the package
version in your dashboard when comparing instructions with your installation.
Developer material begins at [the repository entrypoint](../AGENTS.md).
