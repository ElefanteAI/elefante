---
status: APPROVED — PRODUCT CONTRACT CONVERGED; LOCAL LOOP IMPLEMENTED; CROSS-SURFACE ALIGNMENT PENDING
document_owner: Elefante founder and product owner
target: Upcoming; no release or date commitment
authority: Approved product direction and implementation sequence; released documentation and source remain publication authority
question: How does Elefante supply governed memory guidance to each task while exposing a truthful, safe advanced maintenance console?
consumers:
  - Elefante founder and product owner
  - developers and implementation agents
related:
  - docs/how-to/install.md
  - docs/how-to/rollback.md
  - docs/reference/dashboard-snapshot.md
  - workspace/proposals/tool-consolidation.md
  - workspace/proposals/memory-identity.md
---

# PRD: Elefante as One Product

## 0. Read this first

**Owner:** Elefante product owner

### The product purpose in one sentence

Elefante lets an agent start a task with the smallest governed bundle of durable
memories justified by the task and project—or abstains—so work can compound
instead of restarting from zero.

In this PRD, **advice** is customer shorthand for that selected memory bundle.
Elefante does not synthesize a recommendation, decide the task, or replace the
agent's reasoning. “Best” means best justified by the available indexed
evidence, project boundary, and governance rules at that moment; it is not a
claim of universal optimality.

Memory persistence alone is infrastructure. The immediate product promise is
governed continuity: the right project memory bundle or a truthful abstention.
The ultimate north star is improved accepted task value per total token. Until
representative outcome evidence exists, that improvement remains an objective,
not a shipped performance claim.

### Product contract lock

The following decisions are stable. A later review may refine wording or
interaction design, but it may not reverse them without new source, runtime,
customer, or outcome evidence:

1. **Task intelligence is the purpose.** Elefante exists to improve an agent's
   work on each eligible memory-dependent task by supplying the best governed
   memory bundle it can justify, or by abstaining safely.
2. **The product loop is one system.** Install, Projects, Remember, Recall,
   Correct, and Recover support that purpose; they are not competing product
   definitions.
3. **Host behavior is IDE-agnostic.** MCP carries one semantic contract across
   compatible IDEs and agents. Host adapters may change connection and
   bootstrap mechanics, never memory meaning, Recall policy, project safety, or
   verification requirements.
4. **Home exposes the engine.** The dashboard is the advanced console for
   understanding the complete memory corpus, Recall behavior, relationships,
   scope, corrections, and recovery. Project selection gates delivery and
   mutation, not read-only understanding of all memories.
5. **The website proves the released product.** `elefante.ai` explains the same
   product outcome in customer language and demonstrates only behavior that the
   published package can substantiate.
6. **Capabilities are preserved before they are rearranged.** A confusing
   feature is first given a truthful question, evidence boundary, and useful
   consequence. It is relabeled, regrouped, or progressively disclosed before
   deletion is considered. Deletion requires proof that the capability has no
   unique job, evidence, or consequence, plus explicit owner approval.
7. **Evidence planes stay distinct.** Semantic Memory owns durable meaning;
   Session Intelligence owns consented usage facts; Task Intelligence owns
   task-level outcome evidence. None can impersonate another.

“Think harder” is therefore a request to test this contract against more
evidence, not permission to replace the contract with a new product thesis.

### The complete customer experience

```text
Install -> choose projects -> Remember -> Recall -> Correct when needed -> Recover when needed
```

- The lifecycle above operates Elefante; it is not the ultimate value statement.
- The **agent** is where the customer performs the task and receives
  memory-derived advice.
- **Elefante** selects or withholds the smallest governed memory bundle for that
  task and project.
- The **Elefante dashboard** is the advanced maintenance console for inspecting,
  correcting, and recovering the memory and Recall machinery.
- The MCP surface is internal machinery. Tool names and tool count do not appear
  in the primary customer journey.

### The document rule

Every product requirement must name:

1. the product piece that owns it;
2. what the customer does and sees;
3. what Elefante must do;
4. what happens when it fails;
5. the evidence required to call it complete.

If a term or requirement cannot be placed under an owner and a customer step,
it does not belong in this PRD.

Every dashboard requirement also carries one evidence state:

- **CURRENT LOCAL** — implemented in the active local source contract;
- **CURRENT SOURCE PROTOTYPE** — implemented and browser-verified in source,
  but not yet accepted in an installed customer package;
- **TARGET** — approved product behavior that still requires implementation;
- **NOT PROVEN** — an intended outcome without representative evidence;
- **OUT OF SCOPE** — deliberately excluded from this product phase.

A target prototype, old screenshot, aggregate metric, or marketing sentence may
not be promoted to `CURRENT LOCAL` without matching source and acceptance proof.

### Recommendation

Build one narrow, self-service local product before expanding the surface:

- one accountable technical user;
- one local Elefante installation;
- one certified platform and agent-host combination first;
- multiple isolated projects;
- three operator jobs—Global understanding, Task intelligence, and Continuity—
  composed from the governed Remember, Recall, Correct, and Recover actions;
- no founder involvement during the normal journey.

The product priority remains governed task-specific memory guidance through
project-safe Remember and Recall. The original implementation sequence started with one
narrower trust-bearing vertical slice:
**Verified Resolve**. It proved the shared product discipline — plan, explicit
authority, one semantic write, authoritative readback, atomic Home refresh,
scoped Recall verification, compensation, and a privacy-safe receipt — before
that discipline extended to project safety, the rest of Correct, and Recover.
Those product-loop slices now exist in local source; their exact-package gates
remain open. The 2026-08-31 advanced-dashboard product/evidence audit is
complete, and the 2026-09-01 cross-surface and feature-preservation correction
is now locked in this PRD. The corrected source prototype is implemented. The
next product gates are unfamiliar-operator comprehension trials and an exact-
package acceptance pass, not another product-model rewrite.

## 1. Customer and product boundary

**Owner:** Elefante product owner

### Customer

The first customer is one technical owner inside a small or medium company. The
customer uses an AI agent on recurring projects and wants accumulated knowledge
to improve later tasks. Normal work must not require operating Elefante
internals; the same technical owner may enter the advanced dashboard when they
want to inspect, maintain, or recover the system.

The first product supports one human owner and one local installation. A company
can purchase it, but this PRD does not define shared team memory or multiple
human permissions.

### Customer promise

**Primary commercial promise:** Your agent should not start from zero.

The customer can say:

> Elefante draws from what I asked it to remember, gives my agent the best
> governed advice it can justify for the current task and project, and lets me
> inspect, correct, and recover the system behind that advice.

That sentence is the product contract. Every screen, package feature, and test
must support it.

### What is being sold

The sellable unit is an official Elefante package that makes the complete
experience work without contacting the founder. It includes:

- a verified build for the supported environment;
- guided installation and agent connection;
- project setup and isolation;
- a real disposable Recall test;
- the advanced local dashboard, Elefante Home;
- backup, restore, repair, update, rollback, and uninstall;
- a privacy-safe support report;
- an acceptance receipt proving the installation works.

Payment, licensing, and distribution are later decisions. They are not product
dependencies and are not implemented by this PRD.

## 2. Product assembly and ownership

**Owner:** Elefante product owner

Elefante is one product with six owned lifecycle capabilities, supporting
intelligence capabilities, three operating surfaces, and one public proof
surface. A surface may compose capabilities, but it may not become a competing
service or write directly into another capability's data.

| Product capability | Customer job | Owning component | Primary surface |
|--------------------|--------------|------------------|-----------------|
| Install and Connect | Make Elefante work | Installer | Official package |
| Projects | Tell Elefante where knowledge belongs | Project Registry | Installer and Home |
| Remember | Preserve knowledge deliberately | Memory Service | Agent; Home as fallback |
| Recall | Supply the smallest governed task-specific memory bundle or abstain | Recall Service | Agent |
| Correct | Fix or retire stored knowledge | Memory Service | Home and agent |
| Recover | Protect or restore the product and data | Lifecycle Manager | Home |

| Customer surface | Primary job | Boundary |
|------------------|-------------|----------|
| Official package | Install, connect, repair, update, rollback, and uninstall | Owns product lifecycle, not memory semantics |
| Connected agent | Perform normal tasks; Remember, Recall, and request correction | Primary task and value-delivery surface |
| Elefante Home | Inspect evidence, perform verified maintenance, and Recover | Advanced local console; underlying services still own every action |

The Home Shell owns presentation, navigation, local control-session handling,
and composition. The Project Registry, Memory Service, Recall Service, and
Lifecycle Manager remain authoritative for their own behavior.

### One contract across package, IDE, Home, and website

