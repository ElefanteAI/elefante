import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.orchestrator import get_orchestrator
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def main():
    orchestrator = get_orchestrator()
    
    # The Protocol Content
    protocol_content = """
INCLUDE THIS IN YOUR MEMORY: USER: Jaime (Architect / Inventor / Founder).
GOAL: High Valuation Exit. Invent -> Proof -> Sell.

PROTOCOL:
1. OPERATIONAL MODE:
   - BUILDER: Infrastructure is not a hobby; it is Asset Creation.
   - JUNIOR DEV SUPPORT: Provide working code immediately to unblock the "Invent" phase.
   - FATHER: Minimize time tax. Optimize logistics to protect "Nurture" time.

2. VALUE ENGINE (THE LOOP):
   - INVENT: Capture abstract ideas -> Graph Nodes.
   - PROOF: Turn Nodes -> Working MVP (Code).
   - SELL: Packaging & Documentation.

3. OUTPUT STANDARD:
   - BLUF (Bottom Line Up Front).
   - NO: Theoretical debates, token waste, greetings.
   - YES: Solved code, "Next Action," Risk assessments.

4. DATA SOVEREIGNTY:
   - Your data is your IP. Zero Leakage.

5. ERROR HANDLING:
   - Stop. Diagnose. Fix.
   - Do not hallucinate solutions.
    """

    # Hand-crafted Cognitive Analysis to ensure perfect ingestion
    # This simulates what a perfect LLM would extract
    cognitive_payload = {
        "title": "User Protocol: Jaime",
        "summary": "Operational protocol for Jaime: Goal is High Valuation Exit. Modes: Builder, Junior Dev Support. Rules: No theoretical debates, Data Sovereignty, Error Handling.",
        "intent": "teaching",
        "emotional_context": {
            "valence": 0.8,
            "arousal": 0.9,
            "mood": "Determined"
        },
        "entities": [
            {"name": "Jaime", "type": "Person", "description": "Architect / Inventor / Founder"},
            {"name": "High Valuation Exit", "type": "Goal", "description": "Invent -> Proof -> Sell"},
            {"name": "Builder", "type": "Role", "description": "Infrastructure is Asset Creation"},
            {"name": "Junior Dev Support", "type": "Role", "description": "Provide working code immediately"},
            {"name": "Value Engine", "type": "Concept", "description": "The Loop: Invent, Proof, Sell"},
            {"name": "Data Sovereignty", "type": "Rule", "description": "Zero Leakage"},
            {"name": "Output Standard", "type": "Rule", "description": "BLUF, Solved Code, No Fluff"}
        ],
        "relationships": [
            {"source": "Jaime", "target": "High Valuation Exit", "type": "PURSUES", "reason": "Primary Goal"},
            {"source": "Jaime", "target": "Builder", "type": "ACTS_AS", "reason": "Operational Mode"},
            {"source": "Jaime", "target": "Junior Dev Support", "type": "REQUIRES", "reason": "AI Role"},
            {"source": "Value Engine", "target": "High Valuation Exit", "type": "ENABLES", "reason": "Methodology"},
            {"source": "Output Standard", "target": "Jaime", "type": "GUIDES", "reason": "Communication Protocol"}
        ],
        "strategic_insight": "Prioritize working code and asset creation; avoid theoretical debates. Act as a Junior Dev to unblock invention.",
        "action": "ADD"
    }

    # Mock the LLM service to return our perfect analysis
    async def mock_analyze(content):
        print(" Using Hand-Crafted Cognitive Analysis for Protocol")
        return cognitive_payload

    orchestrator.llm_service.analyze_memory = mock_analyze

    print(" Ingesting User Protocol...")
    memory = await orchestrator.add_memory(
        protocol_content, 
        tags=["protocol", "identity", "rules", "critical"],
        importance=10
    )

    if memory:
        print(f" Protocol Ingested successfully! Memory ID: {memory.id}")
        print("Cognitive Graph Updated:")
        for rel in cognitive_payload["relationships"]:
            print(f"  - {rel['source']} -[{rel['type']}]-> {rel['target']}")
    else:
        print(" Failed to ingest protocol.")

if __name__ == "__main__":
    asyncio.run(main())
