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
from src.models.query import QueryMode, SearchFilters
from src.models.entity import EntityType, RelationshipType
from src.utils.logger import get_logger
from src.utils.validators import validate_memory_content, validate_uuid
from src.utils.elefante_mode import get_mode_manager, is_elefante_enabled, write_lock

logger = get_logger(__name__)

# Tools that do NOT require Elefante Mode to be enabled
# These are safe to call even when databases are locked by another IDE
SAFE_TOOLS = {
    "elefanteSystemEnable",
    "elefanteSystemDisable",
    "elefanteSystemStatusGet",
    "elefanteDashboardOpen",
}


class ElefanteMCPServer:
    """
    MCP Server for Elefante Memory System
    
    Exposes memory operations as MCP tools:
    - elefanteMemoryAdd: Store new memories
    - elefanteMemorySearch: Search with semantic/structured/hybrid modes
    - elefanteGraphQuery: Execute Cypher queries on knowledge graph
    - elefanteContextGet: Retrieve session context
    - elefanteGraphEntityCreate: Create entities in knowledge graph
    - elefanteGraphRelationshipCreate: Link entities with relationships
    - elefanteSystemStatusGet: Get system status and statistics
    """
    
    def __init__(self):
        """Initialize MCP server with lazy loading"""
        self.server = Server("elefante")
        self.orchestrator = None # Lazy loaded
        self.logger = get_logger(self.__class__.__name__)
        self.mode_manager = get_mode_manager()  # Elefante Mode manager (v1.1.0 - transaction-scoped)
        
        # v1.6.0 Compliance Gate: Session state for search-before-write enforcement
        self._compliance_state = {
            "search_performed": False,
            "search_count": 0,
            "search_timestamp": None,
            "last_query": None
        }
        
        # Register tool handlers
        self._register_handlers()
        
        self.logger.info("Elefante MCP Server initialized (v1.6.0 - Compliance Gate)")

    def _inject_pitfalls(self, result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """
        SURGICAL INJECTION (v1.0.1): 
        Injects mandatory protocols and known pitfalls directly into the tool response.
        This ensures the agent CANNOT ignore them, as they are part of the data payload.
        """
        pitfalls = [
            "CRITICAL PROTOCOL: You MUST check for existing memories before creating new ones to avoid duplication.",
            "CRITICAL PROTOCOL: If you are debugging, you MUST read the relevant 'Neural Register' in docs/debug/ first.",
            "CRITICAL PROTOCOL: Do not rely on your internal knowledge base for project specifics; use the memory system."
        ]
        
        # Context-specific injections
        if tool_name == "elefanteMemoryAdd":
            pitfalls.append("WARNING - MEMORY INTEGRITY: Ensure 'layer' and 'sublayer' are correctly classified. Do not default to 'world/fact' if unsure.")
        
        if tool_name == "elefanteMemorySearch":
             pitfalls.append("WARNING - SEARCH BIAS: If results are empty, try broader terms. Do not assume non-existence without a semantic search.")
             pitfalls.append("WARNING - CONTRADICTIONS: If you find contradictory memories, prioritize the most recent one but note the conflict.")

        if tool_name in [
            "elefanteGraphQuery",
            "elefanteGraphEntityCreate",
            "elefanteGraphRelationshipCreate",
        ]:
            pitfalls.append("WARNING - GRAPH CONSISTENCY: Ensure entity types match the allowed enum values. Do not invent new types without updating the schema.")

        if tool_name == "elefanteGraphConnect":
            pitfalls.append("WARNING - WORKFLOW: Prefer stable entity names/types and reuse existing entities. Avoid creating near-duplicates that only differ by punctuation or casing.")

        if tool_name == "elefanteDashboardOpen":
            pitfalls.append("WARNING - DASHBOARD: If refresh=true, this reads from databases and requires Elefante Mode to be enabled.")

        # Add to result with a key that demands attention
        # Developer Etiquette V1.2 (canonical) — concise enforcement reminder.
        pitfalls.append(
            "DEVELOPER ETIQUETTE v1.2 (docs/technical/developer-etiquette.md): Context-first; label UNKNOWN; no fabrication; reuse existing artifacts; for non-trivial work follow SPEC→DESIGN→TASKS→IMPLEMENT→VERIFY; verify before claiming done; keep outputs concise."
        )
        result["MANDATORY_PROTOCOLS_READ_THIS_FIRST"] = pitfalls
        return result

    def _check_compliance_gate(self, tool_name: str) -> Dict[str, Any] | None:
        """
        v1.6.0 Compliance Gate: Enforce search-before-write rule.
        
        Returns None if gate passes, or an error dict if gate blocks.
        Write operations are blocked until elefanteMemorySearch has been called.
        """
        # Tools that require prior search (write operations)
        GATED_TOOLS = {
            "elefanteMemoryAdd",
            "elefanteGraphEntityCreate", 
            "elefanteGraphRelationshipCreate",
            "elefanteGraphConnect",
        }
        
        if tool_name not in GATED_TOOLS:
            return None  # Gate passes - not a gated tool
        
        if self._compliance_state["search_performed"]:
            return None  # Gate passes - search was performed
        
        # GATE BLOCKED
        self.logger.warning(f"Compliance Gate BLOCKED: {tool_name} called without prior search")
        return {
            "success": False,
            "error": "⛔ COMPLIANCE GATE: Search required before write operations.",
            "gate_status": "BLOCKED",
            "action_required": "Call elefanteMemorySearch first to check for existing/related memories.",
            "reason": "This prevents duplicate memories and ensures you have full context before adding new knowledge.",
            "blocked_tool": tool_name,
            "hint": f"Try: elefanteMemorySearch with a query related to what you want to store."
        }
    
    def _reset_compliance_gate(self):
        """Reset compliance state (e.g., after session ends or on explicit reset)"""
        self._compliance_state = {
            "search_performed": False,
            "search_count": 0,
            "search_timestamp": None,
            "last_query": None
        }
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
                    name="elefanteMemoryAdd",
                    description="""Store a new memory in Elefante's dual-database system.

**YOU ARE ELEFANTE'S BRAIN** - You must classify the memory as you store it:
- **layer**: self (who), world (what), intent (do)
- **sublayer**: 
  - SELF: identity, preference, constraint
  - WORLD: fact, failure, method
  - INTENT: rule, goal, anti-pattern
- **importance**: How critical? 1-10 (8+ for preferences, decisions, critical facts)

ALWAYS provide layer and sublayer. You understand the content - classify it.

INTELLIGENT INGESTION: The system automatically detects duplicates (REDUNDANT), related memories (RELATED), or contradictions (CONTRADICTORY) and links to existing knowledge.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The memory content to store"
                            },
                            "layer": {
                                "type": "string",
                                "enum": ["self", "world", "intent"],
                                "description": "Memory layer (self/world/intent)"
                            },
                            "sublayer": {
                                "type": "string",
                                "description": "Memory sublayer (e.g. identity, fact, rule)"
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["conversation", "fact", "insight", "code", "decision", "task", "note", "preference"],
                                "default": "conversation",
                                "description": "Type of memory - YOU MUST CLASSIFY THIS"
                            },
                            "domain": {
                                "type": "string",
                                "enum": ["work", "personal", "learning", "project", "reference", "system"],
                                "description": "High-level context - YOU MUST CLASSIFY THIS"
                            },
                            "category": {
                                "type": "string",
                                "description": "Topic grouping (e.g., 'elefante', 'python', 'user-preferences') - YOU MUST CLASSIFY THIS"
                            },
                            "importance": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "default": 5,
                                "description": "Importance level (1-10). Use 8+ for preferences, decisions, critical facts"
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
                    name="elefanteMemorySearch",
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
                                    "min_importance": {"type": "integer", "minimum": 1, "maximum": 10},
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
                            }
                        },
                        "required": ["query"]
                    }
                ),
                types.Tool(
                    name="elefanteGraphQuery",
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
                    name="elefanteContextGet",
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
                types.Tool(
                    name="elefanteGraphEntityCreate",
                    description="Create a new entity node in Elefante's Kuzu knowledge graph. Entities represent people, projects, files, concepts, technologies, tasks, organizations, locations, or events. These nodes can be linked via relationships to build a rich semantic network of knowledge.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Entity name"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["person", "project", "file", "concept", "technology", "task", "organization", "location", "event", "custom"],
                                "description": "Entity type"
                            },
                            "properties": {
                                "type": "object",
                                "description": "Additional properties"
                            }
                        },
                        "required": ["name", "type"]
                    }
                ),
                types.Tool(
                    name="elefanteGraphRelationshipCreate",
                    description="Create a directed relationship edge in Elefante's Kuzu knowledge graph connecting two existing entities. Relationships define how entities relate (e.g., 'depends_on', 'part_of', 'created_by') and enable graph traversal queries to discover connections and patterns.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_entity_id": {
                                "type": "string",
                                "description": "Source entity UUID"
                            },
                            "to_entity_id": {
                                "type": "string",
                                "description": "Target entity UUID"
                            },
                            "relationship_type": {
                                "type": "string",
                                "enum": ["relates_to", "depends_on", "part_of", "created_by", "references", "blocks", "implements", "uses", "custom"],
                                "description": "Relationship type"
                            },
                            "properties": {
                                "type": "object",
                                "description": "Additional properties"
                            }
                        },
                        "required": ["from_entity_id", "to_entity_id", "relationship_type"]
                    }
                ),
                types.Tool(
                    name="elefanteSessionsList",
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
                    name="elefanteSystemStatusGet",
                    description="Get combined system status and statistics for Elefante. Includes Elefante Mode state (enabled/disabled), lock status, and when enabled, database health/usage statistics from the orchestrator.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="elefanteMemoryConsolidate",
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
                types.Tool(
                    name="elefanteMemoryListAll",
                    description="Retrieve ALL memories from the database without semantic filtering. This tool bypasses semantic search and returns memories directly from ChromaDB, making it ideal for: database inspection, debugging, exporting all memories, browsing complete memory collection, or when you need a comprehensive view. For relevance-based search, use elefanteMemorySearch instead. Supports pagination and optional filtering by memory_type, importance, etc.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "default": 100,
                                "minimum": 1,
                                "maximum": 500,
                                "description": "Maximum number of memories to return"
                            },
                            "offset": {
                                "type": "integer",
                                "default": 0,
                                "minimum": 0,
                                "description": "Number of memories to skip (for pagination)"
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "memory_type": {
                                        "type": "string",
                                        "description": "Filter by memory type (conversation, fact, insight, code, decision, task, note)"
                                    },
                                    "min_importance": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 10,
                                        "description": "Minimum importance level"
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Filter by tags"
                                    }
                                },
                                "description": "Optional filters to apply"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="elefanteMemoryMigrateToV3",
                    description="[ADMIN] Migrate all memories to V3 Schema (Layer/Sublayer). Runs in-process to avoid database locks. Iterates through all memories, re-classifies them, and updates both Vector and Graph stores.",
                    inputSchema={
                         "type": "object",
                         "properties": {
                             "limit": {"type": "integer", "default": 500}
                         }
                    }
                ),
                types.Tool(
                    name="elefanteDashboardOpen",
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
                    name="elefanteGraphConnect",
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
                                "description": "If true, include elefanteSystemStatusGet output in the response."
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                types.Tool(
                    name="elefanteSystemEnable",
                    description="""**REQUIRED FIRST STEP**: Enable Elefante Mode to activate the memory system.

Elefante starts in DISABLED mode by default for multi-IDE safety. You MUST call this tool before using any memory operations (elefanteMemoryAdd, elefanteMemorySearch, etc.).

This tool:
1. Acquires exclusive locks on ChromaDB and Kuzu databases
2. Enables full memory system functionality
3. Activates protocol enforcement

If another IDE is using Elefante, this will fail gracefully with lock information.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "force": {
                                "type": "boolean",
                                "default": False,
                                "description": "Force enable (use with caution - may cause conflicts)"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="elefanteSystemDisable",
                    description="""Disable Elefante Mode and release all database locks.

Use this when:
- Switching to another IDE that needs Elefante access
- Finishing a session and allowing other processes to access the databases
- Troubleshooting lock-related issues

This will gracefully close connections and clear all locks.""",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                # =====================================================================
                # ETL TOOLS (Agent-Brain Classification)
                # =====================================================================
                types.Tool(
                    name="elefanteETLProcess",
                    description="""**PHASE 2 ETL**: Get unclassified memories for YOU (the agent) to classify.

This returns raw memories that need V5 topology classification. YOU must analyze each one and call elefanteETLClassify with your classification.

V5 Topology Schema:
- **ring**: core (immutable truths) | domain (preferences, identity) | topic (project-specific) | leaf (ephemeral)
- **knowledge_type**: law | principle | method | decision | insight | preference | fact
- **topic**: coding-standards | communication | workflow | agent-behavior | tools-environment | collaboration | general
- **summary**: One-line description

Flow:
1. Call elefanteETLProcess(limit=5) → Get raw memories
2. Analyze each memory using your LLM brain
3. Call elefanteETLClassify for each with your classification""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Number of raw memories to process"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="elefanteETLClassify",
                    description="""**PHASE 2 ETL**: Submit YOUR classification for a memory.

After analyzing a memory from elefanteETLProcess, call this to store your V5 classification.

Required fields:
- memory_id: From elefanteETLProcess
- ring: core | domain | topic | leaf
- knowledge_type: law | principle | method | decision | insight | preference | fact
- topic: coding-standards | communication | workflow | agent-behavior | tools-environment | collaboration | general
- summary: One-line description (max 200 chars)""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "Memory UUID from elefanteETLProcess"
                            },
                            "ring": {
                                "type": "string",
                                "enum": ["core", "domain", "topic", "leaf"],
                                "description": "Topology ring: core=immutable, domain=identity, topic=project, leaf=ephemeral"
                            },
                            "knowledge_type": {
                                "type": "string",
                                "enum": ["law", "principle", "method", "decision", "insight", "preference", "fact"],
                                "description": "Type of knowledge"
                            },
                            "topic": {
                                "type": "string",
                                "enum": ["coding-standards", "communication", "workflow", "agent-behavior", "tools-environment", "collaboration", "general"],
                                "description": "Topic cluster"
                            },
                            "summary": {
                                "type": "string",
                                "description": "One-line summary (max 200 chars)"
                            }
                        },
                        "required": ["memory_id", "ring", "knowledge_type", "topic", "summary"]
                    }
                ),
                types.Tool(
                    name="elefanteETLStatus",
                    description="Get ETL processing statistics: how many memories are raw, processing, processed, or failed.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
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

**YOU MUST first call `elefanteMemorySearch`** with a specific query.

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
                    results = await orchestrator.search(
                        query=topic,
                        mode=QueryMode.HYBRID,
                        limit=5,
                        min_similarity=0.3
                    )
                    
                    if results:
                        memory_text = "\\n\\n".join([
                            f"**Memory [{i+1}]** (score: {r.score:.2f}):\\n{r.content}"
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
                if name == "elefanteSystemEnable":
                    result = await self._handle_enable_elefante(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefanteSystemDisable":
                    result = await self._handle_disable_elefante(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefanteSystemStatusGet":
                    result = await self._handle_get_system_status(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefanteDashboardOpen":
                    result = await self._handle_get_elefante_dashboard(arguments)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                
                # v2.0.0: Mode check removed - operations auto-acquire/release locks
                # Write operations use write_lock() context manager internally
                
                if name == "elefanteMemoryAdd":
                    result = await self._handle_add_memory(arguments)
                elif name == "elefanteMemorySearch":
                    result = await self._handle_search_memories(arguments)
                elif name == "elefanteGraphQuery":
                    result = await self._handle_query_graph(arguments)
                elif name == "elefanteContextGet":
                    result = await self._handle_get_context(arguments)
                elif name == "elefanteGraphEntityCreate":
                    result = await self._handle_create_entity(arguments)
                elif name == "elefanteGraphRelationshipCreate":
                    result = await self._handle_create_relationship(arguments)
                elif name == "elefanteSessionsList":
                    result = await self._handle_get_episodes(arguments)
                elif name == "elefanteMemoryListAll":
                    result = await self._handle_list_all_memories(arguments)
                elif name == "elefanteMemoryConsolidate":
                    result = await self._handle_consolidate_memories(arguments)
                elif name == "elefanteMemoryMigrateToV3":
                    result = await self._handle_migrate_memories_v3(arguments)
                elif name == "elefanteGraphConnect":
                    result = await self._handle_set_elefante_connection(arguments)
                # ETL Tools (Agent-Brain Classification)
                elif name == "elefanteETLProcess":
                    result = await self._handle_etl_process(arguments)
                elif name == "elefanteETLClassify":
                    result = await self._handle_etl_classify(arguments)
                elif name == "elefanteETLStatus":
                    result = await self._handle_etl_status(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                # INJECT PITFALLS (v1.0.1)
                # Ensure the agent sees the protocols by embedding them in the response
                if isinstance(result, dict):
                    result = self._inject_pitfalls(result, name)

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
    
    async def _handle_enable_elefante(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteSystemEnable tool call - Activate Elefante Mode"""
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
        """Handle elefanteSystemDisable tool call - Deactivate Elefante Mode"""
        result = self.mode_manager.disable()
        
        # Clear orchestrator reference
        if result["success"]:
            self.orchestrator = None
        
        return result

    async def _handle_get_system_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteSystemStatusGet tool call - Combined mode + stats"""
        status: Dict[str, Any] = {
            "success": True,
            "mode": "enabled" if self.mode_manager.is_enabled else "disabled",
            "status": self.mode_manager.status,
            "lock_status": self.mode_manager.check_locks(),
        }

        if not self.mode_manager.is_enabled:
            status["stats"] = None
            status["message"] = "Elefante Mode is DISABLED - call elefanteSystemEnable to activate"
            return status

        orchestrator = await self._get_orchestrator()
        stats = await orchestrator.get_stats()
        status["stats"] = stats
        status["message"] = "Elefante Mode is ENABLED"
        return status

    async def _handle_add_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteMemoryAdd tool call - Authoritative Pipeline (v1.6.0: Compliance Gate)"""
        # v1.6.0 Compliance Gate Check
        gate_result = self._check_compliance_gate("elefanteMemoryAdd")
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
            
        # Add layer/sublayer to metadata - AUTHORITATIVE
        if args.get("layer"):
            metadata["layer"] = args["layer"]
        if args.get("sublayer"):
            metadata["sublayer"] = args["sublayer"]
            
        # Note: We removed the local classifier fallback. 
        # The Orchestrator's 5-Step Pipeline handles validation and defaults.
        
        memory = await orchestrator.add_memory(
            content=args["content"],
            memory_type=args.get("memory_type", "conversation"),
            importance=args.get("importance", 5),
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
            "layer": memory.metadata.layer,
            "sublayer": memory.metadata.sublayer,
            "importance": memory.metadata.importance,
            "memory_id": str(memory.id)
        }
    
    async def _handle_search_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteMemorySearch tool call"""
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
                min_importance=filter_data.get("min_importance"),
                max_importance=filter_data.get("max_importance"),
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
            min_similarity=args.get("min_similarity", 0.3),
            include_conversation=args.get("include_conversation", True),
            include_stored=args.get("include_stored", True),
            session_id=session_id
        )
        
        response = {
            "success": True,
            "count": len(results),
            "results": [result.to_dict() for result in results]
        }
        
        # v1.6.0 Compliance Gate: Mark search as performed
        self._compliance_state["search_performed"] = True
        self._compliance_state["search_count"] = len(results)
        self._compliance_state["search_timestamp"] = datetime.utcnow()
        self._compliance_state["last_query"] = args["query"]
        
        # Add compliance stamp to response
        if len(results) > 0:
            response["compliance_stamp"] = f"[ELEFANTE] Searched: Found {len(results)} relevant memories"
        else:
            response["compliance_stamp"] = "[ELEFANTE] Searched: No relevant memories found"
        
        response["gate_status"] = "UNLOCKED"  # Write operations now allowed

        return response
    
    async def _handle_query_graph(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteGraphQuery tool call"""
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
        """Handle elefanteContextGet tool call"""
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
    
    async def _handle_create_entity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteGraphEntityCreate tool call (v1.6.0: Compliance Gate)"""
        # v1.6.0 Compliance Gate Check
        gate_result = self._check_compliance_gate("elefanteGraphEntityCreate")
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
            entity = await orchestrator.create_entity(
                name=args["name"],
                entity_type=args["type"],
                properties=args.get("properties")
            )
            
            return {
                "success": True,
                "entity_id": str(entity.id),
                "message": "Entity created successfully",
                "entity": entity.to_dict()
            }
    
    async def _handle_create_relationship(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteGraphRelationshipCreate tool call (v1.6.0: Compliance Gate)"""
        # v1.6.0 Compliance Gate Check
        gate_result = self._check_compliance_gate("elefanteGraphRelationshipCreate")
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
            relationship = await orchestrator.create_relationship(
                from_entity_id=UUID(args["from_entity_id"]),
                to_entity_id=UUID(args["to_entity_id"]),
                relationship_type=args["relationship_type"],
                properties=args.get("properties")
            )
            
            return {
                "success": True,
                "message": "Relationship created successfully",
                "relationship": {
                    "from_entity_id": str(relationship.from_entity_id),
                    "to_entity_id": str(relationship.to_entity_id),
                    "type": relationship.relationship_type.value,
                    "properties": relationship.properties
                }
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
        """Handle elefanteMemoryListAll tool call"""
        orchestrator = await self._get_orchestrator()
        
        # Parse filters if provided
        filters = None
        if "filters" in args and args["filters"]:
            filter_data = args["filters"]
            filters = SearchFilters(
                memory_type=filter_data.get("memory_type"),
                domain=filter_data.get("domain"),
                category=filter_data.get("category"),
                min_importance=filter_data.get("min_importance"),
                max_importance=filter_data.get("max_importance"),
                tags=filter_data.get("tags")
            )
        
        # Get all memories
        memories = await orchestrator.list_all_memories(
            limit=args.get("limit", 100),
            offset=args.get("offset", 0),
            filters=filters
        )
        
        return {
            "success": True,
            "count": len(memories),
            "memories": [memory.to_dict() for memory in memories]
        }
    
    async def _handle_consolidate_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteMemoryConsolidate tool call (v2.0.0: transaction-scoped)"""
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
        """Handle elefanteSessionsList tool call"""
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
                serve_dashboard_in_thread(port=port)
                DASHBOARD_STARTED = True
                self.logger.info(f"Dashboard server started on port {port}")
            except Exception as e:
                # It might already be running (e.g. from another instance or previous run)
                self.logger.warning(f"Failed to start dashboard server (might be running): {e}")
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
            ring = cm.get("ring")
            knowledge_type = cm.get("knowledge_type")
            topic = cm.get("topic")
            summary = cm.get("summary")
            owner_id = cm.get("owner_id")

            node = {
                "id": str(mem.id),
                "name": name,
                "type": "memory",
                "description": mem.content,
                "created_at": mem.metadata.created_at.isoformat(),
                "properties": {
                    "content": mem.content,
                    "memory_type": mem.metadata.memory_type.value if hasattr(mem.metadata.memory_type, "value") else str(mem.metadata.memory_type),
                    "importance": mem.metadata.importance,
                    "layer": getattr(mem.metadata, "layer", "world"),
                    "sublayer": getattr(mem.metadata, "sublayer", "fact"),
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
                    "ring": ring,
                    "knowledge_type": knowledge_type,
                    "topic": topic,
                    "summary": summary,
                    "owner_id": owner_id,
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

        # Add "signal hub" nodes/edges (topic / knowledge_type / ring) so the
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
                    "description": f"V5 signal hub ({kind})",
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

            if isinstance(props.get("knowledge_type"), str) and props.get("knowledge_type").strip():
                sid = _ensure_signal_node("knowledge_type", props["knowledge_type"].strip())
                _add_edge(mem_id, sid, "HAS_KNOWLEDGE_TYPE")

            if isinstance(props.get("ring"), str) and props.get("ring").strip():
                sid = _ensure_signal_node("ring", props["ring"].strip())
                _add_edge(mem_id, sid, "IN_RING")

        # Deterministic memory↔memory cohesion edges derived from shared signals.
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
                "knowledge_type": "CO_KNOWLEDGE_TYPE",
                "ring": "CO_RING",
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
        """Handle elefanteDashboardOpen tool call"""
        refresh = bool(args.get("refresh", False))

        refresh_result = None
        if refresh:
            if not self.mode_manager.is_enabled:
                return self.mode_manager.get_disabled_response("elefanteDashboardOpen")
            refresh_result = await self._refresh_dashboard_snapshot()

        open_result = await self._start_dashboard_and_open()
        result: Dict[str, Any] = {
            "success": True,
            "opened": open_result,
            "refreshed": refresh_result
        }
        return result

    async def _handle_set_elefante_connection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteGraphConnect tool call (v1.6.0: Compliance Gate)"""
        # v1.6.0 Compliance Gate Check
        gate_result = self._check_compliance_gate("elefanteGraphConnect")
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

    async def _handle_migrate_memories_v3(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteMemoryMigrateToV3 tool call (v2.0.0: transaction-scoped)"""
        # Note: This is a long-running operation. We acquire lock per-batch to allow
        # other operations to interleave. Full migration may take multiple lock cycles.
        self.logger.info("Starting V3 Migration (In-Process)...")
        
        with write_lock(timeout=30) as lock:  # Longer timeout for migration
            if not lock.acquired:
                return {
                    "success": False,
                    "error": "Could not acquire write lock - another process is writing",
                    "retry": True
                }
            
            orchestrator = await self._get_orchestrator()
            
            limit = args.get("limit", 500)
            offset = 0
            total_migrated = 0
            errors = 0
            
            from src.core.classifier import classify_memory
        
        # Helper for JSON serialization
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, 'value'): # Enum
                return obj.value
            raise TypeError(f"Type {type(obj)} not serializable")
            
        while True:
            # Fetch batch
            try:
                memories = await orchestrator.vector_store.get_all(limit=limit, offset=offset)
            except Exception as e:
                # Fallback if get_all not available or fails
                self.logger.error(f"Failed to fetch memories: {e}")
                break
                
            if not memories:
                break
                
            for mem in memories:
                try:
                    # Classify
                    content = mem.content
                    layer, sublayer = classify_memory(content)
                    
                    # Update Metadata
                    mem.metadata.layer = layer
                    mem.metadata.sublayer = sublayer
                    
                    # Update Vector Store (Delete + Add)
                    await orchestrator.vector_store.delete_memory(mem.id)
                    await orchestrator.vector_store.add_memory(mem)
                    
                    # Update Graph Store properties
                    props = {
                        "content": content[:200],
                        "full_content": content,
                        "title": mem.metadata.custom_metadata.get("title", f"Memory {mem.id}"),
                        "layer": layer,
                        "sublayer": sublayer,
                        "memory_type": mem.metadata.memory_type.value if hasattr(mem.metadata.memory_type, "value") else str(mem.metadata.memory_type),
                        "importance": mem.metadata.importance,
                        "status": mem.metadata.status.value if hasattr(mem.metadata.status, "value") else str(mem.metadata.status),
                        "timestamp": mem.metadata.created_at.isoformat() if isinstance(mem.metadata.created_at, datetime) else mem.metadata.created_at,
                        "entity_subtype": "memory"
                    }
                    
                    props_json = json.dumps(props, default=json_serializer).replace("'", "\\'")
                    
                    cypher = f"MATCH (e:Entity) WHERE e.id = '{str(mem.id)}' SET e.props = '{props_json}' RETURN e.id"
                    await orchestrator.graph_store.execute_query(cypher)
                    
                    total_migrated += 1
                    
                except Exception as e:
                    self.logger.error(f"Error migrating {mem.id}: {e}")
                    errors += 1
            
            offset += limit
            if len(memories) < limit:
                break
                
        return {
            "success": True,
            "migrated_count": total_migrated,
            "errors": errors,
            "message": f"Migrated {total_migrated} memories to V3 Schema"
        }

    # ==========================================================================
    # ETL HANDLERS (Agent-Brain Classification)
    # ==========================================================================
    
    async def _handle_etl_process(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteETLProcess - Get raw memories for agent classification"""
        from src.core.etl import get_etl_processor
        
        etl = get_etl_processor()
        etl.vector_store = (await self._get_orchestrator()).vector_store
        
        limit = args.get("limit", 5)
        raw_memories = await etl.get_raw_memories(limit=limit)
        
        if not raw_memories:
            return {
                "success": True,
                "count": 0,
                "memories": [],
                "message": "No raw memories to process. All memories are classified."
            }
        
        return {
            "success": True,
            "count": len(raw_memories),
            "memories": raw_memories,
            "instructions": "Analyze each memory and call elefanteETLClassify with your classification. Use V5 schema: ring (core/domain/topic/leaf), knowledge_type (law/principle/method/decision/insight/preference/fact), topic (coding-standards/communication/workflow/agent-behavior/tools-environment/collaboration/general), summary (one-line)."
        }
    
    async def _handle_etl_classify(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteETLClassify - Apply agent's classification (v2.0.0: transaction-scoped)"""
        from src.core.etl import get_etl_processor
        
        # Validate required fields first (before acquiring lock)
        required = ["memory_id", "ring", "knowledge_type", "topic", "summary"]
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
            
            # Apply classification
            result = await etl.apply_classification(
                memory_id=args["memory_id"],
                ring=args["ring"],
                knowledge_type=args["knowledge_type"],
                topic=args["topic"],
                summary=args["summary"][:200],  # Enforce max length
                owner_id=args.get("owner_id", "owner-jay")
            )
            
            return result
    
    async def _handle_etl_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefanteETLStatus - Get processing stats"""
        from src.core.etl import get_etl_processor
        
        etl = get_etl_processor()
        etl.vector_store = (await self._get_orchestrator()).vector_store
        
        stats = await etl.get_stats()
        
        return {
            "success": True,
            **stats,
            "message": f"Total: {stats['total']}, Raw: {stats['raw']}, Processed: {stats['processed']}, Failed: {stats['failed']}"
        }


    
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


# Made with Bob