| Surface | What the user experiences | Required alignment | Must never imply |
|---------|---------------------------|--------------------|------------------|
| Official package | Installs one local daemon, connects selected hosts, proves disposable project-scoped Recall, and owns repair/update/rollback/uninstall | Installed build, host registration, daemon, dashboard, and acceptance receipt identify the same product | A copied file or green installer screen proves the connected workflow |
| Connected IDE or agent | Recognizes a memory-dependent task, calls Recall once with the complete question, reasons over supplied evidence or a terminal abstention, and writes only through explicit governed flows | Every compatible host receives the same Recall, write, correction, project, and restart semantics; only adapter mechanics differ | MCP presence alone causes automatic use, or retrieved memory is automatically correct |
| Elefante Home | Understands the whole corpus read-only, inspects one real Recall event, and performs project-bound maintenance or product-wide recovery | Dashboard labels and evidence map to the same services and postconditions used through MCP | Inventory vitality predicts the next task, or a proxy score proves quality or causal value |
| `elefante.ai` | Understands the problem, released solution, evidence boundary, supported hosts, and download | Copy, screenshots, capability counts, and release identity describe the published package only | Local candidate behavior or developer outcome hypotheses are already shipped |
| Task Intelligence program | Tests whether governed memory changes accepted task outcomes at acceptable total token cost | Uses real task evidence and keeps negative or inconclusive results visible | Infrastructure, retrieval, token savings, or one task proves representative lift |

The IDE-session behavioral contract is fixed:

1. A host restart clears that host's conversational buffer, not Elefante's
   durable memory.
2. The fresh host loads its Elefante bootstrap and opens a new MCP session.
3. When prior decisions, preferences, or project context may matter, the agent
   calls `elefante-Recall` at most once with the complete standalone question
   and exact workspace when known.
4. `supplied`, `no_match`, `blocked`, and `unavailable` are meaningful terminal
   results. The agent does not broaden or retry merely to force memory.
5. Supplied memory is evidence for reasoning, not an instruction to ignore the
   user's current request or current source.
6. Durable capture requires explicit authority, search-before-write, one
   concise record, and a likely future Recall verification. Ordinary chat is
   not silently remembered.
7. Correction and recovery use the same preview, authority, verification,
   rollback, and receipt contracts regardless of whether the request began in
   an IDE or Home.

The browser is not an IDE integration. A healthy installed Home opens directly
through the loopback daemon; no extension, connector, agent command, or
capability-bearing bookmark is required. Host, port, and launch origin are
transport details and may not become alternate product modes or user handoffs.

### Capability preservation and value map

This table places the developed feature set inside the same product. It does
not require every feature to become a top-level navigation item.

| Developed capability | Unique question or value | Primary product home | Truth boundary |
|----------------------|--------------------------|----------------------|----------------|
| Governed Recall and Context | What prior knowledge is safe and useful for this task now? | Agent through Recall; Home Recall workspace for inspection | A bundle or abstention, not an answer-quality guarantee |
| Memory lifecycle | What has been deliberately retained, and should it remain current? | Agent Memory service; Home Memory Intelligence | Persistence and verified lifecycle, not automatic truth |
| Project Registry and isolation | Which knowledge boundary owns this delivery or mutation? | Package and Home Projects; enforced by Recall/Memory | Read-only all-memory understanding does not create global delivery |
| Vitality, decay, health, and access | Which records deserve human review, and why? | Home Memory Intelligence review | Diagnostic priority, not usefulness, correctness, or deletion authority |
| Retrieval Explanation | What evidence does this returned dashboard-search item actually expose? | Memory detail and Recall workspace | Snapshot lexical evidence is not the MCP five-signal explanation |
| Connections and Decision Graph | How do assumptions, evidence, decisions, safeguards, topics, and explicit relationships connect? | Home Connections; Graph tools for advanced queries | Only represented edges; no invented topology or causality |
| Directives | Which always-active behavioral rules affect normal Elefante operations? | Directive MCP tools; Home Rules inspection is a target | Separate rule store, never disguised as semantic memory |
| Sessions and task graph | What prior work episode or explicit work state must survive a host session? | Session/task MCP tools; Home Activity inspection is a target | Persistent work state, not a replacement agent runtime |
| ETL and Live Distiller | Which raw memories need curation, and what supported session material is deliberately processed? | ETL tools and foreground Distiller; Home Curation status is a target | Explicit enrichment/watch; no silent surveillance or automatic storage |
| Session Intelligence | What consented usage and cost evidence exists? | Optional Home Signal Card and separate local ledger | Metadata-only; unknown usage/cost stays `UNKNOWN`; no per-memory causality |
| Team Sync | Which explicit allowlisted memories should move between trusted local installations? | Signed local bundle workflow; Home Exchange is a target | No cloud transport, ambient sync, or global shared scope |
| Local media attachments | Which bounded local artifact belongs to this memory? | Memory service and memory detail | Storage/integrity only; no implied OCR, transcription, or model analysis |
| Private host events | Did a bounded scrubbed event literally trigger relevant retrieval? | Host adapter and Recall diagnostics | No ambient content retention or host surveillance |
| System state and Dashboard Open | Is the local owner healthy and how do I reach Home? | Package, System tools, bare loopback Home | Management transport, not customer value by itself |
| Recover | Can product/data state be protected or restored with verified postconditions? | Recover service and Home | No arbitrary paths, shell, or unverified success |
| Task Intelligence | Did memory causally improve accepted task value per total token? | Developer evidence program | Default-off and not a customer performance claim until representative proof exists |

The v2.13.0 published capability set, the 18-tool local customer candidate, and
developer-only Task Intelligence are different evidence states. Alignment does
not collapse them or advertise the newest local behavior as released.

### Existing foundations and missing work

| Piece | Existing foundation | Missing product work |
|-------|---------------------|----------------------|
| Install and Connect | Guided native/fallback project selection, strict registry setup, source identity, required Codex detection, optional preview selection, disposable installed-Recall proof, visible managed verified backup, and private acceptance receipt | Exact official-artifact execution, rendered native acceptance, and unfamiliar-user proof |
| Projects | Local unreleased Project Registry, durable strict-intent marker, deterministic workspace mapping, Home management, explicit verified assignment of legacy unscoped memories before strict mode, and a zero-sharing policy flag | Exact official-package project selection and released clean-host acceptance |
| Remember | Verified four-term, project-scoped agent and Home paths with pre-write overlap handling, explicit update/supersede/keep-both choices, post-write Recall proof, and rollback | Exact official-package and supported-agent restart acceptance |
| Recall | Bounded read-only Recall, strict project enforcement, terminal abstention, and a content-free Home test | Exact official-package and supported-agent acceptance of the project-safe path |
| Correct | One verified Edit, Replace, Resolve, Archive, Restore, and backup-bound permanent-delete flow shared by MCP and Home; desktop and narrow-screen destructive-flow rendering verified with synthetic data | Exact-package, keyboard/accessibility, and unfamiliar-user destructive-flow acceptance |
| Recover | Home health/backup/restore/support, one package-maintenance handoff with a safe result receipt, and verified package repair, update, rollback, and data-preserving uninstall | Exact official-artifact lifecycle execution and interruption matrix |

Home is therefore not a seventh capability. Its existing foundation is a
snapshot-first local console with readiness, memory inspection, relationships,
project review, verified Correct/Resolve, Recover, and package-maintenance
guidance. Its missing work is a truthful operator workflow, evidence-led
information architecture, and exact-package usability and accessibility proof.

No new product piece is added unless none of these owners can truthfully own the
customer need.

## 3. Install and Connect

**Owner:** Installer

**Customer surface:** Official package; Home is the optional advanced post-install control surface

### Customer promise

The customer runs one package, makes a small number of understandable choices,
and receives proof that Elefante works with Codex.

### Customer flow

1. Open the official package.
2. See whether this computer and Codex are supported.
3. Optionally choose detected compatibility-preview hosts to connect.
4. Choose and name project folders.
5. Review the Elefante-managed local backup location.
6. Review what Elefante will install and own.
7. Install.
8. Watch a real Remember-and-Recall acceptance check.
9. Receive a clear result: **Ready** or one safe next action.
10. Return to the agent.

The certified path must not require editing configuration, managing Python, or
running terminal commands.

### Elefante responsibility

- Verify package identity before changing the machine.
- Require and configure Codex; configure only the additional preview hosts the
  customer explicitly selects.
- Install one managed local runtime for the certified environment.
- Create the Project Registry from the selected folders.
- Display the backup destination derived from the managed data layout and create
  a verified baseline backup there; offer no arbitrary setup-time path choice.
- Create a unique non-secret acceptance memory, retrieve it through the actual
  selected agent path, remove it, and prove removal.
- Produce a human-readable and machine-readable acceptance receipt.
- Preserve existing customer files and registrations it does not own.

The fixed `Indigo-Echo` demonstration is replaced by the generated disposable
check. A failed cleanup means the installation is not Ready.

