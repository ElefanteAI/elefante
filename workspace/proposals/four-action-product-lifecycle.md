---
status: APPROVED — IMPLEMENTATION IN PROGRESS
document_owner: Elefante founder and product owner
target: Upcoming; no release or date commitment
authority: Approved product direction and implementation sequence; released documentation and source remain publication authority
question: How does Elefante become one self-service product organized around Remember, Recall, Correct, and Recover?
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

### The product in one sentence

Elefante keeps the knowledge a user explicitly wants to preserve available to
their AI agent across work sessions, within the correct project, while giving
the user a safe way to inspect, correct, back up, and recover it.

### The complete customer experience

```text
Install -> choose projects -> Remember -> Recall -> Correct when needed -> Recover when needed
```

- The **agent** is where the customer works every day.
- **Elefante Home** is where the customer checks status, inspects knowledge,
  corrects it, and operates recovery.
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

### Recommendation

Build one narrow, self-service local product before expanding the surface:

- one accountable technical user;
- one local Elefante installation;
- one certified platform and agent-host combination first;
- multiple isolated projects;
- four customer actions: Remember, Recall, Correct, Recover;
- no founder involvement during the normal journey.

The product priority remains project-safe Remember and Recall. The implementation
starts with one narrower trust-bearing vertical slice: **Verified Resolve**.
That slice proves the shared product discipline — plan, explicit authority, one
semantic write, authoritative readback, atomic Home refresh, scoped Recall
verification, compensation, and a privacy-safe receipt — before the same
discipline is extended to project safety, the rest of Correct, and Recover.

## 1. Customer and product boundary

**Owner:** Elefante product owner

### Customer

The first customer is one technical owner inside a small or medium company. The
customer uses an AI agent on recurring projects, wants project knowledge to
survive across sessions, and does not want to operate Elefante internals.

The first product supports one human owner and one local installation. A company
can purchase it, but this PRD does not define shared team memory or multiple
human permissions.

### Customer promise

The customer can say:

> Elefante remembers only what I explicitly ask it to remember, recalls it for
> the correct project, lets me fix it, and lets me recover it if something goes
> wrong.

That sentence is the product contract. Every screen, package feature, and test
must support it.

### What is being sold

The sellable unit is an official Elefante package that makes the complete
experience work without contacting the founder. It includes:

- a verified build for the supported environment;
- guided installation and agent connection;
- project setup and isolation;
- a real disposable Recall test;
- Elefante Home;
- backup, restore, repair, update, rollback, and uninstall;
- a privacy-safe support report;
- an acceptance receipt proving the installation works.

Payment, licensing, and distribution are later decisions. They are not product
dependencies and are not implemented by this PRD.

## 2. Product assembly and ownership

**Owner:** Elefante product owner

Elefante is one product assembled from seven owned pieces. A piece may not
create a competing workflow or write directly into another piece's data.

| Product piece | Customer job | Owning component | Primary surface |
|---------------|--------------|------------------|-----------------|
| Install and Connect | Make Elefante work | Installer | Official package |
| Projects | Tell Elefante where knowledge belongs | Project Registry | Installer and Home |
| Remember | Preserve knowledge deliberately | Memory Service | Agent; Home as fallback |
| Recall | Supply useful project knowledge | Recall Service | Agent |
| Correct | Fix or retire stored knowledge | Memory Service | Home and agent |
| Recover | Protect or restore the product and data | Lifecycle Manager | Home |
| Home | Show product state and expose safe controls | Home Shell | Local browser UI |

### Existing foundations and missing work

| Piece | Existing foundation | Missing product work |
|-------|---------------------|----------------------|
| Install and Connect | Guided native/fallback project selection, strict registry setup, source identity, required Codex detection, optional preview selection, disposable installed-Recall proof, visible managed verified backup, and private acceptance receipt | Exact official-artifact execution, rendered native acceptance, and unfamiliar-user proof |
| Projects | Local unreleased Project Registry, durable strict-intent marker, deterministic workspace mapping, Home management, explicit verified assignment of legacy unscoped memories before strict mode, and a zero-sharing policy flag | Exact official-package project selection and released clean-host acceptance |
| Remember | Verified four-term, project-scoped agent and Home paths with pre-write overlap handling, explicit update/supersede/keep-both choices, post-write Recall proof, and rollback | Exact official-package and supported-agent restart acceptance |
| Recall | Bounded read-only Recall, strict project enforcement, terminal abstention, and a content-free Home test | Exact official-package and supported-agent acceptance of the project-safe path |
| Correct | One verified Edit, Replace, Resolve, Archive, Restore, and backup-bound permanent-delete flow shared by MCP and Home; desktop and narrow-screen destructive-flow rendering verified with synthetic data | Exact-package, keyboard/accessibility, and unfamiliar-user destructive-flow acceptance |
| Recover | Home health/backup/restore/support, one package-maintenance handoff with a safe result receipt, and verified package repair, update, rollback, and data-preserving uninstall | Exact official-artifact lifecycle execution and interruption matrix |
| Home | Snapshot-first local dashboard with one opening state, four primary actions, Project review, Correct/Resolve, Recover, and package-maintenance guidance | Exact-package visual/accessibility acceptance and unfamiliar-user proof |

