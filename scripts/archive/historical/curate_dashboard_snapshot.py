#!/usr/bin/env python3
"""Curate dashboard snapshot (offline, no DB access).

This script enriches the active dashboard snapshot with lightweight curated fields
(e.g., `properties.summary`, `properties.title`) so the UI can be curated-first
without dumping raw memory content.

It intentionally does NOT touch ChromaDB/Kuzu, so it is safe to run with
Elefante Mode OFF.

Usage:
    python scripts/curate_dashboard_snapshot.py
    python scripts/curate_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json
    python scripts/curate_dashboard_snapshot.py --force  # rewrite titles/summaries in a consistent style
    python scripts/curate_dashboard_snapshot.py --no-backup
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Optional


_CODEBLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


def _default_snapshot_path() -> Path:
    # Avoid importing project modules so this script can run from anywhere.
    return Path.home() / ".elefante" / "data" / "dashboard_snapshot.json"


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _strip_codeblocks(text: str) -> str:
    return _CODEBLOCK_RE.sub(" ", text or "")


def _first_sentence(text: str) -> str:
    """Return the first sentence-ish chunk from text."""
    text = _collapse_ws(text)
    if not text:
        return ""

    # Common bullet/markdown cleanups
    text = text.replace("- ", "").replace("* ", "")

    # Split on sentence boundaries.
    m = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return m[0].strip() if m else text


def _truncate(text: str, max_len: int) -> str:
    text = _collapse_ws(text)
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rstrip()
    return cut + "…"


def _title_from_text(text: str) -> str:
    text = _collapse_ws(text)
    if not text:
        return "Memory"

    # Remove very common prefixes.
    text = re.sub(r"^(user|the)\s+", "", text, flags=re.IGNORECASE)

    # Take a short chunk.
    words = text.split()
    head = " ".join(words[:7])

    # If there is a colon, prefer what's before it.
    if ":" in head:
        head = head.split(":", 1)[0]

    return _truncate(head, 60) or "Memory"


def _normalize_kind(value: str) -> str:
    v = _collapse_ws(value).lower().replace("-", "_")
    v = re.sub(r"[^a-z0-9_]+", "_", v).strip("_")
    return v


def _best_signal(props: Dict[str, Any], key: str) -> str:
    v = props.get(key)
    if isinstance(v, str):
        return _collapse_ws(v)
    return ""


def _infer_style(props: Dict[str, Any]) -> str:
    """Infer the memory's intent so we can template the summary."""
    kt = _normalize_kind(str(props.get("knowledge_type") or props.get("knowledgeType") or ""))
    mem_type = _normalize_kind(str(props.get("memory_type") or props.get("memoryType") or ""))
    layer = _normalize_kind(str(props.get("layer") or ""))
    sub = _normalize_kind(str(props.get("sublayer") or ""))

    # Prefer V5 knowledge_type.
    for candidate in (kt, mem_type, sub):
        if candidate in {"law", "rule", "principle"}:
            return "rule"
        if candidate in {"preference"}:
            return "preference"
        if candidate in {"decision"}:
            return "decision"
        if candidate in {"method"}:
            return "method"
        if candidate in {"insight"}:
            return "insight"
        if candidate in {"goal"}:
            return "goal"
        if candidate in {"anti_pattern", "antipattern", "failure"}:
            return "anti_pattern"
        if candidate in {"constraint"}:
            return "constraint"
        if candidate in {"identity"}:
            return "identity"

    # Fall back to layer semantics.
    if layer == "intent":
        return "rule"
    if layer == "self" and sub == "preference":
        return "preference"
    return "fact"


