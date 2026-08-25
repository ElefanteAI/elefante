# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/mcp/server.py
# VERSION : 2.7.0
# CHANGED : 2026-04-15
# PURPOSE : MCP server: exposes all Elefante operations as JSON-RPC tools and
#           prompts over stdio transport. Entry point for all agent interactions.
# ROLE    : MCP surface layer — this is what agents talk to. Every tool call,
#           every prompt, every TOKEN_STATS injection goes through this file.
# TOUCHED : When adding/removing/renaming MCP tools or prompts; when changing
#           response envelope (TOKEN_STATS, DIRECTIVES, rejection_reason);
#           when fixing transport-level bugs. __main__ pre-loads the embedding
#           model here (BUG-010 fix) — do NOT move that call inside asyncio.run().
# ─────────────────────────────────────────────────────────────────────────────
"""
MCP Server implementation for Elefante Memory System

This server exposes memory operations as MCP tools that can be called
from IDEs and other MCP clients. It provides a standardized interface
for AI assistants to store and retrieve memories.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Sequence
from datetime import datetime
from uuid import UUID, uuid4

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
from src.utils.validators import validate_cypher_query, validate_memory_content, validate_uuid
from src.utils.elefante_mode import get_mode_manager, is_elefante_enabled, write_lock
from src.utils.runtime_profile import is_client_runtime
from src.utils.token_counter import (
    estimate_tokens, estimate_tokens_json, token_density_score,
    TYPE_TOKEN_BUDGETS, CallTokenSnapshot, SessionTokenLedger,
)

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

# Provenance comes from transport headers or the local process environment, so
# it must stay safe to persist, log, and render. These limits deliberately
# bound each independently useful field without imposing a host-name allowlist.
PROVENANCE_TOOL_MAX_LENGTH = 128
PROVENANCE_INSTANCE_MAX_LENGTH = 256
PROVENANCE_SESSION_MAX_LENGTH = 256
PROVENANCE_CWD_MAX_LENGTH = 1024


class ElefanteMCPServer:
    """
    MCP Server for Elefante Memory System
    
    Exposes memory operations as MCP tools:
    - elefante-Memory: Memory operations (action: add|search|update|delete|consolidate)
    - elefante-GraphQuery: Execute read-only Cypher queries on knowledge graph
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
        self._session_retrieval_history: list[str] = self._load_session_history()
        
        # Token intelligence ledger (per server lifecycle)
        self._token_ledger = SessionTokenLedger()
        # A daemon is one async process serving many MCP sessions. Serialize
        # mutations here before entering the cross-process file lock; otherwise
        # a synchronous lock wait can block the event loop that must complete
        # the current writer.
        self._write_serialization = asyncio.Lock()
        # Direct stdio transports do not provide an MCP session identifier. Give
        # each server process a stable, explicit origin for its lifetime.
        self._stdio_instance_id = self._provenance_value(
            os.environ.get("ELEFANTE_CLIENT_INSTANCE_ID"),
            uuid4().hex,
            PROVENANCE_INSTANCE_MAX_LENGTH,
        )
        
        # Register tool handlers
        self._register_handlers()
        
        self.logger.info("Elefante MCP Server initialized")

    @staticmethod
    def _provenance_value(value: Any, default: str, max_length: int) -> str:
        """Return a bounded, printable provenance value or its safe default.

        Header and environment values are untrusted input. Rejecting control
        characters rather than silently removing them preserves a clear data
        contract for storage, logs, and dashboard rendering.
        """
        try:
            candidate = str(value or "").strip()
        except Exception:
            return default
        if not candidate or not candidate.isprintable():
            return default
        return candidate[:max_length]

    def _request_provenance(self) -> Dict[str, str]:
        """Derive write provenance from the active MCP transport context.

        Clients may enrich their identity with `X-Elefante-Client-*` headers,
        but the daemon always owns the transport and session identifiers. This
        prevents a caller-provided memory metadata object from becoming the
        source of truth for provenance.
        """
        try:
            context = self.server.request_context
            request = context.request
        except LookupError:
            request = None
            context = None

        if request is None:
            return {
                "tool": self._provenance_value(
                    os.environ.get("ELEFANTE_CLIENT_TOOL"),
                    "unknown-stdio",
                    PROVENANCE_TOOL_MAX_LENGTH,
                ),
                "instance_id": self._provenance_value(
                    os.environ.get("ELEFANTE_CLIENT_INSTANCE_ID"),
                    self._stdio_instance_id,
                    PROVENANCE_INSTANCE_MAX_LENGTH,
                ),
                "session_id": "stdio",
                "cwd": self._provenance_value(
                    os.environ.get("ELEFANTE_CLIENT_CWD"),
                    "",
                    PROVENANCE_CWD_MAX_LENGTH,
                ),
                "transport": "stdio",
            }

        headers = request.headers
        client_params = getattr(getattr(context, "session", None), "client_params", None)
        client_info = getattr(client_params, "clientInfo", None)
        client_name = getattr(client_info, "name", None)
        session_id = headers.get("mcp-session-id")

        return {
            "tool": self._provenance_value(
                headers.get("x-elefante-client-tool") or client_name,
                "unknown-http",
                PROVENANCE_TOOL_MAX_LENGTH,
            ),
            "instance_id": self._provenance_value(
                headers.get("x-elefante-client-instance-id") or session_id,
                "unknown-http-instance",
                PROVENANCE_INSTANCE_MAX_LENGTH,
            ),
            "session_id": self._provenance_value(
                session_id,
                "initializing",
                PROVENANCE_SESSION_MAX_LENGTH,
            ),
            "cwd": self._provenance_value(
                headers.get("x-elefante-client-cwd"),
                "",
                PROVENANCE_CWD_MAX_LENGTH,
            ),
            "transport": "streamable-http",
        }

    def _with_request_provenance(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return add arguments with daemon-derived provenance attached."""
        payload = dict(arguments)
        metadata = payload.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError("Memory metadata must be an object")
        payload["metadata"] = {**metadata, "elefante_source": self._request_provenance()}
        return payload

    @asynccontextmanager
    async def _write_operation(self):
        """Serialize daemon mutations before acquiring the process-level lock."""
        async with self._write_serialization:
            with write_lock() as lock:
                yield lock

    # Tools that should NOT get automatic context injection
    # (they already return memory data, or are system/admin tools)
    _CONTEXT_SKIP_TOOLS = {
        "elefante-Memory",  # all actions (add/search/update/delete/consolidate) skip context-injection
        "elefante-ContextGet",
        "elefante-System", "elefante-SystemStatusGet",
        "elefante-DashboardOpen", "elefante-SessionsList",
        "elefante-ETLProcess", "elefante-ETLClassify",
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
        explicit elefante-Memory(action="search") call required.

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
                await orchestrator.record_coactivation(self._session_retrieval_history.copy())
                self._save_session_history()

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
            "CRITICAL PROTOCOL: Do not rely on your internal knowledge base for project specifics; use the memory system.",
        ]
        if not is_client_runtime():
            pitfalls.append(
                "CRITICAL PROTOCOL: If you are debugging, read workspace/ISSUES.md first, "
                "match the BUG/GAP row, and run its verification command before editing source."
            )
        
        # Context-specific injections — for consolidated elefante-Memory, inspect action arg
        # NOTE: _inject_pitfalls signature is (result, tool_name) — arguments not passed in.
        # We can still inspect the result payload's compliance_stamp/action hints for action-specific pitfalls,
        # OR (preferred) accept that consolidated tool's pitfalls are tool-level (not action-level).
        # For atomic-swap correctness, attach BOTH MemoryAdd and MemorySearch pitfalls to elefante-Memory
        # so the agent receives the full guidance regardless of action. Action-specific filtering can land later
        # if measurement shows agent confusion from over-injection.
        if tool_name == "elefante-Memory":
            pitfalls.append("WARNING - MEMORY INTEGRITY (action=add): Score is system-computed. Classify memory_type accurately — it determines the decay rate.")
            pitfalls.append("WARNING - SEARCH BIAS (action=search): If results are empty, try broader terms. Do not assume non-existence without a semantic search.")
            pitfalls.append("WARNING - CONTRADICTIONS (action=search): If you find contradictory memories, prioritize the most recent one but note the conflict.")

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

    def _inject_entrypoint_protocol(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject the exact debug entry sequence into every tool response.

        This is more specific than generic pitfalls: it gives the agent
        the canonical first steps and maintained verification surfaces.
        """
        if is_client_runtime():
            result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"] = [
                "1. Search Elefante memory before asserting project preferences, decisions, or prior context.",
                "2. Use retrieved memories as evidence; surface material conflicts instead of silently choosing one.",
                "3. Ask for missing context when it can change the result, and never store passwords, API keys, or secrets.",
                "4. Keep the response focused on the current task and the smallest useful context set.",
            ]
        else:
            result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"] = [
                "1. Read workspace/ISSUES.md and match the current failure to a BUG/GAP row before changing code.",
                "2. Run the verification command from that BUG row first. If it passes, the documented fix still holds and the root cause is elsewhere.",
                "3. If the verification fails, open the linked workspace/postmortems/<domain>.md entry and use its exact commands and constraints.",
                "4. Read tests/README.md before creating any scratch reproducer. Update an existing maintained test when possible.",
                "5. Only then edit source, rerun the same verifier, and update bug docs plus CHANGELOG if behavior changed.",
            ]
        return result

    # ── Session retrieval history persistence (BUG-018 fix) ─────────────

    _SESSION_HISTORY_FILE = "session_retrieval_history.json"
    _SESSION_HISTORY_MAX_AGE_DAYS = 7

    def _load_session_history(self) -> list[str]:
        """Load persisted session retrieval history from DATA_DIR.

        Prunes entries older than _SESSION_HISTORY_MAX_AGE_DAYS.
        Returns an empty list on any failure (cold-start safe).
        """
        from src.utils.config import DATA_DIR
        path = DATA_DIR / self._SESSION_HISTORY_FILE
        if not path.exists():
            return []
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "ids" not in data:
                return []
            saved_at = data.get("saved_at", "")
            if saved_at:
                age = (datetime.now(tz=__import__("datetime").timezone.utc)
                       - datetime.fromisoformat(saved_at))
                if age.days > self._SESSION_HISTORY_MAX_AGE_DAYS:
                    self.logger.info("Session history expired (%d days old), starting fresh", age.days)
                    path.unlink(missing_ok=True)
                    return []
            ids = [str(i) for i in data["ids"] if isinstance(i, str)][:20]
            if ids:
                self.logger.info("Restored %d session retrieval IDs from disk", len(ids))
            return ids
        except Exception as e:
            self.logger.warning("Could not load session history: %s", e)
            return []

    def _save_session_history(self) -> None:
        """Persist current session retrieval history to DATA_DIR."""
        from src.utils.config import DATA_DIR
        path = DATA_DIR / self._SESSION_HISTORY_FILE
        try:
            payload = {
                "ids": self._session_retrieval_history,
                "saved_at": datetime.now(tz=__import__("datetime").timezone.utc).isoformat(),
            }
            with open(path, "w") as f:
                json.dump(payload, f)
        except Exception as e:
            self.logger.warning("Could not save session history: %s", e)

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
        Write operations are blocked until elefante-Memory(action="search") has been called.
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
            "action_required": "Call elefante-Memory with action='search' first to check for existing/related memories.",
            "reason": "This prevents duplicate memories and ensures you have full context before adding new knowledge.",
            "blocked_tool": tool_name,
            "hint": "Try: elefante-Memory(action='search', query='...') with a query related to what you want to store."
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
            await self.orchestrator.ensure_system_baseline()
            self.logger.info("Orchestrator initialized")
        return self.orchestrator

    async def close(self) -> None:
        """Release a lazily-created orchestrator when this transport stops."""
        orchestrator = self.orchestrator
        self.orchestrator = None
        if orchestrator is not None:
            await orchestrator.close()
    
    def _register_handlers(self):
        """Register all MCP tool handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """List all available tools"""
            self.logger.info("=== list_tools() handler called by MCP client ===")
            tools = [
                # ── elefante-Memory: consolidated memory tool (v2.10.0 atomic swap, 2026-05-02) ──
                # Replaces 5 legacy tools: MemoryAdd, MemorySearch, MemoryUpdate, MemoryDelete, MemoryConsolidate.
                # Compliance Gate (search-before-write) is preserved: handlers still call _check_compliance_gate
                # with the legacy logical names ("elefante-MemoryAdd" etc.) — internal contract unchanged.
                types.Tool(
                    name="elefante-Memory",
                    description="""Persistent memory operations. The `action` parameter selects the operation:

