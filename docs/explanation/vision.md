# Elefante Vision

> Product explanation · Current published version: v2.12.3

## The Thesis

Elefante is a local-first persistent memory engine for AI agents. It maximizes
signal per token by carrying durable decisions, preferences, facts, and lessons
across sessions without making one model provider the owner of that memory.

Every new AI session otherwise starts from zero. The user repeats context, the
agent rediscovers decisions, and the context window fills with history instead
of the evidence needed for the next action. Elefante provides a persistent,
inspectable memory layer so an agent can retrieve the smallest useful context
at the moment of work.

## Role in the Agent Loop

A goal-directed agent typically moves through a recurring cycle:

```text
Goal → Perceive → Plan → Act with tools → Observe → Update → Repeat
          ↑                                         ↓
     retrieve durable context               store verified outcomes
          └──────────────── Elefante ────────────────┘
```

The agent remains responsible for its goal, plan, tool choice, reflection,
stopping condition, and approval gates. Elefante supports **Perceive** by
retrieving relevant durable knowledge and **Update** by preserving verified
facts, preferences, constraints, evidence, decisions, and lessons.

For example, a financial-advisory agent could orchestrate portfolio data, risk
calculations, market sources, and client documents while Elefante carries the
client's durable constraints and prior decisions across sessions. This is an
architectural example, not a claim that Elefante supplies financial advice,
market data, calculations, or permission to execute consequential actions.

Private model reasoning is also outside the memory contract. Integrations
should preserve concise plans, actions, evidence, approvals, and results—not
hidden chain-of-thought.

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

Elefante is not a model host, agent runtime, financial adviser, chat product,
prompting framework, external tool provider, or cloud memory service. It is the
local memory authority that augments the tools developers already use.

Future ideas, draft contracts, release operations, bugs, and implementation
plans live in the developer workspace and are not part of this released-product
explanation.
