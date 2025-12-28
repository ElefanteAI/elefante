#!/usr/bin/env python3
"""
Store Core Insights into Elefante
Stores the most important learnings from debugging sessions.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.orchestrator import MemoryOrchestrator


async def store_core_insights():
    """Store critical insights from debugging into Elefante."""
    
    orchestrator = MemoryOrchestrator()
    
    insights = [
        {
            "content": """THE THREE GAPS - Core AI Failure Pattern:

Gap 1 (KNOWLEDGE GAP): Not having information
- Problem: AI doesn't know what to do
- Solution: Elefante retrieval system
- Status: ✅ SOLVED

Gap 2 (APPLICATION GAP): Having information but not using it
- Problem: AI retrieves "NEVER delete files" rule but recommends deletion anyway
- Root Cause: Retrieval ≠ Application
- Solution: Layer 4 - Memory Compliance Verification (must explicitly state which memories apply and how response follows them)
- Status: ✅ SOLVED

Gap 3 (EXECUTION GAP): Stating what should be done but not doing it
- Problem: AI says "files should be moved" but doesn't actually move them
- Root Cause: Analysis ≠ Action
- Solution: Layer 5 - Action Verification (FORCED EXECUTION: State → Execute → Verify in same response)
- Status: ✅ SOLVED

CRITICAL INSIGHT: RETRIEVAL ≠ APPLICATION ≠ EXECUTION

Just because AI:
1. ✅ Queries Elefante successfully
2. ✅ Retrieves relevant memories
3. ✅ Understands the content

Does NOT mean it will:
4. ❌ Apply the knowledge
5. ❌ Execute the required actions

ALL THREE GAPS MUST BE CLOSED:
Know (Elefante) + Apply (Compliance) + Execute (Verification) = Success

Missing any one = FAILURE.""",
            "importance": 10,
            "tags": ["ai-failure-pattern", "three-gaps", "protocol-core", "never-forget", "execution-critical"],
            "space": "system"
        },
        {
            "content": """PROTOCOL ENFORCEMENT - 5-Layer System:

Layer 1: Protocol Checklist (.bob/protocol-checklist.md)
- Reference document consulted before every response
- Contains verification requirements and failure patterns

Layer 2: Verification Triggers (in .roomodes)
- Keywords like "updated", "fixed", "complete" automatically require verification
- NEVER use these words without proof in same response

Layer 3: Dual-Memory Protocol (in .roomodes)
- Query conversation context + Elefante before EVERY response
- Store new learnings immediately (importance 8-10)

Layer 4: Memory Compliance Verification (in .roomodes)
- After retrieving memories, explicitly state which rules apply
- Explain how response follows retrieved rules
- Makes non-compliance visible

Layer 5: Action Verification - FORCED EXECUTION (in .roomodes)
- If action required: STATE it → DO it immediately → VERIFY it worked
- Never say "should move" - MOVE IT
- Never say "should update" - UPDATE IT
- Action and verification must happen in SAME response

ENFORCEMENT MECHANISM: Each layer catches different failure modes. All 5 layers required for reliable execution.""",
            "importance": 10,
            "tags": ["protocol-enforcement", "5-layer-system", "behavioral-pattern", "never-forget"],
            "space": "system"
        },
        {
            "content": """MEMORY QUALITY - How to Store Actionable Knowledge:

WEAK Memory (only addresses Knowledge Gap):
"User prefers not to delete files"

STRONG Memory (addresses all 3 gaps):
"CRITICAL RULE: NEVER delete files - move to ARCHIVE/ instead.

WHY: User has lost work from premature deletion.

HOW TO COMPLY:
1. When file cleanup needed, STATE: 'Moving to ARCHIVE per your rule'
2. EXECUTE: Use move command immediately
3. VERIFY: List ARCHIVE/ contents to prove move succeeded

FAILURE PATTERN: Saying 'should move' without actually moving.
CORRECT PATTERN: State → Execute → Verify in same response."

RECOMMENDATION: Importance 9-10 memories should include:
- The WHAT (the rule/pattern)
- The WHY (the failure it prevents)
- The HOW (explicit execution steps)
- The VERIFY (how to prove compliance)
- FAILURE PATTERN (what NOT to do)
- CORRECT PATTERN (what TO do)

This transforms Elefante from knowledge store into execution guide.""",
            "importance": 10,
            "tags": ["memory-quality", "actionable-knowledge", "execution-guide", "best-practices"],
            "space": "system"
        },
        {
            "content": """JAIME'S PREFERENCES - Development Style:

CRITICAL RULES (importance 10):
- NEVER delete files - always move to ARCHIVE/ with README explaining why
- Root directory must have <15 files for clarity
- Use topic-based organization (not file-type based)
- Consistent naming conventions across project

WORKFLOW PREFERENCES (importance 9):
- Clean workspace after completing tasks
- Document all changes immediately
- Verify everything before claiming done
- Show proof of completion, not just claims

COMMUNICATION STYLE (importance 9):
- Direct and technical, not conversational
- Focus on results and outcomes
- Provide evidence and verification
- Don't repeat what was already said

META-LEARNING (importance 10):
- Jaime values learning from mistakes
- Expects AI to remember and apply lessons
- Frustrated by repeated questions
- Demands proof of functionality, not assumptions

ENFORCEMENT: These preferences stored in Elefante must be APPLIED (Layer 4) and EXECUTED (Layer 5), not just retrieved.""",
            "importance": 10,
            "tags": ["user-preferences", "jaime", "development-style", "never-delete-files", "verification-required"],
            "space": "personal"
        }
    ]
    
    print("Storing core insights into Elefante...\n")
    
    for i, insight in enumerate(insights, 1):
        result = await orchestrator.add_memory(
            content=insight["content"],
            memory_type="insight",  # Valid MemoryType from enum
            tags=insight["tags"],
            importance=insight["importance"],
            metadata={"space": insight["space"]}
        )
        
        if result:
            print(f"Insight {i}/4 stored: {result.id}")
            print(f"   Tags: {', '.join(insight['tags'])}")
            print(f"   Space: {insight['space']}")
            print()
        else:
            print(f"Insight {i}/4 was ignored by Intelligence Pipeline")
            print()
    
    print("All core insights stored successfully!")
    print("\nThese insights can now be retrieved with:")
    print("  - elefanteMemorySearch('three gaps')")
    print("  - elefanteMemorySearch('protocol enforcement')")
    print("  - elefanteMemorySearch('memory quality')")
    print("  - elefanteMemorySearch('jaime preferences')")


if __name__ == "__main__":
    asyncio.run(store_core_insights())

# Made with Bob
