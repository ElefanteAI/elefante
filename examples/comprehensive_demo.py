"""
Comprehensive Elefante Demo - Understanding the Process, Limitations & Workarounds

This example demonstrates:
1. The complete memory lifecycle (add, search, retrieve, consolidate)
2. Different memory types and their use cases
3. Query modes (semantic, structured, hybrid) and when to use each
4. Common limitations and practical workarounds
5. Best practices for production use

Run this to understand how Elefante works end-to-end.
"""

import asyncio
import sys
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.core.orchestrator import get_orchestrator
from src.models.memory import MemoryType, DomainType, IntentType
from src.models.query import QueryMode


class ElefanteDemo:
    """Comprehensive demonstration of Elefante's capabilities"""
    
    def __init__(self):
        self.orchestrator = get_orchestrator()
        self.memory_ids = []
        
    def print_section(self, title: str):
        """Print a formatted section header"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70 + "\n")
    
    def print_subsection(self, title: str):
        """Print a formatted subsection"""
        print(f"\n{'─'*70}")
        print(f"  {title}")
        print(f"{'─'*70}\n")
    
    async def demo_1_memory_types(self):
        """Demonstrate different memory types and their purposes"""
        self.print_section("📚 PART 1: Understanding Memory Types")
        
        print("Elefante supports multiple memory types, each optimized for different use cases:\n")
        
        # 1. FACT - Objective, verifiable information
        print("1️⃣  FACT - Objective, verifiable information")
        print("   Use for: User profiles, system configurations, established knowledge")
        fact_memory = await self.orchestrator.add_memory(
            content="Python 3.12 introduced improved error messages and the new f-string syntax",
            memory_type=MemoryType.FACT,
            importance=8,
            tags=["python", "version", "features"],
            entities=[
                {"name": "Python 3.12", "type": "technology"},
                {"name": "f-strings", "type": "feature"}
            ]
        )
        print(f"   ✅ Stored: {fact_memory.id if fact_memory else 'None'}\n")
        
        # 2. CONVERSATION - Dialogue context
        print("2️⃣  CONVERSATION - Dialogue and interaction context")
        print("   Use for: Chat history, discussions, Q&A sessions")
        conv_memory = await self.orchestrator.add_memory(
            content="User asked about implementing async/await patterns in Python. Discussed event loops and coroutines.",
            memory_type=MemoryType.CONVERSATION,
            importance=6,
            tags=["discussion", "async", "python"],
            metadata={"session_id": "demo-session-001"}
        )
        print(f"   ✅ Stored: {conv_memory.id if conv_memory else 'None'}\n")
        
        # 3. INSIGHT - Derived understanding
        print("3️⃣  INSIGHT - Derived understanding and patterns")
        print("   Use for: Learned patterns, user preferences, behavioral insights")
        insight_memory = await self.orchestrator.add_memory(
            content="User prefers functional programming style with immutable data structures and pure functions",
            memory_type=MemoryType.INSIGHT,
            importance=9,
            tags=["preference", "coding-style", "functional"],
            entities=[
                {"name": "functional programming", "type": "concept"}
            ]
        )
        print(f"   ✅ Stored: {insight_memory.id if insight_memory else 'None'}\n")
        
        # 4. DECISION - Important choices and rationale
        print("4️⃣  DECISION - Important choices with rationale")
        print("   Use for: Architecture decisions, tool selections, strategic choices")
        decision_memory = await self.orchestrator.add_memory(
            content="Decided to use FastAPI over Flask for the new API service due to better async support and automatic OpenAPI documentation",
            memory_type=MemoryType.DECISION,
            importance=10,
            tags=["architecture", "api", "framework"],
            entities=[
                {"name": "FastAPI", "type": "technology"},
                {"name": "Flask", "type": "technology"}
            ]
        )
        print(f"   ✅ Stored: {decision_memory.id if decision_memory else 'None'}\n")
        
        # 5. TASK - Action items
        print("5️⃣  TASK - Action items and todos")
        print("   Use for: Pending work, reminders, follow-ups")
        task_memory = await self.orchestrator.add_memory(
            content="TODO: Refactor the authentication module to use JWT tokens instead of session cookies",
            memory_type=MemoryType.TASK,
            importance=7,
            tags=["todo", "authentication", "refactoring"],
            metadata={"status": "pending", "priority": "high"}
        )
        print(f"   ✅ Stored: {task_memory.id if task_memory else 'None'}\n")
        
        print("💡 KEY INSIGHT: Choose the right memory type to optimize retrieval and organization")
    
    async def demo_2_query_modes(self):
        """Demonstrate different query modes and when to use each"""
        self.print_section("🔍 PART 2: Understanding Query Modes")
        
        # Add some test memories first
        await self.orchestrator.add_memory(
            content="Redis is an in-memory data store used for caching and session management",
            memory_type=MemoryType.FACT,
            importance=8,
            tags=["redis", "caching", "database"],
            entities=[{"name": "Redis", "type": "technology"}]
        )
        
        await self.orchestrator.add_memory(
            content="PostgreSQL is a relational database with strong ACID guarantees and JSON support",
            memory_type=MemoryType.FACT,
            importance=8,
            tags=["postgresql", "database", "sql"],
            entities=[{"name": "PostgreSQL", "type": "technology"}]
        )
        
        # MODE 1: SEMANTIC - Vector similarity search
        self.print_subsection("Mode 1: SEMANTIC (Vector Search)")
        print("Best for: Natural language queries, conceptual similarity, fuzzy matching")
        print("Query: 'What caching solutions are available?'\n")
        
        semantic_results = await self.orchestrator.search_memories(
            query="What caching solutions are available?",
            mode=QueryMode.SEMANTIC,
            limit=3
        )
        
        print(f"Found {len(semantic_results)} results:")
        for i, result in enumerate(semantic_results, 1):
            print(f"  {i}. Score: {result.score:.3f}")
            print(f"     {result.memory.content[:80]}...")
        
        # MODE 2: STRUCTURED - Graph traversal
        self.print_subsection("Mode 2: STRUCTURED (Graph Search)")
        print("Best for: Entity relationships, structured queries, exact matches")
        print("Note: Requires Cypher query knowledge\n")
        print("Example: Finding all memories related to 'Redis' entity")
        print("(This mode is typically used programmatically with Cypher queries)")
        
        # MODE 3: HYBRID - Combined approach
        self.print_subsection("Mode 3: HYBRID (Vector + Graph)")
        print("Best for: Complex queries needing both semantic and structural context")
        print("Query: 'database technologies'\n")
        
        hybrid_results = await self.orchestrator.search_memories(
            query="database technologies",
            mode=QueryMode.HYBRID,
            limit=3
        )
        
        print(f"Found {len(hybrid_results)} results:")
        for i, result in enumerate(hybrid_results, 1):
            print(f"  {i}. Combined Score: {result.score:.3f}")
            print(f"     Vector: {result.vector_score:.3f} | Graph: {result.graph_score:.3f}")
            print(f"     {result.memory.content[:80]}...")
        
        print("\n💡 KEY INSIGHT: Use SEMANTIC for most queries, HYBRID for complex context")
    
    async def demo_3_importance_and_decay(self):
        """Demonstrate importance scoring and temporal decay"""
        self.print_section("⏰ PART 3: Importance Scoring & Temporal Decay")
        
        print("Elefante uses importance scores (1-10) to prioritize memories:")
        print("  • 1-3: Low importance (routine information)")
        print("  • 4-6: Medium importance (useful context)")
        print("  • 7-9: High importance (critical information)")
        print("  • 10: Critical (never forget)\n")
        
        # Add memories with different importance
        print("Adding memories with different importance levels...\n")
        
        low_imp = await self.orchestrator.add_memory(
            content="User mentioned they had coffee this morning",
            memory_type=MemoryType.CONVERSATION,
            importance=2,
            tags=["casual", "conversation"]
        )
        print(f"  Low importance (2): {low_imp.id if low_imp else 'None'}")
        
        med_imp = await self.orchestrator.add_memory(
            content="User prefers dark mode in their IDE",
            memory_type=MemoryType.PREFERENCE,
            importance=6,
            tags=["preference", "ui"]
        )
        print(f"  Medium importance (6): {med_imp.id if med_imp else 'None'}")
        
        high_imp = await self.orchestrator.add_memory(
            content="User's production API key: NEVER share or log this value",
            memory_type=MemoryType.FACT,
            importance=10,
            tags=["security", "critical", "api-key"]
        )
        print(f"  Critical importance (10): {high_imp.id if high_imp else 'None'}")
        
        print("\n⚠️  LIMITATION: Temporal Decay")
        print("  • Memories naturally decay over time (except importance=10)")
        print("  • Older memories get lower scores in search results")
        print("  • This mimics human memory and prevents information overload")
        
        print("\n✅ WORKAROUND: Boost Important Memories")
        print("  • Set importance=10 for critical information")
        print("  • Use consolidation to merge related memories")
        print("  • Periodically refresh important context")
    
    async def demo_4_entity_relationships(self):
        """Demonstrate entity extraction and relationship building"""
        self.print_section("🕸️  PART 4: Entity Relationships & Knowledge Graph")
        
        print("Elefante automatically extracts entities and builds a knowledge graph:\n")
        
        # Add memories with entities
        print("Adding memories with entity relationships...\n")
        
        await self.orchestrator.add_memory(
            content="Django is a Python web framework that follows the MTV pattern and includes an ORM",
            memory_type=MemoryType.FACT,
            importance=8,
            tags=["django", "python", "framework"],
            entities=[
                {"name": "Django", "type": "technology"},
                {"name": "Python", "type": "language"},
                {"name": "MTV pattern", "type": "concept"},
                {"name": "ORM", "type": "feature"}
            ]
        )
        print("  ✅ Added: Django framework with 4 entities")
        
        await self.orchestrator.add_memory(
            content="Flask is a lightweight Python microframework that gives developers more control",
            memory_type=MemoryType.FACT,
            importance=8,
            tags=["flask", "python", "framework"],
            entities=[
                {"name": "Flask", "type": "technology"},
                {"name": "Python", "type": "language"}
            ]
        )
        print("  ✅ Added: Flask framework with 2 entities")
        
        print("\n💡 The graph now knows:")
        print("  • Django and Flask are both related to Python")
        print("  • They're both web frameworks")
        print("  • Django has MTV pattern and ORM features")
        
        print("\n⚠️  LIMITATION: Entity Disambiguation")
        print("  • 'Python' (language) vs 'Python' (snake) - same name, different meaning")
        print("  • System may conflate entities with identical names")
        
        print("\n✅ WORKAROUND: Use Specific Entity Types")
        print("  • Always provide entity type: {'name': 'Python', 'type': 'language'}")
        print("  • Use descriptive names: 'Python Programming Language'")
        print("  • Add context in tags: ['python-lang', 'programming']")
    
    async def demo_5_context_retrieval(self):
        """Demonstrate context retrieval for sessions and tasks"""
        self.print_section("🎯 PART 5: Context Retrieval & Session Management")
        
        print("Elefante can retrieve relevant context for sessions or tasks:\n")
        
        # Add session-specific memories
        session_id = "demo-coding-session-001"
        
        print(f"Creating memories for session: {session_id}\n")
        
        await self.orchestrator.add_memory(
            content="Started working on the user authentication feature",
            memory_type=MemoryType.CONVERSATION,
            importance=7,
            tags=["session", "authentication"],
            metadata={"session_id": session_id}
        )
        
        await self.orchestrator.add_memory(
            content="Decided to use bcrypt for password hashing with cost factor 12",
            memory_type=MemoryType.DECISION,
            importance=9,
            tags=["security", "authentication", "bcrypt"],
            metadata={"session_id": session_id}
        )
        
        await self.orchestrator.add_memory(
            content="TODO: Add rate limiting to login endpoint",
            memory_type=MemoryType.TASK,
            importance=8,
            tags=["todo", "security", "rate-limiting"],
            metadata={"session_id": session_id, "status": "pending"}
        )
        
        print("  ✅ Added 3 memories to session")
        
        print("\n⚠️  LIMITATION: Context Window Size")
        print("  • Retrieving too much context can overwhelm LLMs")
        print("  • Large sessions may have hundreds of memories")
        print("  • Need to balance completeness vs relevance")
        
        print("\n✅ WORKAROUND: Smart Context Filtering")
        print("  • Use importance threshold (only retrieve importance >= 7)")
        print("  • Limit by time window (last 24 hours)")
        print("  • Use semantic search to get most relevant memories")
        print("  • Consolidate related memories periodically")
    
    async def demo_6_limitations_and_workarounds(self):
        """Comprehensive overview of limitations and practical solutions"""
        self.print_section("⚠️  PART 6: Known Limitations & Practical Workarounds")
        
        limitations = [
            {
                "title": "1. Memory Duplication",
                "problem": "Similar content may be stored multiple times",
                "workaround": [
                    "Use deduplication before adding (check similarity)",
                    "Run periodic consolidation to merge similar memories",
                    "Use unique identifiers in metadata"
                ]
            },
            {
                "title": "2. Embedding Quality",
                "problem": "Short or ambiguous text produces poor embeddings",
                "workaround": [
                    "Add context: 'Redis' → 'Redis is a caching database'",
                    "Use tags to supplement semantic meaning",
                    "Combine with entity relationships for better retrieval"
                ]
            },
            {
                "title": "3. Graph Query Complexity",
                "problem": "Complex Cypher queries can be slow on large graphs",
                "workaround": [
                    "Use indexes on frequently queried properties",
                    "Limit traversal depth (MATCH ... WHERE depth <= 3)",
                    "Cache common query results"
                ]
            },
            {
                "title": "4. Temporal Decay Aggressiveness",
                "problem": "Important old memories may rank too low",
                "workaround": [
                    "Set importance=10 for timeless information",
                    "Periodically 'refresh' important memories",
                    "Use explicit date filters in queries"
                ]
            },
            {
                "title": "5. Entity Extraction Accuracy",
                "problem": "LLM may miss or misidentify entities",
                "workaround": [
                    "Explicitly provide entities in add_memory()",
                    "Review and correct entity relationships",
                    "Use consistent naming conventions"
                ]
            },
            {
                "title": "6. Cross-Session Context",
                "problem": "Hard to retrieve context across multiple sessions",
                "workaround": [
                    "Use project-level tags instead of session IDs",
                    "Create explicit 'summary' memories linking sessions",
                    "Use hybrid search with entity relationships"
                ]
            }
        ]
        
        for lim in limitations:
            print(f"\n{lim['title']}")
            print(f"  ❌ Problem: {lim['problem']}")
            print(f"  ✅ Workarounds:")
            for w in lim['workaround']:
                print(f"     • {w}")
    
    async def demo_7_best_practices(self):
        """Share production-ready best practices"""
        self.print_section("✨ PART 7: Best Practices for Production Use")
        
        practices = [
            {
                "category": "Memory Creation",
                "tips": [
                    "Always provide meaningful tags (3-5 per memory)",
                    "Set appropriate importance (be conservative, most should be 5-7)",
                    "Include entities explicitly for critical relationships",
                    "Add rich metadata (session_id, user_id, project_id)",
                    "Use descriptive content (avoid single words or fragments)"
                ]
            },
            {
                "category": "Search & Retrieval",
                "tips": [
                    "Start with SEMANTIC mode for most queries",
                    "Use HYBRID for complex, multi-faceted questions",
                    "Set reasonable limits (10-20 results max)",
                    "Filter by importance threshold for critical queries",
                    "Use time windows to focus on recent context"
                ]
            },
            {
                "category": "Maintenance",
                "tips": [
                    "Run consolidation weekly to merge similar memories",
                    "Archive or delete low-importance old memories",
                    "Monitor database sizes (ChromaDB and Kuzu)",
                    "Backup databases before major operations",
                    "Review entity relationships periodically"
                ]
            },
            {
                "category": "Performance",
                "tips": [
                    "Batch memory additions when possible",
                    "Use async operations (await) properly",
                    "Cache frequently accessed context",
                    "Index common query patterns in graph",
                    "Monitor embedding generation latency"
                ]
            },
            {
                "category": "Security",
                "tips": [
                    "Never store raw credentials (use references)",
                    "Mark sensitive memories with importance=10",
                    "Use encryption for sensitive content",
                    "Implement access control at application layer",
                    "Audit memory access patterns"
                ]
            }
        ]
        
        for practice in practices:
            print(f"\n📋 {practice['category']}")
            for tip in practice['tips']:
                print(f"   ✓ {tip}")
    
    async def demo_8_real_world_scenario(self):
        """Demonstrate a complete real-world workflow"""
        self.print_section("🌍 PART 8: Real-World Scenario - Code Review Session")
        
        print("Scenario: AI assistant helping with a code review\n")
        
        # Step 1: Store initial context
        print("Step 1: Store code review context")
        await self.orchestrator.add_memory(
            content="Reviewing pull request #342: Add user authentication with OAuth2",
            memory_type=MemoryType.CONVERSATION,
            importance=7,
            tags=["code-review", "pr-342", "oauth2"],
            metadata={"session_id": "review-342", "pr_number": 342}
        )
        print("  ✅ Stored PR context\n")
        
        # Step 2: Store findings
        print("Step 2: Store review findings")
        await self.orchestrator.add_memory(
            content="Security issue: OAuth2 state parameter not validated, vulnerable to CSRF attacks",
            memory_type=MemoryType.INSIGHT,
            importance=10,
            tags=["security", "vulnerability", "csrf", "oauth2"],
            entities=[
                {"name": "OAuth2", "type": "technology"},
                {"name": "CSRF", "type": "vulnerability"}
            ],
            metadata={"session_id": "review-342", "severity": "high"}
        )
        print("  ✅ Stored security finding\n")
        
        # Step 3: Store decision
        print("Step 3: Store architectural decision")
        await self.orchestrator.add_memory(
            content="Decided to use PyJWT library for token validation with RS256 algorithm",
            memory_type=MemoryType.DECISION,
            importance=9,
            tags=["architecture", "jwt", "security"],
            entities=[
                {"name": "PyJWT", "type": "library"},
                {"name": "RS256", "type": "algorithm"}
            ],
            metadata={"session_id": "review-342"}
        )
        print("  ✅ Stored decision\n")
        
        # Step 4: Create action items
        print("Step 4: Create action items")
        await self.orchestrator.add_memory(
            content="TODO: Add state parameter validation in OAuth2 callback handler",
            memory_type=MemoryType.TASK,
            importance=10,
            tags=["todo", "security", "oauth2"],
            metadata={"session_id": "review-342", "status": "pending", "assignee": "developer"}
        )
        print("  ✅ Stored action item\n")
        
        # Step 5: Retrieve context for follow-up
        print("Step 5: Later, retrieve context for follow-up discussion")
        print("Query: 'What security issues did we find in the OAuth implementation?'\n")
        
        results = await self.orchestrator.search_memories(
            query="What security issues did we find in the OAuth implementation?",
            mode=QueryMode.HYBRID,
            limit=5
        )
        
        print(f"Retrieved {len(results)} relevant memories:")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. [{result.memory.memory_type}] Score: {result.score:.3f}")
            print(f"     {result.memory.content[:100]}...")
            if result.memory.metadata:
                print(f"     Metadata: {result.memory.metadata}")
        
        print("\n💡 The AI assistant now has complete context to:")
        print("   • Recall the security vulnerability")
        print("   • Remember the architectural decision")
        print("   • Track the pending action item")
        print("   • Provide informed recommendations")
    
    async def run_all_demos(self):
        """Run all demonstration sections"""
        print("\n" + "="*70)
        print("  🐘 ELEFANTE COMPREHENSIVE DEMONSTRATION")
        print("  Understanding the Process, Limitations & Workarounds")
        print("="*70)
        
        try:
            await self.demo_1_memory_types()
            await self.demo_2_query_modes()
            await self.demo_3_importance_and_decay()
            await self.demo_4_entity_relationships()
            await self.demo_5_context_retrieval()
            await self.demo_6_limitations_and_workarounds()
            await self.demo_7_best_practices()
            await self.demo_8_real_world_scenario()
            
            self.print_section("🎉 DEMONSTRATION COMPLETE!")
            print("You now understand:")
            print("  ✓ Different memory types and when to use them")
            print("  ✓ Query modes (semantic, structured, hybrid)")
            print("  ✓ Importance scoring and temporal decay")
            print("  ✓ Entity relationships and knowledge graphs")
            print("  ✓ Context retrieval strategies")
            print("  ✓ Known limitations and practical workarounds")
            print("  ✓ Production-ready best practices")
            print("  ✓ Real-world application scenarios")
            print("\n🐘 Elefante is ready for your production use!")
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"\n❌ Error during demonstration: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run the comprehensive demonstration"""
    demo = ElefanteDemo()
    await demo.run_all_demos()


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
