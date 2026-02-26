"""
MCP Server implementation for Elefante Memory System

This server exposes memory operations as MCP tools that can be called
from IDEs and other MCP clients. It provides a standardized interface
for AI assistants to store and retrieve memories.
"""

import asyncio
import json
from typing import Any, Dict, Optional, Sequence
from datetime import datetime
from uuid import UUID

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Prompt,
    PromptMessage,
    PromptArgument,
    GetPromptResult,
)
import webbrowser
from src.dashboard.server import serve_dashboard_in_thread

# Global flag to track dashboard status
DASHBOARD_STARTED = False

from src.core.orchestrator import get_orchestrator
from src.core.directive_store import get_directive_store
from src.models.query import QueryMode, SearchFilters
from src.models.entity import EntityType, RelationshipType
from src.utils.logger import get_logger
from src.utils.validators import validate_memory_content, validate_uuid
from src.utils.elefante_mode import get_mode_manager, is_elefante_enabled, write_lock

logger = get_logger(__name__)

# Tools that do NOT require Elefante Mode to be enabled
# These are safe to call even when databases are locked by another IDE
SAFE_TOOLS = {
    "elefante-System",
    "elefante-SystemStatusGet",
    "elefante-DashboardOpen",
    "elefante-DirectiveAdd",
    "elefante-DirectiveList",
    "elefante-DirectiveRemove",
}


