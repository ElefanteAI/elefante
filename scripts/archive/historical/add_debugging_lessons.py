"""
Script to add debugging lessons learned to Elefante memory system
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.orchestrator import get_orchestrator

async def add_debugging_lessons():
    """Add critical debugging lessons from dashboard debugging session"""
    
    orchestrator = get_orchestrator()
    
    lessons = [
        {
            "content": "CRITICAL LESSON: Never claim something is 'fixed' or 'working' without verifying the complete end-to-end user experience. Testing API endpoints in isolation is insufficient - must test the actual user-facing interface.",
            "memory_type": "insight",
            "importance": 10,
            "tags": ["debugging", "testing", "user_experience", "methodology", "critical_lesson"]
        },
        {
            "content": "When debugging web dashboards: Always account for browser caching. After rebuilding frontend, instruct user to hard refresh (Ctrl+Shift+R) or clear cache. Testing in controlled environment (Puppeteer) does not reflect user's cached browser state.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["debugging", "web_development", "browser_caching", "frontend"]
        },
        {
            "content": "Debugging methodology failure: Tested components in isolation (database works, API works) but failed to verify integration (dashboard displays data). Must test complete data flow: Database → API → Frontend → Browser → User sees correct display.",
            "memory_type": "insight",
            "importance": 10,
            "tags": ["debugging", "integration_testing", "methodology", "end_to_end"]
        },
        {
            "content": "User frustration pattern: Repeatedly claiming 'it's fixed' without user confirmation causes justified frustration. Correct protocol: Make fix → Verify in user's environment → Instruct user how to test → Wait for confirmation → THEN claim success.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["user_experience", "communication", "debugging", "protocol"]
        },
        {
            "content": "Technical correctness ≠ User satisfaction. A working API with rendering canvas means nothing if user sees 'zero memories' and 'meaningless dots'. Success is defined by user experience, not technical correctness. Always verify usability, not just functionality.",
            "memory_type": "insight",
            "importance": 10,
            "tags": ["user_experience", "usability", "quality_standards", "philosophy"]
        },
        {
            "content": "Dashboard debugging session (2025-11-28): Took 2 hours and 15+ iterations due to incomplete testing. Root cause: Confused 'technically correct' with 'user-ready'. 75% efficiency loss from not verifying end-to-end before claiming success. See DASHBOARD_DEBUGGING_POSTMORTEM.md for full analysis.",
            "memory_type": "decision",
            "importance": 8,
            "tags": ["debugging", "postmortem", "elefante_project", "lessons_learned"]
        },
        {
            "content": "Elefante dashboard issues resolved: (1) Kuzu 0.11.x database format change, (2) Frontend reading wrong API response fields (stats.total_memories vs stats.vector_store.total_memories), (3) Missing memory labels on graph nodes, (4) Browser caching old frontend. All fixed with proper end-to-end testing.",
            "memory_type": "fact",
            "importance": 7,
            "tags": ["elefante_project", "debugging", "technical_details", "resolved"]
        },
        {
            "content": "New debugging protocol established: (1) Reproduce user's exact experience, (2) Verify complete data flow, (3) Test like a user (not just technically), (4) Account for environment differences (caching, browsers), (5) Only claim success after user confirmation. Document what was tested and what wasn't.",
            "memory_type": "decision",
            "importance": 9,
            "tags": ["debugging", "protocol", "methodology", "best_practices"]
        }
    ]
    
    print("Adding debugging lessons to Elefante memory...")
    print("=" * 70)
    
    for i, lesson in enumerate(lessons, 1):
        try:
            result = await orchestrator.add_memory(
                content=lesson["content"],
                memory_type=lesson["memory_type"],
                importance=lesson["importance"],
                tags=lesson["tags"]
            )
            print(f"[OK] Lesson {i}/{len(lessons)} added")
            print(f"     Type: {lesson['memory_type']}, Importance: {lesson['importance']}")
            print(f"     Preview: {lesson['content'][:80]}...")
            print()
        except Exception as e:
            print(f"[FAIL] Failed to add lesson {i}: {e}")
            print()
    
    print("=" * 70)
    print("Lesson addition complete!")
    
    # Verify memories were added
    print("\nVerifying system state...")
    stats = await orchestrator.get_stats()
    print(f"Total memories in system: {stats.get('vector_store', {}).get('total_memories', 0)}")
    print(f"Total entities in graph: {stats.get('graph_store', {}).get('total_entities', 0)}")
    print("\nThese lessons will help prevent similar issues in future debugging sessions.")

if __name__ == "__main__":
    asyncio.run(add_debugging_lessons())

# Made with Bob
