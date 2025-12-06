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

logger = get_logger(__name__)


class ElefanteMCPServer:
    """
    MCP Server for Elefante Memory System
    
    Exposes memory operations as MCP tools:
    - addMemory: Store new memories
    - searchMemories: Search with semantic/structured/hybrid modes
    - queryGraph: Execute Cypher queries on knowledge graph
    - getContext: Retrieve session context
    - createEntity: Create entities in knowledge graph
    - createRelationship: Link entities with relationships
    - getStats: Get system statistics
    """
    
    def __init__(self):
        """Initialize MCP server with lazy loading"""
        self.server = Server("elefante-memory")
        self.orchestrator = None # Lazy loaded
        self.logger = get_logger(self.__class__.__name__)
        
        # Register tool handlers
        self._register_handlers()
        
        self.logger.info("Elefante MCP Server initialized (Lazy Loading enabled)")

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
                    name="addMemory",
                    description="""Store a new memory in Elefante's dual-database system.

**YOU ARE ELEFANTE'S BRAIN** - You must classify the memory as you store it:
- **domain**: What context? work/personal/learning/project/reference/system
- **category**: What topic? Use lowercase-hyphenated (e.g., 'elefante', 'python', 'debugging')
- **memory_type**: What kind? fact/insight/decision/preference/code/task/note
- **importance**: How critical? 1-10 (8+ for preferences, decisions, critical facts)

ALWAYS provide domain, category, and memory_type. You understand the content - classify it.

INTELLIGENT INGESTION: The system automatically detects duplicates (REDUNDANT), related memories (RELATED), or contradictions (CONTRADICTORY) and links to existing knowledge.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The memory content to store"
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
                            }
                        },
                        "required": ["content"]
                    }
                ),
                types.Tool(
                    name="searchMemories",
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
                    name="queryGraph",
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
                    name="getContext",
                    description="Retrieve comprehensive context from Elefante's memory system for a specific session or task. Returns related memories from ChromaDB, connected entities and relationships from Kuzu graph, with configurable traversal depth. Use this to gather full context before making decisions or generating responses.",
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
                    name="createEntity",
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
                    name="createRelationship",
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
                    name="getEpisodes",
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
                    name="getStats",
                    description="Get comprehensive statistics about Elefante's memory system health and usage. Returns metrics for ChromaDB (vector store size, embedding dimensions) and Kuzu (graph node/edge counts, relationship types), plus system performance indicators. Use for monitoring, debugging, or understanding memory system state.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="consolidateMemories",
                    description="Trigger a background process to analyze recent memories, merge duplicates, and resolve contradictions. Use this when you notice the user is getting inconsistent information or when the memory search returns too many near-identical results. This process uses an LLM to synthesize facts and update the knowledge graph.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "force": {
                                "type": "boolean",
                                "description": "Force consolidation even if threshold not met",
                                "default": False
                            }
                        }
                    }
                ),
                types.Tool(
                    name="listAllMemories",
                    description="Retrieve ALL memories from the database without semantic filtering. This tool bypasses semantic search and returns memories directly from ChromaDB, making it ideal for: database inspection, debugging, exporting all memories, browsing complete memory collection, or when you need a comprehensive view. For relevance-based search, use searchMemories instead. Supports pagination and optional filtering by memory_type, importance, etc.",
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
                    name="openDashboard",
                    description="Launch and open the Elefante Knowledge Garden Dashboard in the user's browser. This visual interface allows the user to explore their memory graph, view connections between concepts, and filter by 'Spaces'. Use this when the user wants to 'see' their memory or explore the knowledge graph visually.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
            self.logger.info(f"=== Returning {len(tools)} tools to MCP client ===")
            return tools
        

        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool calls"""
            self.logger.info(f"Tool called: {name}", arguments=arguments)
            
            try:
                if name == "addMemory":
                    result = await self._handle_add_memory(arguments)
                elif name == "searchMemories":
                    result = await self._handle_search_memories(arguments)
                elif name == "queryGraph":
                    result = await self._handle_query_graph(arguments)
                elif name == "getContext":
                    result = await self._handle_get_context(arguments)
                elif name == "createEntity":
                    result = await self._handle_create_entity(arguments)
                elif name == "createRelationship":
                    result = await self._handle_create_relationship(arguments)
                elif name == "getEpisodes":
                    result = await self._handle_get_episodes(arguments)
                elif name == "listAllMemories":
                    result = await self._handle_list_all_memories(arguments)
                elif name == "getStats":
                    result = await self._handle_get_stats(arguments)
                elif name == "consolidateMemories":
                    result = await self._handle_consolidate_memories(arguments)
                elif name == "openDashboard":
                    result = await self._handle_open_dashboard(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
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
    
    async def _handle_add_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle addMemory tool call - now uses shared singleton connection"""
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
            importance=args.get("importance", 5),
            tags=args.get("tags"),
            entities=args.get("entities"),
            metadata=metadata if metadata else None
        )
        
        return {
            "success": True,
            "memory_id": str(memory.id),
            "message": "Memory stored successfully (shared connection with dashboard)",
            "memory": memory.to_dict()
        }
    
    async def _handle_search_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle searchMemories tool call"""
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
        
        return {
            "success": True,
            "count": len(results),
            "results": [result.to_dict() for result in results]
        }
    
    async def _handle_query_graph(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle queryGraph tool call"""
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
        """Handle getContext tool call"""
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
        """Handle createEntity tool call"""
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
        """Handle createRelationship tool call"""
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
    
    async def _handle_get_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle getStats tool call"""
        orchestrator = await self._get_orchestrator()
        stats = await orchestrator.get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    
    async def _handle_list_all_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle listAllMemories tool call"""
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
        """Handle consolidateMemories tool call"""
        orchestrator = await self._get_orchestrator()
        result = await orchestrator.consolidate_memories(
            force=args.get("force", False)
        )
        return result
    
    async def _handle_get_episodes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle getEpisodes tool call"""
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
    
    async def _handle_open_dashboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle openDashboard tool call"""
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
                DASHBOARD_STARTED = True # Assume it's running
        
        # Open browser
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