### Failure promise

- Preflight failure changes nothing.
- Interrupted installation can be resumed or rolled back.
- A failed agent connection identifies the failed stage and does not claim
  success from daemon health alone.
- A failed upgrade preserves the previous working product and data.
- Every failure ends with one customer action, not a raw stack trace.

### Complete when

An unfamiliar customer can start from the exact official package on a clean
supported computer and reach a verified Recall without founder help, a developer
checkout, or a terminal.

## 4. Projects

**Owner:** Project Registry

**Customer surface:** Installer and Home settings

### Customer promise

Knowledge from one project does not appear in another project. Shared memory and
cross-project delivery are deferred from the first release.

### Customer flow

1. Choose a folder and give the project a visible name.
2. See which agent/workspace paths map to that project.
3. Add, rename, move, deactivate, or remove a project registration in Home.
4. Review old unscoped memories during an upgrade instead of having Elefante
   silently guess where they belong.

### Elefante responsibility

- Assign each project a stable opaque ID independent of its display name.
- Map the current workspace to one unique registered project.
- Use the unique deepest registered folder when projects are nested.
- Ask the customer when no project matches or the result is ambiguous.
- Put every new customer memory in an explicit project scope.
- Keep shared-across-projects memory and delivery out of the first release.
- Never infer project scope from semantic similarity or memory content.

Clean installations start in strict project mode. Upgrades preserve existing
unscoped memories and enter a review/compatibility state; they never relabel
those memories silently.

### Failure promise

If Elefante cannot identify one project, it stores and supplies nothing until
the customer or agent provides the project. Ambiguity is visible; it is not
converted into global memory.

### Complete when

Two projects can contain opposite decisions about the same subject and each
agent session receives only the decision belonging to its active project. The
tolerated cross-project exposure count is zero.

## 5. Remember

**Owner:** Memory Service

**Customer surface:** Agent first; Home as an explicit manual alternative

### Customer promise

When the customer explicitly asks Elefante to remember something, Elefante
stores one clear, project-scoped record and proves that it can be recalled.

### Customer vocabulary

The customer chooses or naturally expresses only four kinds of durable
knowledge:

| Customer term | Meaning | Existing engine representation |
|---------------|---------|--------------------------------|
| Decision | A choice that should guide later work | `decision` |
| Constraint | A boundary later work must respect | `specification`; use `directive` only when the customer explicitly requests enforced behavior |
| Preference | A stable way the customer wants work done | `preference` |
| Lesson | Something learned that should change later work | `insight` |

The internal representation is owned by the Memory Service and is not shown as
a schema decision the customer must understand.

### Customer flow through the agent

1. Customer says what to remember.
2. Agent identifies the current registered project.
3. Elefante searches for the same concept before writing.
4. If there is no duplicate or conflict, Elefante stores it without another
   unnecessary confirmation.
5. If an existing record materially overlaps, the agent asks whether to update,
   supersede, keep both, or cancel.
6. Elefante verifies one likely future Recall in the background.
7. Customer sees a short receipt: what was remembered, for which project, and
   whether Recall verification passed.

Ordinary conversation is not captured automatically. The explicit Remember
request is the authority.

### Failure promise

- Missing project: ask for the project; write nothing.
- Possible duplicate or conflict: show the relevant difference; guess nothing.
- Invalid or secret-like content: reject before persistence and explain why.
- Stored but not recallable: report verification failure and offer Correct or
  diagnosis instead of claiming success.

### Complete when

The customer can preserve each of the four knowledge kinds through the agent,
restart the agent, ask a natural future question, and receive only the applicable
project memory.

## 6. Recall

**Owner:** Recall Service

**Customer surface:** Agent; Home provides only a manual test and inspection

### Customer promise

When prior project knowledge can materially improve the current answer,
Elefante supplies the smallest safe useful set. When it cannot, it says so and
does not force unrelated history into the answer.

### Customer flow

1. Customer asks the agent a normal work question.
2. The agent calls Recall once when prior decisions, constraints, preferences,
   or lessons may matter.
3. Recall determines the active registered project.
4. Recall supplies a bounded set or returns no match.
5. The agent uses supplied memory as evidence alongside current project files
   and current customer instructions.
6. If Recall is unavailable, the agent says prior Elefante context was not
   available and continues only from current evidence.

The customer does not select tools, tune search modes, or choose graph/vector
behavior during normal Recall.

### Elefante responsibility

- Read only; Recall never changes memory.
- Apply project scope, lifecycle, protection, provenance, and conflict rules.
- Abstain when relevance or authority is unsafe.
- Keep responses bounded.
- Never retry a terminal no-match, blocked, or unavailable result for the same
  customer question.
- Do not claim that the UI can explain a specific selection unless the runtime
  has evidence for that selection. Home may show snapshot provenance and
  lifecycle evidence separately, but must not relabel either as the reason a
  memory was selected.

### Failure promise

Wrong-project or ambiguous-project context supplies nothing. Unavailable Recall
does not block the customer's work or fabricate prior knowledge; it produces a
clear health action in Home.

### Complete when

Recall passes relevant, irrelevant, conflicting, missing-project, unavailable,
and two-project isolation scenarios through the actual supported agent path.

## 7. Correct

**Owner:** Memory Service

**Customer surface:** Home first; agent may open or invoke the same flow

### Customer promise

The customer can see what Elefante knows, fix what is wrong, and preserve a
trace of what changed without understanding storage internals.

### Customer flow

1. Search or browse memories for one project.
2. Open a memory and see content, project, source, age, protection, and whether
   another memory conflicts with or replaces it.
3. Choose one understandable correction:
   - **Edit** for a mistake that does not change the meaning;
   - **Replace** when a newer decision supersedes the old one;
   - **Resolve** when two records conflict;
   - **Archive** when a record should stop appearing;
   - **Delete permanently** only through an advanced destructive flow.
4. Preview the result when more than one record changes.
5. Apply the correction.
6. Verify that future Recall reflects the correction.

### Elefante responsibility

- Route every correction through the daemon's governed Memory Service.
- Never let Home write directly to SQLite, Kuzu, or durable files.
- Never choose a conflict winner from similarity, age, or confidence alone.
- Preserve the old assertion when replacing it so the history remains
  inspectable.
- Re-mine only deterministic concept links after content correction; preserve
  explicit relationships and restore the prior projection on failure.
- Make archive recoverable.
- Require explicit authority, exact target, reason, and repeated confirmation
  for permanent deletion or protected knowledge. Permanent deletion must create
  and verify a temporary backup, restore it on failure, and destroy it only
  after every absence check succeeds.
- Refresh Home only after the correction is verified.

### Failure promise

A failed correction leaves the prior valid memory and Home snapshot intact. The
customer sees whether nothing changed, the operation rolled back, or recovery is
required.

### Complete when

Edit, replace, resolve, archive, unarchive, and permanent-delete scenarios pass
through Home, including protected and ambiguous conflict cases, and the next
Recall reflects only the verified result.

## 8. Recover

**Owner:** Lifecycle Manager

**Customer surface:** Home

### Customer promise

The customer can protect data, diagnose a problem, reverse a failed change, and
remove Elefante without needing the founder.

### One operation pattern

Every recovery action follows the same visible sequence:

```text
Plan -> show impact -> confirm -> execute -> verify -> receipt
```

If execution fails, the receipt says whether Elefante changed anything, whether
the previous state was restored, and the one safe next action.

### Customer actions

- **Check health** — show Ready, Needs attention, Recovery required, or
  Unsupported, with one next action.
- **Back up now** — create and verify a local checksummed backup.
- **Restore** — inspect a backup, preserve current data, restore into staging,
  verify, then switch.
- **Repair** — reinstall owned product files and reconnect selected agents while
  preserving data and customer-owned configuration.
- **Update** — verify the new official package, back up, install, run Recall,
  and roll product code back automatically if verification fails.
- **Roll back** — return product code to the prior verified version without
  pretending that code rollback reverses data changes.
- **Uninstall** — remove only installer-owned unchanged files and connections;
  preserve data unless the customer separately requests its deletion.
- **Create support report** — export a previewable privacy-safe diagnostic
  package.

### Support report boundary

The report may include product/build identity, operating environment, agent
connection status, diagnostic codes, backup validity, and operation receipts.
It excludes memory content, project names and paths, prompts, questions,
answers, transcripts, credentials, environment values, and host configuration
contents. The customer previews the manifest before export.

### Elefante responsibility

- Use existing doctor, backup, restore, restart, installer, and uninstall logic
  instead of creating competing procedures.
- Require a verified backup before any operation that may make durable state
  incompatible or difficult to recover.
- Resolve exact targets and reject broad or unsafe paths.
- Keep product-code rollback and data restore separate in language and behavior.
- Record bounded stage receipts that contain no customer content.
- Make interrupted operations inspectable and resumable or safely reversible.

