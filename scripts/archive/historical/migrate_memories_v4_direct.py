#!/usr/bin/env python3
"""Migrate existing memories to V4 semantics (direct, deterministic).

This script follows the V4 documentation in docs/technical/memory-schema-v4.md:

- Populate a stable `canonical_key` for every memory
- Assign a namespace (`prod`/`test`/`ephemeral`) to every memory
- Enforce one-active-per-(namespace, canonical_key) by marking non-winners
  redundant+archived+deprecated and linking them to the winner

Design constraints:

- LLM-free / deterministic
- Bypasses MCP server caching by operating directly in-process

It can optionally export before/after JSON snapshots via direct ChromaDB access.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import chromadb

# Add repo root to path
import sys


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.orchestrator import get_orchestrator
from src.utils.config import get_config


def _timestamp() -> str:
	return datetime.now().strftime("%Y%m%d_%H%M%S")


def _export_all_memories_json(output_path: Path) -> Dict[str, Any]:
	"""Direct unfiltered export from ChromaDB (collection.get)."""
	config = get_config()
	chroma_dir = Path(config.elefante.vector_store.persist_directory)

	# IMPORTANT: match VectorStore's Chroma settings to avoid
	# "An instance of Chroma already exists ... with different settings".
	from chromadb.config import Settings

	client = chromadb.PersistentClient(
		path=str(chroma_dir),
		settings=Settings(
			anonymized_telemetry=config.elefante.anonymized_telemetry,
			allow_reset=True,
		),
	)
	collection = client.get_or_create_collection(
		name=config.elefante.vector_store.collection_name,
		metadata={"hnsw:space": config.elefante.vector_store.distance_metric},
	)

	results = collection.get(include=["metadatas", "documents"])

	ids = results.get("ids") or []
	metadatas = results.get("metadatas") or []
	documents = results.get("documents") or []

	exported: List[Dict[str, Any]] = []
	for i, memory_id in enumerate(ids):
		exported.append(
			{
				"id": memory_id,
				"content": documents[i] if i < len(documents) else "",
				"metadata": metadatas[i] if i < len(metadatas) else {},
			}
		)

	payload: Dict[str, Any] = {
		"exported_at": datetime.now().isoformat(),
		"count": len(exported),
		"chroma_dir": str(chroma_dir),
		"collection": config.elefante.vector_store.collection_name,
		"memories": exported,
	}

	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

	return payload


def _get_str(meta: Dict[str, Any], key: str) -> str:
	value = meta.get(key)
	if value is None:
		return ""
	if isinstance(value, str):
		return value
	return str(value)


def _truthy(value: Any) -> bool:
	if value is True:
		return True
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y"}
	if isinstance(value, (int, float)):
		return bool(value)
	return False


def _summarize_export(payload: Dict[str, Any]) -> Dict[str, Any]:
	memories = payload.get("memories") or []

	missing_namespace = 0
	missing_canonical_key = 0
	namespace_counts: Counter[str] = Counter()
	status_counts: Counter[str] = Counter()
	archived_true = 0
	deprecated_true = 0

	# V4 invariant check (approx): <= 1 active-like per (namespace, canonical_key)
	groups_active_like: Dict[Tuple[str, str], int] = defaultdict(int)
	groups_total: Counter[Tuple[str, str]] = Counter()

	for mem in memories:
		meta = mem.get("metadata") or {}

		namespace = _get_str(meta, "namespace")
		canonical_key = _get_str(meta, "canonical_key")
		status = _get_str(meta, "status")

		archived = _truthy(meta.get("archived"))
		deprecated = _truthy(meta.get("deprecated"))

		if not namespace:
			missing_namespace += 1
		else:
			namespace_counts[namespace] += 1

		if not canonical_key:
			missing_canonical_key += 1

		if status:
			status_counts[status] += 1

		if archived:
			archived_true += 1
		if deprecated:
			deprecated_true += 1

		group_key = (namespace or "", canonical_key or "")
		groups_total[group_key] += 1

		# "Active-like" definition: not archived AND not redundant.
		if (not archived) and status != "redundant":
			groups_active_like[group_key] += 1

	violating_groups = sum(
		1 for k, n in groups_active_like.items() if k[0] and k[1] and n > 1
	)
	duplicate_groups = sum(1 for k, n in groups_total.items() if k[0] and k[1] and n > 1)

	return {
		"count": len(memories),
		"missing_namespace": missing_namespace,
		"missing_canonical_key": missing_canonical_key,
		"namespace_counts": dict(namespace_counts),
		"status_counts": dict(status_counts),
		"archived_true": archived_true,
		"deprecated_true": deprecated_true,
		"duplicate_groups": duplicate_groups,
		"one_active_per_key_violations": violating_groups,
	}


async def _run_refinery(apply: bool) -> Dict[str, Any]:
	orchestrator = get_orchestrator()
	# Operational entry point per docs: consolidate_memories(force=...)
	return await orchestrator.consolidate_memories(force=bool(apply))


async def main() -> int:
	parser = argparse.ArgumentParser(
		description="Migrate memories to V4 (deterministic, direct)"
	)
	parser.add_argument(
		"--apply",
		action="store_true",
		help="Apply changes (default is dry-run)",
	)
	parser.add_argument(
		"--export-before",
		action="store_true",
		help="Write a pre-migration JSON export under the output directory",
	)
	parser.add_argument(
		"--export-after",
		action="store_true",
		help="Write a post-migration JSON export under the output directory",
	)
	parser.add_argument(
		"--out-dir",
		type=str,
		default="data",
		help="Directory for run records and exports (default: data)",
	)
	args = parser.parse_args()

	out_dir = Path(args.out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	stamp = _timestamp()
	pre_export_path = out_dir / f"memory_export_pre_v4_{stamp}.json"
	post_export_path = out_dir / f"memory_export_post_v4_{stamp}.json"
	run_record_path = out_dir / f"v4_migration_run_{stamp}.json"

	cfg = get_config()
	print("\n=== Elefante V4 Migration (Deterministic) ===\n")
	print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
	print(f"Chroma: {cfg.elefante.vector_store.persist_directory}")
	print(f"Collection: {cfg.elefante.vector_store.collection_name}\n")

	pre_summary: Dict[str, Any] | None = None
	if args.export_before:
		pre_payload = _export_all_memories_json(pre_export_path)
		pre_summary = _summarize_export(pre_payload)
		print(f"Wrote PRE export: {pre_export_path}")

	result = await _run_refinery(apply=bool(args.apply))

	with run_record_path.open("w", encoding="utf-8") as f:
		json.dump(result, f, ensure_ascii=False, indent=2, default=str)
	print(f"Wrote run record: {run_record_path}\n")

	refinery = result.get("refinery", {})
	stats = refinery.get("stats", {})
	if stats:
		print("Refinery stats:")
		for key in [
			"total_memories",
			"groups",
			"duplicate_groups",
			"redundant_marked",
			"canonical_key_set",
			"namespace_set",
			"planned_updates",
		]:
			if key in stats:
				print(f"  {key}: {stats[key]}")
		if refinery.get("applied"):
			print(f"  applied_changed: {refinery.get('changed', 0)}")

	post_summary: Dict[str, Any] | None = None
	if args.export_after:
		post_payload = _export_all_memories_json(post_export_path)
		post_summary = _summarize_export(post_payload)
		print(f"\nWrote POST export: {post_export_path}")

	if pre_summary or post_summary:
		print("\nVerification summary:")
		if pre_summary:
			print(f"  pre.count: {pre_summary['count']}")
			print(f"  pre.missing_namespace: {pre_summary['missing_namespace']}")
			print(
				f"  pre.missing_canonical_key: {pre_summary['missing_canonical_key']}"
			)
		if post_summary:
			print(f"  post.count: {post_summary['count']}")
			print(f"  post.missing_namespace: {post_summary['missing_namespace']}")
			print(
				f"  post.missing_canonical_key: {post_summary['missing_canonical_key']}"
			)
			print(f"  post.duplicate_groups: {post_summary['duplicate_groups']}")
			print(
				f"  post.one_active_per_key_violations: {post_summary['one_active_per_key_violations']}"
			)
			print(f"  post.namespace_counts: {post_summary['namespace_counts']}")
			print(f"  post.status_counts: {post_summary['status_counts']}")

	print("\n=== Done ===\n")
	return 0


if __name__ == "__main__":
	raise SystemExit(asyncio.run(main()))
