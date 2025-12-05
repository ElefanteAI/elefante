"""
Script to add user preference memories to Elefante
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.orchestrator import get_orchestrator

async def add_user_preferences():
    """Add memories about user preferences from recent interactions"""
    
    orchestrator = get_orchestrator()
    
    memories = [
        {
            "content": "User strongly dislikes regression in results. When fixing issues, ensure that previously working functionality is not broken. Always verify the complete user experience before claiming something is fixed.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["user_preference", "quality_standards", "testing", "regression"]
        },
        {
            "content": "User expects proactive problem-solving. Do not wait for user to discover issues - test thoroughly and verify end-to-end functionality before declaring success.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["user_preference", "proactive", "testing", "quality"]
        },
        {
            "content": "User prefers complete solutions over incremental half-fixes. Avoid claiming 'it works' without actually testing the full user-facing experience.",
            "memory_type": "insight",
            "importance": 8,
            "tags": ["user_preference", "completeness", "quality_standards"]
        },
        {
            "content": "When debugging, user expects deep investigation and root cause analysis, not surface-level fixes that may break other things.",
            "memory_type": "insight",
            "importance": 8,
            "tags": ["user_preference", "debugging", "root_cause_analysis"]
        },
        {
            "content": "User name: Jaime. Working on Elefante memory system installation and dashboard debugging. Located in Toronto timezone (UTC-5).",
            "memory_type": "fact",
            "importance": 7,
            "tags": ["user_info", "context", "project"]
        },
        {
            "content": "GAP 2 SELF-DISCOVERY - Application Gap Exhibited by AI Agent (2025-12-05)\n\nCONTEXT: Sprint 26 dashboard debugging. User reported 'only 11-17 nodes visible instead of 71'.\n\nWHAT I RETRIEVED (Gap 1 - CLOSED):\n✅ Full conversation context (Sprints 1-26)\n✅ Technical details (GUILLOTINE protocol, physics, snapshot system)\n✅ Previous session claim: 'server.py bypasses graph_service.py and queries Kuzu directly, returning only 11-17 nodes'\n\nWHAT I FAILED TO APPLY (Gap 2 - FAILED):\n❌ Did not VERIFY the backend claim before investigating\n❌ Assumed previous session diagnosis was correct\n❌ Wasted 5 tool uses investigating non-existent backend bug\n❌ Ignored user's own protocol: 'Verify assumptions before fixing'\n\nTHE TRUTH (discovered after reading logs):\n- Backend server.py logs: 'Loaded 71 nodes, 210 edges from snapshot' ✅ CORRECT\n- Frontend GUILLOTINE filter: Removed 12 memory nodes with 'user' in labels ❌ BUG\n- Previous session diagnosis was WRONG\n\nROOT CAUSE: Frontend filter used `label.includes('user')` which removed memory nodes like 'User is a senior applied AI/data science leader' (CORE_PERSONA memories). Should have been `(label === 'user' && type === 'entity')` to only filter User entity nodes.\n\nCRITICAL LESSON - THE VERIFICATION PROTOCOL:\nWhen conversation summary contains diagnostic claims:\n1. VERIFY with logs/code FIRST\n2. Do NOT assume previous sessions are correct\n3. Retrieved knowledge can be WRONG or OUTDATED\n4. Apply user's own debugging protocol: 'Read code first, verify assumptions'\n\nTHIS PROVES THE THREE GAPS FRAMEWORK:\nRETRIEVAL ≠ APPLICATION ≠ EXECUTION\n\nEven with perfect retrieval (I had full context), I still failed at application (didn't verify assumptions). This is exactly what the framework predicts.\n\nSOLUTION IMPLEMENTED: Changed GUILLOTINE V3 filter to only remove User entity nodes, preserving all 71 memory nodes. Dashboard now shows full topology.\n\nMETA-INSIGHT: This session is a perfect example of why Layer 4 (Memory Compliance Verification) exists. I should have explicitly stated which memories I was applying and verified their accuracy before proceeding.\n\nPROTOCOL ADDITION: Before applying retrieved diagnostic claims, verify with current system state (logs, code, data). Previous sessions can be wrong.",
            "memory_type": "insight",
            "importance": 10,
            "tags": ["three-gaps", "self-analysis", "application-gap", "verification-protocol", "never-forget", "meta-learning", "CORE_LESSON"]
        }
    ]
    
    print("Adding user preference memories and critical lessons...")
    print("=" * 60)
    
    for i, mem in enumerate(memories, 1):
        try:
            result = await orchestrator.add_memory(
                content=mem["content"],
                memory_type=mem["memory_type"],
                importance=mem["importance"],
                tags=mem["tags"]
            )
            print(f"[OK] Memory {i}/{len(memories)} added: {result}")
        except Exception as e:
            print(f"[FAIL] Failed to add memory {i}: {e}")
    
    print("=" * 60)
    print("Memory addition complete!")
    
    # Verify memories were added
    print("\nVerifying memories...")
    stats = await orchestrator.get_stats()
    print(f"Total memories in system: {stats.get('vector_store', {}).get('total_memories', 0)}")
    print(f"Total entities in graph: {stats.get('graph_store', {}).get('total_entities', 0)}")

if __name__ == "__main__":
    asyncio.run(add_user_preferences())

# Made with Bob