### Complete when

Backup, restore, repair, successful update, forced-failure update rollback,
uninstall-with-data-preserved, reinstall, and support-report privacy scenarios
pass on the exact supported package.

## 9. Elefante Dashboard (Home)

**Owner:** Home Shell

**Customer surface:** One local Elefante dashboard. Host, port, and launch origin
are transport details; they must never become alternate product modes, alternate
Homes, or user-facing handoffs.

### Role and audience

The dashboard is Elefante's advanced maintenance and control console: the
engine room for inspecting and maintaining the memory-to-Recall machinery. It is
not the primary product-onboarding surface, the marketing value surface, the
daily task surface, or a generic analytics dashboard.

The normal customer experiences Elefante through the agent and the guided
package lifecycle. The advanced technical owner enters the dashboard to
diagnose, inspect, maintain, correct, verify, or recover Elefante. Advanced does
not mean cryptic: every status, signal, and operation must still state what it
means, why it matters, and what the safe next action is.

The storefront may show an exact released Home capture as product proof. That
does not turn Home itself into a sales page or authorize invented controls,
metrics, or retrieval claims. The storefront may sell governed continuity and
inspectability; it may not use a heuristically featured inventory memory as
proof of what shaped one real answer or of improved task performance.

On first visit, Home gives one orientation, not a product tour: **Elefante makes
memory useful for the next task; Home lets advanced users understand, improve,
and protect that system.** It shows the strongest evidence currently available
and one safe next action. A direct visit must not turn missing operational proof
into a product-failure banner or require an IDE, extension, connector, or second
address to explain the product.

### Operating objective

The dashboard must let the advanced owner answer:

1. What memories, review signals, themes, stored vitality values, and explicit
   relationships are represented across Elefante as a whole?
2. Which observations are direct snapshot evidence, which are operation
   receipts, and which remain unknown?
3. For one real project-scoped question, did Recall supply a bundle, abstain
   with no match, block delivery, or become unavailable?
4. Which memories were selected by the current Home Recall contract?
5. What direct evidence supports reviewing a memory, and what does that evidence
   *not* establish?
6. Is a maintenance action justified, or is **No action** the correct result?
7. If an action was applied, did the authoritative store, Home projection, and
   scoped Recall postcondition agree?
8. If the product is unhealthy, what is the one safe recovery action?

Home does not decide whether an answer was intelligent. It makes the inputs,
boundaries, abstentions, and verified maintenance of Recall understandable.
Representative task improvement belongs to Task Intelligence evidence and is
**NOT PROVEN**.

### Operator golden paths

Home starts with the owner's job, not readiness theater:

```text
Global understanding (no project)
  -> inspect Memory Intelligence
  -> inspect Topics, Vitality, and explicit Decision Graph relationships
  -> review direct evidence or stop with No action

Task intelligence (project-bound only when acting)
  -> bind the exact project
  -> Remember durable guidance or run one real Recall Check
  -> inspect only the returned receipt and selected IDs
  -> choose No action or preview one justified correction
  -> apply once and verify store, Home, and scoped Recall

Continuity (product-wide)
  -> check health
  -> inspect the timestamped receipt
  -> back up, restore, or create a support report only when justified
```

Overall understanding never requires a project. Project identity becomes
mandatory only at the boundary where Elefante selects task context or changes
durable project memory. Every path permits a healthy conclusion and must never
pressure the operator to mutate memory merely to complete the journey.

### Information architecture

The preservation-first prototype has six stable operator workspaces:

1. **Home** — one product purpose, the strongest current evidence, three operator
   jobs (Global understanding, Task intelligence, Continuity), one recommended
   next action, and optional advanced Session Intelligence.
2. **Recall** — the advanced Recall Inspector inside the Recall feature; its
   first version runs one ephemeral, project-scoped Recall Check and explains
   only the evidence that response actually carries.
3. **Memory Intelligence** — the complete read-only corpus plus Library,
   Review, vitality/decay, health, access history, provenance, lifecycle,
   curation/ETL state, attachments, and contextual Correct controls.
4. **Connections** — Topics, stored Vitality, explicit relationships, and the Decision
   Graph. It remains a substantial workspace for understanding *between*
   memories and is not folded into a memory-detail drawer.
5. **Projects** — registration, active state, scope boundaries, and unassigned
   memory review.
6. **Recover** — health, backup, restore, support, and official-package
   lifecycle guidance.

Rules, Activity, Curation, Exchange, attachment inspection, and private-trigger
diagnostics remain preserved advanced modules under the workspace named in the
capability-value map. A module may stay unavailable until its truthful read
contract exists; unavailable is not deletion.

`Recall`, not `Advice`, is the truthful label. Elefante currently selects a
memory bundle; it does not synthesize an advisory answer. This navigation is a
prototype hypothesis, not implementation authority. Low-fidelity operator
testing may change hierarchy, wording, or disclosure, but it starts from the
full capability map and may not silently eliminate a unique operator job.

The developed Briefing ideas are preserved where their evidence has real value,
not as a random narrative on Home:

- inventory review priority belongs to **Memory Intelligence → Review**;
- explicit reasoning trails belong to **Connections → Decision Graph**;
- a **Recall Briefing** may appear only after a real Recall Check and must be
  bound to that event's terminal status, project, selected IDs, conflicts, and
  verification time.

Home must not present a heuristically chosen inventory memory as “shaping your
next answer,” “what agents carry forward,” or evidence of why it “endures.” This
relocation preserves the ideas while removing unsupported duplication.

### Evidence capability matrix

**Source basis (2026-09-01):** `docs/reference/dashboard-snapshot.md`,
`src/dashboard/server.py`, `src/mcp/server.py::_handle_home_recall_test`, and the
current `HomeStatePanel`, `RecallTab`, and `RetrievalExplanation` UI contracts. Reverify these
before implementation because this matrix describes local source, not a
released customer artifact.

| Evidence or operation | State | What Home may truthfully show | Hard limit |
|-----------------------|-------|--------------------------------|------------|
| Validated memory snapshot | CURRENT LOCAL | Memory content, declared type, project, provenance fields, lifecycle, explicit relationships, represented conflicts, freshness/vitality diagnostics, and snapshot time | Private local inventory; not proof of task relevance, truth, or usefulness |
| Snapshot lexical search | CURRENT LOCAL | Literal query overlap, returned order, configured storage source, health, and represented relationships | Not the MCP five-signal selection explanation |
| Project-scoped Home Recall Check | CURRENT LOCAL | `supplied`, `no_match`, `blocked`, or `unavailable`; selected count and up to three selected memory IDs/titles; conflict count; project; verification time; no returned memory content | No selected-memory reason, withheld IDs/reasons, per-signal values, or historical trace |
| Vitality, decay, health, access, and provenance | CURRENT LOCAL | The documented diagnostic value, formula/reason, source field, and review implication | No automatic truth, quality, utility, scope, merge, archive, or delete judgment |
| Topics, explicit relationships, and Decision Graph | CURRENT LOCAL | Distribution, represented links, named direction, and source-grounded reasoning trails where the snapshot carries them | No invented topology, causal path, or claim that the trail drove a task |
| Optional Session Intelligence | CURRENT RELEASE | Consented metadata-only Signal Card, evidence provenance, and explicit unknowns | No prompts/transcripts, automatic consent, provider invoice substitution, or per-memory outcome attribution |
| Verified Correct and Recover receipts | CURRENT LOCAL | Preview, authority, result, rollback state, and named postconditions carried by the existing operation contract | Home does not reimplement or bypass the owning service |
| Coherent operator workflow and clear light/dark shell | CURRENT SOURCE PROTOTYPE | One product purpose, three operator jobs, evidence-qualified states, and the next safe action | Installed-package and unfamiliar-operator acceptance remain separate gates |
| Historical Recall traces | OUT OF SCOPE | None | No raw question or task history is created for dashboard convenience |
| Per-memory outcome attribution | NOT PROVEN | `No linked outcome evidence` where that question is relevant | Aggregate Session Intelligence cannot establish that one selected memory improved one task |
| Automatic duplicate, semantic wrong-scope, or factual-truth judgment | OUT OF SCOPE | Only an explicit detector result from a future approved contract | Similarity, age, project difference, or low connectivity cannot establish these defects |

The **Memories** area therefore uses **Review**, not **Quality**. Review groups
evidence that may deserve human inspection without claiming an automatic grade.
It may show Library, represented relationships, and lifecycle state only where
the snapshot carries them. A missing field is shown as unavailable; it is not
derived from a convenient proxy.

### Scope contract

Home separates **view scope** from **action scope**. `All memories` is a
read-only installation-wide view over the validated local snapshot. It is not a
storage scope, a shared-memory feature, or a global agent-delivery path.

