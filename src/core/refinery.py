"""Deterministic memory cleanup (LLM-free).

This module exists to let Elefante clean up its stored memories *using existing tools*.

Design goals:
- No internal LLM calls
- Deterministic canonicalization (prefer agent-supplied SAQ title)
- Quarantine test/ephemeral memories
- Collapse duplicates (one active per (namespace, canonical_key))

The MCP tool `elefante-MemoryConsolidate` can invoke this refinery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from src.models.memory import Memory, MemoryStatus, RelationshipType
from src.utils.logger import get_logger

logger = get_logger(__name__)


_NAMESPACE_PROD = "prod"
_NAMESPACE_TEST = "test"
_NAMESPACE_EPHEMERAL = "ephemeral"


@dataclass(frozen=True)
class RefineryUpdate:
    memory_id: UUID
    updates: Dict[str, Any]


@dataclass(frozen=True)
class RefineryPlan:
    updates: List[RefineryUpdate]
    stats: Dict[str, Any]


def _now_utc() -> datetime:
    return datetime.utcnow()


def _get_custom(metadata: Dict[str, Any], key: str) -> Optional[str]:
    value = metadata.get(key)
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def infer_namespace(memory: Memory) -> str:
    """Infer a namespace for a memory without adding new schema fields."""
    # Prefer explicit agent-supplied value.
    custom = memory.metadata.custom_metadata or {}
    namespace = _get_custom(custom, "namespace")
    if namespace in {_NAMESPACE_PROD, _NAMESPACE_TEST, _NAMESPACE_EPHEMERAL}:
        return namespace

    # Heuristics (deterministic).
    category = (memory.metadata.category or "").strip().lower()
    tags = {t.strip().lower() for t in (memory.metadata.tags or []) if isinstance(t, str)}
    content = (memory.content or "").strip().lower()

    if category == "test" or "test" in tags or "e2e" in tags:
        return _NAMESPACE_TEST

    if content.startswith("elefante e2e test memory") or content.startswith("hybrid search test memory"):
        return _NAMESPACE_TEST

    return _NAMESPACE_PROD


def infer_canonical_key(memory: Memory) -> str:
    """Infer canonical key.

    Priority order:
    1) custom_metadata.canonical_key (explicit agent-supplied identity)
    2) deterministic keyword mapping (content/title heuristics)
    3) normalized title slug (legacy SAQ title)
    4) content-hash fallback (stable identity for exact-text items)
    """
    custom = memory.metadata.custom_metadata or {}

    title = _get_custom(custom, "title")
    content = (memory.content or "")
    haystack = f"{title or ''}\n{content}".lower()

    def _contains_any(text: str, needles: Iterable[str]) -> bool:
        return any(n in text for n in needles)

    def _is_preference_like(m: Memory) -> bool:
        try:
            return str(m.metadata.memory_type).lower() == "preference"
        except Exception:
            return False

    def _matches_simple_concise_preference(text: str) -> bool:
        if not _is_preference_like(memory):
            return False
        simple_markers = (
            "simple terms",
            "simple language",
            "plain language",
            "avoid jargon",
            "no jargon",
            "no fluff",
            "minimal wording",
            "straightforward",
            "concise",
        )
        has_simple = _contains_any(text, simple_markers)
        has_concise = _contains_any(text, ("concise", "no fluff", "minimal", "brief", "short"))
        return has_simple and has_concise

    # If a canonical_key is present, treat it as authoritative, except for a very small
    # set of known-legacy ambiguous keys that can be deterministically refined.
    canonical_key = _get_custom(custom, "canonical_key")
    if canonical_key:
        if canonical_key == "self-pref-always" and _matches_simple_concise_preference(haystack):
            return "self-pref-communication-simple-concise"
        return canonical_key

    # Small deterministic keyword mapping (extend conservatively).
    if "emoji" in haystack or "emojis" in haystack:
        return "Self-Limit-Emojis"

    if _matches_simple_concise_preference(haystack):
        return "self-pref-communication-simple-concise"

    if _is_preference_like(memory) and "do not claim" in haystack and "success" in haystack:
        return "self-pref-no-false-success-claims"

    if title:
        slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
        return slug[:80] if slug else "World-Fact-General"

    normalized = re.sub(r"\s+", " ", content.strip().lower())
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"Content-{digest}"


def _select_winner(memories: List[Memory]) -> Memory:
    """Pick a canonical winner deterministically."""
    # Prefer active (not archived/deprecated/redundant), then processed, then higher importance,
    # then higher access_count, then newer created_at.
    def sort_key(m: Memory) -> Tuple[int, int, int, int, float, str]:
        created_at = m.metadata.created_at
        created_ts = created_at.timestamp() if isinstance(created_at, datetime) else 0.0

        active = (
            not bool(getattr(m.metadata, "archived", False))
            and not bool(getattr(m.metadata, "deprecated", False))
            and getattr(m.metadata, "status", None) != MemoryStatus.REDUNDANT
        )

        cm = m.metadata.custom_metadata or {}
        ps = str(cm.get("processing_status") or "").strip().lower()
        ps_rank = {
            "processed": 3,
            "processing": 2,
            "raw": 1,
            "failed": 0,
        }.get(ps, 0)
        return (
            1 if active else 0,
            ps_rank,
            int(m.metadata.score or 0),
            int(m.metadata.access_count or 0),
            created_ts,
            str(m.id),
        )

    return sorted(memories, key=sort_key, reverse=True)[0]


def build_refinery_plan(memories: Iterable[Memory]) -> RefineryPlan:
    memories_list = list(memories)

    groups: Dict[Tuple[str, str], List[Memory]] = {}
    namespace_updates: Dict[UUID, str] = {}
    key_updates: Dict[UUID, str] = {}

    for memory in memories_list:
        namespace = infer_namespace(memory)
        canonical_key = infer_canonical_key(memory)

        namespace_updates[memory.id] = namespace
        key_updates[memory.id] = canonical_key

        groups.setdefault((namespace, canonical_key), []).append(memory)

    updates: List[RefineryUpdate] = []

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    redundant_count = 0
    namespace_marked_test = 0
    canonical_key_set = 0

    for (namespace, canonical_key), group in groups.items():
        winner = _select_winner(group)

        for memory in group:
            patch: Dict[str, Any] = {}

            # Persist inferred canonicalization into custom_metadata
            custom = dict(memory.metadata.custom_metadata or {})

            if custom.get("namespace") != namespace:
                custom["namespace"] = namespace
                if namespace == _NAMESPACE_TEST:
                    namespace_marked_test += 1

            if custom.get("canonical_key") != canonical_key:
                custom["canonical_key"] = canonical_key
                canonical_key_set += 1

            if custom:
                patch["custom_metadata"] = custom

            # Lifecycle consistency: once redundant, always archived/deprecated.
            # This fixes cases where a memory is already REDUNDANT but is the sole
            # member of its (namespace, canonical_key) group (so it wouldn't get
            # the non-winner patch below).
            if memory.metadata.status == MemoryStatus.REDUNDANT:
                patch.setdefault("deprecated", True)
                patch.setdefault("archived", True)

            if memory.id != winner.id:
                # Mark as redundant and link to winner
                patch.update(
                    {
                        "status": MemoryStatus.REDUNDANT,
                        "deprecated": True,
                        "archived": True,
                        "superseded_by_id": winner.id,
                        "relationship_type": RelationshipType.SUPERSEDES,
                    }
                )
                redundant_count += 1

            if patch:
                updates.append(RefineryUpdate(memory_id=memory.id, updates=patch))

    stats = {
        "total_memories": len(memories_list),
        "groups": len(groups),
        "duplicate_groups": len(duplicate_groups),
        "duplicate_groups_sample": [
            {
                "namespace": ns,
                "canonical_key": ck,
                "count": len(group),
                "winner_id": str(_select_winner(group).id),
                "member_ids": [str(m.id) for m in group],
            }
            for (ns, ck), group in sorted(
                duplicate_groups.items(),
                key=lambda item: (len(item[1]), item[0][0], item[0][1]),
                reverse=True,
            )[:10]
        ],
        "redundant_marked": redundant_count,
        "canonical_key_set": canonical_key_set,
        "namespace_set": namespace_marked_test,
        "planned_updates": len(updates),
        "generated_at": _now_utc().isoformat(),
    }

    return RefineryPlan(updates=updates, stats=stats)


class MemoryRefinery:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.logger = get_logger(self.__class__.__name__)

    async def run(self, *, apply: bool) -> Dict[str, Any]:
        """Build a refinery plan and optionally apply it."""
        # Fetch all memories in pages to avoid giant single allocations.
        all_memories: List[Memory] = []
        offset = 0
        page_size = 500
        while True:
            page = await self.vector_store.get_all(limit=page_size, offset=offset)
            if not page:
                break
            all_memories.extend(page)
            offset += len(page)
            if len(page) < page_size:
                break

        plan = build_refinery_plan(all_memories)

        if not apply:
            self.logger.info("refinery_plan_built_dry_run", **plan.stats)
            return {"success": True, "applied": False, "stats": plan.stats}

        changed = 0
        for update in plan.updates:
            memory = await self.vector_store.get_memory(update.memory_id)
            if memory is None:
                continue

            # Apply patch fields to Memory instance
            patch = update.updates
            if "custom_metadata" in patch:
                memory.metadata.custom_metadata = patch["custom_metadata"]

            if "status" in patch:
                memory.metadata.status = patch["status"]

            if "deprecated" in patch:
                memory.metadata.deprecated = bool(patch["deprecated"])

            if "archived" in patch:
                memory.metadata.archived = bool(patch["archived"])

            if "superseded_by_id" in patch:
                memory.metadata.superseded_by_id = patch["superseded_by_id"]

            if "relationship_type" in patch:
                memory.metadata.relationship_type = patch["relationship_type"]

            memory.metadata.last_modified = _now_utc()

            ok = await self.vector_store.replace_memory(memory)
            if ok:
                changed += 1

        self.logger.info("refinery_applied", changed=changed, **plan.stats)
        return {
            "success": True,
            "applied": True,
            "changed": changed,
            "stats": plan.stats,
        }
