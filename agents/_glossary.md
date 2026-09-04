---
PROTOCOL: glossary
PROTOCOL_VERSION: 2.15.2
LOAD_WHEN: Resolving a codename used in any `agents/*.md` protocol.
DIAGNOSTIC_QUESTION: "What real operation does this codename map to?"
LAYER: 1 (friction, not security — see workspace/PLANNING.md §2.5)
---

# Agent Codename Glossary

Optional glossary for internal codenames. No active Elefante protocol currently
uses a codename, so this file carries no runtime or security claim.

This file is the **only** place where codenames map to plain-English operations. Agents that use codenames must reference this file by name so a confused operator has one place to look.

---

## Codename Table

| Codename | Real operation | First used in |
| -------- | -------------- | ------------- |
| *(none)* | | |

---

## Adoption Rule

When an agent protocol introduces a codename:

1. Add the row here in the same commit.
2. The `Real operation` column must be unambiguous to a developer who has read
   `AGENTS.md` and `agents/orchestrator.md`.
3. The `First used in` column points to the agent file that introduced it.

Removing a shipped codename follows `agents/memory-janitor.md` rule 1.

---

This glossary does not provide access control or anti-reverse-engineering
protection. Security boundaries must be enforced in code and configuration.
