"""
Elefante Golden Cleanup Script
===============================
Cleans memory metadata (topic, score, status) for demo readiness.
NEVER modifies content, title, summary, or any non-metadata field.

Usage:
    python scripts/golden_cleanup.py              # Dry-run (default)
    python scripts/golden_cleanup.py --apply       # Write changes to ChromaDB
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chromadb
from src.utils.config import get_config

# ─── Topic Classifier ────────────────────────────────────────────────────────

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "debugging": [
        "debug", "error", "fix", "bug", "crash", "issue", "traceback",
        "deadlock", "corruption", "broken", "failure", "trap", "workaround",
    ],
    "documentation": [
        "doc.", "readme", "compendium", "neural-register", "docs/",
        "source:", "section:", "changelog",
    ],
    "architecture": [
        "architecture", "design pattern", "module", "pipeline", "refinery",
        "retriev", "layer", "orchestrat", "composite score", "engine",
    ],
    "agent-behavior": [
        "agent", "anti-loop", "protocol", "cognitive", "retrieval",
        "intervention", "fallback", "methodology enforcement",
    ],
    "database": [
        "kuzu", "chroma", "database", "schema", "query", "graph store",
        "reserved word", "sqlite", "vector store",
    ],
    "coding-standards": [
        "code style", "format", "naming", "convention", "standard",
        "safe_eval", "security", "pydantic",
    ],
    "user-profile": [
        "user preference", "user background", "identity", "personal",
        "favorite", "best-performing", "llm model",
    ],
    "tools-environment": [
        "vscode", "terminal", "install", "path", "config", "setup",
        "venv", "pip", "python path", "pre-flight",
    ],
    "communication": [
        "tone", "emoji", "language style", "response style",
        "communication", "direct", "bluf",
    ],
    "testing": [
        "test", "pytest", "e2e", "verif", "validation", "smoke",
        "stress-test", "baseline",
    ],
}


# Manual overrides for low-confidence misclassifications
TITLE_OVERRIDES: dict[str, str] = {
    "ultrathink": "agent-behavior",       # protocol, not a debugging "failure"
    "cartridge v2": "architecture",       # system spec, not tools-environment
    "api server": "architecture",         # infrastructure, not coding-standards
}


def classify_topic(content: str, title: str) -> tuple[str, int, list[str]]:
    """
    Classify memory into a topic based on keyword matching.

    Returns:
        (topic, confidence, matched_keywords)
        confidence = number of distinct keywords matched (0 = unclassifiable)
    """
    # Check manual overrides first
    title_lower = title.lower()
    for pattern, override_topic in TITLE_OVERRIDES.items():
        if pattern in title_lower:
            return (override_topic, 2, [f"override:{pattern}"])

    text = (content + " " + title).lower()
    best_topic = "general"
    best_hits = 0
    best_matched: list[str] = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in text]
        hits = len(matched)
        if hits > best_hits:
            best_hits = hits
            best_topic = topic
            best_matched = matched

    if best_hits == 0:
        return ("general", 0, [])
    return (best_topic, best_hits, best_matched)


# ─── Score Calculator ─────────────────────────────────────────────────────────

ACTIONABLE_MARKERS = re.compile(
    r"\b(always|never|must|ensure|require|prohibit|shall|when|if .+ then)\b",
    re.IGNORECASE,
)

KNOWLEDGE_TYPE_SCORES = {
    "law": 2.0,
    "principle": 2.0,
    "method": 1.5,
    "insight": 1.5,
    "decision": 1.0,
    "fact": 1.0,
    "none": 0.0,
}

MEMORY_TYPE_SCORES = {
    "decision": 2.0,
    "insight": 2.0,
    "fact": 1.0,
    "preference": 1.0,
}


def calculate_score(meta: dict, has_specific_topic: bool) -> int:
    """
    Calculate a meaningful 1-10 score based on metadata quality.

    Formula:
      has_specific_topic:   0 or 3
      knowledge_type:       0-2
      memory_type:          0-2
      is_actionable:        0 or 1
      freshness:            0-2
    Max = 10
    """
    score = 0.0

    # Topic specificity (0 or 3)
    if has_specific_topic:
        score += 3.0

    # Knowledge type (0-2)
    kt = (meta.get("knowledge_type") or "none").lower()
    score += KNOWLEDGE_TYPE_SCORES.get(kt, 0.0)

    # Memory type (0-2)
    mt = (meta.get("memory_type") or "fact").lower()
    score += MEMORY_TYPE_SCORES.get(mt, 0.5)

    # Actionable language (0 or 1)
    content = meta.get("_content") or ""
    if ACTIONABLE_MARKERS.search(content):
        score += 1.0

    # Freshness (0-2)
    created_str = meta.get("created_at") or ""
    if created_str:
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days < 30:
                score += 2.0
            elif age_days < 90:
                score += 1.0
        except (ValueError, TypeError):
            pass

    return max(1, min(10, round(score)))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Elefante Golden Cleanup")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to ChromaDB (default is dry-run)",
    )
    args = parser.parse_args()
    dry_run = not args.apply

    config = get_config()
    chroma_path = config.elefante.vector_store.persist_directory
    print(f"[*] ChromaDB path: {chroma_path}", file=sys.stderr)

    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection("memories")

    all_data = collection.get(include=["documents", "metadatas"])
    total = len(all_data["ids"])
    print(f"[*] Found {total} memories\n", file=sys.stderr)

    # ── Backup ────────────────────────────────────────────────────────────
    if not dry_run:
        backup_dir = Path.home() / ".elefante" / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"pre_golden_backup_{timestamp}.json"

        backup_data = {
            "ids": all_data["ids"],
            "metadatas": all_data["metadatas"],
            "timestamp": timestamp,
        }
        with open(backup_path, "w") as f:
            json.dump(backup_data, f, indent=2, default=str)
        print(f"[*] Backup saved to {backup_path}\n", file=sys.stderr)

    # ── Process Each Memory ───────────────────────────────────────────────
    changes: list[dict] = []
    topic_before: dict[str, int] = {}
    topic_after: dict[str, int] = {}
    score_distribution: dict[int, int] = {}
    status_fixes = 0

    for i in range(total):
        mem_id = all_data["ids"][i]
        meta = all_data["metadatas"][i] or {}
        doc = all_data["documents"][i] or ""

        current_topic = meta.get("topic") or "general"
        current_score = meta.get("score", 0)
        current_status = meta.get("status") or "new"
        title = meta.get("title") or ""

        topic_before[current_topic] = topic_before.get(current_topic, 0) + 1

        new_topic = current_topic
        new_score = current_score
        new_status = current_status
        confidence = 0
        matched_kws: list[str] = []

        # ── Step 1: Re-topic (only if currently "general") ────────────
        if current_topic == "general":
            new_topic, confidence, matched_kws = classify_topic(doc, title)

        # ── Step 2: Re-score ──────────────────────────────────────────
        meta_with_content = {**meta, "_content": doc}
        new_score = calculate_score(
            meta_with_content,
            has_specific_topic=(new_topic != "general"),
        )

        # ── Step 3: Fix contradictory status ──────────────────────────
        if current_status == "contradictory":
            new_status = "related"
            status_fixes += 1

        topic_after[new_topic] = topic_after.get(new_topic, 0) + 1
        score_distribution[new_score] = score_distribution.get(new_score, 0) + 1

        has_changes = (
            new_topic != current_topic
            or new_score != current_score
            or new_status != current_status
        )

        if has_changes:
            changes.append({
                "id": mem_id,
                "title": title[:70],
                "topic": f"{current_topic} -> {new_topic}" if new_topic != current_topic else current_topic,
                "topic_changed": new_topic != current_topic,
                "confidence": confidence,
                "keywords": ", ".join(matched_kws[:4]),
                "score": f"{current_score} -> {new_score}" if new_score != current_score else str(current_score),
                "status": f"{current_status} -> {new_status}" if new_status != current_status else current_status,
                "new_meta": {
                    "topic": new_topic,
                    "score": new_score,
                    "status": new_status,
                },
            })

    # ── Report ────────────────────────────────────────────────────────────
    mode_label = "DRY RUN" if dry_run else "APPLYING"
    print(f"\n{'='*80}")
    print(f"  GOLDEN CLEANUP — {mode_label}")
    print(f"{'='*80}\n")

    # Summary
    topic_changes = sum(1 for c in changes if c["topic_changed"])
    score_changes = sum(1 for c in changes if "->" in c["score"])
    print(f"  Total memories:    {total}")
    print(f"  Topic changes:     {topic_changes}")
    print(f"  Score changes:     {score_changes}")
    print(f"  Status fixes:      {status_fixes}")
    print(f"  Total changes:     {len(changes)}")
    print()

    # Topic distribution before/after
    print("  TOPIC DISTRIBUTION:")
    print(f"  {'Topic':<22} {'Before':>7} {'After':>7}")
    print(f"  {'-'*22} {'-'*7} {'-'*7}")
    all_topics = sorted(set(list(topic_before.keys()) + list(topic_after.keys())))
    for t in all_topics:
        b = topic_before.get(t, 0)
        a = topic_after.get(t, 0)
        marker = " *" if b != a else ""
        print(f"  {t:<22} {b:>7} {a:>7}{marker}")
    print()

    # Score distribution
    print("  SCORE DISTRIBUTION:")
    for s in sorted(score_distribution.keys()):
        bar = "#" * score_distribution[s]
        print(f"  Score {s:>2}: {score_distribution[s]:>3} {bar}")
    print()

    # Change table — split by confidence
    if topic_changes > 0:
        high_conf = [c for c in changes if c["topic_changed"] and c["confidence"] >= 2]
        low_conf = [c for c in changes if c["topic_changed"] and c["confidence"] == 1]

        if high_conf:
            print(f"  HIGH CONFIDENCE TOPIC CHANGES ({len(high_conf)}):")
            print(f"  {'Title':<52} {'Topic Change':<32} {'Conf':>4} {'Keywords'}")
            print(f"  {'-'*52} {'-'*32} {'-'*4} {'-'*30}")
            for c in high_conf:
                print(f"  {c['title']:<52} {c['topic']:<32} {c['confidence']:>4} {c['keywords']}")
            print()

        if low_conf:
            print(f"  LOW CONFIDENCE — REVIEW THESE ({len(low_conf)}):")
            print(f"  {'Title':<52} {'Topic Change':<32} {'Conf':>4} {'Keywords'}")
            print(f"  {'-'*52} {'-'*32} {'-'*4} {'-'*30}")
            for c in low_conf:
                print(f"  {c['title']:<52} {c['topic']:<32} {c['confidence']:>4} {c['keywords']}")
            print()

    # ── Apply ─────────────────────────────────────────────────────────────
    if not dry_run and changes:
        print(f"  [*] Writing {len(changes)} changes to ChromaDB...", file=sys.stderr)

        for c in changes:
            mem_id = c["id"]
            # Get current full metadata to preserve all fields
            current = collection.get(ids=[mem_id], include=["metadatas"])
            if not current["ids"]:
                continue
            full_meta = current["metadatas"][0]

            # Only update the 3 fields we own
            full_meta["topic"] = c["new_meta"]["topic"]
            full_meta["score"] = c["new_meta"]["score"]
            full_meta["status"] = c["new_meta"]["status"]

            collection.update(ids=[mem_id], metadatas=[full_meta])

        print(f"  [OK] {len(changes)} memories updated.\n")
        print("  Next steps:")
        print("    1. python scripts/update_dashboard_data.py")
        print("    2. Restart dashboard server")
        print("    3. Verify dashboard health score\n")
    elif dry_run:
        print("  This was a DRY RUN. No changes written.")
        print("  To apply: python scripts/golden_cleanup.py --apply\n")


if __name__ == "__main__":
    main()
