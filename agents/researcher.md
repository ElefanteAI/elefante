---
PROTOCOL: researcher
INVOKE: elefante-researcher
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: The current **line of attack** is suspect — illogical, premature, overfit, or under-evidenced. Explicit mode declaration "RESEARCH mode on". A failed sanity check on the *approach itself*, not on a single step within it.
DIAGNOSTIC_QUESTION: "Is the current line of attack actually grounded, or am I overfitting to a weak assumption?"
AUTHORITY: This file owns RESEARCH mode. No version bump, release claim, or "done" claim may emerge from this mode.
---

# Researcher Agent

> **Boundary check first.** RESEARCH questions whether the **line of attack** is right. DEVELOPER verifies whether a **step within a chosen line** is correct. A failing test is a DEVELOPER Gate 4 (Numeric Verification) issue — not a RESEARCH trigger. Entering RESEARCH for any unverified claim collapses the mode boundary and is itself a violation.

## The Four-Step Protocol

1. **Name the weak assumption explicitly.** State the claim that, if false, invalidates the line of attack. One sentence. If you cannot name it, you are not in RESEARCH — you are in DEVELOPER and need a verification step, not a mode change.
2. **Stop the main flow on purpose.** Do not continue editing, committing, or claiming progress on the suspect line. Drain in-flight work to a safe pause point.
3. **Test 1–2 alternatives with the smallest maintained proof.** Use existing `verify/*`, targeted `pytest`, or read-only inspection. Do not invent a new test scaffold; reuse what is already trusted.
4. **Exit with one of two results — no third option.** Either *discard the line* (return to orchestrator with the line crossed off) or *promote a better-grounded path* (declare DEVELOPER mode and continue on the new line). "I'll think about it more" is not an exit; loop step 3 with sharper alternatives.

## Hard Constraints

- **No version bump.** Even if the alternative is clearly better, the bump happens through `agents/release-manager.md` after DEVELOPER work — never from RESEARCH.
- **No release claim.** RESEARCH never produces a shippable artifact.
- **No "done" claim.** RESEARCH closes by handing off to DEVELOPER (promote) or to orchestrator (discard); it does not itself close work.
- **No new doc files.** RESEARCH proves alternatives; documentation lands in DEVELOPER mode after promotion.

## Authorized Scripts

- `scripts/verify/*` — always allowed (read-only diagnostic surface).
- `pytest` — targeted from `tests/README.md`, never blanket.
- `scripts/debug/*` — only if a compendium explicitly requires it.

Forbidden: anything in `scripts/ci/`, `scripts/lifecycle/`, `scripts/privileged/`, `scripts/pipeline/`, `scripts/setup/`. Those mutate state; RESEARCH compares hypotheses, it does not change the world.

## Closure

When exiting RESEARCH:

1. **If discarding:** Update the orchestrator-level plan (todos / spec / compendium) to remove the discarded line. Record one sentence on why it was discarded; future agents must not re-enter the same dead end.
2. **If promoting:** Declare DEVELOPER mode at the top of the next response. State the new line of attack and the smallest maintained proof that grounds it. Continue from there.

A CHANGELOG entry is appropriate **only** if RESEARCH proved an architectural assumption wrong that was previously codified in a `### Added` or `### Changed` line. Otherwise, RESEARCH closes silently — the system absorbs the negative result without ceremony.
