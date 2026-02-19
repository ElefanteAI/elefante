"""
Memory Consolidation Module
Handles the synthesis of recent memories into higher-level insights.

ARCHITECTURE RULE:
Elefante must not call LLMs directly. Consolidation is therefore agent-driven:
an external agent can fetch recent memories, run any LLM it wants, then call
Elefante tools to store the consolidated insights.
"""

from typing import List

from src.models.memory import Memory
from src.utils.logger import get_logger


class MemoryConsolidator:
    """
    Consolidates raw memories into refined insights.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    async def consolidate_recent(self, hours: int = 24, force: bool = False) -> List[Memory]:
        """
        Consolidation is agent-driven by design (Elefante is LLM-free).
        External agents should fetch memories, run their own LLM, then
        write synthesized results via the normal add_memory pipeline.
        """
        self.logger.info(f"consolidation_agent_managed (last {hours}h)")
        return []
