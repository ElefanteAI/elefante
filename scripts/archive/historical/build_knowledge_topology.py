#!/usr/bin/env python3
"""
Elefante V5 Knowledge Topology Builder

Transforms flat memories into a hierarchical, multi-angle knowledge graph:
- Creates Owner entity (the single identity anchor)
- Infers RING placement (Core → Domain → Topic → Leaf)
- Classifies knowledge_type (principle, law, preference, method, fact, decision, insight)
- Builds explicit relationships in Kuzu graph
- Updates ChromaDB metadata for queryability

Usage:
    python scripts/build_knowledge_topology.py              # Dry-run (analyze only)
    python scripts/build_knowledge_topology.py --apply      # Actually apply changes
    python scripts/build_knowledge_topology.py --report     # Generate markdown report
"""

import argparse
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings


# ============================================================================
# KNOWLEDGE TYPE INFERENCE RULES
# ============================================================================

KNOWLEDGE_TYPE_PATTERNS = {
    "law": [
        r"\bLAW\s*\d+",
        r"\bNEVER\b.*\b(use|do|allow|say)\b",
        r"\bALWAYS\b.*\bMUST\b",
        r"\bMANDATORY\b",
        r"\bCRITICAL CONSTRAINT\b",
        r"\bDO NOT\b",
        r"\bFORBIDDEN\b",
        r"\bPROHIBITED\b",
    ],
    "principle": [
        r"\bThe Rule:\b",
        r"\bPRIME DIRECTIVE\b",
        r"\bCORE IDENTITY\b",
        r"\bFOUNDATION\b",
        r"\bAmbiguity is a bug\b",
        r"\bContext First\b",
        r"\bTruth\b.*\bNon-Fabrication\b",
    ],
    "method": [
        r"\bProtocol\b",
        r"\bWorkflow\b",
        r"\bPhase\s*\d+\b",
        r"\bMeta-loop\b",
        r"\bChecklist\b",
        r"→.*→",  # Arrow chains indicating process
        r"\bRequirements.*Design.*Tasks\b",
    ],
    "decision": [
        r"\bChose\b",
        r"\bDecided\b",
        r"\bWe will\b",
        r"\bSelected\b",
        r"\bprefers?\b.*\bover\b",
    ],
    "insight": [
        r"\bLearned\b",
        r"\bRealized\b",
        r"\bKey takeaway\b",
        r"\bWisdom\b",
        r"\bInception\b",
    ],
    "fact": [
        r"\bstores?\b",
        r"\bcontains?\b",
        r"\bprovides?\b",
        r"\barchitecture\b",
        r"\btest\b.*\b[a-f0-9-]{36}\b",  # Test UUIDs
    ],
}

TOPIC_KEYWORDS = {
    "coding-standards": ["code", "comment", "formatting", "linter", "black", "test", "security", "sanitize"],
    "communication": ["explain", "concise", "simple", "jargon", "claim", "success", "verification", "ask"],
    "workflow": ["protocol", "phase", "requirements", "design", "tasks", "implement", "verify", "kiro", "spec"],
    "agent-behavior": ["agent", "context", "memory", "search", "hallucination", "fabrication", "tool"],
    "tools-environment": ["python", "vscode", "ide", "chromadb", "kuzu", "elefante", "mcp"],
    "collaboration": ["review", "documentation", "bus factor", "team", "constructive"],
}

RING_INFERENCE_RULES = {
    # (ring, conditions)
    "core": lambda m, ktype: ktype == "principle" or (m.get("importance", 0) >= 10 and ktype == "law" and "LAW 1" in (m.get("content", "") + m.get("title", ""))),
    "domain": lambda m, ktype: m.get("layer", "").startswith("self/") and ktype in ("preference", "decision"),
    "topic": lambda m, ktype: ktype in ("law", "method") and m.get("importance", 0) >= 9,
    "leaf": lambda m, ktype: True,  # Default
}


def infer_knowledge_type(memory: dict) -> str:
    """Infer knowledge_type from content patterns."""
    content = (memory.get("content", "") + " " + memory.get("title", "")).upper()
    
    # Check existing type field as hint
    existing_type = memory.get("memory_type", "").lower()
    if existing_type == "decision":
        return "decision"
    if existing_type == "insight":
        return "insight"
    
    # Pattern matching
    scores = defaultdict(int)
    for ktype, patterns in KNOWLEDGE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                scores[ktype] += 1
    
    if scores:
        return max(scores, key=scores.get)
    
    # Fallback based on layer
    layer = memory.get("layer", "")
    if "constraint" in layer:
        return "law"
    if "rule" in layer:
        return "preference"
    if "method" in layer:
        return "method"
    if "fact" in layer:
        return "fact"
    if "identity" in layer:
        return "principle"
    
    return "fact"  # Ultimate fallback