| Scope | What the owner can inspect | Allowed operations | Hard boundary |
|-------|----------------------------|--------------------|---------------|
| All memories view | Library, declared project ownership, supported review signals, represented relationships, lifecycle, and unassigned items | Browse, filter, inspect, and deliberately choose a project or memory | No implicit Recall, mutation, cross-project ranking, conflict inference, or delivery |
| Active Project action scope | Project memories, supported review evidence, lifecycle, corrections, and the current ad hoc Recall Check | Remember, Recall Check, and Correct through existing verified boundaries | Missing or ambiguous project identity fails closed before delivery or mutation |
| Recover | Product health, backup, restore, support, and official-package lifecycle state | Existing verified lifecycle operations | Recover is product-wide, but any required Recall postcondition remains project-scoped |

Action-scope behavior is deterministic:

- with zero active projects, the owner can inspect `All memories`, register a
  project, and use eligible Recover operations; Remember, Recall Check, and
  Correct remain unavailable;
- with one active project, Home may bind that project visibly;
- with multiple active projects, the owner explicitly chooses one before any
  project-scoped action;
- a correction opened from `All memories` must bind the exact owning project
  before preview or apply.

The same or similar statement in two projects may be legitimate. Home may not
label it a conflict merely because it appears across projects. Unassigned or
invalid registry ownership is observable; semantic “wrong scope” remains a
human judgment unless a future approved contract supplies stronger evidence.

### Maintenance loop

The advanced console follows one understandable operating loop:

```text
Check -> inspect evidence -> No action or preview one correction -> apply once -> verify -> recover if needed
```

Every mutation keeps the existing plan, authority, one-write, readback,
rollback, and receipt requirements. A diagnostic signal never authorizes a
mutation by itself.

| Signal | Supports | Does not establish |
|--------|----------|--------------------|
| Age or decay | Freshness and possible review priority | Factual invalidity or irrelevance |
| Vitality or health label | Snapshot inspection status under the documented formula | Task usefulness, correctness, or automatic repair |
| Access count | Prior exposure/access under the current metadata contract | Use, acceptance, causal value, or endorsement |
| Orphan label | No represented graph neighbor in this snapshot | Uselessness or deletion eligibility |
| Provenance or source reliability | Where the record came from and declared source confidence | Truth |
| Explicit conflict evidence | A represented contradiction requiring review or blocking under the conflict contract | A global winner or cross-project conflict |
| Lexical match or snapshot score | Inventory-search evidence or dashboard vitality | Query-specific MCP relevance or the “best” memory |

Home may recommend **Review**, **No action**, or an existing named operation.
It may not recommend archive, delete, merge, re-scope, or replace from a single
proxy score.

### Data and explanation boundary

- Normal dashboard mode reads only a validated snapshot.
- Recall Inspector may show only the fields in the current Home Recall Check
  response. It cannot infer reasons for selected or withheld memories.
- The current snapshot does not contain a full task trace or per-query
  five-signal explanation. Snapshot lexical search remains separately labeled.
- No dashboard field may be invented to complete a design. Every field maps to
  a maintained source contract or is explicitly labeled as a missing gap.
- The dashboard snapshot can contain private memory content and remains local.
- Recall Check is ephemeral by default. Home must not persist raw questions,
  prompts, tasks, or trace history without a separately approved purpose,
  consent, retention, export, and deletion contract.
- No feature exposes private chain-of-thought.
- Aggregate Session Intelligence remains a separate evidence plane and cannot
  be attributed to one selected memory or Recall event.
- Task Intelligence remains unreleased evidence work. The dashboard may not
  present representative task lift as shipped or proven.

If the low-fidelity workflow cannot be honest with current data, preserve the
capability and choose the smallest truthful treatment: correct its claim,
relabel it as diagnostic, show the missing evidence, move detail behind
progressive disclosure, or mark the control unavailable. A new read-only
contract is proposed only for a unique operator decision with a real
consequence that cannot otherwise be made safely. Deletion is a separate owner
decision and requires the Product Contract Lock evidence test.

### Control boundary

- A direct loopback dashboard visit establishes a short-lived authenticated
  local control session without an IDE or browser connector. Establishing the
  session does not itself change product or memory state.
- With one active project, Home may bind it deterministically. With several
  active projects, the owner chooses one before project-scoped actions.
- The session exposes only named product operations, never arbitrary shell,
  path, query, raw-store, or MCP execution.
- Memory changes go through the Memory Service.
- Lifecycle changes go through the Lifecycle Manager.
- `All memories` cannot be used as an implicit scope for mutation or Recall.
- Closing, timeout, restart, or explicit lock ends control authority.

The exact token/session transport belongs in a technical design. This PRD owns
the behavior and security outcome, not a premature browser protocol.

### Visual and interaction contract

- Default to a clear, high-contrast light operational theme and preserve a
  complete dark equivalent. Exact color tokens belong in the later technical
  design, not this PRD.
- Preserve the exact canonical Elefante mark. The website's copper Matrix and
  scroll choreography remain marketing devices; the dashboard uses a calm,
  stationary operational shell.
- Use progressive disclosure: lead with the operator's job, evidence, impact,
  and next action; place raw counts, scores, engine details, and diagnostics in
  secondary detail.
- Technical language is allowed for the advanced audience, but every term must
  be defined in context. Navigation and controls use job-based labels and
  explicit verbs rather than unexplained internal nouns.
- Product status is compact. Counts and signals support a diagnosis; they do
  not dominate hierarchy or imply value.
- Essential body copy and controls are at least 14 CSS pixels. Smaller metadata
  may not be the sole carrier of state, authority, safety, or instructions.
- Normal text meets WCAG AA contrast, focus is always visible, and color is not
  the only state signal.
- Desktop is the primary advanced-operation target. At 390 x 844, readiness,
  scope, inspection, Recover entry, and every already-supported safety-critical
  correction flow remain usable without hidden actions or horizontal clipping.
  A future dense graph or analysis may be desktop-only only when Home says so
  explicitly and offers a safe read-only alternative.
- Keyboard, 200% zoom, visible focus, reduced motion, and screen-reader state
  names remain release evidence.

The earlier dark-first Memory Intelligence design record remains valid history
for the current implementation. This section is the prospective advanced
dashboard contract and supersedes that shell only after separate implementation
and release approval.

### Complete when

Before visual design, a low-fidelity prototype using synthetic, clearly labeled
data must prove the golden path with only fields in the evidence capability
matrix. Before release, at least three unfamiliar advanced technical users,
without founder explanation, must each be able to:

1. explain that Home maintains Elefante while normal tasks happen in the agent;
2. identify the current action scope and what is unavailable with zero, one,
   or multiple active projects;
3. run a project-scoped Recall Check and correctly distinguish `supplied`,
   `no_match`, `blocked`, and `unavailable`;
4. open a selected memory when its ID exists in the snapshot and state what the
   displayed evidence does and does not prove;
5. choose **No action** when no repair is justified;
6. preview one supported correction, verify its postconditions, and recover from
   a supplied failure scenario;
7. state `No linked outcome evidence` when asked whether a selected memory
   improved the task.

The prototype and exact package must cover this state matrix: ready/no action,
zero projects, one project, multiple projects, stale snapshot, daemon
unavailable, Recall no-match, conflict-blocked Recall, a selected ID absent from
the snapshot, correction failure with rollback, and recovery required.

Release acceptance requires 3/3 task completion, zero accepted cross-project or
unscoped mutations, zero invented causal or relevance explanations, and zero
founder intervention. Dashboard success is accurate diagnosis, safe verified
closure, and reduced support burden. Representative task lift is a separate
Task Intelligence gate.

The dashboard is not required to perform general product marketing or replace
installer/agent onboarding. Rendered desktop and 390 x 844, light and dark,
keyboard, screen-reader, 200% zoom, and reduced-motion states must be inspected.
Exact-package evidence, not a source mock or synthetic screenshot, remains
release authority.

## 10. Build order

**Owner:** Elefante product owner

Build vertical customer slices. Do not build Home screens over incomplete
headless behavior.

### Slice 1 — Verified Resolve trust wedge

**Owners:** Memory Service and Home Shell

- Plan one conflict resolution against exact record and scope hashes.
- Require an explicit winner, reason, disposable verification question, and any
  protected-record confirmation before apply.
- Perform the semantic write once; never retry it automatically.
- Verify authoritative readback, atomic Home refresh, and scoped Recall.
- Compensate from the exact preimage when a postcondition fails; report an
  incomplete compensation as Unsafe.
- Expose only this named operation through a short-lived local Home capability.

**Exit:** Home can resolve one real conflict and truthfully report Verified,
Failed with no change, Failed and rolled back, Needs review, or Unsafe. No raw
memory content or customer-entered reason/question appears in the receipt.