No new product piece is added unless none of these owners can truthfully own the
customer need.

## 3. Install and Connect

**Owner:** Installer

**Customer surface:** Official package, then first-run setup in Home

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

Knowledge from one project does not appear in another project unless the
customer explicitly marks it as shared across projects.

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
- Keep shared-across-projects memory out of the primary flow. The recommended
  first release enables it only as an advanced explicit choice.
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
  has evidence for that selection. Home may show provenance and eligibility,
  but not invented reasoning.

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

## 9. Elefante Home

**Owner:** Home Shell

**Customer surface:** Local browser opened by Elefante

### Customer promise

Home answers two questions immediately:

1. Is Elefante ready for my agent?
2. If not, what is the one safe action I should take?

Home is not another application the customer must keep open. Daily Remember and
Recall stay in the agent.

### Opening screen

The first screen contains:

- one product state: **Ready**, **Setup required**, **Needs attention**,
  **Recovery required**, or **Unsupported**;
- connected agent and active project;
- last verified Recall and backup status;
- four action entries: Remember, Test Recall, Correct, Recover;
- exactly one primary next action when the product is not Ready.

Advanced engine views may remain available below the primary experience, but
they cannot lead navigation or be required for setup, correction, or recovery.

### Control boundary

- Normal Home mode reads only a validated snapshot.
- A state-changing action opens a short-lived authenticated local control
  session.
- The session exposes only named product operations, never arbitrary shell,
  path, query, or MCP execution.
- Memory changes go through the Memory Service.
- Lifecycle changes go through the Lifecycle Manager.
- Closing, timeout, restart, or explicit lock ends control authority.

The exact token/session transport belongs in a technical design after this
product contract is approved. This PRD owns the behavior and security outcome,
not a premature browser protocol.

### Complete when

An unfamiliar customer can identify product state, complete each of the four
actions, and recover from every supported failure using only Home and the agent.
Rendered desktop, narrow-screen, keyboard, light/dark, and reduced-motion states
must be inspected before release.

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

No slice is assigned to a version or date until the preceding exit passes.

## 11. Product release scenarios

**Owner:** Release pipeline

Tests are organized around the assembled product, not isolated feature counts.

### Scenario A — First use

An unfamiliar customer installs the exact package, the installer detects the
required Codex host, the customer selects two projects and reviews the managed
backup location, disposable Recall acceptance passes, and the customer remembers
one real decision, restarts the agent, and recalls it.

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
| Customer language | Can the customer explain this without internal terminology? | Rewrite in the four-action vocabulary or remove it |
| Product assembly | Which owned piece supplies this behavior? | Assign one owner or remove the requirement |
| UX continuity | Where does the customer enter, what do they see, and where do they return? | Complete the flow before adding implementation detail |
| Failure | What happens if this stops halfway? | Add safe state, rollback, and one next action |
| Buildability | Which current component changes and what proves it? | Identify the owner and acceptance evidence before approval |
| One-person company | Does this create recurring manual support or another platform/service to maintain? | Automate, narrow the support lane, or defer it |
| Product value | Does this improve Remember, Recall, Correct, Recover, setup, or trust? | Move it to its own proposal or remove it |

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

This approval authorizes implementation and isolated verification in the active
developer checkout. It does not authorize installation into the customer
runtime, durable customer-data mutation, commit, push, merge, release,
deployment, distribution, or commercial claims.

## 14. Final recommendation

**Owner:** Elefante product owner

Approve Elefante as one closed-loop product:

```text
One package
  -> one local owner
  -> explicit projects
  -> Remember and Recall through the agent
  -> Correct and Recover through Home
  -> proof at every lifecycle boundary
```

Start with Verified Resolve as the smallest complete trust wedge, then enforce
the project-safe memory loop before broadening Correct or Recover. Do not start
with a dashboard redesign, tool-count reduction, broader host support, or
payment machinery. If each slice cannot be explained, owned, failed safely,
and verified through the customer-facing read path, it is not complete.