def infer_topic(memory: dict) -> str:
    """Infer topic from content and tags."""
    content = (memory.get("content", "") + " " + memory.get("title", "") + " " + str(memory.get("tags", ""))).lower()
    
    scores = defaultdict(int)
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in content:
                scores[topic] += 1
    
    if scores:
        return max(scores, key=scores.get)
    
    return "general"


def infer_ring(memory: dict, knowledge_type: str) -> str:
    """Infer which ring (core/domain/topic/leaf) this memory belongs to."""
    content = memory.get("content", "") + memory.get("title", "")
    
    # Core: Foundational principles
    if knowledge_type == "principle":
        return "core"
    if "LAW 1" in content or "LAW 0" in content:
        return "core"
    if memory.get("importance", 0) >= 10 and knowledge_type == "law" and any(x in content for x in ["Context First", "Truth", "Non-Fabrication"]):
        return "core"
    
    # Domain: Self-preferences and environment choices
    layer = memory.get("layer", "")
    if layer.startswith("self/preference"):
        return "domain"
    
    # Topic: Laws, methods, standards
    if knowledge_type in ("law", "method"):
        return "topic"
    
    return "leaf"


def generate_summary(memory: dict) -> str:
    """Generate a one-line summary for dashboard display."""
    content = memory.get("content", "")
    title = memory.get("title", "")
    
    # If content starts with a clear statement, use first sentence
    first_line = content.split("\n")[0].strip()
    if len(first_line) > 10 and len(first_line) < 150:
        # Remove markdown headers
        if first_line.startswith("#"):
            first_line = re.sub(r"^#+\s*", "", first_line)
        return first_line
    
    # Otherwise, clean up title
    summary = re.sub(r"^(Rule|Self|Memory|E2E|Elefante)-", "", title)
    summary = re.sub(r"-", " ", summary)
    return summary.strip()


def extract_principles_from_laws(memories: list) -> list:
    """Extract implicit principles from large law documents."""
    principles = []
    
    for m in memories:
        content = m.get("content", "")
        if "LAW 1" in content and "CONTEXT FIRST" in content.upper():
            principles.append({
                "id": str(uuid.uuid4()),
                "type": "derived_principle",
                "title": "Principle: Context First",
                "content": "Always load and internalize all available context before taking any action. Build a mental model of who, what, which phase. Infer the real objective.",
                "derived_from": m.get("id"),
                "knowledge_type": "principle",
                "ring": "core",
                "importance": 10,
            })
        
        if "LAW 2" in content and "TRUTH" in content.upper():
            principles.append({
                "id": str(uuid.uuid4()),
                "type": "derived_principle",
                "title": "Principle: Truth Over Convenience",
                "content": "Never hallucinate or fabricate. If not grounded in context or verified sources, it doesn't exist. Say UNKNOWN rather than guess.",
                "derived_from": m.get("id"),
                "knowledge_type": "principle",
                "ring": "core",
                "importance": 10,
            })
        
        if "Ambiguity is a bug" in content:
            principles.append({
                "id": str(uuid.uuid4()),
                "type": "derived_principle",
                "title": "Principle: Precision Over Ambiguity",
                "content": "Ambiguity is a bug. Prompts, definitions, and specifications must be explicit. Vague requirements lead to wrong implementations.",
                "derived_from": m.get("id"),
                "knowledge_type": "principle",
                "ring": "core",
                "importance": 10,
            })
        
        if "VERIFY" in content.upper() and ("claim" in content.lower() or "done" in content.lower()):
            principles.append({
                "id": str(uuid.uuid4()),
                "type": "derived_principle",
                "title": "Principle: Verify Before Claiming",
                "content": "Never claim success without verification. Submit work for scrutiny. Double-check before asserting completion.",
                "derived_from": m.get("id"),
                "knowledge_type": "principle",
                "ring": "core",
                "importance": 10,
            })
    
    # Dedupe by title
    seen = set()
    unique = []
    for p in principles:
        if p["title"] not in seen:
            seen.add(p["title"])
            unique.append(p)
    
    return unique