This slice is an implementation wedge, not a reprioritization of the product.
It is deliberately operation-specific; a shared lifecycle framework is
extracted only after a second operation proves the common shape.

### Slice 2 — Project-safe memory loop

**Owners:** Project Registry, Memory Service, Recall Service

- Implement project registration and deterministic workspace mapping.
- Require explicit project scope for new memories.
- Complete Remember and Recall headlessly.
- Prove two-project isolation with conflicting decisions.

**Exit:** restart-safe Remember and Recall work through the supported agent, with
zero cross-project exposure.

**Implementation status (2026-08-29): LOCAL SOURCE COMPLETE / NOT INSTALLED OR
RELEASED.** The private versioned registry assigns stable project IDs, maps the
current workspace to the unique deepest active root, and gives strict mode a
separate durable intent marker so loss or corruption of the registry fails
closed instead of reverting to global memory. Remember stamps and verifies the
project identity; Search and Recall enforce the same project; Home can add,
rename, move, activate, deactivate, and remove registrations without touching
project files or memories. Registry, intent marker, and Home projection are
published or restored as one checked operation. A real SQLite/Kuzu restart test
proved opposite decisions remain isolated, and the broader project-control gate
passed 230 tests with 3 intentional deselections. The production UI build and
desktop, narrow-screen, keyboard, reduced-motion, read-only, missing-folder,
stable-ID, strict-confirmation, and removal browser acceptance also passed.
Official-package project selection, disposable clean-client acceptance,
upgrade review, backup/restore coverage, installation, and release remain later
gates.

### Slice 3 — Complete correction

**Owners:** Memory Service and Home Shell

- Extend the verified operation pattern to edit, replace, archive, restore, and
  delete, preserving the distinct authority and reversibility rules of each.
- Complete Home inspection and correction flows.
- Prove scoped Recall after every correction type.

**Exit:** the customer can fix stale, wrong, duplicate, or conflicting
knowledge without direct store access or founder help.

**Implementation status (2026-08-30): LOCAL SOURCE COMPLETE / DESTRUCTIVE UI
DESKTOP AND NARROW-SCREEN RENDERING VERIFIED / EXACT-PACKAGE AND ACCESSIBILITY
ACCEPTANCE PENDING / NOT INSTALLED OR RELEASED.**
One shared verified-operation boundary owns Edit, Replace, Archive, Restore,
and advanced permanent deletion, while Resolve keeps its explicit two-record
authority decision. Every operation plans against exact record, graph,
relationship, content, and project-scope hashes; writes once; verifies SQLite,
Kuzu, the atomic Home snapshot, and scoped Recall; and restores the exact
preimage when a postcondition fails. Edit and Replace atomically re-mine only
deterministic concept links and preserve explicit relationships. Permanent
deletion requires a second confirmation, creates and revalidates a fresh
workflow backup under the same write boundary, verifies the target absent from
the stores, connections, Home, Recall, and unshared attachments, then destroys
that temporary backup. Any failure before completion restores it. Home exposes
the same named operations with content-free one-use tickets and clear
non-recoverable success language. Core, daemon, Home-control, static UI, and
production-build tests pass. Real localhost browser acceptance with a generated
showcase snapshot and mock control responses verified the complete desktop and
390 x 844 flow: exact target, temporary-backup explanation, non-recoverable
warning, disabled action before exact `DELETE`, reachable narrow-screen
controls, and a `Recoverable: No` receipt with backup-removal verification.
That proves the rendered Home contract only; exact-package, keyboard/accessibility,
and unfamiliar-user acceptance remain release gates, while backend mutation and
rollback safety are proven separately by the maintained source and HTTP tests.

### Slice 4 — Recovery

**Owners:** Lifecycle Manager and Home Shell

- Unify health, backup, restore, repair, update, rollback, uninstall, and
  support report under plan / confirm / execute / verify behavior.
- Keep lifecycle authority separate from memory authority.
- Add interruption and forced-failure tests.

**Exit:** every supported lifecycle failure is self-service or produces a safe
privacy-preserving escalation package.

**Implementation status (2026-08-30): LOCAL SOURCE IMPLEMENTED / EXACT-PACKAGE
ACCEPTANCE PENDING / NOT INSTALLED OR RELEASED.** Home now owns Check health,
verified backup, verified data restore, and a privacy-safe support report. The
report is built from a strict allowlist,
shows Included and Never included categories before confirmation, binds apply to
the exact preview hash, creates one private ZIP with one JSON manifest, verifies
readback, removes an untrusted archive on failure, and downloads only through
the short-lived local Home capability. Adversarial fixtures prove memory text,
project paths, prompts, answers, credentials, environment values, host config
contents, unknown receipt fields, and duplicate JSON keys do not enter the
preview or ZIP. Desktop and narrow-screen rendered acceptance passed without
executing an export. The official package separately implements verified
Repair, Update, failed-update rollback, and explicit retained-code rollback.
Its data-preserving Uninstall requires the exact matching package, binds
confirmation to the installed identity, ownership manifest, and content-free
data fingerprint, creates and preflights a new backup, removes only the active
app and unchanged owned connections, proves memories remained byte-identical,
writes private receipts, and lets a verified reinstall reattach the preserved
data root. Stale state, mismatched packages, unsafe paths, and partial
connection removal fail closed or report `NEEDS_HUMAN` without overstating
rollback. Isolated source tests cover success, stale confirmation, forced app
rollback, and partial-detachment escalation. Recover now presents all four code
operations as one package handoff: Home explains whether the matching, newer,
or current package is required, highlights Repair when health selects it as the
one safe next action, keeps code rollback distinct from memory restore, and
shows only the allowlisted content-free result from the last package receipt.
The running app never claims authority to replace or remove itself. Desktop and
390 x 844 rendered acceptance verified the handoff, recommendation, receipt,
and reachable lower content with synthetic health evidence and no package
execution. The release workflow now defines
the supported-package install → uninstall → reinstall proof, including stable
project IDs, verified backup evidence, data preservation, and zero leftover
installer memory. That job and the forced-failure matrix still must run against
the exact artifact; therefore the slice is not yet released complete.

### Slice 5 — Self-service installation

**Owner:** Installer

- Integrate project selection and backup configuration.
- Replace the fixed test memory with generated disposable acceptance.
- Produce the acceptance receipt.
- Prove cancellation, rerun, repair, and failed-install rollback.

**Exit:** clean-package-to-verified-Recall requires no founder or terminal.

**Implementation status (2026-08-30): LOCAL SOURCE IMPLEMENTED / RENDERED AND
EXACT-PACKAGE ACCEPTANCE PENDING / NOT INSTALLED OR RELEASED.** Fresh native
macOS and portable fallback flows require one or more existing project folders,
create strict isolated project scopes, and preserve existing registrations on
repair or upgrade. The installed MCP bridge creates a generated project-scoped
acceptance memory, proves governed Recall, removes it, proves absence, creates a
verified backup, and emits a private content-free receipt. The fixed demo seed
has been removed. Focused lifecycle tests pass; cancellation/rerun/rollback are
covered in source, while the native visual review and exact customer-artifact
run remain gates.

### Slice 6 — Exact official package

**Owners:** Installer and release pipeline

- Package the managed reference environment.
- Sign/notarize the exact customer artifact.
- Run the complete acceptance matrix on clean machines.
- Verify customer documentation against the package, not the source checkout.

**Exit:** the product release scenarios in §11 pass from the exact artifact.

**Implementation status (2026-08-30): BUILD AND A/E LIFECYCLE PIPELINE
IMPLEMENTED / COMPLETE SIX-SCENARIO PIPELINE AND RELEASE EVIDENCE PENDING.**
The customer archive builder and verifier carry the guided installer. The macOS
candidate workflow proves identity, clean first installation, disposable
acceptance cleanup, verified backup, data-preserving uninstall, reinstall, and
stable project IDs. It does not yet execute exact-package Scenarios B, C, D, or
F, native/accessibility acceptance, a real supported-agent restart, or
unfamiliar-user acceptance. Signing, notarization, clean-machine execution, and
all six scenario receipts therefore remain unproven. No package claim follows
from source tests or the partial workflow contract.

### Slice 7 — Advanced dashboard maintenance UX

**Owners:** Elefante product owner and Home Shell

**Status (2026-09-01): SOURCE PROTOTYPE IMPLEMENTED / ISOLATED BROWSER AND
FOCUSED TESTS GREEN / UNFAMILIAR-OPERATOR AND EXACT-PACKAGE ACCEPTANCE PENDING.**

The goal is to make the already-built advanced maintenance console clear and
useful without weakening project isolation, snapshot privacy, truthful Recall
evidence, or verified operations.

#### Specification-driven sequence

