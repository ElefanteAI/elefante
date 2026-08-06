# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/utils/dashboard_serializer.py
# PURPOSE : Single source of truth for converting Memory objects into dashboard
#           node/edge JSON consumed by the frontend and snapshot pipeline.
# ROLE    : Utils — shared by update_dashboard_data.py and the live server.
# TOUCHED : When changing the dashboard node schema, adding new node fields,
#           changing the redaction/scoring rules applied at serialization time.
#           Changes here affect both live dashboard and snapshot export.
# ─────────────────────────────────────────────────────────────────────────────
"""
Shared Memory → Dashboard Node serializer.

Single source of truth for converting a Memory object into the dashboard
snapshot node format. Both the MCP server refresh path and the standalone
update_dashboard_data.py script MUST use this function.

NO OTHER CODE should build dashboard node dicts from Memory objects.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, Optional

from src.models.memory import Memory, TYPE_DECAY_RATES


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)([^\s\"']{8,})"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s\"']{8,})"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s\"']{8,})"),
]


def _redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


# ---------------------------------------------------------------------------
# Topic derivation
# ---------------------------------------------------------------------------
def _derive_topic(title: str, category: Optional[str]) -> str:
    if category and str(category).strip() and str(category).strip().lower() != "general":
        return category.strip()
    if not title:
        return "General"
    if " | " in title:
        return title.split(" | ")[0].strip()
    if "." in title and ":" in title:
        try:
            cat = title.split(".")[1].split(":")[0].strip()
            if cat:
                return cat.title()
        except IndexError:
            pass
    return "General"


# ---------------------------------------------------------------------------
# Live score computation
# ---------------------------------------------------------------------------
_TYPE_WEIGHTS = {
    "specification": 1.0,
    "directive": 1.0,
    "decision": 0.85,
    "preference": 0.80,
    "fact": 0.75,
    "insight": 0.70,
    "note": 0.55,
    "conversation": 0.45,
}


def _composite_dashboard_score(vitality: float, memory_type: str, access_count: int) -> int:
    """
    THE scoring formula. Both Memory-object and raw-dict paths converge here.

    Components (weighted blend):
      - Vitality (50%): exponential decay (0.0-1.0)
      - Type weight (25%): inherent importance by memory type
      - Engagement (25%): retrieval frequency relative to age

    Returns 0-100 integer.
    """
    type_weight = _TYPE_WEIGHTS.get(str(memory_type).lower(), 0.60)
    engagement = min(1.0, math.log(max(access_count, 1) + 1) / math.log(20))
    composite = vitality * 0.50 + type_weight * 0.25 + engagement * 0.25
    return min(100, max(0, round(composite * 100)))


def compute_live_score(mem: Memory) -> int:
    """Score from a Memory object. Delegates vitality to Memory.calculate_relevance_score()."""
    try:
        vitality = mem.calculate_relevance_score()  # 0.0-1.0
        mem_type = mem.metadata.memory_type.value if hasattr(mem.metadata.memory_type, "value") else str(mem.metadata.memory_type)
        return _composite_dashboard_score(vitality, mem_type, max(0, mem.metadata.access_count))
    except Exception:
        return 0


def compute_live_score_from_raw(meta: dict) -> int:
    """Score from raw persisted metadata. Same formula as compute_live_score()."""
    try:
        memory_type = str(meta.get("memory_type", "fact"))
        decay_rate = TYPE_DECAY_RATES.get(memory_type, 0.01)

        now = datetime.utcnow()
        created_str = meta.get("created_at") or ""
        accessed_str = meta.get("last_accessed") or ""
        access_count = int(meta.get("access_count") or 0)

        created = datetime.fromisoformat(created_str.replace("Z", "")) if created_str else now
        last_accessed = datetime.fromisoformat(accessed_str.replace("Z", "")) if accessed_str else created

        days_since_created = max(0.0, (now - created).total_seconds() / 86400)
        days_since_access = max(0.0, (now - last_accessed).total_seconds() / 86400)

        effective_decay_rate = decay_rate / (1.0 + 0.25 * math.log(access_count + 1))
        recency = math.exp(-effective_decay_rate * days_since_created)
        freshness = math.exp(-0.005 * days_since_access)
        vitality = recency * freshness

        return _composite_dashboard_score(vitality, memory_type, access_count)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Test artifact filter
# ---------------------------------------------------------------------------
def is_test_artifact(*, content: str, title: str) -> bool:
    c = (content or "").strip().lower()
    t = (title or "").strip().lower()
    if c.startswith("elefante e2e test memory") or c.startswith("hybrid search test memory"):
        return True
    if c.startswith("entity relationship test ") or c.startswith("persistence test "):
        return True
    if t.startswith("e2e-test") or "hybrid_test_" in t:
        return True
    if t.startswith("entity_target") or c.startswith("entity_target"):
        return True
    if c.startswith("[battery_test]"):
        return True
    if "battery_test" in t or "test_battery_" in t:
        return True
    return False


# ---------------------------------------------------------------------------
# Core serializer: Memory → dashboard node dict
# ---------------------------------------------------------------------------
def _configured_vector_source() -> str:
    """Return the active embedded vector backend without freezing a legacy label."""
    try:
        from src.utils.config import get_config

        return str(get_config().elefante.vector_store.type)
    except Exception:
        return "embedded"


def memory_to_dashboard_node(
    mem: Memory,
    *,
    vector_source: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Convert a Memory object into a dashboard-consumable node dict.

    Returns None if the memory is a test artifact that should be excluded.
    This is the SINGLE SOURCE OF TRUTH for dashboard node structure.
    """
    cm = mem.metadata.custom_metadata or {}

    # Title resolution
    title = (cm.get("title") or "").strip()
    if not title:
        words = (mem.content or "").split()[:10]
        title = " ".join(words) if words else "Untitled Memory"

    if is_test_artifact(content=mem.content, title=title):
        return None

    content_redacted = _redact_secrets(mem.content)
    title_redacted = _redact_secrets(title)

    mem_type = mem.metadata.memory_type.value if hasattr(mem.metadata.memory_type, "value") else str(mem.metadata.memory_type)
    status_val = mem.metadata.status.value if hasattr(mem.metadata.status, "value") else str(mem.metadata.status)
    rel_type_val = (
        mem.metadata.relationship_type.value
        if getattr(mem.metadata, "relationship_type", None) and hasattr(mem.metadata.relationship_type, "value")
        else str(getattr(mem.metadata, "relationship_type", "") or "")
    )

    topic = _derive_topic(title, mem.metadata.category)

    return {
        "id": str(mem.id),
        "name": title_redacted,
        "type": "memory",
        "description": content_redacted,
        "created_at": mem.metadata.created_at.isoformat(),
        "properties": {
            "content": content_redacted,
            "memory_type": mem_type,
            "score": compute_live_score(mem),
            "tags": ",".join(mem.metadata.tags) if mem.metadata.tags else "",
            "status": status_val,
            "relationship_type": rel_type_val,
            "archived": bool(getattr(mem.metadata, "archived", False)),
            "deprecated": bool(getattr(mem.metadata, "deprecated", False)),
            "supersedes_id": str(mem.metadata.supersedes_id) if mem.metadata.supersedes_id else "",
            "superseded_by_id": str(mem.metadata.superseded_by_id) if mem.metadata.superseded_by_id else "",
            "processing_status": cm.get("processing_status"),
            "canonical_key": cm.get("canonical_key"),
            "namespace": cm.get("namespace"),
            "title": title_redacted,
            "topic": topic,
            "summary": _redact_secrets(cm.get("summary") or ""),
            "access_count": max(0, mem.metadata.access_count),
            "last_accessed": mem.metadata.last_accessed.isoformat() if mem.metadata.last_accessed else None,
            "last_modified": mem.metadata.last_modified.isoformat() if mem.metadata.last_modified else None,
            "ring": cm.get("ring"),
            "knowledge_type": cm.get("knowledge_type"),
            "owner_id": cm.get("owner_id"),
            "concepts": cm.get("concepts"),
            "surfaces_when": cm.get("surfaces_when"),
            "authority_score": cm.get("authority_score"),
            "source": vector_source or _configured_vector_source(),
        }
    }