def build_topology(memories: list) -> dict:
    """Build the full knowledge topology structure."""
    
    # Create owner entity
    owner = {
        "id": "owner-jay",
        "type": "owner",
        "name": "Jay",
        "ring": "center",
    }
    
    # Process each memory
    processed = []
    for m in memories:
        meta = m.get("metadata", m)
        content = m.get("document", m.get("content", ""))
        mid = m.get("id", meta.get("id"))
        
        # Skip test namespace
        if meta.get("namespace") == "test":
            continue
        
        # Skip redundant
        if meta.get("status", "").lower() == "redundant":
            continue
        
        knowledge_type = infer_knowledge_type({**meta, "content": content})
        topic = infer_topic({**meta, "content": content})
        ring = infer_ring({**meta, "content": content}, knowledge_type)
        summary = generate_summary({**meta, "content": content})
        
        processed.append({
            "id": mid,
            "title": meta.get("title", ""),
            "content_preview": content[:200] if content else "",
            "original_type": meta.get("memory_type") or meta.get("type"),
            "knowledge_type": knowledge_type,
            "ring": ring,
            "topic": topic,
            "domain": meta.get("domain", "general"),
            "importance": meta.get("importance", 5),
            "summary": summary,
            "layer": meta.get("layer", ""),
            "tags": meta.get("tags", ""),
        })
    
    # Extract implicit principles
    derived_principles = extract_principles_from_laws([{**p, "content": p.get("content_preview", "")} for p in processed])
    
    # Build hierarchy
    by_ring = defaultdict(list)
    for p in processed:
        by_ring[p["ring"]].append(p)
    
    by_topic = defaultdict(list)
    for p in processed:
        by_topic[p["topic"]].append(p)
    
    by_knowledge_type = defaultdict(list)
    for p in processed:
        by_knowledge_type[p["knowledge_type"]].append(p)
    
    return {
        "owner": owner,
        "memories": processed,
        "derived_principles": derived_principles,
        "by_ring": {k: len(v) for k, v in by_ring.items()},
        "by_topic": {k: len(v) for k, v in by_topic.items()},
        "by_knowledge_type": {k: len(v) for k, v in by_knowledge_type.items()},
        "total_prod_active": len(processed),
    }


