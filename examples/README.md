# Try Elefante With One Real Memory

> Applies to v2.15.2 · Audience: first-time users and connected agents

This five-minute demo proves the product loop with knowledge that matters to
your work. It does not preload fake memories, modify Elefante's source, or claim
that a successful retrieval automatically improved an answer.

## Before you start

- Install Elefante and restart the agent selected during setup.
- Use a real project folder. In this release, the folder is a memory-isolation
  boundary; Elefante does not scan or import its contents.
- Choose one decision you genuinely want the agent to remember. Do not store a
  password, API key, transcript, guess, or temporary status update.

## 1. Remember one real decision

Tell your connected agent a durable rule from the work you are doing. For
example, use the following only when it is actually your rule:

> Remember for this project: every customer-facing change must be checked on
> desktop and mobile before release.

Inspect the result. It must say whether Elefante added a record, found existing
knowledge, or blocked the write. A request to remember is not proof that
anything was stored.

## 2. Recall it for a later task

Start a new conversation or later task in the same project and ask:

> What must I verify before releasing this customer-facing change?

Have the agent use Elefante Recall once. Inspect both parts of the outcome:

1. **Memory selection:** the saved decision should be supplied. If nothing
   qualifies, Elefante should explicitly return no match or blocked—not an
   unrelated memory.
2. **Task use:** the agent's answer should include desktop and mobile checking.
   Selection alone does not prove that the answer used the memory well.

## 3. Inspect the same evidence in Home

Open [http://localhost:8000](http://localhost:8000) on the installed computer.
No browser extension is required.

1. **Memory Intelligence → Library:** find the decision and inspect its source,
   project, lifecycle, and health.
2. **Recall:** enter the same question and run the read-only check. Open the
   returned record. The dashboard shows supplied memory; it does not answer the
   question.
3. **Recover → Back up now:** create a verified local backup and read its final
   receipt.

The demo is complete only when the stored record is visible, Recall supplies it
for the matching question, the agent uses it in the task, and the backup reports
verified completion. A green status by itself is not enough.

## 4. Keep or remove the demo memory

Keep the record if it remains a real rule. Otherwise open it in **Memory
Intelligence** and use **Archive** so it is no longer eligible for Recall.
Permanent deletion is a separate backup-bound action and is unnecessary for a
normal demo cleanup.

## Advanced agent integration

These two files are for people configuring or building an MCP-capable agent.
They are not additional first-use steps:

| Guide | Use it for |
|---|---|
| [Agent integration tutorial](AGENT_TUTORIAL.md) | Exact search, Recall, write, correction, and result-handling rules |
| [System-prompt fallback](system-prompt-template.md) | Minimal host guidance when no equivalent instruction surface exists |

The [complete customer guide](../docs/README.md) explains every dashboard area,
all released feature groups, recovery, and troubleshooting. Exact schemas for
the 18 tools and 2 prompts live in the
[advanced tool reference](../docs/reference/tools.md).
