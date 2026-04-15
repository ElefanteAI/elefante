# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_integration_smoke.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : End-to-end integration smoke test (10x battery) — exercises memory
#           CRUD, search, graph, and directive operations in sequence.
# RUN     : pytest tests/test_integration_smoke.py -v
# WHEN    : Before release; after changes to orchestrator.py or server.py that
#           span multiple operation types.
# ─────────────────────────────────────────────────────────────────────────────
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
import atexit
import asyncio
import shutil
import tempfile
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import sys

# Ensure src is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.vector_store import VectorStore
from src.models.memory import Memory, MemoryMetadata, MemoryType, MemoryStatus

# =============================================================================
# TEST CONFIGURATION
# =============================================================================

TEST_PREFIX = "TEST_BATTERY_"
TEST_MARKER = "[BATTERY_TEST]"
MIN_SIMILARITY = 0.3  # Minimum acceptable similarity score
CLEANUP_ENABLED = True  # Set False to inspect test data after run


@dataclass
class BatteryScenario:
    """Defines a single test scenario"""
    name: str
    add_content: str
    search_queries: List[str]  # Multiple queries to try
    expected_keywords: List[str]  # Keywords that should match
    category: str


@dataclass 
class BatteryResult:
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
    BatteryScenario(
        name="user_preference_coding_style",
        add_content=f"{TEST_MARKER} User prefers 4-space indentation in Python code. Always use spaces, never tabs. This is a strict formatting preference for all Python files.",
        search_queries=[
            "what indentation does the user prefer",
            "Python code formatting preference",
            "spaces or tabs preference",
            "how should I format Python code"
        ],
        expected_keywords=["indentation", "spaces", "Python", "formatting"],
        category="coding-preferences",
    ),
    
    # 2. Project decision
    BatteryScenario(
        name="project_decision_architecture",
        add_content=f"{TEST_MARKER} Decision: Use FastAPI for all REST endpoints. Django was considered but rejected due to complexity. FastAPI provides async support and automatic OpenAPI docs.",
        search_queries=[
            "what framework for REST API",
            "FastAPI decision",
            "why not Django",
            "API framework choice"
        ],
        expected_keywords=["FastAPI", "REST", "decision", "Django"],
        category="architecture-decisions",
    ),
    
    # 3. Error solution (debugging)
    BatteryScenario(
        name="error_solution_chromadb",
        add_content=f"{TEST_MARKER} Solution: ChromaDB 'Collection not found' error is fixed by ensuring init_databases.py runs before server start. The collection 'elefante_memories' must exist.",
        search_queries=[
            "ChromaDB collection not found error",
            "how to fix database error",
            "elefante_memories collection",
            "init databases fix"
        ],
        expected_keywords=["ChromaDB", "collection", "error", "init"],
        category="debugging",
    ),
    
    # 4. Tool preference
    BatteryScenario(
        name="tool_preference_editor",
        add_content=f"{TEST_MARKER} User prefers VS Code with Copilot for all development. PyCharm is acceptable but VS Code is primary. Always suggest the MCP-native path first.",
        search_queries=[
            "what editor does user prefer",
            "VS Code or PyCharm",
            "IDE preference",
            "development environment"
        ],
        expected_keywords=["VS Code", "editor", "prefer", "Copilot"],
        category="tool-preferences",
    ),
    
    # 5. Naming convention
    BatteryScenario(
        name="naming_convention_functions",
        add_content=f"{TEST_MARKER} Convention: All Python functions use snake_case. Class names use PascalCase. Constants use UPPER_SNAKE_CASE. No exceptions to this rule.",
        search_queries=[
            "function naming convention",
            "how to name Python functions",
            "snake_case or camelCase",
            "naming style preference"
        ],
        expected_keywords=["snake_case", "naming", "convention", "Python"],
        category="coding-standards",
    ),
    
    # 6. Workflow rule
    BatteryScenario(
        name="workflow_rule_testing",
        add_content=f"{TEST_MARKER} Rule: Always run pytest before committing. Never push code without tests passing. Use pytest -v for verbose output. This is mandatory for all commits.",
        search_queries=[
            "what to do before commit",
            "testing requirement",
            "pytest before push",
            "commit workflow"
        ],
        expected_keywords=["pytest", "commit", "testing", "mandatory"],
        category="workflow-rules",
    ),
    
    # 7. API pattern
    BatteryScenario(
        name="api_pattern_error_handling",
        add_content=f"{TEST_MARKER} API response format and error handling pattern: JSON response structure must include 'success' boolean and 'data' or 'error' field. How to return errors in API: Use HTTP 200 for success, 400 for client errors, 500 for server errors. This API error handling pattern is mandatory.",
        search_queries=[
            "API response format",
            "how to return errors in API",
            "JSON response structure",
            "API error handling pattern"
        ],
        expected_keywords=["API", "JSON", "error", "response"],
        category="api-patterns",
    ),
    
    # 8. Documentation preference
    BatteryScenario(
        name="documentation_preference_docstrings",
        add_content=f"{TEST_MARKER} Documentation preference: User prefers Google-style docstrings format for documenting all Python functions. How to document functions: Include Args section, Returns section, and Raises section. This docstring format preference is strictly enforced.",
        search_queries=[
            "docstring format preference",
            "how to document functions",
            "Google style docstrings",
            "documentation format"
        ],
        expected_keywords=["docstrings", "Google", "documentation", "Args"],
        category="documentation",
    ),
    
    # 9. Git workflow
    BatteryScenario(
        name="git_workflow_branches",
        add_content=f"{TEST_MARKER} Git branch naming convention and PR workflow: How to create feature branch - use 'feat/description' naming. Commit to main allowed? No, never commit directly to main branch. PR workflow requires creating pull request for all changes and squash commits on merge.",
        search_queries=[
            "git branch naming",
            "how to create feature branch",
            "commit to main allowed?",
            "PR workflow"
        ],
        expected_keywords=["branch", "feature", "PR", "main"],
        category="git-workflow",
    ),
    
    # 10. Performance rule
    BatteryScenario(
        name="performance_rule_queries",
        add_content=f"{TEST_MARKER} Performance rule: Database queries must complete in under 100ms. If slower, add index or optimize query. Log all queries taking over 50ms for review.",
        search_queries=[
            "database query performance",
            "query timeout limit",
            "how fast should queries be",
            "performance requirements"
        ],
        expected_keywords=["query", "100ms", "performance", "database"],
        category="performance",
    ),
]


