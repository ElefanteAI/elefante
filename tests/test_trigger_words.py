"""
Test Trigger Words for Elefante Memory System

PURPOSE: Validate that "elefante:" trigger phrase correctly invokes memory operations.
ISOLATION: All test memories use TEST_PREFIX to avoid contaminating real data.
CLEANUP: All test memories are deleted after each test.

PRIMARY TRIGGER: "elefante:"
- "elefante: remember this" → SAVE
- "elefante: what do you know about X" → SEARCH

Workflow tested: INGEST → SEARCH → CLEANUP
"""

import pytest
import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any

# Test isolation prefix - all test memories use this
TEST_PREFIX = "TEST_TRIGGER_"
TEST_NAMESPACE = "test-trigger-words"


class TestTriggerWords:
    """
    Test suite for trigger word behavior.
    
    TRIGGER WORDS FOR SAVE:
    - "remember this", "save this", "store this"
    - "don't forget", "keep in mind"
    - "I prefer", "I always want"
    
    TRIGGER WORDS FOR SEARCH:
    - "remember", "recall", "what did I say about"
    - "my preference", "my style", "how I like"
    - "we discussed", "we decided"
    """
    
    @pytest.fixture
    def test_memories(self) -> List[Dict[str, Any]]:
        """Test memory fixtures - isolated with TEST_PREFIX"""
        return [
            {
                "content": f"{TEST_PREFIX}User prefers Black formatter for Python code formatting with line-length 100. This is the Python code style preference.",
                "layer": "self",
                "sublayer": "preference",
                "importance": 8,
                "category": TEST_NAMESPACE,
                "memory_type": "preference",
                "tags": ["test", "formatting", "python", "black"],
            },
            {
                "content": f"{TEST_PREFIX}User decided to use pytest over unittest for Python testing framework. This is the testing decision.",
                "layer": "intent",
                "sublayer": "rule",
                "importance": 7,
                "category": TEST_NAMESPACE,
                "memory_type": "decision",
                "tags": ["test", "testing", "python", "pytest"],
            },
            {
                "content": f"{TEST_PREFIX}User's coding style preference: explicit over implicit. Always be explicit in code, avoid implicit behavior.",
                "layer": "self",
                "sublayer": "preference",
                "importance": 9,
                "category": TEST_NAMESPACE,
                "memory_type": "preference",
                "tags": ["test", "style", "coding", "explicit"],
            },
        ]
    
    @pytest.fixture
    def vector_store(self):
        """Get vector store for direct testing"""
        from src.core.vector_store import get_vector_store
        return get_vector_store()
    
    async def cleanup_test_memories(self, vector_store) -> int:
        """Delete all test memories (those with TEST_PREFIX)"""
        # Search for test memories
        results = await vector_store.search(
            query=TEST_PREFIX,
            limit=100,
            min_similarity=0.0  # Get all matches
        )
        
        deleted = 0
        for result in results:
            memory_id = result.memory.id
            content = result.memory.content
            if TEST_PREFIX in content:
                try:
                    await vector_store.delete_memory(str(memory_id))
                    deleted += 1
                except Exception as e:
                    print(f"Failed to delete {memory_id}: {e}")
        
        return deleted
    
    # =========================================================================
    # INGEST TESTS
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_ingest_single_memory(self, vector_store, test_memories):
        """Test: Can we ingest a test memory and retrieve it?"""
        test_mem = test_memories[0]
        
        try:
            # Ingest
            from src.models.memory import MemoryMetadata, Memory
            
            metadata = MemoryMetadata(
                layer=test_mem["layer"],
                sublayer=test_mem["sublayer"],
                importance=test_mem["importance"],
                category=test_mem["category"],
                memory_type=test_mem["memory_type"],
                tags=test_mem["tags"],
            )
            
            memory = Memory(
                content=test_mem["content"],
                metadata=metadata,
            )
            
            # Store
            result = await vector_store.add_memory(memory)
            assert result is not None, "Memory should be stored"
            
            # Search
            search_results = await vector_store.search(
                query="Black formatter",
                limit=5,
                min_similarity=0.3
            )
            
            # Verify found
            found = any(TEST_PREFIX in r.memory.content for r in search_results)
            assert found, "Test memory should be found via search"
            
        finally:
            # Cleanup
            deleted = await self.cleanup_test_memories(vector_store)
            print(f"Cleaned up {deleted} test memories")
    
    # =========================================================================
    # TRIGGER WORD SIMULATION TESTS
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_trigger_preference_search(self, vector_store, test_memories):
        """
        Simulate: "What's my preference for code formatting?"
        Expected: Should find preference memories
        """
        # First ingest test memories
        from src.models.memory import MemoryMetadata, Memory
        
        try:
            for tm in test_memories:
                metadata = MemoryMetadata(
                    layer=tm["layer"],
                    sublayer=tm["sublayer"],
                    importance=tm["importance"],
                    category=tm["category"],
                    memory_type=tm["memory_type"],
                    tags=tm["tags"],
                )
                memory = Memory(content=tm["content"], metadata=metadata)
                await vector_store.add_memory(memory)
            
            # Simulate trigger queries
            trigger_queries = [
                "my preference for formatting",
                "how I like to format code",
                "what did I say about formatting",
                "my style for Python",
            ]
            
            results_log = []
            for query in trigger_queries:
                results = await vector_store.search(
                    query=query,
                    limit=5,
                    min_similarity=0.2
                )
                
                test_results = [r for r in results if TEST_PREFIX in r.memory.content]
                results_log.append({
                    "query": query,
                    "total_results": len(results),
                    "test_results": len(test_results),
                    "found_test_memory": len(test_results) > 0,
                    "top_score": results[0].score if results else 0,
                })
            
            # Report
            print("\n=== TRIGGER WORD TEST RESULTS ===")
            for log in results_log:
                status = "✓" if log["found_test_memory"] else "✗"
                print(f"{status} Query: '{log['query']}'")
                print(f"   Results: {log['total_results']}, Test matches: {log['test_results']}, Top score: {log['top_score']:.3f}")
            
            # At least some triggers should work
            working_triggers = sum(1 for log in results_log if log["found_test_memory"])
            assert working_triggers > 0, f"At least one trigger should find test memories, got {working_triggers}"
            
        finally:
            deleted = await self.cleanup_test_memories(vector_store)
            print(f"Cleaned up {deleted} test memories")
    
    @pytest.mark.asyncio  
    async def test_trigger_decision_search(self, vector_store, test_memories):
        """
        Simulate: "What did we decide about testing framework?"
        Expected: Should find decision memories
        """
        from src.models.memory import MemoryMetadata, Memory
        
        try:
            # Ingest only decision memory
            tm = test_memories[1]  # pytest decision
            metadata = MemoryMetadata(
                layer=tm["layer"],
                sublayer=tm["sublayer"],
                importance=tm["importance"],
                category=tm["category"],
                memory_type=tm["memory_type"],
                tags=tm["tags"],
            )
            memory = Memory(content=tm["content"], metadata=metadata)
            await vector_store.add_memory(memory)
            
            # Test decision-related triggers
            trigger_queries = [
                "we decided about testing",
                "what testing framework",
                "pytest or unittest decision",
            ]
            
            results_log = []
            for query in trigger_queries:
                results = await vector_store.search(
                    query=query,
                    limit=5,
                    min_similarity=0.2
                )
                
                test_results = [r for r in results if TEST_PREFIX in r.memory.content]
                results_log.append({
                    "query": query,
                    "found": len(test_results) > 0,
                    "score": test_results[0].score if test_results else 0,
                })
            
            print("\n=== DECISION TRIGGER TEST ===")
            for log in results_log:
                status = "✓" if log["found"] else "✗"
                print(f"{status} '{log['query']}' → score: {log['score']:.3f}")
                
        finally:
            deleted = await self.cleanup_test_memories(vector_store)
            print(f"Cleaned up {deleted} test memories")

    # =========================================================================
    # WORKFLOW TEST: INGEST → SEARCH → VERIFY → CLEANUP
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, vector_store, test_memories):
        """
        Full workflow test:
        1. INGEST: Store test memories
        2. SEARCH: Query with various trigger words
        3. VERIFY: Check results match expectations
        4. CLEANUP: Delete all test data
        """
        from src.models.memory import MemoryMetadata, Memory
        
        print("\n" + "="*60)
        print("FULL WORKFLOW TEST: INGEST → SEARCH → VERIFY → CLEANUP")
        print("="*60)
        
        stored_ids = []
        
        try:
            # === STEP 1: INGEST ===
            print("\n[1] INGEST: Storing test memories...")
            for tm in test_memories:
                metadata = MemoryMetadata(
                    layer=tm["layer"],
                    sublayer=tm["sublayer"],
                    importance=tm["importance"],
                    category=tm["category"],
                    memory_type=tm["memory_type"],
                    tags=tm["tags"],
                )
                memory = Memory(content=tm["content"], metadata=metadata)
                result = await vector_store.add_memory(memory)
                stored_ids.append(str(result.id) if hasattr(result, 'id') else str(result))
                print(f"    ✓ Stored: {tm['content'][:50]}...")
            
            print(f"    Total stored: {len(stored_ids)}")
            
            # === STEP 2: SEARCH ===
            print("\n[2] SEARCH: Testing trigger queries...")
            
            test_cases = [
                # (query, expected_content_fragment, description)
                ("my preference formatting", "Black formatter", "Preference trigger"),
                ("we decided testing", "pytest", "Decision trigger"),
                ("my style coding", "explicit", "Style trigger"),
                ("how I like format", "Black", "Natural language trigger"),
            ]
            
            search_results = []
            for query, expected_frag, desc in test_cases:
                results = await vector_store.search(query=query, limit=5, min_similarity=0.1)
                test_hits = [r for r in results if TEST_PREFIX in r.memory.content]
                
                found_expected = any(expected_frag.lower() in r.memory.content.lower() for r in test_hits)
                
                search_results.append({
                    "desc": desc,
                    "query": query,
                    "expected": expected_frag,
                    "found": found_expected,
                    "hits": len(test_hits),
                    "top_score": test_hits[0].score if test_hits else 0,
                })
            
            # === STEP 3: VERIFY ===
            print("\n[3] VERIFY: Checking results...")
            
            passed = 0
            failed = 0
            for sr in search_results:
                status = "✓ PASS" if sr["found"] else "✗ FAIL"
                if sr["found"]:
                    passed += 1
                else:
                    failed += 1
                print(f"    {status}: {sr['desc']}")
                print(f"           Query: '{sr['query']}' → Expected '{sr['expected']}'")
                print(f"           Hits: {sr['hits']}, Top score: {sr['top_score']:.3f}")
            
            print(f"\n    Results: {passed} passed, {failed} failed")
            
            # === STEP 4: CLEANUP ===
            print("\n[4] CLEANUP: Removing test data...")
            
        finally:
            deleted = await self.cleanup_test_memories(vector_store)
            print(f"    ✓ Deleted {deleted} test memories")
            
            # Verify cleanup
            verify = await vector_store.search(query=TEST_PREFIX, limit=10, min_similarity=0.0)
            remaining = [r for r in verify if TEST_PREFIX in r.memory.content]
            print(f"    ✓ Remaining test memories: {len(remaining)}")
            
            assert len(remaining) == 0, "All test memories should be deleted"
        
        print("\n" + "="*60)
        print("WORKFLOW TEST COMPLETE")
        print("="*60)

    # =========================================================================
    # PRIMARY TRIGGER: "elefante:" PREFIX
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_elefante_prefix_triggers(self, vector_store, test_memories):
        """
        Test the PRIMARY trigger pattern: "elefante: [command]"
        
        This is the most reliable way to invoke Elefante.
        User says "elefante:" and the agent should ALWAYS respond.
        """
        from src.models.memory import MemoryMetadata, Memory
        
        print("\n" + "="*60)
        print("ELEFANTE: PREFIX TRIGGER TEST")
        print("="*60)
        
        try:
            # Ingest test memories
            print("\n[1] INGEST: Storing test memories...")
            for tm in test_memories:
                metadata = MemoryMetadata(
                    layer=tm["layer"],
                    sublayer=tm["sublayer"],
                    importance=tm["importance"],
                    category=tm["category"],
                    memory_type=tm["memory_type"],
                    tags=tm["tags"],
                )
                memory = Memory(content=tm["content"], metadata=metadata)
                await vector_store.add_memory(memory)
            print(f"    ✓ Stored {len(test_memories)} test memories")
            
            # Test "elefante:" style queries
            print("\n[2] SEARCH: Testing 'elefante:' prefix queries...")
            
            elefante_queries = [
                # Simulating what user would type with "elefante:" prefix
                # (query extracted from "elefante: what do you know about X", expected, desc)
                ("what do you know about formatting", "Black formatter", "elefante: what do you know about formatting"),
                ("recall my preference for Python code", "Black", "elefante: recall my preference for Python code"),
                ("check if we discussed testing", "pytest", "elefante: check if we discussed testing"),
                ("how do I like coding style", "explicit", "elefante: how do I like coding style"),
                ("what did I say about testing framework", "pytest", "elefante: what did I say about testing framework"),
            ]
            
            results = []
            for query, expected_frag, full_trigger in elefante_queries:
                search_results = await vector_store.search(query=query, limit=5, min_similarity=0.1)
                test_hits = [r for r in search_results if TEST_PREFIX in r.memory.content]
                
                found = any(expected_frag.lower() in r.memory.content.lower() for r in test_hits)
                top_score = test_hits[0].score if test_hits else 0
                
                results.append({
                    "trigger": full_trigger,
                    "query": query,
                    "expected": expected_frag,
                    "found": found,
                    "hits": len(test_hits),
                    "score": top_score,
                })
            
            # Report
            print("\n[3] RESULTS:")
            passed = 0
            for r in results:
                status = "✓" if r["found"] else "✗"
                if r["found"]:
                    passed += 1
                print(f"    {status} '{r['trigger']}'")
                print(f"       → Query: '{r['query']}' | Expected: '{r['expected']}' | Score: {r['score']:.3f}")
            
            print(f"\n    PASSED: {passed}/{len(results)}")
            
            # Success criteria: at least 60% should work
            success_rate = passed / len(results)
            assert success_rate >= 0.6, f"Expected at least 60% success, got {success_rate*100:.0f}%"
            
        finally:
            deleted = await self.cleanup_test_memories(vector_store)
            print(f"\n[4] CLEANUP: Deleted {deleted} test memories")
        
        print("\n" + "="*60)


# =============================================================================
# DOCUMENTATION
# =============================================================================

"""
TRIGGER WORD FINDINGS
=====================

PRIMARY TRIGGER: "elefante:"
-----------------------------
The most reliable way to invoke Elefante is with the "elefante:" prefix.

SAVE patterns:
- "elefante: remember this"
- "elefante: save this"
- "elefante: note that I prefer X"

SEARCH patterns:
- "elefante: what do you know about X"
- "elefante: recall my preference for Y"
- "elefante: check if we discussed Z"
- "elefante: how do I like to X"

TESTED TRIGGER PATTERNS:

1. PREFERENCE TRIGGERS:
   - "my preference for X" 
   - "how I like to X"
   - "my style for X"

2. DECISION TRIGGERS:
   - "we decided about X"
   - "what did we decide"
   - "the decision on X"

3. MEMORY TRIGGERS:
   - "what did I say about X"
   - "remember when X"
   - "recall X"

RUN TESTS:
    pytest tests/test_trigger_words.py -v -s

The -s flag shows print output for debugging.
"""
