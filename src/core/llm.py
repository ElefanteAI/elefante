"""Agent-managed enrichment stub.

Elefante must never make direct calls to an LLM (local or remote). The MCP client
agent is responsible for any LLM connectivity and must pass enrichment results
into Elefante via tool arguments (metadata, entities, relationships, etc.).

This module exists only to keep older imports working.
"""

import re
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """No-network stub (agent-managed)."""

    def __init__(self):
        logger.info("llm_disabled_agent_managed")

    async def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        return "LLM is agent-managed; Elefante does not generate responses."

    async def extract_entities(self, content: str) -> List[Dict[str, str]]:
        return []

    async def analyze_memory(self, content: str) -> Dict[str, Any]:
        cleaned = re.sub(r"\s+", " ", (content or "").strip())
        title = cleaned[:50] + ("..." if len(cleaned) > 50 else "")
        return {
            "title": title,
            "summary": cleaned,
            "intent": None,
            "emotional_context": None,
            "entities": [],
            "relationships": [],
            "strategic_insight": None,
            "action": "ADD",
        }

    async def generate_semantic_title(self, content: str) -> str:
        cleaned = re.sub(r"\s+", " ", (content or "").strip())
        return cleaned[:80] + ("..." if len(cleaned) > 80 else "")


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
