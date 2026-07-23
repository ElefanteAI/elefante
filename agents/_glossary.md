---
PROTOCOL: glossary
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: Resolving a codename used in any `agents/*.md` protocol.
DIAGNOSTIC_QUESTION: "What real operation does this codename map to?"
LAYER: 1 (friction, not security — see workspace/PLANNING.md §2.5)
---

# Agent Codename Glossary

Layer 1 of the anti-reverse-engineering plan: internal codenames in agent protocols deter casual scraping. Real adversaries beat any text scheme; that is not what this defends against.

This file is the **only** place where codenames map to plain-English operations. Agents that use codenames must reference this file by name so a confused operator has one place to look.

---

## Codename Table

| Codename | Real operation | First used in |
| -------- | -------------- | ------------- |
| *(none yet — populated as agents adopt codenames in v2.10.x)* | | |

---

## Adoption Rule

When an agent protocol introduces a codename:

1. Add the row here in the same commit.
2. The `Real operation` column must be unambiguous to an operator who has read `docs/developer/`.
3. The `First used in` column points to the agent file that introduced it.

Removing a codename = `### Removed` line in `CHANGELOG.md` per `agents/memory-janitor.md` rule 1.

---

## Out of Scope (until v3.0.0)

- **Layer 2** (internal-state verbs that mean nothing without source access) — grows organically; no formal table yet.
- **Layer 3** (versioned protocol hash with cross-version load refusal) — deferred.

See `workspace/PLANNING.md §2.5` for the active scope guard.