- `action=add` — store a new memory. content + memory_type + domain + category + tags + entities. Score is system-computed (0-100) from behavioral signals; you do NOT assign importance. Compliance Gate enforces search-before-write.
- `action=search` — query memory. ChromaDB (semantic) + Kuzu (structured) hybrid by default. Rewrite pronouns to specific entities before calling. Use `list_all=true` to bypass semantic relevance filtering for browsing/export.
- `action=update` — amend an existing memory in-place. memory_id + content/tags/deprecated/archived/supersedes_id. Compliance Gate.
- `action=delete` — permanently remove a memory. memory_id + reason (audit trail). Compliance Gate.
- `action=consolidate` — deterministic LLM-free cleanup (canonicalize and mark duplicates redundant). Default dry-run; pass `force=true` to apply.

**ALWAYS** call action=search before answering questions about user preferences, past decisions, or "the usual way". **NEVER** assume you know an answer that might be in memory. **IF RESULTS ARE CONTRADICTORY:** prefer most recent timestamp; "decision"/"fact" types over "conversation".

**CRITICAL PERSISTENCE RULE:** The chronological session context buffer clears on IDE restart. After important decisions, run `elefante-Memory(action=add, ...)` to make them durable.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["add", "search", "update", "delete", "consolidate"],
                                "description": "Operation to perform"
                            },
                            # action=add fields
                            "content": {"type": "string", "description": "Memory content (action=add) or replacement content (action=update)"},
                            "memory_type": {
                                "type": "string",
                                "enum": ["fact", "decision", "preference", "insight", "note", "conversation", "specification", "directive"],
                                "default": "fact",
                                "description": "Memory type (action=add) — determines decay rate. Preferences decay slowest, conversations fastest. Specifications and directives are immutable."
                            },
                            "domain": {
                                "type": "string",
                                "enum": ["work", "personal", "learning", "project", "reference", "system"],
                                "description": "High-level context (action=add)"
                            },
                            "category": {"type": "string", "description": "Topic grouping (action=add)"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags (action=add) or replacement tags (action=update)"},
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
                                "description": "Entities to link in knowledge graph (action=add)"
                            },
                            "metadata": {"type": "object", "description": "Additional metadata (action=add)"},
                            "force_new": {"type": "boolean", "default": False, "description": "Bypass dedup (action=add)"},
                            # action=search fields
                            "query": {"type": "string", "description": "Search query (action=search). Rewrite pronouns to specific entities first."},
                            "mode": {
                                "type": "string",
                                "enum": ["semantic", "structured", "hybrid"],
                                "default": "hybrid",
                                "description": "Search mode (action=search)"
                            },
                            "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100, "description": "Max results (action=search)"},
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "memory_type": {"type": "string"},
                                    "domain": {"type": "string", "enum": ["work", "personal", "learning", "project", "reference", "system"]},
                                    "category": {"type": "string"},
                                    "min_score": {"type": "integer", "minimum": 0, "maximum": 100},
                                    "tags": {"type": "array", "items": {"type": "string"}},
                                    "start_date": {"type": "string", "format": "date-time"},
                                    "end_date": {"type": "string", "format": "date-time"}
                                },
                                "description": "Optional search filters (action=search)"
                            },
                            "min_similarity": {"type": "number", "default": 0.3, "minimum": 0.0, "maximum": 1.0, "description": "Min similarity (action=search)"},
                            "include_conversation": {"type": "boolean", "default": True, "description": "Include recent conversation in search (action=search)"},
                            "include_stored": {"type": "boolean", "default": True, "description": "Include stored memories in search (action=search)"},
                            "session_id": {"type": "string", "description": "Session UUID (action=search, required if include_conversation=true)"},
                            "list_all": {"type": "boolean", "default": False, "description": "Bypass semantic relevance filtering — for browsing/export (action=search)"},
                            "offset": {"type": "integer", "default": 0, "minimum": 0, "description": "Pagination offset (action=search)"},
                            # action=update / delete fields
                            "memory_id": {"type": "string", "description": "Target memory UUID (action=update or delete)"},
                            "deprecated": {"type": "boolean", "description": "Mark deprecated — excluded from normal search (action=update)"},
                            "archived": {"type": "boolean", "description": "Mark archived (action=update)"},
                            "supersedes_id": {"type": "string", "description": "UUID of older memory this supersedes (action=update)"},
                            "reason": {"type": "string", "description": "Audit trail (action=delete)"},
                            # action=consolidate fields
                            "force": {"type": "boolean", "default": False, "description": "Apply cleanup (default dry-run) (action=consolidate)"},
                        },
                        "required": ["action"]
                    }
                ),
                types.Tool(
                    name="elefante-GraphQuery",
                    description="Execute read-only Cypher queries directly on Elefante's Kuzu knowledge graph for advanced structured data retrieval. Use this for complex relationship traversals, pattern matching, and graph analytics. Use elefante-GraphConnect for mutations. Ideal for queries like 'Find all entities connected to X', 'Show the path between A and B', or 'List all relationships of type Y'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cypher_query": {
                                "type": "string",
                                "description": "Read-only Cypher query to execute"
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
                # MemoryConsolidate consolidated into elefante-Memory(action=consolidate) at v2.10.0 / 2026-05-02
                # elefante-MemoryListAll REMOVED — use elefante-Memory(action=search) with list_all=true
                # elefante-MemoryMigrateToV3 REMOVED (one-time admin, moved to scripts/)
                # MemoryUpdate consolidated into elefante-Memory(action=update) at v2.10.0 / 2026-05-02
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
- **surfaces_when**: Stored trigger metadata for inspection and future proactive surfacing; not a current ranking signal

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

Optional enrichment fields:
- concepts: 3-5 key terms for graph edges
- surfaces_when: Stored trigger metadata for inspection and future proactive surfacing; not a current ranking signal""",
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
                                "description": "Stored trigger metadata for inspection and future proactive surfacing; not a current ranking signal"
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

**YOU MUST first call `elefante-Memory` with `action="search"`** and a specific query.

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
            
            # Measure input tokens once (arguments sent by the agent)
            input_tokens = estimate_tokens_json(arguments)
            
            try:
                # Handle mode management + safe tools FIRST (always available)
                if name == "elefante-System":
                    action = arguments.get("action", "enable")
                    if action == "disable":
                        result = await self._handle_disable_elefante(arguments)
                    else:
                        result = await self._handle_enable_elefante(arguments)
                    if isinstance(result, dict):
                        result = self._record_and_inject_token_stats(result, name, input_tokens)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-SystemStatusGet":
                    result = await self._handle_get_system_status(arguments)
                    if isinstance(result, dict):
                        result = self._record_and_inject_token_stats(result, name, input_tokens)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-DashboardOpen":
                    result = await self._handle_get_elefante_dashboard(arguments)
                    if isinstance(result, dict):
                        result = self._record_and_inject_token_stats(result, name, input_tokens)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                # Directive tools — safe, no DB locks needed
                elif name == "elefante-DirectiveAdd":
                    result = self._handle_directive_add(arguments)
                    if isinstance(result, dict):
                        result = self._record_and_inject_token_stats(result, name, input_tokens)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-DirectiveList":
                    result = self._handle_directive_list(arguments)
                    if isinstance(result, dict):
                        result = self._record_and_inject_token_stats(result, name, input_tokens)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                elif name == "elefante-DirectiveRemove":
                    result = self._handle_directive_remove(arguments)
                    if isinstance(result, dict):
                        result = self._record_and_inject_token_stats(result, name, input_tokens)
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                
                # Mode check removed - operations auto-acquire/release locks
                # Write operations use write_lock() context manager internally
                
                # ── elefante-Memory dispatch (v2.10.0 atomic swap) ──
                # Routes Memory(action=...) to the existing _handle_* methods. The handlers retain
                # their internal contract (incl. Compliance Gate via legacy logical names) — only
                # the public tool surface is consolidated. 'action' is stripped before delegation.
                if name == "elefante-Memory":
                    action = arguments.get("action")
                    if action is None:
                        raise ValueError("elefante-Memory requires 'action' (add|search|update|delete|consolidate)")
                    delegate_args = {k: v for k, v in arguments.items() if k != "action"}
                    if action == "add":
                        result = await self._handle_add_memory(delegate_args)
                    elif action == "search":
                        result = await self._handle_search_memories(delegate_args)
                    elif action == "update":
                        result = await self._handle_update_memory(delegate_args)
                    elif action == "delete":
                        result = await self._handle_delete_memory(delegate_args)
                    elif action == "consolidate":
                        result = await self._handle_consolidate_memories(delegate_args)
                    else:
                        raise ValueError(f"elefante-Memory: unknown action '{action}' (expected add|search|update|delete|consolidate)")
                elif name == "elefante-GraphQuery":
                    result = await self._handle_query_graph(arguments)
                elif name == "elefante-ContextGet":
                    result = await self._handle_get_context(arguments)
                elif name == "elefante-SessionsList":
                    result = await self._handle_get_episodes(arguments)
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
                    result = self._inject_entrypoint_protocol(result)
                    result = self._inject_directives(result)
                    result = self._record_and_inject_token_stats(result, name, input_tokens)

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]
                
            except Exception as e:
                self.logger.error(f"Tool execution failed: {name}", error=str(e), exc_info=True)
                # Surface compendium citation for database-class errors
                error_msg = str(e)
                if not is_client_runtime() and "workspace/ISSUES.md" not in error_msg:
                    error_msg += "\nDebug: workspace/ISSUES.md -> match the BUG/GAP row"
                error_payload = {
                    "error": error_msg,
                    "tool": name,
                    "success": False,
                }
                error_payload = self._inject_pitfalls(error_payload, name)
                error_payload = self._inject_entrypoint_protocol(error_payload)
                error_payload = self._inject_directives(error_payload)
                error_payload = self._record_and_inject_token_stats(error_payload, name, input_tokens)
                return [TextContent(
                    type="text",
                    text=json.dumps(error_payload, indent=2)
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
            await self.close()
        
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
        
        # Token intelligence: session-level analytics
        status["token_intelligence"] = self._token_ledger.to_dict()
        
        return status

    async def _handle_add_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemoryAdd tool call - Authoritative Pipeline (Compliance Gate)"""
        # Compliance Gate Check
        gate_result = self._check_compliance_gate("elefante-MemoryAdd")
        if gate_result is not None:
            return gate_result
        
        # Keep the lock until both vector and graph writes have completed. The
        # previous scope ended after lazy initialization and left the actual
        # Kuzu write outside its intended single-writer boundary.
        async with self._write_operation() as lock:
            if not lock.acquired:
                return {
                    "success": False,
                    "error": "Could not acquire write lock - another process is writing",
                    "retry": True
                }

            orchestrator = await self._get_orchestrator()
            args = self._with_request_provenance(args)

            # Build metadata with domain/category if provided
            metadata = args.get("metadata") or {}
            if args.get("domain"):
                metadata["domain"] = args["domain"]
            if args.get("category"):
                metadata["category"] = args["category"]

            # Token intelligence: stamp content token count at ingestion
            content = args["content"]
            memory_type = args.get("memory_type", "conversation")
            content_tokens = estimate_tokens(content)
            density = token_density_score(content_tokens, memory_type)
            system_meta = metadata.get("system_metadata", {})
            system_meta["content_tokens"] = content_tokens
            system_meta["token_density"] = density
            metadata["system_metadata"] = system_meta

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
                rejection_reason = getattr(orchestrator, '_last_rejection_reason', None)
                return {
                    "status": "ignored",
                    "classification": "IGNORE",
                    "entity_count": 0,
                    "relationship_count": 0,
                    "embedding_id": None,
                    "graph_ids": [],
                    "message": "Memory filtered by Intelligence Pipeline",
                    "rejection_reason": rejection_reason or "Unknown — orchestrator returned None without setting a reason",
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
                "memory_id": str(memory.id),
                "content_tokens": content_tokens,
                "token_density": density,
                **({
                    "density_warning": f"Memory is {density:.1f}x over budget for {memory_type} (budget: {TYPE_TOKEN_BUDGETS.get(memory_type, 300)} tokens). Consider trimming or splitting."
                } if density > 2.0 else {}),
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
            await orchestrator.record_coactivation(self._session_retrieval_history.copy())
            self._save_session_history()
        
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
        """Handle a read-only elefante-GraphQuery tool call."""
        validate_cypher_query(args["cypher_query"])
        # The daemon owns one graph-store instance. Opening the module-level
        # singleton here creates a second handle to the same Kuzu file.
        graph_store = (await self._get_orchestrator()).graph_store
        # Note: Kuzu doesn't support parameterized queries in current implementation.
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
        
        async with self._write_operation() as lock:
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
        
        async with self._write_operation() as lock:
            if not lock.acquired:
                return {"success": False, "error": "Could not acquire write lock", "retry": True}
            
            from uuid import UUID as _UUID
            mid = _UUID(memory_id)
            
            orchestrator = await self._get_orchestrator()
            vs = orchestrator.vector_store
            gs = orchestrator.graph_store

            vector_deleted = await vs.delete_memory(mid)
            graph_deleted = False
            if vector_deleted:
                graph_deleted = await gs.delete_entity(mid)
            success = vector_deleted and graph_deleted
            
            if success:
                # Purge deleted ID from session history to prevent stale
                # co-activation queries against a nonexistent memory.
                self._session_retrieval_history = [
                    mid_str for mid_str in self._session_retrieval_history
                    if mid_str != memory_id
                ]
                self._save_session_history()
                self.logger.info(f"Memory deleted (purposeful forgetting): {memory_id}", reason=reason)
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "reason": reason,
                    "message": "Memory permanently deleted"
                }
            elif vector_deleted and not graph_deleted:
                self.logger.error(
                    f"Memory delete partially failed: graph cleanup failed for {memory_id}",
                    reason=reason,
                )
                return {
                    "success": False,
                    "memory_id": memory_id,
                    "error": "Vector delete succeeded but graph cleanup failed"
                }
            else:
                return {"success": False, "error": f"Memory {memory_id} not found or deletion failed"}

    async def _handle_consolidate_memories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-MemoryConsolidate tool call (transaction-scoped)"""
        async with self._write_operation() as lock:
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
        import json

        limit = args.get("limit", 10)
        offset = args.get("offset", 0)
        
        from src.core.graph_store import get_graph_store
        graph_store = get_graph_store()
        
        # Query for sessions
        cypher = f"""
        MATCH (s:Entity {{type: 'session'}})
        RETURN s
        ORDER BY s.created_at DESC
        SKIP {offset}
        LIMIT {limit}
        """
        
        results = await graph_store.execute_query(cypher)
        episodes = []
        
        for row in results:
            session = row.get("s")
            if session:
                props_raw = session.get("props") if isinstance(session, dict) else getattr(session, "props", None)
                props: Dict[str, Any] = {}
                if isinstance(props_raw, str) and props_raw:
                    try:
                        props = json.loads(props_raw)
                    except Exception:
                        props = {}

                session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
                session_name = session.get("name") if isinstance(session, dict) else getattr(session, "name", None)
                created_at = session.get("created_at") if isinstance(session, dict) else getattr(session, "created_at", None)

                episodes.append({
                    "id": str(session_id),
                    "name": session_name,
                    "last_active": props.get("last_active") or created_at,
                    "source": props.get("source")
                })
        
        return {
            "success": True,
            "count": len(episodes),
            "episodes": episodes
        }
    
    async def _start_dashboard_and_open(self, force_restart: bool = False) -> Dict[str, Any]:
        global DASHBOARD_STARTED

        import subprocess
        import sys
        import time
        import urllib.request
        import urllib.error

        port = 8000
        url = f"http://localhost:{port}"

        def _is_server_up(timeout: float = 1.0) -> bool:
            try:
                req = urllib.request.Request(f"{url}/health", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status == 200
            except Exception:
                return False

        def _kill_existing() -> None:
            """Kill any process currently listening on port 8000."""
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True, text=True
                )
                pids = result.stdout.strip().split()
                for pid in pids:
                    subprocess.run(["kill", pid], capture_output=True)
                if pids:
                    time.sleep(0.5)  # brief settle
            except Exception:
                pass

        def _wait_for_ready(max_wait: float = 5.0) -> bool:
            """Poll /health until the server responds or timeout expires."""
            deadline = time.time() + max_wait
            while time.time() < deadline:
                if _is_server_up(timeout=1.0):
                    return True
                time.sleep(0.3)
            return False

        try:
            already_running = _is_server_up()

            if force_restart and already_running:
                # Snapshot was just refreshed — restart so the new data is served immediately.
                self.logger.info("Dashboard restart requested: killing existing server process.")
                _kill_existing()
                already_running = False
                DASHBOARD_STARTED = False

            if not already_running:
                subprocess.Popen(
                    [sys.executable, "-m", "src.dashboard.server"],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=str(self._get_project_root()),
                )
                self.logger.info(f"Dashboard server started via subprocess on port {port}")

                # Wait for Uvicorn to bind before opening the browser.
                # Cold Python starts (first launch) can take 10-15s due to imports.
                ready = _wait_for_ready(max_wait=15.0)
                if not ready:
                    self.logger.warning("Dashboard server did not become ready within 15s.")
            else:
                ready = True
                self.logger.info(f"Dashboard already running on port {port}")

            DASHBOARD_STARTED = True

        except Exception as e:
            self.logger.warning(f"Failed to start dashboard server: {e}")
            DASHBOARD_STARTED = True
            ready = False

        # Gate: only open browser once the server is confirmed ready.
        # If not ready, do one final check — the server may have come up
        # in the brief window between the wait loop and now.
        if not ready:
            ready = _is_server_up(timeout=2.0)

        if ready:
            try:
                webbrowser.open(url)
                message = f"Dashboard opened at {url}"
            except Exception as e:
                message = f"Dashboard server running at {url}, but failed to open browser: {e}"
        else:
            message = (
                f"Dashboard server is still starting on port {port}. "
                f"Open {url} manually once it's ready."
            )
            self.logger.warning(message)

        return {
            "success": ready,
            "message": message,
            "url": url
        }

    def _get_project_root(self):
        """Return the project root directory (parent of src/)."""
        from pathlib import Path
        return Path(__file__).parent.parent.parent

    async def _refresh_dashboard_snapshot(self) -> Dict[str, Any]:
        import os
        from src.utils.config import DATA_DIR

        orchestrator = await self._get_orchestrator()

        memories = await orchestrator.vector_store.get_all(limit=1000)

        from src.utils.dashboard_serializer import memory_to_dashboard_node

        nodes = []
        edges = []
        seen_ids = set()

        for mem in memories:
            node = memory_to_dashboard_node(mem)
            if node is None:
                continue
            nodes.append(node)
            seen_ids.add(node["id"])

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

        open_result = await self._start_dashboard_and_open(force_restart=refresh)
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
        
        async with self._write_operation() as lock:
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
                "instructions": "Analyze each memory and call elefante-ETLClassify with your enrichment. Required: summary (one-line). Optional: concepts (3-5 retrieval terms), surfaces_when (stored trigger metadata; not a current ranking signal)."
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
        
        async with self._write_operation() as lock:
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

    def _measure_overhead_tokens(self, result: Dict[str, Any]) -> int:
        """Count tokens consumed by static protocol injections."""
        overhead = 0
        for key in ("MANDATORY_PROTOCOLS_READ_THIS_FIRST",
                     "ENTRYPOINT_SEQUENCE_READ_THIS_FIRST",
                     "DIRECTIVES"):
            if key in result:
                overhead += estimate_tokens_json(result[key])
        return overhead

    def _measure_context_tokens(self, result: Dict[str, Any]) -> int:
        """Count tokens consumed by dynamic context injection."""
        ctx = result.get("RELEVANT_CONTEXT")
        if ctx:
            return estimate_tokens_json(ctx)
        return 0

    def _record_and_inject_token_stats(
        self,
        result: Dict[str, Any],
        tool_name: str,
        input_tokens: int,
    ) -> Dict[str, Any]:
        """Measure output tokens, record in ledger, inject stats into response.
        
        ADV-006: Measures payload BEFORE injecting TOKEN_STATS, then accounts
        for TOKEN_STATS own size in the final output_tokens count.
        """
        overhead = self._measure_overhead_tokens(result)
        context = self._measure_context_tokens(result)
        # Measure payload before TOKEN_STATS injection
        payload_tokens = estimate_tokens_json(result)
        
        # Measure TOKEN_STATS block size dynamically (ADV-013: eliminates magic constant)
        stats_stub = {"TOKEN_STATS": {"output_tokens": payload_tokens, "overhead_tokens": overhead, "signal_ratio": 0.500}}
        stats_overhead = estimate_tokens_json(stats_stub)
        output_total = payload_tokens + stats_overhead

        snapshot = CallTokenSnapshot(
            tool_name=tool_name,
            input_tokens=input_tokens,
            output_tokens=output_total,
            overhead_tokens=overhead + stats_overhead,
            context_tokens=context,
        )
        self._token_ledger.record(snapshot)

        result["TOKEN_STATS"] = {
            "output_tokens": output_total,
            "overhead_tokens": overhead + stats_overhead,
            "signal_ratio": snapshot.signal_ratio,
        }
        return result

    # =========================================================================
    # TASK ORCHESTRATION HANDLERS
    # =========================================================================

    async def _handle_task_create(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle elefante-TaskCreate — create a new task node."""
        try:
            async with self._write_operation() as lock:
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
            async with self._write_operation() as lock:
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
        
        async with stdio_server() as (read_stream, write_stream):
            self.logger.info("MCP Server running on stdio")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for MCP server.

    Developer workflow references: workspace/ISSUES.md and tests/README.md.
    """
    server = ElefanteMCPServer()
    try:
        await server.run()
    finally:
        await server.close()


if __name__ == "__main__":
    # BUG-010 fix: Pre-load the embedding model BEFORE the asyncio event loop
    # starts.  `from sentence_transformers import SentenceTransformer` (which
    # imports torch) deadlocks when executed inside a worker thread under an
    # active anyio event loop with piped stdio on Windows + Python 3.11.
    # Loading eagerly here (~7-10 s on CPU) avoids the issue entirely because
    # _load_model() becomes a no-op once self._model is set.
    import sys as _sys
    _sys.stderr.write("[elefante] pre-loading embedding model ...\n")
    _sys.stderr.flush()
    from src.core.embeddings import get_embedding_service as _get_emb
    _get_emb()._load_model()
    _sys.stderr.write("[elefante] embedding model ready\n")
    _sys.stderr.flush()

    asyncio.run(main())
