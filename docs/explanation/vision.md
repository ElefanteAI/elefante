# Elefante Vision

> Product explanation · Current published version: v2.12.0

## The Thesis

Elefante is a local-first persistent memory engine for AI agents. It maximizes
signal per token by carrying durable decisions, preferences, facts, and lessons
across sessions without making one model provider the owner of that memory.

Every new AI session otherwise starts from zero. The user repeats context, the
agent rediscovers decisions, and the context window fills with history instead
of the evidence needed for the next action. Elefante provides a persistent,
inspectable second brain so an agent can retrieve the smallest useful context
at the moment of work.

## How the Released Product Works

Elefante stores semantic vectors in embedded SQLite and relationships in Kuzu.
A local daemon owns both stores. MCP-compatible clients connect through local
HTTP or a storage-free bridge, depending on the host.

The store remains on the user's machine. Context the user intentionally sends
to a connected AI client is governed by that provider's data policy.

The dashboard reads a redacted local snapshot. It explains memory freshness,
confidence, lifecycle state, sources, and explicit decision relationships
without giving the browser authority to query or mutate the live store.

## The Four Laws

1. **Continuity** — a session is a continuation, not a blank start.
2. **Compliance** — search before writing so existing knowledge is reused.
3. **Grounding** — if a claim is not in memory or the workspace, it is unknown.
4. **Full Signal Injection** — injected context must improve the next answer;
   irrelevant memory is noise.

## Product Boundary

Elefante is not a model host, agent runtime, chat product, prompting framework,
or cloud memory service. It is the local memory authority that augments the
tools developers already use.

Future ideas, draft contracts, release operations, bugs, and implementation
plans live in the developer workspace and are not part of this released-product
explanation.
