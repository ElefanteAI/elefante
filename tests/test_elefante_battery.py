"""
ELEFANTE 10X BATTERY TEST
=========================

PURPOSE: Verify that Elefante triggers reliably in "normal" usage scenarios.
Tests ADD (ingestion) and RETRIEVAL (search) patterns with isolated test data.

TEST ISOLATION:
- All test memories use prefix: TEST_BATTERY_
- All test content contains marker: [BATTERY_TEST]
- Automatic cleanup after tests
- Safe to run without corrupting real data
- Uses ELEFANTE_ALLOW_TEST_MEMORIES=true to bypass test memory guardrails

SUCCESS CRITERIA:
- 100% of ADD operations must succeed
- 100% of RETRIEVAL operations must find relevant data (score > 0.3)
- All test data must be purged after completion
"""

import pytest
import asyncio
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import sys

# Enable test memories
os.environ["ELEFANTE_ALLOW_TEST_MEMORIES"] = "true"

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.vector_store import get_vector_store
from src.models.memory import Memory, MemoryMetadata, MemoryType, MemoryStatus

# =============================================================================
# TEST CONFIGURATION
# =============================================================================

TEST_PREFIX = "TEST_BATTERY_"
TEST_MARKER = "[BATTERY_TEST]"
MIN_SIMILARITY = 0.3  # Minimum acceptable similarity score
CLEANUP_ENABLED = True  # Set False to inspect test data after run


@dataclass
class TestScenario:
    """Defines a single test scenario"""
    name: str
    add_content: str
    search_queries: List[str]  # Multiple queries to try
    expected_keywords: List[str]  # Keywords that should match
    layer: str
    sublayer: str
    category: str
    importance: int = 7


@dataclass 
class TestResult:
    """Result of a single test"""
    scenario_name: str
    add_success: bool
    add_time_ms: float
    memory_id: str
    search_results: List[Dict[str, Any]]
    search_success: bool
    best_score: float
    search_time_ms: float
    error: str = None


# =============================================================================
# 10 TEST SCENARIOS - Simulating Real Usage Patterns
# =============================================================================