| Stage | Deliverable | Exit condition |
|-------|-------------|----------------|
| 7A — Product and evidence audit | Capability/surface ownership, preservation/value map, current claim inventory, source/API/snapshot matrix, operator jobs, state matrix, and unsupported-inference list | **Complete in this PRD:** every developed capability has a unique question, product home, evidence boundary, and release state; unsupported `Advice`, automatic Quality, historical-trace, and task-outcome claims are reclassified without deleting their underlying features |
| 7B — Low-fidelity workflow prototype | Home / Recall / Memory Intelligence / Connections / Projects / Recover content and interaction flow using only current fields and clearly synthetic states | **Source prototype complete; human gate pending:** isolated deterministic-showcase browser proof covers all six workspaces. Three unfamiliar advanced operators must still complete the Section 9 comprehension and decision tasks without founder instruction |
| 7C — Contract decision | For each blocked operator decision, correct the claim or disclosure first; specify one smallest privacy-safe read-only field addition only when the unique decision still cannot be made | No new endpoint, persistence, score, or trace exists without a named operator decision, owner, privacy lifecycle, and fail-first contract; no feature disappears without the Product Contract Lock evidence test and owner approval |
| 7D — Visual and technical design | Approved workflow translated into semantic theme tokens, component/data map, accessibility behavior, migration plan, and fail-first UI assertions | **Complete in source prototype:** light-default semantic tokens, retained dark mode, stable six-workspace hierarchy, and evidence-bounded states are implemented; exact-package visual acceptance remains pending |
| 7E — Implementation | Authorized source and maintained-documentation change | **Complete in local source:** focused dashboard, snapshot, Home control, and UI tests plus the production frontend build pass; no installed runtime or durable customer data changed |
| 7F — Product acceptance | Exact-package state/visual matrix and three advanced-operator trials from Section 9 | All maintenance tasks pass without founder intervention; release/publication remains separately authorized |

#### Known contract surfaces from the pre-write leakage scan

| Surface | Required synchronized change after implementation is authorized |
|---------|---------------------------------------------------------------|
| Shell and navigation | `App`, `TabNav`, tab types, keyboard shortcuts, footer guidance, and persisted view state for the prototype-approved Home / Recall / Memory Intelligence / Connections / Projects / Recover flow |
| Overview inference recurrence | Repaired in local source: Home no longer features a heuristically selected memory. Review priority lives in Memory Intelligence, explicit trails live in Connections, and any Recall Briefing requires an authoritative Recall event. |
| Overview target | `HomeStatePanel` states one product purpose, current evidence, Global understanding, Task intelligence, Continuity, and one safe next action; existing control-session and fail-closed project behavior remain authoritative |
| Recall Inspector | Start with the existing content-free `/control/recall/test` response: status, selected IDs/count, conflict count, project, and verification time. Do not assume reasons, withheld IDs, five-signal values, history, or outcomes. |
| Memory Intelligence | `MemoriesTab`, `MemoryDetailPanel`, Review semantics, vitality/decay, health, access, provenance, lifecycle, curation, attachments, rules/activity modules, and existing corrections; no automatic duplicate, truth, or semantic wrong-scope judgment |
| Connections | Preserve `ExploreTab`, Topics, Vitality, explicit relationships, and Decision Graph as a first-class workspace; do not bury between-memory understanding inside Memory Intelligence |
| Projects and Recover | Existing project isolation, unassigned review, health, backup, restore, support, and package-lifecycle contracts |
| Visual system | Semantic light/dark tokens and component states; exact logo pixels remain unchanged |
| Product documentation | `docs/reference/dashboard-snapshot.md` and the maintained HTML dashboard guide change only when the matching behavior exists |
| Verification | `tests/test_dashboard_ui.py`, routing/reference guards, production build, real browser matrix, and exact-package advanced-operator evidence |

No new raw-store browser access, cross-project Recall path, arbitrary scoring
control, persisted query history, task-outcome claim, or control operation is
assumed. When current validated data cannot support an operator decision,
preserve the capability and correct its claim, hierarchy, disclosure, or
availability state first; expand a read-only contract only under Stage 7C.

**Exit:** advanced operators can diagnose and maintain the memory-to-Recall
machinery without replacing the agent as the daily work surface or turning the
dashboard into a global memory-delivery path.

No slice is assigned to a version or date until the preceding exit passes.

## 11. Product release scenarios

**Owner:** Release pipeline

Tests are organized around the assembled product, not isolated feature counts.

### Scenario A — First use

An unfamiliar customer installs the exact package, the installer detects the
required Codex host, selects two projects, reviews the managed backup location,
passes disposable Recall acceptance, remembers one real decision, restarts the
agent, and recalls it.

**Pass:** no founder instruction, terminal, leftover acceptance data, or
unsupported claim.

### Scenario B — Project isolation

Project Alpha says use one approach; Project Beta says use the opposite. The
customer asks the same question in both projects.

**Pass:** each receives only its own decision; ambiguous/no-project context
receives neither.

### Scenario C — Wrong or stale knowledge

The customer edits a mistake, replaces a changed decision, resolves an ambiguous
conflict, archives an old record, restores an archived record, and permanently
deletes one explicitly chosen record through the advanced flow.

**Pass:** each preview is understandable, history is preserved where promised,
subsequent Recall matches the verified correction, and successful permanent
deletion leaves neither the record nor its temporary safety backup recoverable.

### Scenario D — Product failure

Installation is interrupted, the daemon restarts, an agent session becomes
stale, and an update fails during verification.

**Pass:** data remains safe, the previous working product is restored when
possible, and Home shows one next action.

### Scenario E — Data recovery

The customer creates a backup, changes data, previews restore, restores the
backup, verifies Recall, uninstalls while preserving data, reinstalls, and
recovers it.

**Pass:** checksums, counts, graph integrity, project isolation, and Recall pass;
customer-owned files and registrations remain untouched.

### Scenario F — Support without disclosure

A failure cannot be self-repaired. The customer creates and previews a support
report.

**Pass:** it contains enough product state to identify the failed stage and none
of the prohibited customer content or secrets.

### Current evidence matrix

The source and package gates remain separate. A green source row does not
substitute for execution of the exact customer artifact.

| Scenario | Current authoritative source evidence | What is still required |
|----------|---------------------------------------|------------------------|
| A — First use | Formal runner first installs the supplied package into a new disposable root, then verifies the first-run receipt and backup, two strict projects, acceptance cleanup, Codex health, a real decision, and Recall after a new agent process | Execute it from the final signed/notarized package and collect three unfamiliar-user runs without founder help |
| B — Project isolation | Formal runner first installs the supplied package into a new disposable root, then proves opposite Alpha/Beta decisions, missing-project abstention, invalid-registry abstention, and zero cross-project delivery | Execute it from the final signed/notarized package on the certified lane |
| C — Wrong or stale knowledge | Formal runner first installs the supplied package into a new disposable root, then exercises Edit, Replace, Resolve, Archive, Restore, permanent deletion, scoped Recall, and promised correction history | Execute it from the final signed/notarized package; complete native keyboard/accessibility acceptance |
| D — Product failure | Isolated runner interrupts fresh install, restarts the daemon behind one live agent session, forces a stage-4 host-configuration failure after the candidate payload switch, and verifies exact baseline rollback, Recall, and one Home action | Execute it with one exact candidate and a distinct compatible known-good baseline on the certified lane |
| E — Data recovery | Isolated runner installs the supplied package and verifies backup and restore hashes, SQLite/Kuzu integrity, scoped Recall, stable project IDs, data-preserving uninstall, same-package reinstall, and customer canaries | Execute the complete lifecycle from the final signed/notarized artifact on a clean machine |
| F — Support without disclosure | Formal runner first installs the supplied package, proves Remember/Recall, forces a real failed repair, verifies exact automatic runtime rollback, then checks that Home exposes only the safe support action and that the exported report identifies the failed stage without prohibited disclosure | Execute it from the final signed/notarized package and retain only its content-free receipt |

The 2026-08-30 final local source suite passed 965 tests with 9 intentional
skips. That proves the maintained source contract only. The exact artifact,
native rendered setup, supported-agent behavior, and unfamiliar-user results
remain missing evidence.

`scripts/ci/run_product_release_scenarios.py` implements the A–F receipt-producing
execution contract, but source presence is not execution evidence.
`scripts/ci/verify_product_release_gate.py` defines the fail-closed evidence
boundary for this section. It accepts no free-text customer evidence and cannot
pass without reading the exact DMG bytes; live macOS signature, Gatekeeper, and
stapled-notarization checks; each actual private scenario receipt and matching
hash; seven distinct hashed native/accessibility evidence files; and three
unique unfamiliar-user Scenario A receipts that each bind a real first-run
acceptance receipt and declare zero founder intervention. The verifier creates
none of those facts. It can validate receipt identity and consistency, but the
claim that a participant was genuinely unfamiliar remains a human attestation.
Missing executions or trials remain missing product evidence.

