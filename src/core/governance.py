"""Small, deterministic governance gates used before task ranking.

Governance answers whether a memory may participate in a task.  It does not
rank memories, synthesize content, or prove that a memory improved an outcome.
"""

from __future__ import annotations

import re
from typing import Any


def _value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().casefold()


def is_protected(metadata: Any) -> bool:
    """Return whether automation must not archive or weaken this memory."""
    return (
        bool(getattr(metadata, "user_locked", False))
        or _value(getattr(metadata, "retention_policy", "")) == "permanent"
    )


def scope_matches(
    metadata: Any,
    context: str,
    *,
    project: str | None = None,
    workspace: str | None = None,
) -> bool:
    """Check declared and request scope without inventing a default scope."""
    memory_project = str(getattr(metadata, "project", "") or "").strip().casefold()
    memory_workspace = str(getattr(metadata, "workspace", "") or "").strip().casefold()
    if project and memory_project and memory_project != str(project).strip().casefold():
        return False
    if (
        workspace
        and memory_workspace
        and memory_workspace != str(workspace).strip().casefold()
    ):
        return False

    declared = str(getattr(metadata, "scope", "") or "").strip().casefold()
    if not declared or declared == "global":
        return True

    context_folded = str(context or "").casefold()
    candidates = {
        str(project or "").strip().casefold(),
        str(workspace or "").strip().casefold(),
        memory_project,
        memory_workspace,
        context_folded,
    }
    candidates.discard("")
    if declared in candidates:
        return True

    # Permit conventional `project:name` / `workspace:path` declarations while
    # retaining exact matching for arbitrary scope labels.
    if ":" in declared and declared.split(":", 1)[1] in candidates:
        return True
    return bool(
        re.search(
            rf"(?<!\w){re.escape(declared)}(?!\w)",
            context_folded,
        )
    )


def matching_triggers(metadata: Any, context: str) -> list[str]:
    """Return declared literal triggers present in ``context``.

    Triggered delivery is an explicit opt-in path.  Matching remains literal
    and case-insensitive so a host can pass a file name, terminal error, or
    conversation excerpt without introducing a second semantic retriever.
    Duplicate phrases are returned once in declaration order, and the original
    phrase is preserved for a useful explanation in the caller's response.
    """
    triggers = list(getattr(metadata, "trigger", None) or [])
    # ``surfaces_when`` predates the governance field and remains a valid
    # backward-compatible trigger source for memories explicitly marked
    # ``injection_policy=triggered``.
    triggers.extend(list(getattr(metadata, "surfaces_when", None) or []))
    context_folded = str(context or "").casefold()
    if not context_folded:
        return []

    matches: list[str] = []
    seen: set[str] = set()
    for trigger in triggers:
        phrase = str(trigger).strip()
        key = phrase.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        if key in context_folded:
            matches.append(phrase)
    return matches


def trigger_matches(metadata: Any, context: str) -> bool:
    """Return true when a declared trigger phrase appears in the context."""
    return bool(matching_triggers(metadata, context))


def governance_reason(
    metadata: Any,
    context: str,
    *,
    project: str | None = None,
    workspace: str | None = None,
) -> str | None:
    """Return a rejection reason, or ``None`` when ranked delivery is allowed.

    ``always`` is intentionally fail-closed unless the user explicitly locked
    the memory.  A locked always-inject memory returns ``None`` so the caller
    can reserve it before ordinary ranking.
    """
    if not scope_matches(metadata, context, project=project, workspace=workspace):
        return "governance-scope"

    policy = _value(getattr(metadata, "injection_policy", "ranked")) or "ranked"
    if policy == "always":
        if not bool(getattr(metadata, "user_locked", False)):
            return "always-requires-user-lock"
        return None
    if policy == "triggered" and not trigger_matches(metadata, context):
        return "trigger-not-matched"
    return None


def is_mandatory(
    metadata: Any,
    context: str,
    *,
    project: str | None = None,
    workspace: str | None = None,
) -> bool:
    """Return true only for a scoped, user-locked always-inject memory."""
    return (
        _value(getattr(metadata, "injection_policy", "ranked")) == "always"
        and bool(getattr(metadata, "user_locked", False))
        and governance_reason(metadata, context, project=project, workspace=workspace)
        is None
    )