TEST_SCENARIOS = [
    # 1. User preference (coding style)
    TestScenario(
        name="user_preference_coding_style",
        add_content=f"{TEST_MARKER} User prefers 4-space indentation in Python code. Always use spaces, never tabs. This is a strict formatting preference for all Python files.",
        search_queries=[
            "what indentation does the user prefer",
            "Python code formatting preference",
            "spaces or tabs preference",
            "how should I format Python code"
        ],
        expected_keywords=["indentation", "spaces", "Python", "formatting"],
        layer="self",
        sublayer="preference",
        category="coding-preferences",
        importance=8
    ),
    
    # 2. Project decision
    TestScenario(
        name="project_decision_architecture",
        add_content=f"{TEST_MARKER} Decision: Use FastAPI for all REST endpoints. Django was considered but rejected due to complexity. FastAPI provides async support and automatic OpenAPI docs.",
        search_queries=[
            "what framework for REST API",
            "FastAPI decision",
            "why not Django",
            "API framework choice"
        ],
        expected_keywords=["FastAPI", "REST", "decision", "Django"],
        layer="intent",
        sublayer="rule",
        category="architecture-decisions",
        importance=9
    ),
    
    # 3. Error solution (debugging)
    TestScenario(
        name="error_solution_chromadb",
        add_content=f"{TEST_MARKER} Solution: ChromaDB 'Collection not found' error is fixed by ensuring init_databases.py runs before server start. The collection 'elefante_memories' must exist.",
        search_queries=[
            "ChromaDB collection not found error",
            "how to fix database error",
            "elefante_memories collection",
            "init databases fix"
        ],
        expected_keywords=["ChromaDB", "collection", "error", "init"],
        layer="world",
        sublayer="fact",
        category="debugging",
        importance=8
    ),
    
    # 4. Tool preference
    TestScenario(
        name="tool_preference_editor",
        add_content=f"{TEST_MARKER} User prefers VS Code with Copilot for all development. PyCharm is acceptable but VS Code is primary. Always suggest VS Code extensions first.",
        search_queries=[
            "what editor does user prefer",
            "VS Code or PyCharm",
            "IDE preference",
            "development environment"
        ],
        expected_keywords=["VS Code", "editor", "prefer", "Copilot"],
        layer="self",
        sublayer="preference",
        category="tool-preferences",
        importance=7
    ),
    
    # 5. Naming convention
    TestScenario(
        name="naming_convention_functions",
        add_content=f"{TEST_MARKER} Convention: All Python functions use snake_case. Class names use PascalCase. Constants use UPPER_SNAKE_CASE. No exceptions to this rule.",
        search_queries=[
            "function naming convention",
            "how to name Python functions",
            "snake_case or camelCase",
            "naming style preference"
        ],
        expected_keywords=["snake_case", "naming", "convention", "Python"],
        layer="intent",
        sublayer="rule",
        category="coding-standards",
        importance=8
    ),
    
    # 6. Workflow rule
    TestScenario(
        name="workflow_rule_testing",
        add_content=f"{TEST_MARKER} Rule: Always run pytest before committing. Never push code without tests passing. Use pytest -v for verbose output. This is mandatory for all commits.",
        search_queries=[
            "what to do before commit",
            "testing requirement",
            "pytest before push",
            "commit workflow"
        ],
        expected_keywords=["pytest", "commit", "testing", "mandatory"],
        layer="intent",
        sublayer="rule",
        category="workflow-rules",
        importance=9
    ),
    
    # 7. API pattern
    TestScenario(
        name="api_pattern_error_handling",
        add_content=f"{TEST_MARKER} Pattern: All API endpoints must return JSON with 'success' boolean and 'data' or 'error' field. Use HTTP 200 for success, 400 for client errors, 500 for server errors.",
        search_queries=[
            "API response format",
            "how to return errors in API",
            "JSON response structure",
            "API error handling pattern"
        ],
        expected_keywords=["API", "JSON", "error", "response"],
        layer="intent",
        sublayer="rule",
        category="api-patterns",
        importance=8
    ),
    
    # 8. Documentation preference
    TestScenario(
        name="documentation_preference_docstrings",
        add_content=f"{TEST_MARKER} Preference: Use Google-style docstrings for all Python functions. Include Args, Returns, and Raises sections. Example format must be followed strictly.",
        search_queries=[
            "docstring format preference",
            "how to document functions",
            "Google style docstrings",
            "documentation format"
        ],
        expected_keywords=["docstrings", "Google", "documentation", "Args"],
        layer="self",
        sublayer="preference",
        category="documentation",
        importance=7
    ),
    
    # 9. Git workflow
    TestScenario(
        name="git_workflow_branches",
        add_content=f"{TEST_MARKER} Git workflow: Use feature branches named 'feat/description'. Never commit directly to main. Create PR for all changes. Squash commits on merge.",
        search_queries=[
            "git branch naming",
            "how to create feature branch",
            "commit to main allowed?",
            "PR workflow"
        ],
        expected_keywords=["branch", "feature", "PR", "main"],
        layer="intent",
        sublayer="rule",
        category="git-workflow",
        importance=8
    ),
    
    # 10. Performance rule
    TestScenario(
        name="performance_rule_queries",
        add_content=f"{TEST_MARKER} Performance rule: Database queries must complete in under 100ms. If slower, add index or optimize query. Log all queries taking over 50ms for review.",
        search_queries=[
            "database query performance",
            "query timeout limit",
            "how fast should queries be",
            "performance requirements"
        ],
        expected_keywords=["query", "100ms", "performance", "database"],
        layer="intent",
        sublayer="rule",
        category="performance",
        importance=8
    ),
]


# =============================================================================
# TEST INFRASTRUCTURE
# =============================================================================