### Release gate

All six scenarios must pass on the certified platform/agent combination. At
least three unfamiliar technical users must complete Scenario A without founder
instruction. Any founder intervention is a failed product requirement to fix,
not a support procedure to normalize.

Passing this gate proves the package is operable. It does not prove market
demand, pricing, or improved task outcomes.

This gate is intentionally not wired into the existing tagged-release workflow
during this product phase because distribution is deferred. Therefore a green
tag workflow is not product-release approval. No product tag should be created
until the later distribution phase either wires this private evidence gate into
publication or records an equally strict authorized manual approval.

## 12. Adversarial review gate

**Owner:** Elefante product owner

Every future change to this PRD must pass all seven angles:

| Angle | Adversarial question | Failure response |
|-------|----------------------|------------------|
| Customer language | Can the customer explain this without internal terminology? | Rewrite or progressively disclose the terminology; do not delete the underlying capability by default |
| Product assembly | Which owned piece supplies this behavior? | Assign one owner or mark the requirement unplaced pending the Product Contract Lock test |
| UX continuity | Where does the customer enter, what do they see, and where do they return? | Complete the flow before adding implementation detail |
| Failure | What happens if this stops halfway? | Add safe state, rollback, and one next action |
| Buildability | Which current component changes and what proves it? | Identify the owner and acceptance evidence before approval |
| One-person company | Does this create recurring manual support or another platform/service to maintain? | Automate, narrow the support lane, or defer it |
| Product value | Does this improve governed task memory guidance, its durable inputs, the four-action lifecycle, setup, recovery, or trust? | Reframe or relocate it; deletion requires the Product Contract Lock evidence test and owner approval |

This gate is applied to whole sections, not only suspicious words. Deleting one
example term while preserving an unowned concept does not pass.

## 13. Owner decisions

**Owner:** Elefante founder

The owner approved this product direction and authorized local implementation on
2026-08-29. On 2026-08-30 the owner also approved the three first-release
defaults from the product assembly audit. These defaults remain in force until
explicitly changed:

| Decision | Recommendation | Why |
|----------|----------------|-----|
| First certified lane | macOS Apple Silicon + Codex only; certification remains pending exact-package external proof | One narrow lane is supportable by one founder; market preference remains UNKNOWN |
| Shared-across-projects memory | Deferred entirely; first release promises zero cross-project delivery | Strict project behavior is easier to understand and safer to prove |
| Existing unscoped memories | Preserve in compatibility mode and require review before strict migration | Silent relabeling would be untrustworthy and hard to reverse |
| Local control UI name | Use Elefante Home as a working name | The architecture does not depend on branding |
| Managed runtime packaging | The official package owns install, repair, update, rollback, and data-preserving uninstall; certify it through the exact-artifact gate | The lifecycle mechanism is implemented locally but still needs package evidence |

### Approved product-audit defaults before the exact package

The 2026-08-30 implementation audit found three customer promises whose wording
and source did not match. The founder approved the recommendations below. They
are now local source requirements, not optional engineering details:

| Decision | Approved first-release contract | Local implementation result | Why |
|----------|---------------------------------|-----------------------------|-----|
| Agent connection | Codex is required and is the only certified acceptance lane; other detected hosts are optional compatibility previews and cannot block customer readiness | Installer selection, host plan, doctor, Recover health, and support evidence now distinguish the certified lane from previews | One failing preview integration must not block the narrow supported lane |
| Backup location | Elefante owns one managed backup location, displays it during setup and in Recover, and offers no arbitrary setup-time path choice | Setup and Recover resolve the directory from the managed Elefante data layout; environment overrides cannot move it | Arbitrary paths create permissions, removable-drive, and recovery support cases without improving the core loop |
| Shared-across-project memory | No shared scope or cross-project delivery in the first release | Project Registry, Home, Remember, Search, Recall, and correction paths expose isolated project policy only and reject caller scope overrides | Sharing would expand Recall, Correct, deletion, migration, and leak testing before customer need is proven |

Project-folder display names may continue to derive from folder names during
setup and remain renameable in Home; that simplification does not weaken
isolation. Local implementation does not certify the lane or authorize the exact
customer package gate; those require the release evidence in Section 11.

### Converged product and advanced-dashboard contract — source prototype implemented

On 2026-08-31 the founder corrected the product and dashboard premise; on
2026-09-01 the founder locked its cross-surface, IDE-agnostic, and
feature-preservation consequences. The founder then explicitly authorized the
immediate local source actions on 2026-09-01. That authority covers the
preservation-first dashboard prototype and isolated verification, not customer
runtime installation or publication.

| Decision | Approved contract | Why |
|----------|-------------------|-----|
| Product purpose | Supply the smallest governed bundle of durable memories justified for the current task and project, or abstain, so the agent does not start from zero | This is the truthful Elefante contribution; improved task decisions are the intended but still unproven downstream outcome |
| Meaning of advice | Treat “advice” as customer shorthand for the selected memory bundle, never as a synthesized recommendation or an Elefante-made task decision | Recall selects context; the agent still reasons and acts |
| Dashboard role | Make Home an advanced maintenance console, not the primary onboarding, marketing, or daily task surface | The dashboard manages Elefante's internal machinery; the agent is where task value is delivered |
| Capability versus surface | Keep Install/Connect, Projects, Remember, Recall, Correct, and Recover as the six owned capabilities; Home is a composing surface, not a seventh service | Navigation must not create duplicate ownership or a competing write path |
| Information architecture | Use Home / Recall / Memory Intelligence / Connections / Projects / Recover; Recall Inspector is an add-on inside Recall, Memory Intelligence preserves all-corpus inspection and diagnostics, and Connections remains first-class | Implemented in local source with six stable tabs and keyboard routes; Recall remains bounded to the existing content-free check |
| Feature preservation | Preserve each developed feature by assigning its unique question, evidence boundary, useful consequence, product home, and release state before changing hierarchy | Confusion, density, or weak copy alone is not evidence that a capability lacks value |
| Scope model | Offer read-only `All memories` view scope; bind one exact active project for Recall Check or mutation | Whole-installation understanding must not create a global storage scope, cross-project conflict inference, or delivery |
| Evidence semantics | Explain decay, health, access, provenance, graph, lexical, conflict, and lifecycle signals with their limits; support **No action** | Maintenance proxies are not truth, usefulness, causal value, or automatic repair authority |
| First visit | State that Home maintains Elefante, then show readiness, action scope, and one safe next step | An advanced console still must orient an unfamiliar owner without pretending to be the daily task surface |
| Theme and hierarchy | Default to clear high-contrast light, preserve complete dark, and use progressive disclosure | Implemented in local source with semantic color tokens, a persistent local theme control, light-default first visit, and retained dark presentation; exact-package visual acceptance remains pending |
| Evidence boundary | Show only the current Recall Check fields and snapshot evidence; no selected/withheld reasons, historical trace, per-signal values, or linked outcomes are assumed | The current dashboard contracts do not supply them; aggregate Session Intelligence cannot prove per-memory impact |

The current 2026-09-01 authorization covers implementation and isolated
verification of this source prototype. It does not authorize installation into
the customer runtime, durable customer-data mutation, commit, push, merge,
release, deployment, distribution, or commercial claims.

## 14. Final recommendation

**Owner:** Elefante product owner

Approve Elefante around one outcome chain:

```text
Durable memories
  -> governed Recall for the current task and project
  -> smallest justified memory bundle or abstention
  -> agent decision and action
  -> accepted outcome evidence when available
```

Remember, Recall, Correct, and Recover operate that product loop. The dashboard
maintains the machinery behind it:

```text
Diagnose -> inspect -> correct -> verify -> recover
```

Verified Resolve, project isolation, complete Correct, and Recover exist in
the exact clean local candidate. Its installed dashboard confirms the light
default, retained dark theme, all six workspaces, Library/Review, Decision
Graph, and fail-closed read-only states. The published customer release remains
unchanged until the product-release gate passes.

The single next product move is **unfamiliar-operator validation of the source
prototype**. Run the Section 9 golden path with three unfamiliar technical
users and record where they cannot understand evidence or choose a safe action.
Correct claim, hierarchy, explanation, disclosure, or unavailable state first.
If that passes, request separate authority for exact-package installation and
acceptance; only the accepted package should drive website synchronization and
the later publication gate. A remaining decision-critical evidence gap may
enter a separate privacy-safe read-only contract design. Backend expansion is
not the default next move.

Do not add cross-project Recall, automatic memory grading, arbitrary ranking
controls, persisted query history, fabricated selection explanations, or linked
task-outcome claims. Representative per-task outcome lift remains unproven.