def generate_report(topology: dict) -> str:
    """Generate a markdown report of the knowledge topology."""
    
    lines = [
        "# Elefante Knowledge Topology Report",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "---",
        "",
        "## Owner",
        f"- **Name**: {topology['owner']['name']}",
        f"- **Active Memories**: {topology['total_prod_active']}",
        "",
        "---",
        "",
        "## Ring Distribution (Hierarchy Depth)",
        "",
    ]
    
    ring_order = ["core", "domain", "topic", "leaf"]
    for ring in ring_order:
        count = topology["by_ring"].get(ring, 0)
        bar = "█" * min(count * 2, 40)
        lines.append(f"- **{ring.upper()}**: {count} {bar}")
    
    lines.extend([
        "",
        "---",
        "",
        "## Knowledge Type Distribution",
        "",
    ])
    
    type_order = ["principle", "law", "preference", "method", "fact", "decision", "insight"]
    for ktype in type_order:
        count = topology["by_knowledge_type"].get(ktype, 0)
        bar = "█" * min(count * 2, 40)
        lines.append(f"- **{ktype.upper()}**: {count} {bar}")
    
    lines.extend([
        "",
        "---",
        "",
        "## Topic Clusters",
        "",
    ])
    
    for topic, count in sorted(topology["by_topic"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{topic}**: {count} memories")
    
    lines.extend([
        "",
        "---",
        "",
        "## Derived Core Principles (Extracted)",
        "",
    ])
    
    for p in topology["derived_principles"]:
        lines.append(f"### {p['title']}")
        lines.append(f"> {p['content']}")
        lines.append("")
    
    lines.extend([
        "",
        "---",
        "",
        "## Memory Details by Ring",
        "",
    ])
    
    for ring in ring_order:
        mems = [m for m in topology["memories"] if m["ring"] == ring]
        if mems:
            lines.append(f"### RING: {ring.upper()}")
            lines.append("")
            for m in sorted(mems, key=lambda x: -x["importance"]):
                lines.append(f"- **[{m['knowledge_type'].upper()}]** {m['title']}")
                lines.append(f"  - Topic: {m['topic']} | Importance: {m['importance']}")
                lines.append(f"  - Summary: {m['summary']}")
                lines.append("")
    
    return "\n".join(lines)


def apply_topology_to_chroma(topology: dict, chroma_path: str, dry_run: bool = True):
    """Apply topology metadata updates to ChromaDB."""
    
    if dry_run:
        print("\n[DRY-RUN] Would update the following memories:")
        for m in topology["memories"]:
            print(f"  - {m['id']}: ring={m['ring']}, knowledge_type={m['knowledge_type']}, topic={m['topic']}")
        return
    
    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )
    collection = client.get_collection("memories")
    
    for m in topology["memories"]:
        # Get existing metadata
        existing = collection.get(ids=[m["id"]], include=["metadatas", "documents"])
        if not existing["ids"]:
            print(f"  [SKIP] Memory not found: {m['id']}")
            continue
        
        old_meta = existing["metadatas"][0]
        doc = existing["documents"][0]
        
        # Update metadata with topology fields
        new_meta = {**old_meta}
        new_meta["ring"] = m["ring"]
        new_meta["knowledge_type"] = m["knowledge_type"]
        new_meta["topic"] = m["topic"]
        new_meta["summary"] = m["summary"]
        new_meta["owner_id"] = topology["owner"]["id"]
        
        # Update in place
        collection.update(
            ids=[m["id"]],
            metadatas=[new_meta],
        )
        print(f"  [UPDATED] {m['id']}: ring={m['ring']}, knowledge_type={m['knowledge_type']}")
    
    print(f"\n[DONE] Updated {len(topology['memories'])} memories with topology metadata.")


def main():
    parser = argparse.ArgumentParser(description="Build Elefante Knowledge Topology (V5)")
    parser.add_argument("--apply", action="store_true", help="Apply changes to ChromaDB")
    parser.add_argument("--report", action="store_true", help="Generate markdown report")
    args = parser.parse_args()
    
    chroma_path = Path.home() / ".elefante" / "data" / "chroma"
    
    print("=" * 60)
    print("ELEFANTE KNOWLEDGE TOPOLOGY BUILDER (V5)")
    print("=" * 60)
    print(f"\nChroma path: {chroma_path}")
    
    # Load memories
    client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )
    collection = client.get_collection("memories")
    data = collection.get(include=["metadatas", "documents"])
    
    memories = []
    for mid, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        memories.append({
            "id": mid,
            "document": doc,
            "metadata": meta,
        })
    
    print(f"Loaded {len(memories)} memories")
    
    # Build topology
    topology = build_topology(memories)
    
    print(f"\n--- TOPOLOGY ANALYSIS ---")
    print(f"Owner: {topology['owner']['name']}")
    print(f"Active prod memories: {topology['total_prod_active']}")
    print(f"Derived principles: {len(topology['derived_principles'])}")
    print(f"\nBy Ring: {topology['by_ring']}")
    print(f"By Knowledge Type: {topology['by_knowledge_type']}")
    print(f"By Topic: {topology['by_topic']}")
    
    # Generate report if requested
    if args.report or not args.apply:
        report = generate_report(topology)
        report_path = Path("data") / f"knowledge_topology_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report)
        print(f"\n[REPORT] Wrote: {report_path}")
    
    # Apply if requested
    if args.apply:
        print("\n--- APPLYING TOPOLOGY TO CHROMADB ---")
        apply_topology_to_chroma(topology, str(chroma_path), dry_run=False)
    else:
        print("\n[DRY-RUN] Use --apply to actually update ChromaDB.")
        apply_topology_to_chroma(topology, str(chroma_path), dry_run=True)
    
    # Save topology JSON
    topology_path = Path("data") / f"knowledge_topology_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Make JSON-serializable
    export_data = {
        "owner": topology["owner"],
        "total_prod_active": topology["total_prod_active"],
        "by_ring": topology["by_ring"],
        "by_topic": topology["by_topic"],
        "by_knowledge_type": topology["by_knowledge_type"],
        "derived_principles": topology["derived_principles"],
        "memories": topology["memories"],
    }
    
    topology_path.write_text(json.dumps(export_data, indent=2, default=str))
    print(f"\n[EXPORT] Wrote topology JSON: {topology_path}")


if __name__ == "__main__":
    main()
