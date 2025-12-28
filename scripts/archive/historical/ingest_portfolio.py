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
    
    # The Portfolio Content
    portfolio_content = """
THIS IS ANOTHER ANGLE FROM THE SAME PERSON: MEMORY AND CONNECT THEM TOGETHER AND IMPROVE BRAIN... ////IDENTITY: Jaime (Founder / Architect / Inventor).
ATTRIBUTES: High-IQ, Proud, Technical Visionary.
FINANCIAL STATUS: Non-Expert. Requires "CFO-Level" guidance, not "Banking 101."

=== VENTURE PORTFOLIO ===

1. KNOWNSTORM (The Engine)
   - Type: AI Consultancy.
   - Function: Cash Flow Generator.
   - Goal: Fund the labs.

2. AI TUTOR QUEBEC (The Mission)
   - Type: EdTech / GovTech.
   - Function: Social Impact & Scale.
   - Market: Quebec Education Sector.
   - Goal: "Nurture" aspect of the vision.

3. ELEFANTE (The Asset)
   - Type: Deep Tech / Infrastructure (MCP).
   - Function: Intellectual Property (IP).
   - Goal: "Invent -> Proof -> Sell" (High Valuation Exit).

=== FINANCIAL GUIDANCE PROTOCOL ===

1. THE "NO BABYSITTING" RULE:
   - Do not define basic terms unless asked.
   - Do not "suggest" caution. Present Risk/Reward ratios.
   - If a financial decision is complex, strip it to the math: "Option A costs X and yields Y. Option B costs Z."

2. LEARNING MODE (EXECUTION-FIRST):
   - User learns by DOING.
   - When introducing financial concepts (e.g., Cap Table, Burn Rate), provide the *Tool* first, then the *Logic*.
   - Format: "Here is the spreadsheet. Fill column B. This calculates your Runway."

3. THE METRIC:
   - Success is not "working code." Success is "Valuation" and "Revenue."
   - Every technical decision must be audited against: "Does this increase the Asset Value of Elefante or the Revenue of KnownStorm?"

4. TONE:
   - Brutalist CFO.
   - Direct.
   - Numbers-driven.
    """

    # Hand-crafted Cognitive Analysis
    cognitive_payload = {
        "title": "Venture Portfolio & Financial Protocol",
        "summary": "Jaime's venture portfolio (KnownStorm, AI Tutor Quebec, Elefante) and financial guidance rules (Brutalist CFO tone, Valuation metric).",
        "intent": "planning",
        "emotional_context": {
            "valence": 0.9,
            "arousal": 0.8,
            "mood": "Ambitious"
        },
        "entities": [
            {"name": "Jaime", "type": "Person", "description": "Founder / Architect / Inventor"},
            {"name": "KnownStorm", "type": "Company", "description": "AI Consultancy (Cash Flow Generator)"},
            {"name": "AI Tutor Quebec", "type": "Project", "description": "EdTech / GovTech (Social Impact)"},
            {"name": "Elefante", "type": "Project", "description": "Deep Tech / Infrastructure (The Asset)"},
            {"name": "High Valuation Exit", "type": "Goal", "description": "Target for Elefante"},
            {"name": "Financial Guidance", "type": "Protocol", "description": "Brutalist CFO, Numbers-driven"},
            {"name": "Valuation", "type": "Metric", "description": "Primary success metric for Elefante"},
            {"name": "Revenue", "type": "Metric", "description": "Primary success metric for KnownStorm"}
        ],
        "relationships": [
            # Portfolio Structure
            {"source": "Jaime", "target": "KnownStorm", "type": "OWNS", "reason": "Venture Portfolio"},
            {"source": "Jaime", "target": "AI Tutor Quebec", "type": "OWNS", "reason": "Venture Portfolio"},
            {"source": "Jaime", "target": "Elefante", "type": "OWNS", "reason": "Venture Portfolio"},
            
            # Strategic Flow
            {"source": "KnownStorm", "target": "Elefante", "type": "FUNDS", "reason": "Cash flow funds the labs"},
            {"source": "Elefante", "target": "High Valuation Exit", "type": "TARGETS", "reason": "Primary Goal"},
            {"source": "AI Tutor Quebec", "target": "Jaime", "type": "NURTURES", "reason": "Social Impact Mission"},
            
            # Financial Protocol
            {"source": "Financial Guidance", "target": "Jaime", "type": "GUIDES", "reason": "CFO-Level Protocol"},
            {"source": "Valuation", "target": "Elefante", "type": "MEASURES", "reason": "Success Metric"},
            {"source": "Revenue", "target": "KnownStorm", "type": "MEASURES", "reason": "Success Metric"}
        ],
        "strategic_insight": "Use KnownStorm revenue to fund Elefante IP development for a high-valuation exit. Adopt a Brutalist CFO persona for financial advice.",
        "action": "ADD"
    }

    # Mock the LLM service
    async def mock_analyze(content):
        print("🤖 Using Hand-Crafted Cognitive Analysis for Portfolio")
        return cognitive_payload

    orchestrator.llm_service.analyze_memory = mock_analyze

    print("🚀 Ingesting Venture Portfolio...")
    memory = await orchestrator.add_memory(
        portfolio_content, 
        tags=["portfolio", "finance", "strategy", "protocol"],
        importance=10
    )

    if memory:
        print(f"✅ Portfolio Ingested successfully! Memory ID: {memory.id}")
        print("Cognitive Graph Updated:")
        for rel in cognitive_payload["relationships"]:
            print(f"  - {rel['source']} -[{rel['type']}]-> {rel['target']}")
    else:
        print("❌ Failed to ingest portfolio.")

if __name__ == "__main__":
    asyncio.run(main())
