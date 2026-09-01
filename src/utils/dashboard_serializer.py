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
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from src.models.memory import Memory, TYPE_DECAY_RATES
from src.utils.curation import assess_health


def graph_entity_payload(value: Any) -> dict[str, Any]:
    """Normalize one Kuzu entity value across driver result shapes."""
    if isinstance(value, Mapping):
        return {
            str(key): item
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, Mapping) else {}
    properties = getattr(value, "properties", None)
    if not isinstance(properties, Mapping):
        return {}
    payload = dict(properties)
    for name in ("id", "name", "type", "description", "created_at"):
        attribute = getattr(value, name, None)
        if attribute is not None:
            payload.setdefault(name, attribute)
    return payload


def graph_relationship_label(row: Mapping[str, Any]) -> str:
    """Return a relationship label despite Kuzu's version-specific key text."""
    direct = row.get("label(r)")
    if direct:
        return str(direct)
    for key, value in row.items():
        if str(key).upper().startswith("LABEL(") and value:
            return str(value)
    values = row.get("values")
    if isinstance(values, (list, tuple)) and len(values) >= 3 and values[2]:
        return str(values[2])
    return "RELATED"


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


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _redacted_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _redact_secrets(str(value))


def _bounded_resolution_history(custom_metadata: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Expose only the correction fields Home can explain, newest ten only."""
    raw_history = custom_metadata.get("conflict_resolution_history") or []
    if not isinstance(raw_history, list):
        return []
    allowed = (
        "at",
        "action",
        "winner_memory_id",
        "loser_memory_id",
        "reason",
        "invocation_mode",
    )
    history: list[Dict[str, Any]] = []
    for raw_event in raw_history[-10:]:
        if not isinstance(raw_event, dict):
            continue
        event = {
            key: _redact_secrets(str(raw_event[key]))
            for key in allowed
            if raw_event.get(key) is not None
        }
        if event:
            history.append(event)
    return history


def _bounded_correction_history(custom_metadata: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Expose newest verified Correct events without leaking arbitrary metadata."""
    raw_history = custom_metadata.get("verified_correction_history") or []
    if not isinstance(raw_history, list):
        return []
    history: list[Dict[str, Any]] = []
    for raw_event in raw_history[-10:]:
        if not isinstance(raw_event, dict):
            continue
        event: Dict[str, Any] = {}
        for key in ("operation_id", "at", "action", "reason", "invocation_mode"):
            if raw_event.get(key) is not None:
                event[key] = _redact_secrets(str(raw_event[key]))
        memory_ids = raw_event.get("memory_ids")
        if isinstance(memory_ids, dict):
            event["memory_ids"] = {
                _redact_secrets(str(key)): _redact_secrets(str(value))
                for key, value in memory_ids.items()
                if value is not None
            }
        if event:
            history.append(event)
    return history


def connection_counts_from_edges(
    memory_ids: set[str],
    edges: list[Dict[str, Any]],
    *,
    node_ids: Optional[set[str]] = None,
) -> Dict[str, int]:
    """Return unique graph degree for each memory in a snapshot."""
    neighbors = {memory_id: set[str]() for memory_id in memory_ids}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("from") or edge.get("source")
        target = edge.get("to") or edge.get("target")
        if source is None or target is None:
            continue
        source = str(source)
        target = str(target)
        if source == target:
            continue
        if node_ids is not None and (source not in node_ids or target not in node_ids):
            continue
        if source in neighbors:
            neighbors[source].add(target)
        if target in neighbors:
            neighbors[target].add(source)
    return {memory_id: len(links) for memory_id, links in neighbors.items()}


def usage_summary_from_nodes(nodes: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize retrieval history from the redacted memory nodes in a snapshot."""
    memory_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "memory"]
    access_counts: list[int] = []
    for node in memory_nodes:
        properties = node.get("properties")
        raw_count = properties.get("access_count", 0) if isinstance(properties, dict) else 0
        try:
            access_counts.append(max(0, int(raw_count)))
        except (TypeError, ValueError, OverflowError):
            access_counts.append(0)

    total_memories = len(access_counts)
    total_accesses = sum(access_counts)
    never_retrieved = sum(1 for count in access_counts if count == 0)
    retrieved_memories = total_memories - never_retrieved
    return {
        "total_accesses": total_accesses,
        "retrieved_memories": retrieved_memories,
        "never_retrieved": never_retrieved,
        "retrieval_rate": round((retrieved_memories / total_memories) * 100) if total_memories else 0,
        "average_access_count": round(total_accesses / total_memories, 1) if total_memories else 0.0,
        "max_access_count": max(access_counts, default=0),
    }


def health_summary_from_nodes(
    nodes: list[Dict[str, Any]],
    edges: list[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Return the deterministic aggregate health summary for a snapshot."""
    memory_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "memory"]
    total_memories = len(memory_nodes)
    if total_memories == 0:
        return {
            "score": 0,
            "freshness": 0,
            "coverage": 0,
            "usage": 0,
            "connectivity": 0,
            "counts": {},
        }

    current = now or datetime.utcnow()
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)

    fresh_sum = 0.0
    valid_dates = 0
    memory_ids = {str(node.get("id")) for node in memory_nodes if node.get("id") is not None}
    node_ids = {str(node.get("id")) for node in nodes if node.get("id") is not None}
    health_counts: Dict[str, int] = {}
    general_count = 0
    for node in memory_nodes:
        properties = node.get("properties") if isinstance(node.get("properties"), dict) else {}
        topic = str(properties.get("topic") or "general")
        if topic == "general":
            general_count += 1
        status = properties.get("health_status")
        if status:
            status = str(status)
            health_counts[status] = health_counts.get(status, 0) + 1

        date_value = node.get("created_at") or properties.get("created_at")
        if not date_value:
            continue
        try:
            created = datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
            if created.tzinfo is not None:
                created = created.astimezone(timezone.utc).replace(tzinfo=None)
            age_days = max(0.0, (current - created).total_seconds() / 86400)
        except (TypeError, ValueError, OverflowError):
            continue
        valid_dates += 1
        fresh_sum += max(0.0, 1.0 - age_days / 90.0)

    freshness = round((fresh_sum / valid_dates) * 100) if valid_dates else 0
    non_general = total_memories - general_count
    coverage = round((non_general / total_memories) * 100)
    usage = usage_summary_from_nodes(nodes)
    connection_counts = connection_counts_from_edges(memory_ids, edges, node_ids=node_ids)
    connected = sum(1 for count in connection_counts.values() if count > 0)
    connectivity = round((connected / total_memories) * 100)
    score = round(
        freshness * 0.30
        + coverage * 0.30
        + usage["retrieval_rate"] * 0.20
        + connectivity * 0.20
    )
    return {
        "score": max(0, min(100, score)),
        "freshness": freshness,
        "coverage": coverage,
        "usage": usage["retrieval_rate"],
        "connectivity": connectivity,
        "counts": dict(sorted(health_counts.items())),
    }


