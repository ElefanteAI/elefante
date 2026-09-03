import json
import os
import re
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Any, Optional

# LAW #1: Dashboard does NOT import core services that access databases
# from src.core.embeddings import get_embedding_service  # DISABLED
from src.utils.logger import get_logger
from src.utils.config import get_config
from src.utils.atomic_json import read_json_strict

logger = get_logger(__name__)

DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_CORS_ORIGINS = (
    "http://127.0.0.1:8000",
    "http://localhost:8000",
)


def _dashboard_host() -> str:
    """Return the explicit dashboard bind host, defaulting to loopback only."""
    return os.environ.get("ELEFANTE_DASHBOARD_HOST", DEFAULT_DASHBOARD_HOST).strip() or DEFAULT_DASHBOARD_HOST


def _dashboard_cors_origins() -> list[str]:
    """Return the explicit browser origins permitted to call the local dashboard."""
    configured = os.environ.get("ELEFANTE_DASHBOARD_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or list(DEFAULT_DASHBOARD_CORS_ORIGINS)


def _daemon_port() -> int:
    """Return the loopback daemon port advertised to this local Home page."""
    raw_port = os.environ.get("ELEFANTE_DAEMON_PORT", "8765").strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError(
            "ELEFANTE_DAEMON_PORT must be an integer from 1 to 65535"
        ) from error
    if not 1 <= port <= 65535:
        raise RuntimeError("ELEFANTE_DAEMON_PORT must be an integer from 1 to 65535")
    return port


def _snapshot_path() -> Path:
    """Return the only data file the dashboard is permitted to read."""
    return Path(get_config().elefante.data_dir) / "dashboard_snapshot.json"


def _session_intelligence_snapshot_path() -> Path:
    """Return the separate metadata-only Session Intelligence snapshot path."""
    override = os.environ.get("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(get_config().elefante.data_dir) / "session_intelligence_snapshot.json"


def _read_snapshot() -> dict[str, Any] | None:
    """Load the static dashboard snapshot without opening a live data store."""
    snapshot_path = _snapshot_path()
    if not snapshot_path.is_file():
        return None
    snapshot = read_json_strict(snapshot_path)
    if not isinstance(snapshot, dict):
        raise ValueError("Dashboard snapshot must contain a JSON object")
    return snapshot


def _unavailable_project_registry(error_code: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "schema_version": None,
        "mode": "invalid",
        "revision": None,
        "projects": [],
        "error_code": error_code,
    }


def _project_registry_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the private registry snapshot instead of inventing readiness."""
    value = data.get("project_registry")
    if not isinstance(value, dict):
        return _unavailable_project_registry("PROJECT_REGISTRY_UNAVAILABLE")
    status = value.get("status")
    mode = value.get("mode")
    projects = value.get("projects")
    if (
        status not in {"ready", "invalid", "unavailable"}
        or mode not in {"compatibility", "strict", "invalid"}
        or not isinstance(projects, list)
    ):
        return _unavailable_project_registry("PROJECT_REGISTRY_SNAPSHOT_INVALID")
    if status == "ready" and mode not in {"compatibility", "strict"}:
        return _unavailable_project_registry("PROJECT_REGISTRY_SNAPSHOT_INVALID")
    if status != "ready" and mode != "invalid":
        return _unavailable_project_registry("PROJECT_REGISTRY_SNAPSHOT_INVALID")
    return value


def _snapshot_context(data: dict[str, Any]) -> dict[str, Any]:
    """Expose a bounded display contract, never arbitrary snapshot copy."""
    curation = data.get("curation")
    is_showcase = (
        isinstance(curation, dict)
        and curation.get("purpose")
        == "Elefante Memory Intelligence dashboard showcase"
        and curation.get("deterministic") is True
        and curation.get("contains_user_data") is False
    )
    if is_showcase:
        return {
            "mode": "showcase",
            "label": "Example workspace",
            "contains_user_data": False,
            "source_grounded_content": curation.get("source_grounded_content") is True,
            "synthetic_behavioral_metadata": (
                curation.get("synthetic_behavioral_metadata") is True
            ),
            "disclaimer": (
                "Deterministic example data; counts and activity do not describe "
                "customer behavior or product performance."
            ),
        }
    return {
        "mode": "local_snapshot",
        "label": "Local snapshot",
        "contains_user_data": None,
        "source_grounded_content": None,
        "synthetic_behavioral_metadata": None,
        "disclaimer": (
            "Read-only snapshot evidence; live actions require a verified local "
            "control session."
        ),
    }


def _request_origin(request: Request) -> str:
    host = request.url.hostname or ""
    port = request.url.port
    default_port = 443 if request.url.scheme == "https" else 80
    suffix = "" if port in {None, default_port} else f":{port}"
    return f"{request.url.scheme}://{host}{suffix}"


def _read_session_intelligence_snapshot() -> dict[str, Any] | None:
    """Load the derived metadata-only snapshot without opening its SQLite ledger."""
    snapshot_path = _session_intelligence_snapshot_path()
    if not snapshot_path.is_file():
        ledger_override = os.environ.get("ELEFANTE_SESSION_INTELLIGENCE_DB", "").strip()
        ledger_path = (
            Path(ledger_override).expanduser()
            if ledger_override
            else Path(get_config().elefante.data_dir) / "session_intelligence.db"
        )
        if snapshot_path.exists() or ledger_path.exists():
            raise ValueError("Session Intelligence exists but its snapshot is unavailable")
        return None
    with snapshot_path.open("r", encoding="utf-8") as snapshot_file:
        snapshot = json.load(snapshot_file)
    if not isinstance(snapshot, dict):
        raise ValueError("Session Intelligence snapshot must contain a JSON object")
    consent = snapshot.get("consent")
    if not isinstance(consent, dict) or not isinstance(consent.get("enabled"), bool):
        raise ValueError("Session Intelligence snapshot has invalid consent state")
    card = snapshot.get("signal_card")
    if card is not None:
        if not isinstance(card, dict) or any(
            not isinstance(card.get(key), dict)
            for key in ("scope", "usage", "cost", "accepted_outcome_evidence")
        ):
            raise ValueError("Session Intelligence snapshot has an invalid Signal Card")
        if not isinstance(card.get("unknowns"), list) or not isinstance(card.get("hypothesis"), str):
            raise ValueError("Session Intelligence snapshot has invalid evidence labels")
        if any(not isinstance(card["usage"].get(key), dict) for key in ("actual", "estimated")):
            raise ValueError("Session Intelligence snapshot has invalid usage evidence")
    report = snapshot.get("enterprise_report")
    if report is not None and (
        not isinstance(report, dict)
        or any(not isinstance(report.get(key), list) for key in ("groups", "hypotheses"))
        or any(
            not isinstance(item, dict) or not isinstance(item.get("basis"), dict)
            for item in report.get("hypotheses", [])
        )
    ):
        raise ValueError("Session Intelligence snapshot has an invalid aggregate report")
    return snapshot


def _snapshot_search(snapshot: dict[str, Any], query: str, limit: int, min_similarity: float) -> list[dict[str, Any]]:
    """Return lexical matches from the redacted snapshot, never a live store."""
    query_terms = set(re.findall(r"[\w-]+", query.casefold()))
    if not query_terms:
        return []

    matches: list[dict[str, Any]] = []
    for node in snapshot.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") != "memory":
            continue
        properties = node.get("properties") if isinstance(node.get("properties"), dict) else {}
        content = str(properties.get("content") or node.get("description") or "")
        searchable = " ".join(
            str(value)
            for value in (content, node.get("name"), properties.get("title"), properties.get("tags"), properties.get("topic"))
            if value is not None
        ).casefold()
        matched_terms = sum(term in searchable for term in query_terms)
        similarity = matched_terms / len(query_terms)
        if similarity < min_similarity:
            continue
        matches.append(
            {
                "id": str(node.get("id") or ""),
                "content": content,
                "metadata": properties,
                "similarity": similarity,
            }
        )
    return sorted(matches, key=lambda item: item["similarity"], reverse=True)[:limit]


app = FastAPI(title="Elefante Knowledge Garden")

# The dashboard can expose private memory content. Keep its browser surface local
# by default and require an explicit origin list for a wrapped deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_dashboard_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

# API Endpoints
@app.get("/api/graph")
async def get_graph(
    limit: int = Query(default=1000, ge=1, le=5000),
    space: Optional[str] = None,
):
    """
    Fetch graph data from the pre-generated configured-store/Kuzu snapshot.
    The snapshot is generated by scripts/pipeline/update_dashboard_data.py
    """
    try:
        data = _read_snapshot()
        if data is None:
            logger.warning("Snapshot not found, returning empty graph")
            return {
                "nodes": [],
                "edges": [],
                "stats": {"node_count": 0, "edge_count": 0, "semantic_edge_count": 0},
                "snapshot_context": _snapshot_context({}),
                "project_registry": _unavailable_project_registry(
                    "PROJECT_SNAPSHOT_UNAVAILABLE"
                ),
            }
        
        # Transform nodes to frontend format
        nodes = []
        for n in data.get("nodes", [])[:limit]:
            node_type = n.get("type", "memory")
            raw_props = n.get("properties", {}) if isinstance(n.get("properties"), dict) else {}
            node_name = n.get("name") or ""
            nodes.append({
                "id": n.get("id"),
                "label": node_name[:50] + ("..." if len(node_name) > 50 else ""),
                "type": node_type,
                "entityType": node_type,
                "created_at": n.get("created_at") or "",
                "name": node_name,
                "description": n.get("description") or "",
                "properties": {
                    "description": n.get("description") or "",
                    "created_at": n.get("created_at") or "",
                    **raw_props,
                    "access_count": raw_props.get("access_count", 0),
                    "last_accessed": raw_props.get("last_accessed"),
                    "last_modified": raw_props.get("last_modified"),
                },
                "full_data": n
            })
        
        # Transform edges to frontend format
        edges = []
        node_ids = {n["id"] for n in nodes}
        for e in data.get("edges", []):
            src = e.get("from") or e.get("source")
            dst = e.get("to") or e.get("target")
            if src in node_ids and dst in node_ids:
                label = e.get("label", "RELATED")
                edge_type = e.get("type") or ("semantic" if label == "SIMILAR" else "graph")
                edges.append({
                    "source": src,
                    "target": dst,
                    "type": edge_type,
                    "label": label,
                    "similarity": e.get("similarity"),
                    "properties": {}
                })
        
        logger.info(f"Loaded {len(nodes)} nodes, {len(edges)} edges from snapshot")
        
        return {
            "nodes": nodes,
            "edges": edges,
            "project_registry": _project_registry_snapshot(data),
            "project_registry_generated_at": data.get(
                "project_registry_generated_at"
            ),
            "generated_at": data.get("generated_at"),
            "snapshot_context": _snapshot_context(data),
            "stats": data.get("stats", {
                "total_nodes": len(nodes),
                "memories": sum(1 for n in nodes if n.get("type") == "memory"),
                "entities": sum(1 for n in nodes if n.get("type") != "memory"),
                "edges": len(edges),
            }),
        }
        
    except Exception as error:
        logger.error(f"Failed to fetch graph data: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read dashboard snapshot")

@app.get("/api/search")
async def search_memories(
    query: str = Query(min_length=1, max_length=1000),
    limit: int = Query(default=5, ge=1, le=50),
    min_similarity: float = Query(default=0.5, ge=0.0, le=1.0),
):
    """Search the existing, redacted dashboard snapshot lexically."""
    try:
        snapshot = _read_snapshot()
        flat_results = _snapshot_search(snapshot, query, limit, min_similarity) if snapshot else []
        return {
            "success": True,
            "count": len(flat_results),
            "results": flat_results
        }
    except Exception as error:
        logger.error(f"Dashboard snapshot search failed: {error}")
        return {"success": False, "count": 0, "results": [], "error": "Snapshot search is unavailable"}


@app.get("/health")
async def health_check():
    """Simple health check endpoint for connection testing"""
    return {"status": "ok", "service": "elefante-dashboard"}


@app.get("/api/control-config")
async def get_control_config(request: Request):
    """Advertise control only when this page can pass the daemon origin gate."""
    if _request_origin(request) not in DEFAULT_DASHBOARD_CORS_ORIGINS:
        return {
            "available": False,
            "mode": "snapshot_only",
            "reason_code": "CONTROL_ORIGIN_UNAVAILABLE",
            "reason": "Live controls are intentionally unavailable from this dashboard origin.",
        }
    snapshot = _read_snapshot()
    if snapshot and _snapshot_context(snapshot)["mode"] == "showcase":
        return {
            "available": False,
            "mode": "snapshot_only",
            "reason_code": "SHOWCASE_SNAPSHOT_READ_ONLY",
            "reason": "Live controls are intentionally unavailable for example data.",
        }
    try:
        return {
            "available": True,
            "mode": "live_control",
            "daemon_host": "127.0.0.1",
            "daemon_port": _daemon_port(),
            "session_path": "/control/session",
        }
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="The local Elefante service configuration is invalid",
        )


@app.get("/api/stats")
async def get_stats():
    """Get system statistics from snapshot (LAW #1: No direct DB access)"""
    try:
        data = _read_snapshot()
        if data is None:
            return {"error": "Snapshot not found. Run update_dashboard_data.py first."}
        cfg = get_config()
        try:
            from src import __version__ as pkg_version
        except Exception:
            pkg_version = None

        snapshot_stat = data.get("stats", {}) if isinstance(data.get("stats", {}), dict) else {}
        snapshot_generated_at = data.get("generated_at", "unknown")

        return {
            "elefante": {
                "package_version": pkg_version,
                "config_version": getattr(cfg.elefante, "version", None),
            },
            "vector_store": {
                "total_memories": snapshot_stat.get("memories", 0),
            },
            "graph_store": {
                "total_entities": snapshot_stat.get("entities", 0),
                "total_relationships": snapshot_stat.get("edges", 0),
            },
            "snapshot": {
                "generated_at": snapshot_generated_at,
                "total_nodes": snapshot_stat.get("total_nodes", 0),
                "memories": snapshot_stat.get("memories", 0),
                "entities": snapshot_stat.get("entities", 0),
                "edges": snapshot_stat.get("edges", 0),
                "health": snapshot_stat.get("health", {}),
                "usage": snapshot_stat.get("usage", {}),
            }
        }
    except Exception as error:
        logger.error(f"Failed to fetch stats: {error}")
        raise HTTPException(status_code=500, detail="Could not read dashboard snapshot")


@app.get("/api/session-intelligence")
async def get_session_intelligence():
    """Read the usage snapshot plus content-free health of the owning process."""
    try:
        data = _read_session_intelligence_snapshot()
        status_reader = getattr(app.state, "session_intelligence_capture_status", None)
        capture_status = status_reader() if callable(status_reader) else None
        if data is None:
            return {
                "schema_version": 1,
                "generated_at": None,
                "consent": {"schema_version": 1, "enabled": False, "purposes": []},
                "signal_card": None,
                "enterprise_report": None,
                "privacy": {
                    "metadata_only": True,
                    "prompts_stored": False,
                    "transcripts_stored": False,
                    "responses_stored": False,
                    "employee_ranking": False,
                    "sensitive_trait_inference": False,
                },
            }
        if capture_status is not None:
            data = {**data, "capture": capture_status}
        return data
    except Exception as error:
        logger.error(f"Failed to read Session Intelligence snapshot: {error}")
        raise HTTPException(
            status_code=500,
            detail="Could not read Session Intelligence snapshot",
        )

# Serve Frontend
# We assume the frontend is built to src/dashboard/ui/dist
frontend_path = os.path.join(os.path.dirname(__file__), "ui", "dist")

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    @app.get("/")
    def index():
        return {"message": "Elefante Dashboard API is running. Frontend not found (run 'npm run build' in src/dashboard/ui)."}

def start_server(host: Optional[str] = None, port: int = 8000):
    """Start the dashboard server"""
    # Configure Uvicorn to log to stderr to avoid corrupting MCP stdout stream
    # MCP uses stdout for JSON-RPC, so application logs must go to stderr
    log_config = uvicorn.config.LOGGING_CONFIG.copy()
    log_config["handlers"]["default"]["stream"] = "ext://sys.stderr"
    log_config["handlers"]["access"]["stream"] = "ext://sys.stderr"
    
    uvicorn.run(app, host=host or _dashboard_host(), port=port, log_config=log_config)

def serve_dashboard_in_thread(host: Optional[str] = None, port: int = 8000):
    """Start the dashboard server in a background thread"""
    thread = threading.Thread(target=start_server, args=(host, port), daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    start_server()