class ElefanteBatteryTest:
    """Test harness for Elefante battery tests"""
    
    def __init__(self):
        self.vector_store = None
        self.added_memory_ids: List[str] = []
        self.results: List[TestResult] = []
        
    async def setup(self):
        """Initialize test environment"""
        print("\n" + "="*70)
        print("ELEFANTE 10X BATTERY TEST")
        print("="*70)
        print(f"Test prefix: {TEST_PREFIX}")
        print(f"Test marker: {TEST_MARKER}")
        print(f"Min similarity: {MIN_SIMILARITY}")
        print(f"Cleanup enabled: {CLEANUP_ENABLED}")
        print("="*70 + "\n")
        
        self.vector_store = get_vector_store()
        
    async def cleanup(self):
        """Remove all test data"""
        if not CLEANUP_ENABLED:
            print("\n⚠️  CLEANUP DISABLED - Test data preserved for inspection")
            return
            
        print("\n" + "-"*50)
        print("CLEANUP: Removing test data...")
        
        deleted_count = 0
        for memory_id in self.added_memory_ids:
            try:
                await self.vector_store.delete_memory(memory_id)
                deleted_count += 1
            except Exception as e:
                print(f"  ⚠️  Failed to delete {memory_id}: {e}")
                
        print(f"  ✓ Deleted {deleted_count}/{len(self.added_memory_ids)} test memories")
        print("-"*50)
        
    async def run_single_scenario(self, scenario: TestScenario) -> TestResult:
        """Run a single test scenario"""
        print(f"\n📋 Testing: {scenario.name}")
        print(f"   Category: {scenario.category}")
        
        result = TestResult(
            scenario_name=scenario.name,
            add_success=False,
            add_time_ms=0,
            memory_id="",
            search_results=[],
            search_success=False,
            best_score=0,
            search_time_ms=0
        )
        
        # STEP 1: ADD MEMORY (using vector_store directly with Memory object)
        try:
            start_time = time.time()
            
            # Create Memory object with proper metadata
            metadata = MemoryMetadata(
                layer=scenario.layer,
                sublayer=scenario.sublayer,
                importance=scenario.importance,
                category=scenario.category,
                memory_type="preference" if "preference" in scenario.category.lower() else "fact",
                tags=[TEST_PREFIX.strip("_"), "battery_test"],
            )
            
            memory = Memory(
                content=scenario.add_content,
                metadata=metadata,
            )
            
            memory_id = await self.vector_store.add_memory(memory)
            end_time = time.time()
            
            result.add_time_ms = (end_time - start_time) * 1000
            result.memory_id = str(memory_id)
            result.add_success = True
            self.added_memory_ids.append(str(memory_id))
            
            print(f"   ✓ ADD: Success ({result.add_time_ms:.1f}ms)")
            
        except Exception as e:
            result.error = f"ADD failed: {e}"
            print(f"   ✗ ADD: FAILED - {e}")
            return result
            
        # STEP 2: SEARCH (try all queries, take best result)
        best_score = 0
        best_results = []
        total_search_time = 0
        
        for query in scenario.search_queries:
            try:
                start_time = time.time()
                search_results = await self.vector_store.search(
                    query=query,
                    limit=5,
                    min_similarity=MIN_SIMILARITY
                )
                end_time = time.time()
                total_search_time += (end_time - start_time) * 1000
                
                # Check if our test memory is in results
                for sr in search_results:
                    if TEST_MARKER in sr.memory.content:
                        if sr.score > best_score:
                            best_score = sr.score
                            best_results = [{"query": query, "score": sr.score, "content_preview": sr.memory.content[:100]}]
                            
            except Exception as e:
                print(f"   ⚠️  Search query failed: {query} - {e}")
                
        result.search_time_ms = total_search_time / len(scenario.search_queries) if scenario.search_queries else 0
        result.best_score = best_score
        result.search_results = best_results
        result.search_success = best_score >= MIN_SIMILARITY
        
        if result.search_success:
            print(f"   ✓ SEARCH: Found (best score: {best_score:.3f}, avg {result.search_time_ms:.1f}ms)")
        else:
            print(f"   ✗ SEARCH: FAILED (best score: {best_score:.3f} < {MIN_SIMILARITY})")
            
        return result
        
    async def run_all_scenarios(self) -> List[TestResult]:
        """Run all 10 test scenarios"""
        print("\n" + "="*70)
        print("RUNNING 10 TEST SCENARIOS")
        print("="*70)
        
        for i, scenario in enumerate(TEST_SCENARIOS, 1):
            print(f"\n[{i}/10] ", end="")
            result = await self.run_single_scenario(scenario)
            self.results.append(result)
            
        return self.results
        
    def print_summary(self):
        """Print test summary with pass/fail counts"""
        print("\n" + "="*70)
        print("TEST RESULTS SUMMARY")
        print("="*70)
        
        add_successes = sum(1 for r in self.results if r.add_success)
        search_successes = sum(1 for r in self.results if r.search_success)
        total = len(self.results)
        
        print(f"\n{'Scenario':<35} {'ADD':^8} {'SEARCH':^8} {'Score':^8}")
        print("-"*70)
        
        for r in self.results:
            add_status = "✓" if r.add_success else "✗"
            search_status = "✓" if r.search_success else "✗"
            score = f"{r.best_score:.3f}" if r.best_score > 0 else "N/A"
            print(f"{r.scenario_name:<35} {add_status:^8} {search_status:^8} {score:^8}")
            
        print("-"*70)
        print(f"\n📊 ADD SUCCESS:    {add_successes}/{total} ({100*add_successes/total:.0f}%)")
        print(f"📊 SEARCH SUCCESS: {search_successes}/{total} ({100*search_successes/total:.0f}%)")
        
        # Calculate average scores
        scores = [r.best_score for r in self.results if r.best_score > 0]
        if scores:
            print(f"📊 AVG SCORE:      {sum(scores)/len(scores):.3f}")
        
        # Overall verdict
        print("\n" + "="*70)
        if add_successes == total and search_successes == total:
            print("🎉 VERDICT: ALL TESTS PASSED (100%)")
            print("   Elefante triggers reliably in normal usage scenarios!")
        elif search_successes >= total * 0.8:
            print(f"⚠️  VERDICT: MOSTLY PASSING ({100*search_successes/total:.0f}%)")
            print("   Some scenarios need tuning but core functionality works.")
        else:
            print(f"❌ VERDICT: FAILING ({100*search_successes/total:.0f}%)")
            print("   MCP needs fixes - retrieval not reliable enough!")
        print("="*70)
        
        # List failures for debugging
        failures = [r for r in self.results if not r.search_success]
        if failures:
            print("\n🔍 FAILED SCENARIOS (need investigation):")
            for r in failures:
                print(f"   - {r.scenario_name}: best_score={r.best_score:.3f}")
                
        return add_successes == total and search_successes == total


# =============================================================================
# PYTEST INTEGRATION
# =============================================================================

class TestElefanteBattery:
    """Pytest wrapper for battery tests"""
    
    @pytest.fixture
    def battery(self):
        return ElefanteBatteryTest()
        
    @pytest.mark.asyncio
    async def test_full_battery(self, battery):
        """Run complete 10x battery test"""
        await battery.setup()
        try:
            await battery.run_all_scenarios()
            battery.print_summary()
            
            # Assert all tests passed
            add_successes = sum(1 for r in battery.results if r.add_success)
            search_successes = sum(1 for r in battery.results if r.search_success)
            
            assert add_successes == 10, f"ADD failed: {add_successes}/10"
            assert search_successes == 10, f"SEARCH failed: {search_successes}/10"
            
        finally:
            await battery.cleanup()


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

async def main():
    """Run battery test standalone"""
    battery = ElefanteBatteryTest()
    await battery.setup()
    
    try:
        await battery.run_all_scenarios()
        all_passed = battery.print_summary()
        return 0 if all_passed else 1
    finally:
        await battery.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