def memory_to_dashboard_node(
    mem: Memory,
    *,
    vector_source: Optional[str] = None,
    connection_count: Optional[int] = None,
    now: Optional[datetime] = None,
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

    mem_type = _enum_text(mem.metadata.memory_type)
    status_val = _enum_text(mem.metadata.status)
    rel_type_val = (
        mem.metadata.relationship_type.value
        if getattr(mem.metadata, "relationship_type", None) and hasattr(mem.metadata.relationship_type, "value")
        else str(getattr(mem.metadata, "relationship_type", "") or "")
    )

    topic = _derive_topic(title, mem.metadata.category)
    health = assess_health(
        mem,
        len(mem.related_entities) if connection_count is None else connection_count,
        now=now,
    )

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
            "health_status": health.status.value,
            "health_reason": health.reason,
            "connection_count": health.connection_count,
            "processing_status": cm.get("processing_status"),
            "canonical_key": cm.get("canonical_key"),
            "namespace": cm.get("namespace"),
            "title": title_redacted,
            "topic": topic,
            "summary": _redact_secrets(mem.metadata.summary or cm.get("summary") or ""),
            "access_count": max(0, mem.metadata.access_count),
            "last_accessed": mem.metadata.last_accessed.isoformat() if mem.metadata.last_accessed else None,
            "last_modified": mem.metadata.last_modified.isoformat() if mem.metadata.last_modified else None,
            "ring": cm.get("ring"),
            "knowledge_type": cm.get("knowledge_type"),
            "owner_id": cm.get("owner_id"),
            "concepts": mem.metadata.concepts or cm.get("concepts") or [],
            "surfaces_when": (
                mem.metadata.surfaces_when or cm.get("surfaces_when") or []
            ),
            "recall_cues": [
                _redact_secrets(str(cue))
                for cue in (mem.metadata.recall_cues or cm.get("recall_cues") or [])
                if str(cue).strip()
            ],
            "authority_score": mem.metadata.authority_score,
            "source": _enum_text(mem.metadata.source),
            "source_detail": _redact_secrets(mem.metadata.source_detail or ""),
            "source_reliability": mem.metadata.source_reliability,
            "verified": bool(mem.metadata.verified),
            "author": _redact_secrets(mem.metadata.author or ""),
            "storage_backend": vector_source or _configured_vector_source(),
            "project": _redacted_optional(mem.metadata.project),
            "workspace": _redacted_optional(mem.metadata.workspace),
            "scope": _redacted_optional(mem.metadata.scope),
            "file_path": _redacted_optional(mem.metadata.file_path),
            "line_number": mem.metadata.line_number,
            "url": _redacted_optional(mem.metadata.url),
            "location": _redacted_optional(mem.metadata.location),
            "retention_policy": _enum_text(mem.metadata.retention_policy),
            "injection_policy": _enum_text(mem.metadata.injection_policy),
            "user_locked": bool(mem.metadata.user_locked),
            "version": max(1, int(mem.metadata.version)),
            "conflict_ids": [str(item) for item in (mem.metadata.conflict_ids or [])],
            "conflict_resolution_history": _bounded_resolution_history(cm),
            "verified_correction_history": _bounded_correction_history(cm),
        }
    }