def _clean_for_summary(text: str) -> str:
    text = _collapse_ws(_strip_codeblocks(text))
    # Remove leading schema-ish prefixes.
    text = re.sub(r"^(self|world|intent)\.[a-z_]+:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(user\s+preference|user\s+constraint|developer\s+etiquette\s+preference)\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _curated_summary(style: str, raw_text: str, max_len: int) -> str:
    base = _first_sentence(_clean_for_summary(raw_text))
    base = _truncate(base, max_len)

    prefix = {
        "rule": "Rule:",
        "preference": "Preference:",
        "decision": "Decision:",
        "method": "Method:",
        "insight": "Insight:",
        "goal": "Goal:",
        "anti_pattern": "Avoid:",
        "constraint": "Constraint:",
        "identity": "Identity:",
        "fact": "Fact:",
    }.get(style, "Note:")

    # Avoid double-prefixing.
    lowered = base.lower()
    if lowered.startswith(prefix.lower()):
        return base
    return _truncate(f"{prefix} {base}" if base else prefix, max_len)


def _curated_title(props: Dict[str, Any], raw_text: str, max_len: int) -> str:
    # If a title already exists and looks good, we may preserve it unless forcing.
    topic = _best_signal(props, "topic")
    kt = _best_signal(props, "knowledge_type")
    style = _infer_style(props)

    core = _title_from_text(_clean_for_summary(raw_text))
    # Make titles more structured but still short.
    parts = []
    if topic:
        parts.append(topic)
    if kt:
        parts.append(kt)
    else:
        parts.append(style)
    parts.append(core)
    title = " — ".join([p for p in parts if p])
    return _truncate(title, max_len) or "Memory"


@dataclass
class CurationStats:
    memories_seen: int = 0
    summaries_added: int = 0
    titles_added: int = 0
    summaries_rewritten: int = 0
    titles_rewritten: int = 0
    memories_with_summary: int = 0


def _is_memory_node(node: Dict[str, Any]) -> bool:
    # Snapshot nodes use `type: memory` for memories.
    return (node.get("type") or "memory") == "memory"


def _ensure_props(node: Dict[str, Any]) -> Dict[str, Any]:
    props = node.get("properties")
    if not isinstance(props, dict):
        props = {}
        node["properties"] = props
    return props


def _extract_best_text(node: Dict[str, Any], props: Dict[str, Any]) -> str:
    # Prefer the explicit content field if present.
    for key in ("content", "description", "raw", "text"):
        val = props.get(key)
        if isinstance(val, str) and val.strip():
            return val

    # Fallbacks from node itself.
    for key in ("description", "name"):
        val = node.get(key)
        if isinstance(val, str) and val.strip():
            return val

    return ""


def curate_snapshot(
    snapshot_path: Path,
    *,
    force: bool,
    max_summary: int,
    max_title: int,
) -> Tuple[Dict[str, Any], CurationStats]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("Snapshot format error: 'nodes' must be a list")

    stats = CurationStats()

    for node in nodes:
        if not isinstance(node, dict):
            continue
        if not _is_memory_node(node):
            continue

        stats.memories_seen += 1
        props = _ensure_props(node)

        existing_summary = str(props.get("summary") or "").strip()
        if existing_summary:
            stats.memories_with_summary += 1

        existing_title = str(props.get("title") or "").strip()

        raw_text = _extract_best_text(node, props)
        raw_text = _strip_codeblocks(raw_text)

        style = _infer_style(props)

        # Title
        if force or not existing_title:
            candidate_title = _curated_title(props, raw_text, max_title)
            props["title"] = candidate_title
            # Also set node.name so the graph label becomes curated.
            node["name"] = candidate_title
            if existing_title:
                stats.titles_rewritten += 1
            else:
                stats.titles_added += 1

        # Summary
        if force or not existing_summary:
            if raw_text.strip():
                candidate_summary = _curated_summary(style, raw_text, max_summary)
            else:
                # As a last resort, summarize from metadata signals.
                ring = str(props.get("ring") or "").strip()
                topic = str(props.get("topic") or "").strip()
                kt = str(props.get("knowledge_type") or "").strip()
                parts = [p for p in (ring, topic, kt) if p]
                candidate_summary = "Classified memory" + (": " + " • ".join(parts) if parts else "")
                candidate_summary = _truncate(candidate_summary, max_summary)

            props["summary"] = candidate_summary
            if existing_summary:
                stats.summaries_rewritten += 1
            else:
                stats.summaries_added += 1
            stats.memories_with_summary += 1

        # Mark provenance (useful for debugging)
        props.setdefault("curation", {})
        if isinstance(props["curation"], dict):
            props["curation"].update(
                {
                    "summary_source": "rewritten" if (existing_summary and force) else ("generated" if not existing_summary else "existing"),
                    "title_source": "rewritten" if (existing_title and force) else ("generated" if not existing_title else "existing"),
                    "curated_at": datetime.utcnow().isoformat() + "Z",
                    "curation_version": "snapshot-curation-v2",
                    "style": style,
                }
            )

    data["curation"] = {
        "version": "snapshot-curation-v2",
        "curated_at": datetime.utcnow().isoformat() + "Z",
        "memories_seen": stats.memories_seen,
        "summaries_added": stats.summaries_added,
        "titles_added": stats.titles_added,
        "summaries_rewritten": stats.summaries_rewritten,
        "titles_rewritten": stats.titles_rewritten,
    }

    return data, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Curate dashboard snapshot offline")
    parser.add_argument(
        "--path",
        type=str,
        default=str(_default_snapshot_path()),
        help="Path to dashboard_snapshot.json (default: ~/.elefante/data/dashboard_snapshot.json)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite title/summary for every memory (best-effort, consistent style)",
    )
    parser.add_argument(
        "--max-summary",
        type=int,
        default=180,
        help="Max characters for curated summary",
    )
    parser.add_argument(
        "--max-title",
        type=int,
        default=80,
        help="Max characters for curated title",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a timestamped .bak copy",
    )

    args = parser.parse_args()
    snapshot_path = Path(args.path).expanduser()

    if not snapshot_path.exists():
        raise SystemExit(f"Snapshot not found: {snapshot_path}")

    if not args.no_backup:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = snapshot_path.with_suffix(snapshot_path.suffix + f".bak_{ts}")
        backup_path.write_text(snapshot_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[backup] {backup_path}")

    data, stats = curate_snapshot(
        snapshot_path,
        force=bool(args.force),
        max_summary=int(args.max_summary),
        max_title=int(args.max_title),
    )

    snapshot_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[ok] curated snapshot: {snapshot_path}")
    print(
        f"[stats] memories={stats.memories_seen} summaries_added={stats.summaries_added} summaries_rewritten={stats.summaries_rewritten} "
        f"titles_added={stats.titles_added} titles_rewritten={stats.titles_rewritten}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
