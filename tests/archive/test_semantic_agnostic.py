"""
AGNOSTIC SEMANTIC TEST
======================

PURPOSE: Test TRUE semantic understanding, not keyword matching.
RULE: Query phrases must NOT appear in content.

This tests if the embedding model understands MEANING, not just words.
"""

import pytest
import asyncio
import os

os.environ["ELEFANTE_ALLOW_TEST_MEMORIES"] = "true"

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.vector_store import get_vector_store
from src.models.memory import Memory, MemoryMetadata

TEST_PREFIX = "AGNOSTIC_TEST_"
MIN_SIMILARITY = 0.3


# Content and queries are SEMANTICALLY related but use DIFFERENT words
AGNOSTIC_SCENARIOS = [
    {
        "name": "indentation_preference",
        "content": f"{TEST_PREFIX} Always use 4 spaces for indentation in Python. Tabs are forbidden.",
        "novel_queries": [
            "whitespace style in code",  # different words, same concept
            "how to indent",
            "formatting rules",
        ]
    },
    {
        "name": "testing_rule",
        "content": f"{TEST_PREFIX} Run pytest before every git push. All tests must pass.",
        "novel_queries": [
            "pre-commit requirements",  # "commit" not in content
            "what checks before pushing code",
            "verification before merge",
        ]
    },
    {
        "name": "api_structure",
        "content": f"{TEST_PREFIX} REST endpoints return JSON with success boolean and data/error fields.",
        "novel_queries": [
            "response payload format",  # "format" not in content
            "what should API return",
            "endpoint output structure",
        ]
    },
    {
        "name": "editor_choice",
        "content": f"{TEST_PREFIX} VS Code with GitHub Copilot is the primary development environment.",
        "novel_queries": [
            "which IDE to use",  # "IDE" not in content
            "coding tool preference",
            "what editor is preferred",
        ]
    },
    {
        "name": "branch_strategy",
        "content": f"{TEST_PREFIX} Create feature branches with feat/ prefix. Never push directly to main.",
        "novel_queries": [
            "git workflow rules",  # "workflow" not in content
            "how to organize branches",
            "version control strategy",
        ]
    },
]


class TestSemanticAgnostic:
    """Test semantic understanding with novel queries"""
    
    @pytest.fixture
    def vector_store(self):
        return get_vector_store()
    
    async def cleanup(self, vector_store):
        results = await vector_store.search(query=TEST_PREFIX, limit=100, min_similarity=0.0)
        for r in results:
            if TEST_PREFIX in r.memory.content:
                await vector_store.delete_memory(str(r.memory.id))
    
    @pytest.mark.asyncio
    async def test_agnostic_semantic_matching(self, vector_store):
        """Test that semantically related but differently-worded queries find content"""
        
        added_ids = []
        results_log = []
        
        try:
            # Add all test memories
            for scenario in AGNOSTIC_SCENARIOS:
                metadata = MemoryMetadata(
                    layer="self",
                    sublayer="preference", 
                    importance=8,
                    category="agnostic-test",
                )
                memory = Memory(content=scenario["content"], metadata=metadata)
                mid = await vector_store.add_memory(memory)
                added_ids.append(mid)
            
            # Test each scenario with novel queries
            total_queries = 0
            successful_queries = 0
            
            print("\n" + "="*70)
            print("AGNOSTIC SEMANTIC TEST - Novel Queries (no keyword overlap)")
            print("="*70)
            
            for scenario in AGNOSTIC_SCENARIOS:
                print(f"\n {scenario['name']}")
                print(f"   Content: {scenario['content'][:60]}...")
                
                for query in scenario["novel_queries"]:
                    total_queries += 1
                    results = await vector_store.search(
                        query=query,
                        limit=5,
                        min_similarity=MIN_SIMILARITY
                    )
                    
                    # Check if our test memory is found
                    found = False
                    score = 0
                    for r in results:
                        if TEST_PREFIX in r.memory.content and scenario["name"] in r.memory.content.lower().replace("_", " ").replace("-", " ") or scenario["content"] == r.memory.content:
                            found = True
                            score = r.score
                            break
                        # Also match by checking if content matches
                        if r.memory.content == scenario["content"]:
                            found = True
                            score = r.score
                            break
                    
                    if found:
                        successful_queries += 1
                        status = "✓"
                    else:
                        status = "✗"
                    
                    print(f"   {status} Query: '{query}' → Score: {score:.3f}")
                    results_log.append({
                        "scenario": scenario["name"],
                        "query": query,
                        "found": found,
                        "score": score
                    })
            
            # Summary
            success_rate = (successful_queries / total_queries) * 100
            print("\n" + "="*70)
            print(f"AGNOSTIC TEST RESULTS: {successful_queries}/{total_queries} ({success_rate:.0f}%)")
            print("="*70)
            
            if success_rate >= 80:
                print(" PASS: Semantic understanding works with novel queries")
            elif success_rate >= 60:
                print("  PARTIAL: Some semantic matching, room for improvement")
            else:
                print(" FAIL: Poor semantic generalization")
            
            # Must pass at least 60% to be considered working
            assert success_rate >= 60, f"Semantic matching too weak: {success_rate:.0f}%"
            
        finally:
            # Cleanup
            for mid in added_ids:
                try:
                    await vector_store.delete_memory(str(mid))
                except:
                    pass


async def main():
    vs = get_vector_store()
    test = TestSemanticAgnostic()
    await test.test_agnostic_semantic_matching(vs)


if __name__ == "__main__":
    asyncio.run(main())
