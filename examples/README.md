# Elefante Agent Examples

> Applies to v2.12.2 · Audience: agents connected through MCP

| File | Question answered |
|---|---|
| [`AGENT_TUTORIAL.md`](AGENT_TUTORIAL.md) | How should an agent search, store, update, and interpret memory? |
| [`system-prompt-template.md`](system-prompt-template.md) | What minimal guidance can a host use when no equivalent instruction surface exists? |

Start with a read-only status check and search. `elefante-System(action="enable")`
is optional logical-mode setup, not a prerequisite for every operation and not
a session-wide database lock.

Never start by adding a memory. Search first, then write only durable
information when the task or user authorizes it. The complete 16-tool and
2-prompt contract is in
[`../docs/reference/tools.md`](../docs/reference/tools.md).
