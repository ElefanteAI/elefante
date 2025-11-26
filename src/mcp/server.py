"""
MCP Server implementation for Elefante Memory System

This server exposes memory operations as MCP tools that can be called
from IDEs and other MCP clients. It provides a standardized interface
for AI assistants to store and retrieve memories.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime
from uuid import UUID

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

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
        """Initialize MCP server with Elefante orchestrator"""
        self.server = Server("elefante-memory")
        self.orchestrator = get_orchestrator()
        self.logger = get_logger(self.__class__.__name__)
        
        # Register tool handlers
        self._register_handlers()
        
        self.logger.info("Elefante MCP Server initialized")
    
    def _register_handlers(self):
        """Register all MCP tool handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools"""
            return [
                Tool(
                    name="addMemory",
                    description="Store a new memory in Elefante's dual-database system. Memories are persisted in ChromaDB (vector embeddings for semantic search) and Kuzu (knowledge graph for structured relationships), enabling powerful hybrid retrieval across both semantic similarity and explicit connections.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The memory content to store"
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["conversation", "fact", "insight", "code", "decision", "task", "note"],
                                "default": "conversation",
                                "description": "Type of memory"
                            },
                            "importance": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "default": 5,
                                "description": "Importance level (1-10)"
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
                Tool(
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

This tool queries ChromaDB (vector embeddings) and Kuzu (knowledge graph) using semantic, structured, or hybrid search modes. The database cannot infer context from pronouns - it needs explicit, searchable terms.""",
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
                                "default": true,
                                "description": "Include recent conversation context in search results"
                            },
                            "include_stored": {
                                "type": "boolean",
                                "default": true,
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
                Tool(
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
                Tool(
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
                Tool(
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
                Tool(
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
                Tool(
                    name="getStats",
                    description="Get comprehensive statistics about Elefante's memory system health and usage. Returns metrics for ChromaDB (vector store size, embedding dimensions) and Kuzu (graph node/edge counts, relationship types), plus system performance indicators. Use for monitoring, debugging, or understanding memory system state.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
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
                elif name == "getStats":
                    result = await self._handle_get_stats(arguments)
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
        """Handle addMemory tool call"""
        memory = await self.orchestrator.add_memory(
            content=args["content"],
            memory_type=args.get("memory_type", "conversation"),
            importance=args.get("importance", 5),
            tags=args.get("tags"),
            entities=args.get("entities"),
            metadata=args.get("metadata")
        )
        
        return {
            "success": True,
            "memory_id": str(memory.id),
            "message": "Memory stored successfully",
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
        results = await self.orchestrator.search_memories(
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
        
        context = await self.orchestrator.get_context(
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
        entity = await self.orchestrator.create_entity(
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
        relationship = await self.orchestrator.create_relationship(
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
        stats = await self.orchestrator.get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    
    async def run(self):
        """Run the MCP server"""
        self.logger.info("Starting Elefante MCP Server...")
        
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