class ElefanteMCPServer:
    """
    MCP Server for Elefante Memory System
    
    Exposes memory operations as MCP tools:
    - elefante-MemoryAdd: Store new memories
    - elefante-MemorySearch: Search with semantic/structured/hybrid modes
    - elefante-GraphQuery: Execute Cypher queries on knowledge graph
    - elefante-ContextGet: Retrieve session context
    - elefante-GraphConnect: Batch upsert entities and relationships
    - elefante-SystemStatusGet: Get system status and statistics
    """
    
    def __init__(self):
        """Initialize MCP server with lazy loading"""
        self.server = Server("elefante")
        self.orchestrator = None # Lazy loaded
        self.logger = get_logger(self.__class__.__name__)
        self.mode_manager = get_mode_manager()  # Elefante Mode manager (transaction-scoped)
        self.directive_store = get_directive_store()  # Always-on behavioral constraints
        
        # Compliance Gate: Session state for search-before-write enforcement
        # Check for persistent compliance state or initialize clean
        state = self._get_compliance_state()
        if not state:
            self._reset_compliance_gate()
        
        # Session state for autonomous graph maintenance (passive co-activation)
        self._session_retrieval_history: list[str] = []
        
        # Register tool handlers
        self._register_handlers()
        
        self.logger.info("Elefante MCP Server initialized")

    # Tools that should NOT get automatic context injection
    # (they already return memory data, or are system/admin tools)
    _CONTEXT_SKIP_TOOLS = {
        "elefante-MemorySearch", "elefante-MemoryAdd",
        "elefante-ContextGet", "elefante-MemoryConsolidate",
        "elefante-System", "elefante-SystemStatusGet",
        "elefante-DashboardOpen", "elefante-SessionsList",
        "elefante-ETLProcess", "elefante-ETLClassify",
        "elefante-MemoryUpdate", "elefante-MemoryDelete",
        "elefante-DirectiveAdd", "elefante-DirectiveList",
        "elefante-DirectiveRemove",
    }

    def _extract_search_signal(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """Extract a meaningful search string from tool arguments for context injection."""
        # Prioritize description/content fields, fall back to concatenating string values
        for key in ("description", "content", "query", "cypher_query", "search"):
            if key in arguments and isinstance(arguments[key], str) and len(arguments[key].strip()) > 5:
                return arguments[key].strip()[:200]

        # For task create with subtasks, join subtask descriptions
        if tool_name == "elefante-TaskCreate" and "subtasks" in arguments:
            descs = [s.get("description", "") for s in arguments.get("subtasks", []) if isinstance(s, dict)]
            combined = "; ".join(d for d in descs if d)
            if combined:
                return combined[:200]

        # Generic: concatenate short string values
        parts = [str(v) for v in arguments.values() if isinstance(v, str) and len(v) > 5]
        if parts:
            return " ".join(parts)[:200]
        return None

    async def _inject_context(self, result: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        AUTOMATIC CONTEXT INJECTION:
        On every tool call, surfaces the top 3 most relevant memories from ChromaDB
        and appends them to the response. The agent gets context for free — no
        explicit elefante-MemorySearch call required.

        Skips tools that already return memory data (search, list, ETL, system).
        Budget: max 3 memories, high similarity threshold (0.5), summary only.
        """
        if tool_name in self._CONTEXT_SKIP_TOOLS:
            return result

        signal = self._extract_search_signal(tool_name, arguments)
        if not signal:
            return result

        try:
            orchestrator = await self._get_orchestrator()
            search_results = await orchestrator.vector_store.search(
                query=signal,
                limit=3,
                min_similarity=0.5,
                apply_temporal_decay=False
            )

            if not search_results:
                return result

            context_items = []
            new_ids = []
            for sr in search_results:
                # SearchResult has .memory.content and .score
                content = sr.memory.content if hasattr(sr, 'memory') and hasattr(sr.memory, 'content') else str(sr)
                # Truncate each memory to ~150 chars for token budget
                snippet = content[:150].strip()
                if len(content) > 150:
                    snippet += "..."
                score = f"{sr.score:.2f}" if hasattr(sr, 'score') else "?"
                context_items.append(f"[{score}] {snippet}")
                
                if hasattr(sr, 'memory') and hasattr(sr.memory, 'id'):
                    new_ids.append(str(sr.memory.id))

            if new_ids:
                self._session_retrieval_history.extend(new_ids)
                # Keep sliding window of recent unique ids, max 20
                self._session_retrieval_history = list(dict.fromkeys(self._session_retrieval_history))[-20:]
                # Fire and forget passive co-activation recording
                asyncio.create_task(orchestrator.record_coactivation(self._session_retrieval_history.copy()))

            result["RELEVANT_CONTEXT"] = {
                "note": "Auto-surfaced memories relevant to this operation. No search tool call was needed.",
                "memories": context_items
            }
        except Exception as e:
            # Never let context injection break a tool call
            self.logger.debug(f"Context injection skipped: {e}")

        return result

    def _inject_pitfalls(self, result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """
        SURGICAL INJECTION: 
        Injects mandatory protocols and known pitfalls directly into the tool response.
        This ensures the agent CANNOT ignore them, as they are part of the data payload.
        """
        pitfalls = [
            "CRITICAL PROTOCOL: You MUST check for existing memories before creating new ones to avoid duplication.",
            "CRITICAL PROTOCOL: If you are debugging, you MUST read the relevant 'Neural Register' in docs/debug/ first.",
            "CRITICAL PROTOCOL: Do not rely on your internal knowledge base for project specifics; use the memory system."
        ]
        
        # Context-specific injections
        if tool_name == "elefante-MemoryAdd":
            pitfalls.append("WARNING - MEMORY INTEGRITY: Score is system-computed. Classify memory_type accurately — it determines the decay rate.")
        
        if tool_name == "elefante-MemorySearch":
             pitfalls.append("WARNING - SEARCH BIAS: If results are empty, try broader terms. Do not assume non-existence without a semantic search.")
             pitfalls.append("WARNING - CONTRADICTIONS: If you find contradictory memories, prioritize the most recent one but note the conflict.")

        if tool_name in [
            "elefante-GraphQuery",
            "elefante-GraphConnect",
        ]:
            pitfalls.append("WARNING - GRAPH CONSISTENCY: Ensure entity types match the allowed enum values. Do not invent new types without updating the schema.")

        if tool_name == "elefante-GraphConnect":
            pitfalls.append("WARNING - WORKFLOW: Prefer stable entity names/types and reuse existing entities. Avoid creating near-duplicates that only differ by punctuation or casing.")

        if tool_name == "elefante-DashboardOpen":
            pitfalls.append("WARNING - DASHBOARD: If refresh=true, this reads from databases and requires Elefante Mode to be enabled.")

        # Add to result with a key that demands attention
        # Developer Etiquette V1.2 (canonical) — concise enforcement reminder.
        pitfalls.append(
            "STRICT ENFORCEMENT: 1. Keep all responses SHORT, SIMPLE, and DIRECT. "
            "2. NO GUESSING. If the exact information is not found in memory, your final response MUST BE EXACTLY 'UNKNOWN.' with no apologies or filler. "
            "3. Ask context questions ONLY if you are hard-blocked from proceeding."
        )
        result["MANDATORY_PROTOCOLS_READ_THIS_FIRST"] = pitfalls
        return result

    def _get_compliance_file(self):
        """Get path to persistent compliance state file"""
        from pathlib import Path
        state_file = Path.home() / ".elefante" / "compliance_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        return state_file

    def _get_compliance_state(self) -> Dict[str, Any]:
        """Read compliance state from persistent storage"""
        import json
        state_file = self._get_compliance_file()
        if not state_file.exists():
            return None
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read compliance state: {e}")
            return None

    def _save_compliance_state(self, state: Dict[str, Any]):
        """Save compliance state to persistent storage"""
        import json
        state_file = self._get_compliance_file()
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.logger.error(f"Failed to save compliance state: {e}")

    def _check_compliance_gate(self, tool_name: str) -> Dict[str, Any] | None:
        """
        Compliance Gate: Enforce search-before-write rule.
        
        Returns None if gate passes, or an error dict if gate blocks.
        Write operations are blocked until elefante-MemorySearch has been called.
        """
        # Tools that require prior search (write operations)
        GATED_TOOLS = {
            "elefante-MemoryAdd",
            "elefante-MemoryUpdate",
            "elefante-MemoryDelete",
            "elefante-GraphConnect",
        }
        
        if tool_name not in GATED_TOOLS:
            return None  # Gate passes - not a gated tool
            
        state = self._get_compliance_state()
        if not state:
            self._reset_compliance_gate()
            state = self._get_compliance_state()
        
        if state.get("search_performed", False):
            return None  # Gate passes - search was performed
        
        # GATE BLOCKED
        self.logger.warning(f"Compliance Gate BLOCKED: {tool_name} called without prior search")
        return {
            "success": False,
            "error": " COMPLIANCE GATE: Search required before write operations.",
            "gate_status": "BLOCKED",
            "action_required": "Call elefante-MemorySearch first to check for existing/related memories.",
            "reason": "This prevents duplicate memories and ensures you have full context before adding new knowledge.",
            "blocked_tool": tool_name,
            "hint": f"Try: elefante-MemorySearch with a query related to what you want to store."
        }
    
    def _reset_compliance_gate(self):
        """Reset compliance state (e.g., after session ends or on explicit reset)"""
        state = {
            "search_performed": False,
            "search_count": 0,
            "search_timestamp": None,
            "last_query": None
        }
        self._save_compliance_state(state)
        self.logger.info("Compliance Gate reset")

    async def _get_orchestrator(self):
        """Lazy load the orchestrator"""
        if self.orchestrator is None:
            self.logger.info("Initializing Orchestrator (First Run)...")
            self.orchestrator = get_orchestrator()
            self.logger.info("Orchestrator initialized")
        return self.orchestrator
    
    def _register_handlers(self):
        """Register all MCP tool handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """List all available tools"""
            self.logger.info("=== list_tools() handler called by MCP client ===")
            tools = [
                types.Tool(
                    name="elefante-MemoryAdd",
                    description="""Store a new memory in Elefante's dual-database system.

Score is system-computed (0-100) based on behavioral signals: recency, freshness, and reinforcement. You do NOT assign importance — it emerges from how the memory is used over time.

Classify the memory by providing memory_type, domain, and category. The system handles the rest: duplicate detection (REDUNDANT), relation detection (RELATED), and contradiction detection (CONTRADICTORY).""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The memory content to store"
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["fact", "decision", "preference", "insight", "note", "conversation"],
                                "default": "fact",
                                "description": "Type of memory — determines decay rate. Preferences decay slowest, conversations fastest."
                            },
                            "domain": {
                                "type": "string",
                                "enum": ["work", "personal", "learning", "project", "reference", "system"],
                                "description": "High-level context"
                            },
                            "category": {
                                "type": "string",
                                "description": "Topic grouping (e.g., 'elefante', 'python', 'user-preferences')"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for categorization"
                            },
                            "entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {"type": "string"}
                                    },
                                    "required": ["name", "type"]
                                },
                                "description": "Entities to link in knowledge graph"
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Additional metadata"
                            },
                            "force_new": {
                                "type": "boolean",
                                "default": False,
                                "description": "If true, always create a new memory record (bypass title-based deduplication and do not mark as REDUNDANT)."
                            }
                        },
                        "required": ["content"]
                    }
                ),
                types.Tool(
                    name="elefante-MemorySearch",
                    description="""**CRITICAL: USE THIS TOOL FOR ALL MEMORY QUERIES** - Search Elefante's memory system when user asks about their preferences, past conversations, or anything they want you to remember. DO NOT search workspace files for memory queries.

**QUERY REWRITING REQUIREMENT:** Before calling this tool, you MUST rewrite the user's query to be standalone and specific. Replace ALL pronouns (it, that, this, he, she, they) and vague references with the actual entities from conversation context.

**Bad Queries (will fail):**
- "How do I install it?" → Missing: what is "it"?
- "Fix that error" → Missing: which error?
- "What did he say about the project?" → Missing: who is "he"?

**Good Queries (will succeed):**
- "How to install Elefante memory system on Windows"
- "ChromaDB ImportError solution in Python"
- "Jaime's preferences for development folder organization"

This tool queries ChromaDB (vector embeddings) and Kuzu (knowledge graph) using semantic, structured, or hybrid search modes. The database cannot infer context from pronouns - it needs explicit, searchable terms.
                    
**AUTOMATIC USAGE RULES:**
1.  **ALWAYS** call this tool when the user asks an open-ended question about the project (e.g., "How does the auth system work?", "What are the coding standards?").
2.  **ALWAYS** call this tool when the user refers to past decisions or preferences (e.g., "Do it like we discussed", "Use the usual style").
3.  **NEVER** assume you know the answer if it might be in the memory. Check first.
4.  **IF RESULTS ARE CONTRADICTORY:** The most recent memory (by timestamp) usually takes precedence, but check for "decision" or "fact" types over "conversation".
5.  **IF RESULTS ARE IRRELEVANT:** Try a broader query or switch to `mode="semantic"` to catch fuzzy matches.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["semantic", "structured", "hybrid"],
                                "default": "hybrid",
                                "description": "Search mode: semantic (vector), structured (graph), or hybrid (both)"
                            },
                            "limit": {
                                "type": "integer",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 100,
                                "description": "Maximum results to return"
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "memory_type": {"type": "string"},
                                    "domain": {"type": "string", "enum": ["work", "personal", "learning", "project", "reference", "system"]},
                                    "category": {"type": "string"},
                                    "min_score": {"type": "integer", "minimum": 0, "maximum": 100, "description": "Minimum behavioral score (0-100)"},
                                    "tags": {"type": "array", "items": {"type": "string"}},
                                    "start_date": {"type": "string", "format": "date-time"},
                                    "end_date": {"type": "string", "format": "date-time"}
                                },
                                "description": "Optional filters"
                            },
                            "min_similarity": {
                                "type": "number",
                                "default": 0.3,
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "description": "Minimum similarity threshold"
                            },
                            "include_conversation": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include recent conversation context in search results"
                            },
                            "include_stored": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include stored memories from vector/graph databases"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Session UUID for conversation context (required if include_conversation=true)"
                            },
                            "list_all": {
                                "type": "boolean",
                                "default": False,
                                "description": "If true, bypass semantic search and return all memories (for inspection, export, debugging). Pagination via limit/offset."
                            },
                            "offset": {
                                "type": "integer",
                                "default": 0,
                                "minimum": 0,
                                "description": "Number of memories to skip (for pagination, used with list_all=true)"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                types.Tool(
                    name="elefante-GraphQuery",
                    description="Execute Cypher queries directly on Elefante's Kuzu knowledge graph for advanced structured data retrieval. Use this for complex relationship traversals, pattern matching, and graph analytics. Ideal for queries like 'Find all entities connected to X', 'Show the path between A and B', or 'List all relationships of type Y'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cypher_query": {
                                "type": "string",
                                "description": "Cypher query to execute"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Query parameters"
                            }
                        },
                        "required": ["cypher_query"]
                    }
                ),
                types.Tool(
                    name="elefante-ContextGet",
                    description="**CONTEXTUAL GROUNDING**: Retrieve comprehensive context from Elefante's memory system for a specific session or task. Returns related memories from ChromaDB, connected entities and relationships from Kuzu graph, with configurable traversal depth. Use this to gather full context before making decisions or generating responses.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Session UUID (optional)"
                            },
                            "depth": {
                                "type": "integer",
                                "default": 2,
                                "minimum": 1,
                                "maximum": 5,
                                "description": "Relationship traversal depth"
                            },
                            "limit": {
                                "type": "integer",
                                "default": 50,
                                "minimum": 1,
                                "maximum": 200,
                                "description": "Maximum memories to retrieve"
                            }
                        }
                    }
                ),
                # elefante-GraphEntityCreate and elefante-GraphRelationshipCreate REMOVED
                # Use elefante-GraphConnect instead (batch upsert covers both use cases)
                types.Tool(
                    name="elefante-SessionsList",
                    description="Retrieve a list of recent sessions (episodes) with summaries. Use this to browse past interactions and understand the timeline of work. Each episode represents a distinct session of activity.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "default": 10,
                                "description": "Number of episodes to return"
                            },
                            "offset": {
                                "type": "integer",
                                "default": 0,
                                "description": "Pagination offset"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="elefante-SystemStatusGet",
                    description="Get combined system status and statistics for Elefante. Includes Elefante Mode state (enabled/disabled), lock status, and when enabled, database health/usage statistics from the orchestrator.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="elefante-MemoryConsolidate",
                    description="**MEMORY MAINTENANCE**: Deterministic, LLM-free memory cleanup. Use this to canonicalize memories (set stable keys), quarantine test data, and mark duplicates as redundant/superseded so exports and search stay clean. Default is dry-run (`force=false`); set `force=true` to apply changes.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "force": {
                                "type": "boolean",
                                "description": "Apply cleanup changes (default false = dry-run)",
                                "default": False
                            }
                        }
                    }
                ),
                # elefante-MemoryListAll REMOVED — use elefante-MemorySearch with list_all=true
                # elefante-MemoryMigrateToV3 REMOVED (one-time admin, moved to scripts/)
                # Memory Custodial Tools (Amendment + Forgetting)
                types.Tool(
                    name="elefante-MemoryUpdate",
                    description="""**MEMORY AMENDMENT**: Update an existing memory's content or metadata in-place. Use this to correct wrong facts, mark memories as deprecated/archived, or set supersession chains. This is the Amendment duty — correct the record rather than burying it under new entries.

When to use:
- A stored fact is wrong or outdated → update content
- A decision has been superseded → set deprecated=true and/or supersedes_id
- Tags need correction

Requires prior elefante-MemorySearch (Compliance Gate).""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "The UUID of the memory to update"
                            },
                            "content": {
                                "type": "string",
                                "description": "New content to replace the existing content (triggers re-embedding)"
                            },
                            "deprecated": {
                                "type": "boolean",
                                "description": "Mark memory as deprecated (excluded from search results)"
                            },
                            "archived": {
                                "type": "boolean",
                                "description": "Mark memory as archived (excluded from search results)"
                            },
                            "supersedes_id": {
                                "type": "string",
                                "description": "UUID of the older memory this one supersedes"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Replacement tags"
                            }
                        },
                        "required": ["memory_id"]
                    }
                ),
                types.Tool(
                    name="elefante-MemoryDelete",
                    description="""**PURPOSEFUL FORGETTING**: Permanently delete a memory from the vector store. Use this for: removing incorrect/harmful facts, cleaning up test data, pruning transient context that should not persist. Requires a reason for audit trail.

This is the Forgetting duty — some information must be actively removed, not just deprioritized.

Requires prior elefante-MemorySearch (Compliance Gate).""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "The UUID of the memory to delete"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Why this memory is being deleted (audit trail)"
                            }
                        },
                        "required": ["memory_id", "reason"]
                    }
                ),
                types.Tool(
                    name="elefante-DashboardOpen",
                    description="Launch and open the Elefante Knowledge Garden Dashboard in the user's browser. Optionally refresh the dashboard snapshot data first.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "refresh": {
                                "type": "boolean",
                                "default": False,
                                "description": "If true, regenerate dashboard snapshot data before opening. Requires Elefante Mode to be enabled."
                            }
                        }
                    }
                ),
                types.Tool(
                    name="elefante-GraphConnect",
                    description="Create a small, idempotent graph workflow in one call: upsert entities (by name+type) and create relationships between them. Designed to reduce tool-chaining and keep graph operations consistent.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "description": "Entities to upsert. Provide either id or (name+type). Use a stable ref to connect relationships.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ref": {"type": "string", "description": "Client reference key (e.g., 'project', 'repo', 'person1')"},
                                        "id": {"type": "string", "description": "Existing entity UUID (optional)"},
                                        "name": {"type": "string", "description": "Entity name (required if id not provided)"},
                                        "type": {"type": "string", "description": "Entity type (required if id not provided)"},
                                        "properties": {"type": "object", "description": "Optional properties"}
                                    },
                                    "required": ["ref"],
                                    "additionalProperties": False
                                }
                            },
                            "relationships": {
                                "type": "array",
                                "description": "Relationships to create. Provide either from_ref/to_ref or from_entity_id/to_entity_id.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from_ref": {"type": "string"},
                                        "to_ref": {"type": "string"},
                                        "from_entity_id": {"type": "string"},
                                        "to_entity_id": {"type": "string"},
                                        "relationship_type": {"type": "string", "description": "Relationship type (accepts enum value, case-insensitive)"},
                                        "properties": {"type": "object"}
                                    },
                                    "required": ["relationship_type"],
                                    "additionalProperties": False
                                }
                            },
                            "include_system_status": {
                                "type": "boolean",
                                "default": False,
                                "description": "If true, include elefante-SystemStatusGet output in the response."
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                types.Tool(
                    name="elefante-System",
                    description="""Enable or disable Elefante Mode. Controls the memory system's on/off state and database locks.

action="enable" (default): Acquires exclusive locks on ChromaDB and Kuzu databases, activates memory operations. Required first step.
action="disable": Releases all locks for multi-IDE safety.

If another IDE is using Elefante, enable will fail gracefully with lock information.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["enable", "disable"],
                                "default": "enable",
                                "description": "Enable or disable Elefante Mode"
                            },
                            "force": {
                                "type": "boolean",
                                "default": False,
                                "description": "Force enable (use with caution - may cause conflicts)"
                            }
                        }
                    }
                ),
                # =====================================================================
                # TASK ORCHESTRATION TOOLS
                # =====================================================================
                types.Tool(
                    name="elefante-TaskCreate",
                    description="""Create a new task in Elefante's orchestration graph. Tasks are stored as Kuzu nodes and can form hierarchies (parent/child) and dependency chains (blocked_by). Use this to register a unit of work that agents will execute.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What needs to be done"
                            },
                            "parent_id": {
                                "type": "string",
                                "description": "Parent task ID (creates a subtask relationship)"
                            },
                            "priority": {
                                "type": "integer",
                                "default": 1,
                                "minimum": 1,
                                "maximum": 10,
                                "description": "Priority 1-10 (10 = highest)"
                            },
                            "assigned_agent": {
                                "type": "string",
                                "description": "Which agent or role handles this task"
                            },
                            "blocked_by": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of task IDs that must complete before this task can start"
                            },
                            "subtasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string", "description": "What this subtask does"},
                                        "priority": {"type": "integer", "default": 1},
                                        "assigned_agent": {"type": "string"}
                                    },
                                    "required": ["description"]
                                },
                                "description": "Optional: create subtasks under this task in one call (absorbs former elefante-TaskDecompose)"
                            }
                        },
                        "required": ["description"]
                    }
                ),
                # elefante-TaskDecompose REMOVED — use elefante-TaskCreate with subtasks array
                types.Tool(
                    name="elefante-TaskUpdate",
                    description="""Update a task's status or output. Use this to mark tasks as in_progress, completed, failed, or blocked. Optionally attach output text (result summary, error message, etc.).""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "The task ID to update"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed", "failed", "blocked"],
                                "description": "New status for the task"
                            },
                            "output": {
                                "type": "string",
                                "description": "Result or output from the task execution"
                            }
                        },
                        "required": ["task_id"]
                    }
                ),
                types.Tool(
                    name="elefante-TaskGraph",
                    description="""Get the task hierarchy. Without a task_id, returns all root tasks (top-level goals). With a task_id, returns that task and its direct subtasks. Use this to see what's planned, in progress, and completed.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Optional: specific task ID to inspect. Omit to see all root tasks."
                            }
                        }
                    }
                ),
                # =====================================================================
                # ETL TOOLS (Agent-Brain Classification)
                # =====================================================================
                types.Tool(
                    name="elefante-ETLProcess",
                    description="""**PHASE 2 ETL**: Get unclassified memories for YOU (the agent) to enrich.

This returns raw memories that need agent enrichment. YOU must analyze each one and call elefante-ETLClassify with your enrichment.

Enrichment fields:
- **summary**: One-line description of what this memory is about
- **concepts**: 3-5 key terms for graph edges and retrieval (optional, improves search)
- **surfaces_when**: Query patterns that should trigger this memory (optional, improves search)

Flow:
1. Call elefante-ETLProcess(limit=5) → Get raw memories
2. Analyze each memory using your LLM brain
3. Call elefante-ETLClassify for each with your enrichment""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Number of raw memories to process"
                            },
                            "include_stats": {
                                "type": "boolean",
                                "default": False,
                                "description": "If true, include ETL processing statistics (raw/processed/failed counts) in the response"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="elefante-ETLClassify",
                    description="""**PHASE 2 ETL**: Submit YOUR enrichment for a memory.

After analyzing a memory from elefante-ETLProcess, call this to store your enrichment.

Required fields:
- memory_id: From elefante-ETLProcess
- summary: One-line description (max 200 chars)

Optional fields (improve retrieval quality):
- concepts: 3-5 key terms for graph edges
- surfaces_when: Query patterns that should trigger this memory""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "Memory UUID from elefante-ETLProcess"
                            },
                            "summary": {
                                "type": "string",
                                "description": "One-line summary (max 200 chars)"
                            },
                            "concepts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "3-5 key terms for graph edges and retrieval"
                            },
                            "surfaces_when": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Query patterns that should trigger this memory"
                            }
                        },
                        "required": ["memory_id", "summary"]
                    }
                ),
                # =====================================================================
                # DIRECTIVE TOOLS (Always-On Behavioral Constraints)
                # =====================================================================
                types.Tool(
                    name="elefante-DirectiveAdd",
                    description="""Add a persistent behavioral directive. Directives are NOT memories — they are unconditional constraints injected into EVERY MCP tool response, ensuring the agent sees them at the decision boundary.

Use this for rules that must always be active regardless of context:
- "Never claim success without user confirmation"
- "Always verify a server is alive before opening it"
- "Do not use emojis in code comments"

Directives are stored separately from the memory system (not in ChromaDB, not in Kuzu). They cannot be outcompeted by similarity scores.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The directive text — a clear, actionable behavioral constraint"
                            }
                        },
                        "required": ["content"]
                    }
                ),
                types.Tool(
                    name="elefante-DirectiveList",
                    description="List all active directives. These are the unconditional behavioral constraints injected into every tool response.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="elefante-DirectiveRemove",
                    description="Remove a directive by its ID. The directive will no longer be injected into tool responses.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "directive_id": {
                                "type": "string",
                                "description": "The ID of the directive to remove (from elefante-DirectiveList)"
                            }
                        },
                        "required": ["directive_id"]
                    }
                ),
                # elefante-ETLStatus REMOVED — use elefante-ETLProcess with include_stats=true
            ]
            self.logger.info(f"=== Returning {len(tools)} tools to MCP client ===")
            return tools
        
        # =========================================================================
        # MCP PROMPTS - Inject grounding behavior into LLM context
        # =========================================================================
        
        @self.server.list_prompts()
        async def list_prompts() -> list[Prompt]:
            """List available prompts that inject memory-aware behavior"""
            self.logger.info("=== list_prompts() handler called ===")
            return [
                Prompt(
                    name="elefante-grounding",
                    title="Elefante Memory Grounding",
                    description="ALWAYS use this prompt at the start of conversations. It injects memory-aware behavior so the AI automatically checks memories before answering.",
                    arguments=[]
                ),
                Prompt(
                    name="elefante-context",
                    title="Get Context Before Answering",
                    description="Use this before answering any question about user preferences, past decisions, or project knowledge. Searches memories first.",
                    arguments=[
                        PromptArgument(
                            name="topic",
                            description="What topic to retrieve context for",
                            required=True
                        )
                    ]
                )
            ]
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
            """Return prompt content for injection into LLM context"""
            self.logger.info(f"=== get_prompt({name}) called ===")
            
            if name == "elefante-grounding":
                return GetPromptResult(
                    description="Elefante Memory Grounding Instructions",
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(
                                type="text",
                                text="""# ELEFANTE MEMORY SYSTEM - ACTIVE

You have access to a persistent memory system called **Elefante** - the user's second brain.

## AUTOMATIC BEHAVIOR REQUIRED

**BEFORE answering ANY question about:**
- User preferences (coding style, tools, formatting)
- Past decisions or discussions
- Project-specific knowledge ("how we do X")
- "The usual way" or "like we discussed"

**YOU MUST first call `elefante-MemorySearch`** with a specific query.

## RULE: When in doubt, SEARCH.
- Memory search is FAST (< 100ms)
- Better to search and find nothing than miss critical context
- The user has invested time teaching you - use that knowledge

## TRIGGER PATTERNS
- "elefante:" prefix → ALWAYS act on this
- "remember", "recall", "what did I say" → SEARCH first
- "preference", "decision", "how do I like" → SEARCH first

## NEVER DO THIS
- Answer from general knowledge when user asks about THEIR preferences
- Assume you know the answer without checking memories
- Skip the memory search to be faster"""
                            )
                        )
                    ]
                )
            
            elif name == "elefante-context":
                topic = arguments.get("topic", "") if arguments else ""
                # Actually search memories and include results
                try:
                    orchestrator = await self._get_orchestrator()
                    from src.models.query import QueryMode
                    results = await orchestrator.search_memories(
                        query=topic,
                        mode=QueryMode.HYBRID,
                        limit=5,
                        min_similarity=0.3
                    )
                    
                    if results:
                        memory_text = "\\n\\n".join([
                            f"**Memory [{i+1}]** (score: {r.score:.2f}):\\n{r.memory.content}"
                            for i, r in enumerate(results)
                        ])
                        context_msg = f"# Relevant Memories for: {topic}\\n\\n{memory_text}\\n\\n---\\nUse this context to answer the user's question."
                    else:
                        context_msg = f"# No memories found for: {topic}\\n\\nNo relevant memories in the database. You may proceed with general knowledge, but note this is a gap in the user's knowledge base."
                except Exception as e:
                    context_msg = f"# Memory search failed\\n\\nError: {e}\\n\\nProceed with caution."
                
                return GetPromptResult(
                    description=f"Memory context for: {topic}",
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(
                                type="text",
                                text=context_msg
                            )
                        )
                    ]
                )
            
            raise ValueError(f"Unknown prompt: {name}")        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool calls"""
            self.logger.info(f"Tool called: {name}", arguments=arguments)
            
            try:
                # Handle mode management + safe tools FIRST (always available)
                if name == "elefante-System":
                    action = arguments.get("action", "enable")
                    if action == "disable":
                        result = await self._handle_disable_elefante(arguments)
                    else:
                        result = await self._handle_enable_elefante(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-SystemStatusGet":
                    result = await self._handle_get_system_status(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-DashboardOpen":
                    result = await self._handle_get_elefante_dashboard(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                # Directive tools — safe, no DB locks needed
                elif name == "elefante-DirectiveAdd":
                    result = self._handle_directive_add(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-DirectiveList":
                    result = self._handle_directive_list(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-DirectiveRemove":
                    result = self._handle_directive_remove(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                
                # Mode check removed - operations auto-acquire/release locks
                # Write operations use write_lock() context manager internally
                
                if name == "elefante-MemoryAdd":
                    result = await self._handle_add_memory(arguments)
                elif name == "elefante-MemorySearch":
                    result = await self._handle_search_memories(arguments)
                elif name == "elefante-GraphQuery":
                    result = await self._handle_query_graph(arguments)
                elif name == "elefante-ContextGet":
                    result = await self._handle_get_context(arguments)
                elif name == "elefante-SessionsList":
                    result = await self._handle_get_episodes(arguments)
                elif name == "elefante-MemoryConsolidate":
                    result = await self._handle_consolidate_memories(arguments)
                elif name == "elefante-MemoryUpdate":
                    result = await self._handle_update_memory(arguments)
                elif name == "elefante-MemoryDelete":
                    result = await self._handle_delete_memory(arguments)
                elif name == "elefante-GraphConnect":
                    result = await self._handle_set_elefante_connection(arguments)
                # ETL Tools (Agent-Brain Classification)
                elif name == "elefante-ETLProcess":
                    result = await self._handle_etl_process(arguments)
                elif name == "elefante-ETLClassify":
                    result = await self._handle_etl_classify(arguments)
                # Task Orchestration Tools
                elif name == "elefante-TaskCreate":
                    result = await self._handle_task_create(arguments)
                elif name == "elefante-TaskUpdate":
                    result = await self._handle_task_update(arguments)
                elif name == "elefante-TaskGraph":
                    result = await self._handle_task_graph(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                # INJECT CONTEXT + PITFALLS + DIRECTIVES
                if isinstance(result, dict):
                    result = await self._inject_context(result, name, arguments)
                    result = self._inject_pitfalls(result, name)
                    result = self._inject_directives(result)

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]
                
            except Exception as e:
                self.logger.error(f"Tool execution failed: {name}", error=str(e), exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "tool": name,
                        "success": False
                    }, indent=2)
                )]
            finally:
                # Release Kuzu write lock after every tool call.
                # This makes the lock transaction-scoped (held only during the operation)
                # allowing multiple MCP server instances to take turns without deadlock.
                try:
                    from src.core.graph_store import close_graph_store
                    close_graph_store()
                except Exception:
                    pass
    
    async def _handle_enable_elefante(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-System tool call (action=enable) - Activate Elefante Mode"""
        force = args.get("force", False)
        result = self.mode_manager.enable(force=force)
        
        if result["success"]:
            # Store orchestrator reference for cleanup
            try:
                orchestrator = await self._get_orchestrator()
                self.mode_manager.set_orchestrator_ref(orchestrator)
            except Exception as e:
                self.logger.warning(f"Could not pre-load orchestrator: {e}")
        
        return result
    
    async def _handle_disable_elefante(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-System tool call (action=disable) - Deactivate Elefante Mode"""
        result = self.mode_manager.disable()
        
        # Clear orchestrator reference
        if result["success"]:
            self.orchestrator = None
        
        return result

    async def _handle_get_system_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-SystemStatusGet tool call - Combined mode + stats"""
        status: Dict[str, Any] = {
            "success": True,
            "mode": "enabled" if self.mode_manager.is_enabled else "disabled",
            "status": self.mode_manager.status,
            "lock_status": self.mode_manager.check_locks(),
        }

        if not self.mode_manager.is_enabled:
            status["stats"] = None
            status["message"] = "Elefante Mode is DISABLED - call elefante-System(action='enable') to activate"
            return status

        orchestrator = await self._get_orchestrator()
        stats = await orchestrator.get_stats()
        status["stats"] = stats
        status["message"] = "Elefante Mode is ENABLED"
        return status

    async def _handle_add_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemoryAdd tool call - Authoritative Pipeline (Compliance Gate)"""
        # Compliance Gate Check
        gate_result = self._check_compliance_gate("elefante-MemoryAdd")
        if gate_result is not None:
            return gate_result
        
        # Acquire write lock for duration of operation
        with write_lock() as lock:
            if not lock.acquired:
                return {
                    "success": False,
                    "error": "Could not acquire write lock - another process is writing",
                    "retry": True
                }
            
            orchestrator = await self._get_orchestrator()
        
        # Build metadata with domain/category if provided
        metadata = args.get("metadata") or {}
        if args.get("domain"):
            metadata["domain"] = args["domain"]
        if args.get("category"):
            metadata["category"] = args["category"]
        
        memory = await orchestrator.add_memory(
            content=args["content"],
            memory_type=args.get("memory_type", "conversation"),
            tags=args.get("tags"),
            entities=args.get("entities"),
            metadata=metadata if metadata else None,
            force_new=bool(args.get("force_new", False))
        )
        
        # Handle case where memory was IGNORED by cognitive pipeline
        if memory is None:
            return {
                "status": "ignored",
                "classification": "IGNORE",
                "entity_count": 0,
                "relationship_count": 0,
                "embedding_id": None,
                "graph_ids": [],
                "message": "Memory filtered by Intelligence Pipeline"
            }
        
        # Authoritative Output Format
        # Count entities passed in + auto-generated (approximation)
        entity_count = len(args.get("entities", []))
        
        # Handle status as either enum or string
        status_value = memory.metadata.status.value if hasattr(memory.metadata.status, 'value') else str(memory.metadata.status)
        
        return {
            "status": "stored",
            "classification": status_value.upper(),  # NEW|REDUNDANT|RELATED|CONTRADICTORY
            "entity_count": entity_count,
            "relationship_count": entity_count,  # 1 relationship per entity
            "embedding_id": str(memory.id),
            "graph_ids": [str(memory.id)],  # Memory node ID
            "score": memory.metadata.score,
            "memory_type": memory.metadata.memory_type.value if hasattr(memory.metadata.memory_type, 'value') else str(memory.metadata.memory_type),
            "memory_id": str(memory.id)
        }
    
    async def _handle_search_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        args = args.copy()
        args.setdefault("include_explanation", True)
        """Handle elefante-MemorySearch tool call"""
        # list_all mode (absorbs former elefante-MemoryListAll)
        if args.get("list_all", False):
            return await self._handle_list_all_memories(args)
        
        # Parse mode
        mode_str = args.get("mode", "hybrid")
        mode = QueryMode(mode_str)
        
        # Parse filters
        filters = None
        if "filters" in args:
            filter_data = args["filters"]
            filters = SearchFilters(
                memory_type=filter_data.get("memory_type"),
                domain=filter_data.get("domain"),
                category=filter_data.get("category"),
                min_score=filter_data.get("min_score"),
                max_score=filter_data.get("max_score"),
                tags=filter_data.get("tags"),
                start_date=datetime.fromisoformat(filter_data["start_date"]) if "start_date" in filter_data else None,
                end_date=datetime.fromisoformat(filter_data["end_date"]) if "end_date" in filter_data else None
            )
        
        # Parse session_id if provided
        session_id = None
        if "session_id" in args and args["session_id"]:
            session_id = UUID(args["session_id"])
        
        # Search with conversation context support
        orchestrator = await self._get_orchestrator()
        results = await orchestrator.search_memories(
            query=args["query"],
            mode=mode,
            limit=args.get("limit", 10),
            filters=filters,
            min_similarity=args.get("min_similarity", 0.1), # Issue #8 Fix: Lowered from 0.3
            include_conversation=args.get("include_conversation", True),
            include_stored=args.get("include_stored", True),
            session_id=session_id,
            recent_memory_ids=self._session_retrieval_history
        )
        
        # Session Tracking for Co-Activation
        new_ids = [str(r.memory.id) for r in results if hasattr(r, 'memory') and hasattr(r.memory, 'id')]
        if new_ids:
            self._session_retrieval_history.extend(new_ids)
            self._session_retrieval_history = list(dict.fromkeys(self._session_retrieval_history))[-20:]
            asyncio.create_task(orchestrator.record_coactivation(self._session_retrieval_history.copy()))
        
        # Filter out deprecated/archived memories from results
        filtered_results = []
        excluded_count = 0
        for result in results:
            meta = result.memory.get("metadata", {}) if isinstance(result.memory, dict) else getattr(result.memory, "metadata", None)
            if meta:
                m = meta if isinstance(meta, dict) else meta.__dict__ if hasattr(meta, "__dict__") else {}
                if m.get("deprecated", False) or m.get("archived", False):
                    excluded_count += 1
                    continue
            filtered_results.append(result)
        results = filtered_results

        # Data Compression (Issue #7) - Aggressive Slim Response Payload to prevent User UI spam
        compressed_results = []
        for result in results:
            r_dict = result.to_dict()
            slim = {}
            if 'memory' in r_dict:
                mem_dict = r_dict['memory']
                slim_mem = {
                    'id': mem_dict.get('id'),
                    'content': mem_dict.get('content')
                }
                
                # Keep metadata extremely lean for the LLM
                meta = mem_dict.get('metadata', {})
                if meta:
                    slim_meta = {}
                    for key in ['created_at', 'memory_type', 'category']:
                        if key in meta:
                            slim_meta[key] = meta[key]
                    slim_mem['metadata'] = slim_meta
                    
                slim['memory'] = slim_mem
            
            slim['score'] = r_dict.get('score')
            compressed_results.append(slim)

        # Actionable Integration (Issue #9) - Force behavioral compliance
        action_summary = (
            "CRITICAL DIRECTIVE: These memories are your authoritative context. You MUST read the 'content' of each memory and integrate it directly into your solution. "
            "STRICT COMMUNICATION PROTOCOL: If you do not see the exact requested information in these memories, you MUST respond to the user with EXACTLY the word 'UNKNOWN.' and absolutely NO other text. "
            "ANTI-SPAM PROTOCOL: You MUST NEVER output raw JSON, database IDs, or internal search metadata to the user. Integrate the knowledge into a natural human response."
        )

        response = {
            "success": True,
            "count": len(results),
            "suggested_action": action_summary,
            "results": compressed_results
        }
        if excluded_count > 0:
            response["excluded_deprecated"] = excluded_count
        
        # Compliance Gate: Mark search as performed (Persistent)
        state = self._get_compliance_state()
        if not state:
            state = {}
        state["search_performed"] = True
        state["search_count"] = len(results)
        state["search_timestamp"] = getattr(datetime.utcnow(), 'isoformat', lambda: str(datetime.utcnow()))()
        state["last_query"] = args["query"]
        self._save_compliance_state(state)
        
        # Add compliance stamp to response
        if len(results) > 0:
            response["compliance_stamp"] = f"[ELEFANTE] Searched: Found {len(results)} relevant memories"
        else:
            response["compliance_stamp"] = "[ELEFANTE] Searched: No relevant memories found"
        
        response["gate_status"] = "UNLOCKED"  # Write operations now allowed

        return response
    
    async def _handle_query_graph(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-GraphQuery tool call"""
        from src.core.graph_store import get_graph_store
        
        graph_store = get_graph_store()
        # Note: Kuzu doesn't support parameterized queries in current implementation
        results = await graph_store.execute_query(args["cypher_query"])
        
        return {
            "success": True,
            "count": len(results),
            "results": results
        }
    
    async def _handle_get_context(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-ContextGet tool call"""
        session_id = None
        if "session_id" in args:
            session_id = UUID(args["session_id"])
        
        orchestrator = await self._get_orchestrator()
        context = await orchestrator.get_context(
            session_id=session_id,
            depth=args.get("depth", 2),
            limit=args.get("limit", 50)
        )
        
        return {
            "success": True,
            "context": context
        }
    

    
    def _normalize_relationship_type(self, relationship_type: str) -> str:
        if not isinstance(relationship_type, str) or not relationship_type.strip():
            raise ValueError("relationship_type must be a non-empty string")

        candidate = relationship_type.strip()
        # Support both canonical enum values and legacy-ish lowercase values.
        # RelationshipType values are uppercase like RELATES_TO.
        candidate_upper = candidate.upper()
        candidate_upper = candidate_upper.replace("-", "_")
        return candidate_upper
    
    async def _handle_list_all_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemorySearch tool call with list_all=true"""
        orchestrator = await self._get_orchestrator()
        
        # Parse filters if provided
        filters = None
        if "filters" in args and args["filters"]:
            filter_data = args["filters"]
            filters = SearchFilters(
                memory_type=filter_data.get("memory_type"),
                domain=filter_data.get("domain"),
                category=filter_data.get("category"),
                min_score=filter_data.get("min_score"),
                max_score=filter_data.get("max_score"),
                tags=filter_data.get("tags")
            )
        
        # Get all memories
        memories = await orchestrator.list_all_memories(
            limit=args.get("limit", 100),
            offset=args.get("offset", 0),
            filters=filters
        )
        
        compressed_memories = []
        for mem in memories:
            m_dict = mem.to_dict()
            slim = {
                'id': m_dict.get('id'),
                'content': m_dict.get('content')
            }
            meta = m_dict.get('metadata', {})
            if meta:
                slim_meta = {}
                for key in ['created_at', 'memory_type', 'category']:
                    if key in meta:
                        slim_meta[key] = meta[key]
                slim['metadata'] = slim_meta
            compressed_memories.append(slim)

        return {
            "success": True,
            "count": len(memories),
            "memories": compressed_memories
        }
    
    # =========================================================================
    # CUSTODIAL TOOLS — Amendment & Forgetting
    # =========================================================================
    
    async def _handle_update_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemoryUpdate tool call — amend memories in-place."""
        gate_result = self._check_compliance_gate("elefante-MemoryUpdate")
        if gate_result is not None:
            return gate_result
        
        memory_id = args.get("memory_id")
        if not memory_id:
            return {"success": False, "error": "memory_id is required"}
        
        with write_lock() as lock:
            if not lock.acquired:
                return {"success": False, "error": "Could not acquire write lock", "retry": True}
            
            from uuid import UUID as _UUID
            mid = _UUID(memory_id)
            
            # Build updates dict from provided args
            updates = {}
            for key in ("content", "deprecated", "archived", "tags", "supersedes_id"):
                if key in args:
                    val = args[key]
                    if key == "supersedes_id" and val:
                        val = _UUID(val)
                    updates[key] = val
            
            if not updates:
                return {"success": False, "error": "No fields to update. Provide at least one of: content, deprecated, archived, supersedes_id, tags"}
            
            orchestrator = await self._get_orchestrator()
            vs = orchestrator.vector_store
            success = await vs.update_memory(mid, updates)
            
            if success:
                # If we're superseding another memory, mark the old one as superseded_by
                if "supersedes_id" in updates and updates["supersedes_id"]:
                    old_id = updates["supersedes_id"]
                    await vs.update_memory(old_id, {"superseded_by_id": mid})
                
                self.logger.info(f"Memory amended: {memory_id}", updates=list(updates.keys()))
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "updated_fields": list(updates.keys()),
                    "message": "Memory amended in-place"
                }
            else:
                return {"success": False, "error": f"Memory {memory_id} not found or update failed"}
    
    async def _handle_delete_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemoryDelete tool call — purposeful forgetting."""
        gate_result = self._check_compliance_gate("elefante-MemoryDelete")
        if gate_result is not None:
            return gate_result
        
        memory_id = args.get("memory_id")
        reason = args.get("reason")
        if not memory_id or not reason:
            return {"success": False, "error": "Both memory_id and reason are required"}
        
        with write_lock() as lock:
            if not lock.acquired:
                return {"success": False, "error": "Could not acquire write lock", "retry": True}
            
            from uuid import UUID as _UUID
            mid = _UUID(memory_id)
            
            orchestrator = await self._get_orchestrator()
            vs = orchestrator.vector_store
            success = await vs.delete_memory(mid)
            
            if success:
                self.logger.info(f"Memory deleted (purposeful forgetting): {memory_id}", reason=reason)
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "reason": reason,
                    "message": "Memory permanently deleted"
                }
            else:
                return {"success": False, "error": f"Memory {memory_id} not found or deletion failed"}

    async def _handle_consolidate_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemoryConsolidate tool call (transaction-scoped)"""
        with write_lock() as lock:
            if not lock.acquired:
                return {
                    "success": False,
                    "error": "Could not acquire write lock - another process is writing",
                    "retry": True
                }
            
            orchestrator = await self._get_orchestrator()
            result = await orchestrator.consolidate_memories(
                force=args.get("force", False)
            )
            return result
    
    async def _handle_get_episodes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-SessionsList tool call"""
        limit = args.get("limit", 10)
        offset = args.get("offset", 0)
        
        from src.core.graph_store import get_graph_store
        graph_store = get_graph_store()
        
        # Query for sessions
        cypher = f"""
        MATCH (s:Entity {{type: 'session'}})
        RETURN s
        ORDER BY s.last_active DESC
        SKIP {offset}
        LIMIT {limit}
        """
        
        results = await graph_store.execute_query(cypher)
        episodes = []
        
        for row in results:
            session = row.get("s")
            if session:
                episodes.append({
                    "id": str(session.id),
                    "name": session.name,
                    "last_active": session.properties.get("last_active"),
                    "source": session.properties.get("source")
                })
        
        return {
            "success": True,
            "count": len(episodes),
            "episodes": episodes
        }
    
    async def _start_dashboard_and_open(self) -> Dict[str, Any]:
        global DASHBOARD_STARTED

        port = 8000
        url = f"http://localhost:{port}"

        if not DASHBOARD_STARTED:
            try:
                import subprocess
                import sys
                
                # Check if it's already running by trying to connect
                import urllib.request
                import urllib.error
                is_running = False
                try:
                    req = urllib.request.Request(f"{url}/health", headers={"Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=1) as resp:
                        if resp.status == 200:
                            is_running = True
                except (urllib.error.URLError, TimeoutError):
                    pass
                
                if not is_running:
                    # Launch as an independent, detached subprocess so it survives the MCP server
                    subprocess.Popen(
                        [sys.executable, "-m", "src.dashboard.server"],
                        start_new_session=True,  # Detach from parent process group
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    self.logger.info(f"Dashboard server started via subprocess on port {port}")
                else:
                    self.logger.info(f"Dashboard already running on {port}")
                
                DASHBOARD_STARTED = True
            except Exception as e:
                self.logger.warning(f"Failed to start dashboard server: {e}")
                DASHBOARD_STARTED = True  # Assume it's running

        try:
            webbrowser.open(url)
            message = f"Dashboard opened at {url}"
        except Exception as e:
            message = f"Dashboard server running at {url}, but failed to open browser: {e}"

        return {
            "success": True,
            "message": message,
            "url": url
        }

    async def _refresh_dashboard_snapshot(self) -> Dict[str, Any]:
        import os
        from src.utils.config import DATA_DIR

        orchestrator = await self._get_orchestrator()

        memories = await orchestrator.vector_store.get_all(limit=1000)

        nodes = []
        edges = []
        seen_ids = set()

        def _is_test_artifact(*, content: str, title: str) -> bool:
            c = (content or "").strip().lower()
            t = (title or "").strip().lower()

            if c.startswith("elefante e2e test memory") or c.startswith("hybrid search test memory"):
                return True

            if c.startswith("entity relationship test ") or c.startswith("persistence test "):
                return True

            if t.startswith("e2e-test") or "hybrid_test_" in t:
                return True

            return False

        for mem in memories:
            cm = mem.metadata.custom_metadata or {}
            if cm.get("title"):
                name = cm.get("title")
            else:
                words = mem.content.split()[:5]
                name = " ".join(words) if words else "Untitled Memory"

            if _is_test_artifact(content=mem.content, title=str(name)):
                continue

            status_value = mem.metadata.status.value if hasattr(mem.metadata.status, "value") else str(mem.metadata.status)
            rel_type_value = (
                mem.metadata.relationship_type.value
                if getattr(mem.metadata, "relationship_type", None) and hasattr(mem.metadata.relationship_type, "value")
                else str(getattr(mem.metadata, "relationship_type", "") or "")
            )

            processing_status = cm.get("processing_status")
            canonical_key = cm.get("canonical_key")
            namespace = cm.get("namespace")
            topic = mem.metadata.category if mem.metadata.category and mem.metadata.category != "general" else cm.get("topic")
            summary = cm.get("summary")

            node = {
                "id": str(mem.id),
                "name": name,
                "type": "memory",
                "description": mem.content,
                "created_at": mem.metadata.created_at.isoformat(),
                "properties": {
                    "content": mem.content,
                    "memory_type": mem.metadata.memory_type.value if hasattr(mem.metadata.memory_type, "value") else str(mem.metadata.memory_type),
                    "score": mem.metadata.score,
                    "tags": ",".join(mem.metadata.tags) if mem.metadata.tags else "",
                    "status": status_value,
                    "relationship_type": rel_type_value,
                    "archived": bool(getattr(mem.metadata, "archived", False)),
                    "deprecated": bool(getattr(mem.metadata, "deprecated", False)),
                    "supersedes_id": str(mem.metadata.supersedes_id) if mem.metadata.supersedes_id else "",
                    "superseded_by_id": str(mem.metadata.superseded_by_id) if mem.metadata.superseded_by_id else "",
                    "processing_status": processing_status,
                    "canonical_key": canonical_key,
                    "namespace": namespace,
                    "title": cm.get("title", ""),
                    "topic": topic,
                    "summary": summary,
                    "source": "chromadb",
                }
            }
            nodes.append(node)
            seen_ids.add(str(mem.id))

        # Add explicit supersession edges from vector-store metadata.
        for mem in memories:
            if mem.metadata.superseded_by_id:
                src = str(mem.id)
                dst = str(mem.metadata.superseded_by_id)
                if src != dst and src in seen_ids and dst in seen_ids:
                    edges.append({
                        "from": src,
                        "to": dst,
                        "label": "SUPERSEDED_BY",
                        "type": "supersession",
                    })

        # Add "signal hub" nodes/edges (topic) so the
        # dashboard has useful connectivity even when Kuzu graph edges are empty.
        signal_index = {}
        signal_members: dict[str, set[str]] = {}
        signal_kind_by_id: dict[str, str] = {}

        def _signal_id(kind: str, value: str) -> str:
            return f"signal:{kind}:{value}".lower().replace(" ", "_")

        def _ensure_signal_node(kind: str, value: str) -> str:
            key = (kind, value)
            if key in signal_index:
                return signal_index[key]
            sid = _signal_id(kind, value)
            signal_index[key] = sid
            nodes.append(
                {
                    "id": sid,
                    "name": f"{kind}: {value}",
                    "type": "entity",
                    "description": f"signal hub ({kind})",
                    "created_at": datetime.utcnow().isoformat(),
                    "properties": {
                        "source": "snapshot",
                        "signal_type": kind,
                        "value": value,
                    },
                }
            )
            seen_ids.add(sid)
            signal_kind_by_id[sid] = kind
            signal_members.setdefault(sid, set())
            return sid

        existing_edge_keys = set()

        def _add_edge(src: str, dst: str, label: str) -> None:
            if not src or not dst or src == dst:
                return
            if src not in seen_ids or dst not in seen_ids:
                return
            a, b = (src, dst) if src < dst else (dst, src)
            key = (a, b, label)
            if key in existing_edge_keys:
                return
            existing_edge_keys.add(key)
            edges.append({"from": src, "to": dst, "label": label, "type": "signal"})

            # Membership tracking for cohesion edges.
            if src.startswith("signal:") and dst in seen_ids:
                signal_members.setdefault(src, set()).add(dst)
            elif dst.startswith("signal:") and src in seen_ids:
                signal_members.setdefault(dst, set()).add(src)

        for n in nodes:
            if n.get("type") != "memory":
                continue
            props = n.get("properties") if isinstance(n.get("properties"), dict) else {}
            mem_id = str(n.get("id") or "")

            if isinstance(props.get("topic"), str) and props.get("topic").strip():
                sid = _ensure_signal_node("topic", props["topic"].strip())
                _add_edge(mem_id, sid, "HAS_TOPIC")

        # Deterministic memorymemory cohesion edges derived from shared signals.
        try:
            max_per_signal = int(os.getenv("ELEFANTE_SNAPSHOT_COHESION_MAX_PER_SIGNAL", "200"))
        except Exception:
            max_per_signal = 200

        def _add_cohesion_edge(a_id: str, b_id: str, label: str) -> None:
            if not a_id or not b_id or a_id == b_id:
                return
            if a_id not in seen_ids or b_id not in seen_ids:
                return
            x, y = (a_id, b_id) if a_id < b_id else (b_id, a_id)
            key = (x, y, label)
            if key in existing_edge_keys:
                return
            existing_edge_keys.add(key)
            edges.append({"from": a_id, "to": b_id, "label": label, "type": "cohesion"})

        for sid, members in signal_members.items():
            mem_ids = sorted(members)
            if len(mem_ids) < 2:
                continue
            anchor = mem_ids[0]
            kind = signal_kind_by_id.get(sid, "signal")
            label = {
                "topic": "CO_TOPIC",
            }.get(kind, "CO_SIGNAL")
            for other in mem_ids[1 : 1 + max_per_signal]:
                _add_cohesion_edge(anchor, other, label)

        try:
            results = await orchestrator.graph_store.execute_query("MATCH (n:Entity) RETURN n")

            for row in results:
                entity = row.get("n")
                if not entity:
                    continue

                props = {}
                eid = str(entity.id)

                if eid in seen_ids:
                    continue

                extra = {}
                if "props" in entity.properties and isinstance(entity.properties["props"], str):
                    try:
                        extra = json.loads(entity.properties["props"])
                    except Exception:
                        extra = {}

                etype = entity.properties.get("type", "entity")
                if etype == "memory" or extra.get("entity_subtype") == "memory":
                    continue

                node = {
                    "id": eid,
                    "name": entity.properties.get("name", eid[:20]),
                    "type": etype,
                    "description": entity.properties.get("description", ""),
                    "created_at": str(entity.properties.get("created_at", "")),
                    "properties": {"source": "kuzu"}
                }
                node["properties"].update(extra)
                nodes.append(node)
                seen_ids.add(eid)

            edge_results = await orchestrator.graph_store.execute_query(
                "MATCH (a)-[r]->(b) RETURN a.id, b.id, label(r)"
            )

            for row in edge_results:
                src = row.get("a.id")
                dst = row.get("b.id")
                lbl = row.get("label(r)")

                if src and dst:
                    edges.append({
                        "from": src,
                        "to": dst,
                        "label": lbl or "RELATED"
                    })

        except Exception as e:
            self.logger.error(f"Error fetching graph data: {e}")

        snapshot = {
            "generated_at": datetime.utcnow().isoformat(),
            "stats": {
                "total_nodes": len(nodes),
                "memories": sum(1 for n in nodes if n["type"] == "memory"),
                "entities": sum(1 for n in nodes if n["type"] != "memory"),
                "edges": len(edges)
            },
            "nodes": nodes,
            "edges": edges
        }

        output_path = str(DATA_DIR / "dashboard_snapshot.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

        return {
            "success": True,
            "message": f"Dashboard data refreshed. Nodes: {len(nodes)}, Edges: {len(edges)}",
            "stats": snapshot["stats"]
        }

    async def _handle_get_elefante_dashboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-DashboardOpen tool call"""
        refresh = bool(args.get("refresh", False))

        refresh_result = None
        if refresh:
            if not self.mode_manager.is_enabled:
                return self.mode_manager.get_disabled_response("elefante-DashboardOpen")
            refresh_result = await self._refresh_dashboard_snapshot()

        open_result = await self._start_dashboard_and_open()
        result: Dict[str, Any] = {
            "success": True,
            "opened": open_result,
            "refreshed": refresh_result
        }
        return result

    async def _handle_set_elefante_connection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-GraphConnect tool call (Compliance Gate)"""
        # Compliance Gate Check
        gate_result = self._check_compliance_gate("elefante-GraphConnect")
        if gate_result is not None:
            return gate_result
        
        with write_lock() as lock:
            if not lock.acquired:
                return {
                    "success": False,
                    "error": "Could not acquire write lock - another process is writing",
                    "retry": True
                }
            
            orchestrator = await self._get_orchestrator()

        entities_input = args.get("entities") or []
        relationships_input = args.get("relationships") or []
        include_system_status = bool(args.get("include_system_status", False))

        ref_to_entity_id: Dict[str, str] = {}
        created_entities = []

        for item in entities_input:
            ref = item.get("ref")
            if not ref or not isinstance(ref, str):
                raise ValueError("Each entity must include a non-empty 'ref' string")

            if item.get("id"):
                entity_id = validate_uuid(item.get("id"))
                ref_to_entity_id[ref] = str(entity_id)
                created_entities.append({
                    "ref": ref,
                    "entity_id": str(entity_id),
                    "source": "existing"
                })
                continue

            name = item.get("name")
            entity_type = item.get("type")
            if not name or not entity_type:
                raise ValueError("Entity requires either 'id' or both 'name' and 'type'")

            entity = await orchestrator.create_entity(
                name=name,
                entity_type=entity_type,
                properties=item.get("properties")
            )
            ref_to_entity_id[ref] = str(entity.id)
            created_entities.append({
                "ref": ref,
                "entity_id": str(entity.id),
                "name": entity.name,
                "type": entity.type.value,
                "source": "upsert"
            })

        created_relationships = []
        for rel in relationships_input:
            from_id = rel.get("from_entity_id")
            to_id = rel.get("to_entity_id")

            if not from_id and rel.get("from_ref"):
                from_id = ref_to_entity_id.get(rel.get("from_ref"))
            if not to_id and rel.get("to_ref"):
                to_id = ref_to_entity_id.get(rel.get("to_ref"))

            if not from_id or not to_id:
                raise ValueError("Relationship requires from/to via entity_id or ref")

            from_uuid = validate_uuid(from_id)
            to_uuid = validate_uuid(to_id)

            rel_type = self._normalize_relationship_type(rel.get("relationship_type"))
            # Validate enum
            _ = RelationshipType(rel_type)

            relationship = await orchestrator.create_relationship(
                from_entity_id=from_uuid,
                to_entity_id=to_uuid,
                relationship_type=rel_type,
                properties=rel.get("properties")
            )

            created_relationships.append({
                "from_entity_id": str(relationship.from_entity_id),
                "to_entity_id": str(relationship.to_entity_id),
                "type": relationship.relationship_type.value,
                "properties": relationship.properties
            })

        result: Dict[str, Any] = {
            "success": True,
            "entities": created_entities,
            "relationships": created_relationships,
            "entity_ref_map": ref_to_entity_id,
            "message": "Connection workflow completed"
        }

        if include_system_status:
            result["system_status"] = await self._handle_get_system_status({})

        return result



    # ==========================================================================
    # ETL HANDLERS (Agent-Brain Classification)
    # ==========================================================================
    
    async def _handle_etl_process(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-ETLProcess - Get raw memories for agent classification"""
        from src.core.etl import get_etl_processor
        
        etl = get_etl_processor()
        etl.vector_store = (await self._get_orchestrator()).vector_store
        
        limit = args.get("limit", 5)
        raw_memories = await etl.get_raw_memories(limit=limit)
        
        if not raw_memories:
            result = {
                "success": True,
                "count": 0,
                "memories": [],
                "message": "No raw memories to process. All memories are classified."
            }
        else:
            result = {
                "success": True,
                "count": len(raw_memories),
                "memories": raw_memories,
                "instructions": "Analyze each memory and call elefante-ETLClassify with your enrichment. Required: summary (one-line). Optional: concepts (3-5 key terms), surfaces_when (query patterns)."
            }
        
        # include_stats (absorbs former elefante-ETLProcess (include_stats=true))
        if args.get("include_stats", False):
            stats = await etl.get_stats()
            result["stats"] = stats
            result["stats_message"] = f"Total: {stats['total']}, Raw: {stats['raw']}, Processed: {stats['processed']}, Failed: {stats['failed']}"
        
        return result
    
    async def _handle_etl_classify(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-ETLClassify - Apply agent's enrichment (v2.1.0: simplified)"""
        from src.core.etl import get_etl_processor
        
        # Validate required fields first (before acquiring lock)
        required = ["memory_id", "summary"]
        missing = [f for f in required if not args.get(f)]
        if missing:
            return {
                "success": False,
                "error": f"Missing required fields: {missing}"
            }
        
        with write_lock() as lock:
            if not lock.acquired:
                return {
                    "success": False,
                    "error": "Could not acquire write lock - another process is writing",
                    "retry": True
                }
            
            etl = get_etl_processor()
            etl.vector_store = (await self._get_orchestrator()).vector_store
            
            # Apply enrichment
            result = await etl.apply_classification(
                memory_id=args["memory_id"],
                summary=args["summary"][:200],  # Enforce max length
                concepts=args.get("concepts"),
                surfaces_when=args.get("surfaces_when"),
            )
            
            return result
    

    # =========================================================================
    # DIRECTIVE HANDLERS (Always-On Behavioral Constraints)
    # =========================================================================

    def _handle_directive_add(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-DirectiveAdd — add a persistent behavioral constraint."""
        content = args.get("content", "").strip()
        if not content:
            return {"success": False, "error": "Directive content cannot be empty"}

        directive = self.directive_store.add(content)
        return {
            "success": True,
            "directive": directive.to_dict(),
            "total_directives": self.directive_store.count(),
            "message": "Directive stored. It will be injected into every future tool response."
        }

    def _handle_directive_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-DirectiveList — list all directives."""
        directives = self.directive_store.list_all()
        return {
            "success": True,
            "count": len(directives),
            "directives": directives
        }

    def _handle_directive_remove(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-DirectiveRemove — remove a directive by ID."""
        directive_id = args.get("directive_id", "").strip()
        if not directive_id:
            return {"success": False, "error": "directive_id is required"}

        removed = self.directive_store.remove(directive_id)
        if removed:
            return {
                "success": True,
                "directive_id": directive_id,
                "total_directives": self.directive_store.count(),
                "message": "Directive removed. It will no longer appear in tool responses."
            }
        return {
            "success": False,
            "error": f"Directive '{directive_id}' not found"
        }

    def _inject_directives(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject active directives into the tool response.

        This is the core mechanism: directives appear in the data payload
        the agent reads right before deciding its next action.
        Not retrieved by similarity. Not competing with memories.
        Always present. Unconditional.
        """
        active = self.directive_store.get_active_texts()
        if active:
            result["DIRECTIVES"] = active
        return result

    # =========================================================================
    # TASK ORCHESTRATION HANDLERS
    # =========================================================================

    async def _handle_task_create(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-TaskCreate — create a new task node."""
        try:
            with write_lock() as lock:
                if not lock.acquired:
                    return {"success": False, "error": "Could not acquire write lock", "retry": True}
                
                orchestrator = await self._get_orchestrator()
                task_id = await orchestrator.create_task(
                    description=args["description"],
                    parent_id=args.get("parent_id"),
                    blocked_by=args.get("blocked_by"),
                    priority=args.get("priority", 1),
                    assigned_agent=args.get("assigned_agent")
                )
                
                result = {
                    "success": True,
                    "task_id": task_id,
                    "description": args["description"],
                    "status": "pending",
                    "message": f"Task created: {task_id}"
                }
                
                # Inline subtask creation (absorbs former elefante-TaskCreate (subtasks))
                if "subtasks" in args and args["subtasks"]:
                    subtask_ids = await orchestrator.decompose_task(
                        parent_task_id=task_id,
                        subtasks=args["subtasks"]
                    )
                    result["subtask_ids"] = subtask_ids
                    result["subtask_count"] = len(subtask_ids)
                    result["message"] += f" with {len(subtask_ids)} subtasks"
                
                return result
        except ValueError as e:
            return {"success": False, "error": str(e), "tool": "elefante-TaskCreate"}
        except Exception as e:
            self.logger.error(f"Task create failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "tool": "elefante-TaskCreate"}

    async def _handle_task_update(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-TaskUpdate - Update task status/output"""
        try:
            with write_lock() as lock:
                if not lock.acquired:
                    return {"success": False, "error": "Could not acquire write lock", "retry": True}
                
                orchestrator = await self._get_orchestrator()
                success = await orchestrator.update_task(
                    task_id=args["task_id"],
                    status=args.get("status"),
                    output=args.get("output")
                )
                
                return {
                    "success": success,
                    "task_id": args["task_id"],
                    "updated_status": args.get("status"),
                    "message": f"Task {args['task_id']} updated" if success else f"Task {args['task_id']} not found"
                }
        except ValueError as e:
            return {"success": False, "error": str(e), "tool": "elefante-TaskUpdate"}
        except Exception as e:
            self.logger.error(f"Task update failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "tool": "elefante-TaskUpdate"}

    async def _handle_task_graph(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-TaskGraph - Get task hierarchy"""
        try:
            orchestrator = await self._get_orchestrator()
            result = await orchestrator.get_task_graph(
                task_id=args.get("task_id")
            )
            
            return {
                "success": True,
                "data": result
            }
        except Exception as e:
            self.logger.error(f"Task graph query failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "tool": "elefante-TaskGraph"}


    
    async def run(self):
        """Run the MCP server"""
        self.logger.info("Starting Elefante MCP Server...")
        
        # Pre-initialize orchestrator to load embedding model BEFORE handling requests
        # This prevents timeout issues on first tool call
        self.logger.info("Pre-initializing orchestrator and embedding model...")
        try:
            orchestrator = await self._get_orchestrator()
            # Trigger model loading by generating a test embedding
            await orchestrator.embedding_service.generate_embedding("initialization test")
            self.logger.info("Orchestrator and embedding model initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to pre-initialize orchestrator: {e}")
            # Continue anyway - will lazy load on first request
        
        async with stdio_server() as (read_stream, write_stream):
            self.logger.info("MCP Server running on stdio")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for MCP server"""
    server = ElefanteMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())


