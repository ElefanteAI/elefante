"""
Elefante Session Distiller — Memory Ingester
Bridge between the Distiller pipeline and Elefante's MemoryOrchestrator.

Two modes:
  1. Raw Archive: Store a lightweight session reference (high decay).
  2. Insight Promotion: Store distilled insights as permanent memories.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from .models import ChatSession, DistilledInsight, InsightType

logger = logging.getLogger("elefante.distiller.ingester")

# Mapping from InsightType → Elefante memory_type
_INSIGHT_TYPE_MAP = {
    InsightType.DECISION:           "decision",
    InsightType.ROOT_CAUSE:         "insight",
    InsightType.PREFERENCE:         "preference",
    InsightType.ARCHITECTURE_RULE:  "fact",
    InsightType.FACT:               "fact",
    InsightType.CODE_SNIPPET:       "note",
    InsightType.ERROR_FIX:          "insight",
    InsightType.WORKFLOW:           "note",
}


class MemoryIngester:
    """Stores distilled content into Elefante's memory system."""

    def __init__(self):
        self._orchestrator = None

    def _get_orchestrator(self):
        """Lazy import to avoid circular deps and heavy init until needed."""
        if self._orchestrator is None:
            try:
                from src.core.orchestrator import MemoryOrchestrator
                self._orchestrator = MemoryOrchestrator()
                logger.info("Connected to Elefante MemoryOrchestrator")
            except ImportError as e:
                logger.error(f"Cannot import MemoryOrchestrator: {e}")
                raise RuntimeError(
                    "Elefante core not available. Ensure you're running from the Elefante project root "
                    "and all dependencies are installed."
                ) from e
        return self._orchestrator

    def store_raw_reference(self, session: ChatSession) -> Optional[str]:
        """
        Store a lightweight raw session reference (NOT the full transcript).
        This is the Free Tier archival — low score, high decay.
        Returns the memory ID if successful.
        """
        content = (
            f"Chat session with {session.turn_count} turns in workspace "
            f"'{session.workspace_name or session.workspace_id or 'unknown'}'. "
            f"Topics discussed: {self._extract_topic_summary(session)}. "
            f"Session ID: {session.session_id}"
        )

        metadata = {
            "category": "chat_session",
            "source_detail": "session_distiller",
            "session_id": session.session_id,
            "workspace": session.workspace_name or session.workspace_id,
            "decay_rate": 0.5,  # Fades unless reinforced
            "custom_metadata": {
                "source_path": session.source_path,
                "content_hash": session.content_hash,
                "turn_count": session.turn_count,
                "extracted_at": session.extracted_at.isoformat(),
            },
        }

        return self._run_async(self._store(
            content=content,
            memory_type="conversation",
            tags=["chat_session", "raw_archive", session.workspace_name or "unknown"],
            metadata=metadata,
        ))

    def store_insights(self, session: ChatSession, insights: List[DistilledInsight]) -> List[str]:
        """
        Store distilled insights as high-value, permanent memories.
        This is the Pro Tier — the money maker.
        Returns list of memory IDs for successfully stored insights.
        """
        stored_ids = []

        for insight in insights:
            memory_type = _INSIGHT_TYPE_MAP.get(insight.insight_type, "fact")

            metadata = {
                "category": f"distilled_{insight.insight_type.value}",
                "source_detail": "session_distiller",
                "confidence": insight.confidence,
                "decay_rate": 0.0,  # Permanent — this is refined knowledge
                "custom_metadata": {
                    "source_session": session.session_id,
                    "source_workspace": session.workspace_name or session.workspace_id,
                    "source_turn": insight.source_turn,
                    "insight_type": insight.insight_type.value,
                },
            }

            tags = list(insight.suggested_tags) + [
                "distilled",
                insight.insight_type.value,
                session.workspace_name or "unknown",
            ]

            mem_id = self._run_async(self._store(
                content=insight.content,
                memory_type=memory_type,
                tags=tags,
                metadata=metadata,
            ))

            if mem_id:
                stored_ids.append(mem_id)
                logger.info(
                    f"Stored insight: [{insight.insight_type.value}] "
                    f"score=50 (default) → {mem_id}"
                )

        return stored_ids

    async def _store(
        self,
        content: str,
        memory_type: str,
        tags: List[str],
        metadata: dict,
    ) -> Optional[str]:
        """Internal async store via orchestrator."""
        try:
            orch = self._get_orchestrator()
            memory = await orch.add_memory(
                content=content,
                memory_type=memory_type,
                tags=tags,
                metadata=metadata,
            )
            if memory:
                return str(memory.id)
            return None
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return None

    @staticmethod
    def _run_async(coro) -> Optional[str]:
        """Run async coroutine from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an existing async context — create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result(timeout=30)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    @staticmethod
    def _extract_topic_summary(session: ChatSession) -> str:
        """Quick topic extraction from first few user messages."""
        topics = []
        for turn in session.turns[:5]:
            # Take first 60 chars of each user message
            snippet = turn.user_text[:60].replace("\n", " ").strip()
            if snippet:
                topics.append(snippet)
        return "; ".join(topics) if topics else "unknown"