# =============================================================================
# TEST INFRASTRUCTURE
# =============================================================================

class ElefanteBatteryTest:
    """Test harness for Elefante battery tests"""
    
    def __init__(self):
        self.vector_store: Optional[VectorStore] = None
        self.added_memory_ids: List[str] = []
        self.results: List[BatteryResult] = []
        self._test_dir: Optional[str] = None
        self._atexit_registered: bool = False
        
    def _emergency_cleanup(self):
        """Synchronous cleanup registered with atexit.
        
        Called on process exit, including after KeyboardInterrupt kills the
        asyncio event loop.  shutil.rmtree is synchronous and does not need
        a running event loop, so it is guaranteed to run.
        """
        if self._test_dir:
            shutil.rmtree(self._test_dir, ignore_errors=True)
            self._test_dir = None
        
    async def setup(self):
        """Initialize isolated test environment.
        
        Creates a throw-away ChromaDB directory so the battery test NEVER
        touches the production database at ~/.elefante/data/.
        """
        print("\n" + "="*70)
        print("ELEFANTE 10X BATTERY TEST")
        print("="*70)
        print(f"Test prefix: {TEST_PREFIX}")
        print(f"Test marker: {TEST_MARKER}")
        print(f"Min similarity: {MIN_SIMILARITY}")
        print(f"Cleanup enabled: {CLEANUP_ENABLED}")
        print("="*70 + "\n")

        # Isolated temp database — never touches production
        self._test_dir = tempfile.mkdtemp(prefix="elefante_battery_")
        os.environ["ELEFANTE_ALLOW_TEST_MEMORIES"] = "true"

        # Register synchronous atexit handler — survives Ctrl+C killing the loop
        if not self._atexit_registered:
            atexit.register(self._emergency_cleanup)
            self._atexit_registered = True

        # Direct VectorStore with isolated path — independent of global singleton
        self.vector_store = VectorStore(persist_directory=self._test_dir)
        print(f"  Isolated DB: {self._test_dir}\n")
        
    async def cleanup(self):
        """Remove isolated test database directory."""
        if not CLEANUP_ENABLED:
            print("\n  CLEANUP DISABLED - Test data preserved for inspection")
            print(f"  DB path: {self._test_dir}")
            return
            
        print("\n" + "-"*50)
        print("CLEANUP: Removing isolated test database...")

        os.environ.pop("ELEFANTE_ALLOW_TEST_MEMORIES", None)
        if self._test_dir:
            shutil.rmtree(self._test_dir, ignore_errors=True)
            self._test_dir = None

        print("  Deleted isolated test database")
        print("-"*50)
        
    async def run_single_scenario(self, scenario: BatteryScenario) -> BatteryResult:
        """Run a single test scenario"""
        print(f"\n Testing: {scenario.name}")
        print(f"   Category: {scenario.category}")
        
        result = BatteryResult(
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
                print(f"     Search query failed: {query} - {e}")
                
        result.search_time_ms = total_search_time / len(scenario.search_queries) if scenario.search_queries else 0
        result.best_score = best_score
        result.search_results = best_results
        result.search_success = best_score >= MIN_SIMILARITY
        
        if result.search_success:
            print(f"   ✓ SEARCH: Found (best score: {best_score:.3f}, avg {result.search_time_ms:.1f}ms)")
        else:
            print(f"   ✗ SEARCH: FAILED (best score: {best_score:.3f} < {MIN_SIMILARITY})")
            
        return result
        
    async def run_all_scenarios(self) -> List[BatteryResult]:
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
        print(f"\n ADD SUCCESS:    {add_successes}/{total} ({100*add_successes/total:.0f}%)")
        print(f" SEARCH SUCCESS: {search_successes}/{total} ({100*search_successes/total:.0f}%)")
        
        # Calculate average scores
        scores = [r.best_score for r in self.results if r.best_score > 0]
        if scores:
            print(f" AVG SCORE:      {sum(scores)/len(scores):.3f}")
        
        # Overall verdict
        print("\n" + "="*70)
        if add_successes == total and search_successes == total:
            print(" VERDICT: ALL TESTS PASSED (100%)")
            print("   Elefante triggers reliably in normal usage scenarios!")
        elif search_successes >= total * 0.8:
            print(f"  VERDICT: MOSTLY PASSING ({100*search_successes/total:.0f}%)")
            print("   Some scenarios need tuning but core functionality works.")
        else:
            print(f" VERDICT: FAILING ({100*search_successes/total:.0f}%)")
            print("   MCP needs fixes - retrieval not reliable enough!")
        print("="*70)
        
        # List failures for debugging
        failures = [r for r in self.results if not r.search_success]
        if failures:
            print("\n FAILED SCENARIOS (need investigation):")
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
