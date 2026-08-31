"""Loopback-only Streamable HTTP daemon for the Elefante MCP surface."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import hashlib
import os
from collections.abc import Mapping
from typing import Awaitable, Callable

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from src.core.home_control import DEFAULT_HOME_ORIGINS, HomeControlError
from src.mcp.server import ElefanteMCPServer
from src.integrations.event_adapters import (
    EventAdapterError,
    MAX_SERIALIZED_PAYLOAD_BYTES,
    normalize_host_event,
)
from src.session_intelligence import (
    ConsentRequiredError,
    ingest_runtime_usage,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)
DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 8765
MAX_DAEMON_REQUEST_BYTES = 1_048_576
MAX_USAGE_EVENT_BYTES = 65_536
MAX_HOME_CONTROL_BYTES = 16_384


def _strict_json_object(body: bytes) -> dict[str, object]:
    """Decode one JSON object while rejecting duplicate keys."""
    if len(body) > MAX_HOME_CONTROL_BYTES:
        raise HomeControlError(
            "Home control request exceeds its byte limit.",
            code="CONTROL_BODY_TOO_LARGE",
            status_code=413,
        )

    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Home control JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        payload = json.loads(body.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise HomeControlError(
            "Home control request must be one valid JSON object.",
            code="CONTROL_JSON_INVALID",
            status_code=400,
        ) from error
    if not isinstance(payload, dict):
        raise HomeControlError(
            "Home control request must be one valid JSON object.",
            code="CONTROL_JSON_INVALID",
            status_code=400,
        )
    return payload


def _control_credentials(request: Request) -> tuple[str, str]:
    origin = request.headers.get("origin", "")
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HomeControlError(
            "Open Home through Elefante to manage memories.",
            code="CONTROL_AUTH_REQUIRED",
            status_code=401,
        )
    token = authorization[len(prefix) :].strip()
    if not 12 <= len(token) <= 256:
        raise HomeControlError(
            "Home control authorization is invalid.",
            code="CONTROL_SESSION_INVALID",
            status_code=401,
        )
    return token, origin


def _control_error(error: HomeControlError) -> JSONResponse:
    return JSONResponse(
        {
            "success": False,
            "error": str(error),
            "error_code": error.code,
        },
        status_code=error.status_code,
    )


async def surface_host_event(
    elefante: ElefanteMCPServer,
    event: Mapping[str, object],
) -> dict[str, object]:
    """Normalize one host event and run bounded read-only proactive retrieval."""
    envelope = normalize_host_event(event)
    context = envelope.to_surface_context()
    retrieval = await elefante._handle_search_memories(
        {
            "query": context,
            "surface_context": context,
            "limit": 3,
            "min_similarity": 0.1,
            "include_conversation": False,
            "include_stored": True,
        }
    )
    return {
        "success": True,
        "event_kind": envelope.kind.value,
        "host": envelope.host,
        "timestamp": envelope.timestamp.isoformat(),
        "redacted_fields": list(envelope.redacted_fields),
        "surface_context": context,
        "retrieval": retrieval,
        "event_persisted": False,
    }


class BoundedRequestBody:
    """Reject oversized HTTP requests before the MCP transport parses JSON."""

    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int = MAX_DAEMON_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        try:
            if any(int(value) > self.max_bytes for value in declared_lengths):
                await self._reject(scope, receive, send)
                return
        except ValueError:
            await self._reject(scope, receive, send, status=400, message="Invalid Content-Length")
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay_receive():
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(
        scope,
        receive,
        send,
        *,
        status: int = 413,
        message: str = "MCP request body exceeds 1048576 byte limit",
    ) -> None:
        response = JSONResponse({"error": message}, status_code=status)
        await response(scope, receive, send)


def create_app(*, elefante: ElefanteMCPServer | None = None) -> Starlette:
    """Create one HTTP application backed by one Elefante MCP server instance."""
    elefante = elefante or ElefanteMCPServer()
    sessions = StreamableHTTPSessionManager(elefante.server, json_response=True)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        app.state.elefante_server = elefante
        try:
            async with sessions.run():
                logger.info("elefante_daemon_started", transport="streamable-http")
                yield
        finally:
            await elefante.close()
            logger.info("elefante_daemon_stopped")

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "elefante-daemon", "transport": "streamable-http"})

    async def event_surface(request: Request) -> JSONResponse:
        body = await request.body()
        if len(body) > MAX_SERIALIZED_PAYLOAD_BYTES:
            return JSONResponse(
                {"success": False, "error": "Host event exceeds its byte limit"},
                status_code=413,
            )
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Host event must be a JSON object")
            result = await surface_host_event(elefante, payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, EventAdapterError) as error:
            return JSONResponse(
                {"success": False, "error": str(error)}, status_code=400
            )
        return JSONResponse(result)

    async def event_usage(request: Request) -> JSONResponse:
        """Ingest one opt-in, metadata-only provider or estimated usage event."""
        body = await request.body()
        if len(body) > MAX_USAGE_EVENT_BYTES:
            return JSONResponse(
                {"success": False, "error": "Usage event exceeds its byte limit"},
                status_code=413,
            )
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Usage event must be a JSON object")
            result = ingest_runtime_usage(payload)
        except ConsentRequiredError as error:
            return JSONResponse(
                {"success": False, "error": str(error), "consent_required": True},
                status_code=403,
            )
        except ValueError as error:
            return JSONResponse(
                {"success": False, "error": str(error)}, status_code=400
            )
        return JSONResponse(result)

    async def control_session(request: Request) -> JSONResponse:
        """Issue one browser-local capability without requiring an agent launch."""
        try:
            origin = request.headers.get("origin", "")
            if origin not in DEFAULT_HOME_ORIGINS:
                raise HomeControlError(
                    "Home control origin is not allowed.",
                    code="CONTROL_ORIGIN_REJECTED",
                    status_code=403,
                )
            payload = _strict_json_object(await request.body())
            if set(payload) - {"project_id"}:
                raise HomeControlError(
                    "Home session fields are invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )

            requested_project_id = payload.get("project_id")
            if requested_project_id is not None and not isinstance(
                requested_project_id,
                str,
            ):
                raise HomeControlError(
                    "Home project identity is invalid.",
                    code="CONTROL_PROJECT_INVALID",
                    status_code=400,
                )
            requested_project_id = str(requested_project_id or "").strip() or None

            registry = elefante._project_registry_snapshot()
            raw_projects = registry.get("projects")
            projects = raw_projects if isinstance(raw_projects, list) else []
            active_project_ids = {
                str(project.get("project_id"))
                for project in projects
                if isinstance(project, Mapping)
                and project.get("active") is True
                and project.get("root_status") != "missing"
                and isinstance(project.get("project_id"), str)
            }
            if requested_project_id is not None and requested_project_id not in active_project_ids:
                raise HomeControlError(
                    "Choose an active registered project for this Home session.",
                    code="CONTROL_PROJECT_INVALID",
                    status_code=400,
                )

            project_id = requested_project_id
            if (
                project_id is None
                and registry.get("status") == "ready"
                and registry.get("mode") == "strict"
                and len(active_project_ids) == 1
            ):
                project_id = next(iter(active_project_ids))

            grant = elefante.home_control.issue(origin, project_id=project_id)
            return JSONResponse(
                {
                    "success": True,
                    "token": grant.token,
                    "expires_in_seconds": grant.expires_in_seconds,
                    "project_id": project_id,
                },
                headers={
                    "Cache-Control": "no-store",
                    "Pragma": "no-cache",
                    "Referrer-Policy": "no-referrer",
                },
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_remember(request: Request) -> JSONResponse:
        """Remember once or return one content-free overlap choice ticket."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            allowed = {"content", "knowledge_kind", "verification_question"}
            if set(payload) != allowed:
                raise HomeControlError(
                    "Home Remember fields are invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            content = payload.get("content")
            question = payload.get("verification_question")
            knowledge_kind = payload.get("knowledge_kind")
            if (
                not isinstance(content, str)
                or not 1 <= len(content.strip()) <= 8000
                or not isinstance(question, str)
                or not 1 <= len(question.strip()) <= 1000
                or knowledge_kind
                not in {"decision", "constraint", "preference", "lesson"}
            ):
                raise HomeControlError(
                    "Home Remember requires a kind, durable text, and one future question.",
                    code="REMEMBER_INPUT_INVALID",
                    status_code=400,
                )
            content = content.strip()
            question = question.strip()
            session = elefante.home_control.authorize(token, origin)
            result = await elefante._handle_home_remember(
                session.project_id,
                {
                    "content": content,
                    "knowledge_kind": knowledge_kind,
                    "verification_question": question,
                },
            )
            plan_id = None
            raw_plan = result.get("plan")
            plan = dict(raw_plan) if isinstance(raw_plan, dict) else None
            if plan is not None:
                content_sha256 = plan.pop("content_sha256", None)
                plan.pop("scope_sha256", None)
                plan.pop("memory_type", None)
                raw_overlaps = plan.get("overlaps")
                safe_overlaps: list[dict[str, object]] = []
                overlap_sha256: dict[str, str] = {}
                if isinstance(raw_overlaps, list):
                    for raw_overlap in raw_overlaps:
                        if not isinstance(raw_overlap, dict):
                            continue
                        overlap = dict(raw_overlap)
                        record_sha256 = overlap.pop("record_sha256", None)
                        memory_id = overlap.get("memory_id")
                        if isinstance(memory_id, str) and isinstance(
                            record_sha256,
                            str,
                        ):
                            overlap_sha256[memory_id] = record_sha256
                        safe_overlaps.append(overlap)
                plan["overlaps"] = safe_overlaps
                if (
                    result.get("remember_status") == "NEEDS_HUMAN"
                    and plan.get("reason_code")
                    == "REMEMBER_OVERLAP_REQUIRES_CHOICE"
                    and isinstance(content_sha256, str)
                    and overlap_sha256
                    and session.project_id
                ):
                    plan_id = elefante.home_control.create_remember_plan_for_session(
                        session,
                        project_id=session.project_id,
                        knowledge_kind=str(knowledge_kind),
                        content_sha256=content_sha256,
                        question_sha256=hashlib.sha256(
                            question.encode("utf-8")
                        ).hexdigest(),
                        overlap_sha256=overlap_sha256,
                    )
            safe_result = dict(result)
            if plan is not None:
                safe_result["plan"] = plan
            safe_result["plan_id"] = plan_id
            status = str(result.get("remember_status") or result.get("status") or "")
            status_code = (
                200
                if status in {"VERIFIED_COMPLETE", "NEEDS_HUMAN"}
                else 500
                if status == "UNSAFE"
                else 409
            )
            return JSONResponse(safe_result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_remember_apply(request: Request) -> JSONResponse:
        """Consume one exact overlap plan and explicitly keep both records."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) != {
                "plan_id",
                "content",
                "verification_question",
                "choice",
                "confirm",
            }:
                raise HomeControlError(
                    "Home Remember apply fields are invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if payload.get("choice") != "keep_both" or payload.get("confirm") is not True:
                raise HomeControlError(
                    "Keeping both memories requires explicit confirmation.",
                    code="CONFIRMATION_REQUIRED",
                    status_code=400,
                )
            plan_id = payload.get("plan_id")
            content = payload.get("content")
            question = payload.get("verification_question")
            if (
                not isinstance(plan_id, str)
                or not 8 <= len(plan_id) <= 256
                or not isinstance(content, str)
                or not 1 <= len(content.strip()) <= 8000
                or not isinstance(question, str)
                or not 1 <= len(question.strip()) <= 1000
            ):
                raise HomeControlError(
                    "Home Remember apply input is invalid.",
                    code="REMEMBER_INPUT_INVALID",
                    status_code=400,
                )
            content = content.strip()
            question = question.strip()
            ticket = elefante.home_control.consume_remember_plan(
                token,
                origin,
                plan_id,
                content=content,
                verification_question=question,
            )
            result = await elefante._handle_home_remember(
                ticket.project_id,
                {
                    "content": content,
                    "knowledge_kind": ticket.knowledge_kind,
                    "verification_question": question,
                    "overlap_choice": "keep_both",
                    "expected_overlap_sha256": ticket.overlap_sha256,
                },
            )
            status = str(result.get("remember_status") or result.get("status") or "")
            status_code = (
                200
                if status == "VERIFIED_COMPLETE"
                else 500
                if status == "UNSAFE"
                else 409
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_recall_test(request: Request) -> JSONResponse:
        """Run one project-bound Recall question without returning memory content."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) != {"question"} or not isinstance(
                payload.get("question"),
                str,
            ):
                raise HomeControlError(
                    "Home Recall test requires one question.",
                    code="RECALL_TEST_QUESTION_INVALID",
                    status_code=400,
                )
            question = str(payload["question"])
            if not 1 <= len(question.strip()) <= 1000:
                raise HomeControlError(
                    "Home Recall test question is invalid.",
                    code="RECALL_TEST_QUESTION_INVALID",
                    status_code=400,
                )
            session = elefante.home_control.authorize(token, origin)
            result = await elefante._handle_home_recall_test(
                session.project_id,
                question,
            )
            status = str(result.get("recall_status") or "unavailable")
            status_code = (
                200
                if status in {"supplied", "no_match"}
                else 409
                if status == "blocked"
                else 503
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_resolve_plan(request: Request) -> JSONResponse:
        """Inspect one exact pair and mint a one-use plan ticket."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            allowed = {
                "memory_id",
                "related_memory_id",
                "winner_memory_id",
                "confirm_protected",
            }
            if set(payload) - allowed:
                raise HomeControlError(
                    "Home Resolve plan contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if not isinstance(payload.get("memory_id"), str) or not isinstance(
                payload.get("related_memory_id"), str
            ):
                raise HomeControlError(
                    "Home Resolve requires two memory IDs.",
                    code="RESOLVE_IDS_INVALID",
                    status_code=400,
                )
            if payload.get("winner_memory_id") is not None and not isinstance(
                payload.get("winner_memory_id"), str
            ):
                raise HomeControlError(
                    "Home Resolve winner ID is invalid.",
                    code="RESOLVE_IDS_INVALID",
                    status_code=400,
                )
            if not isinstance(payload.get("confirm_protected", False), bool):
                raise HomeControlError(
                    "Home Resolve protected confirmation is invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            session = elefante.home_control.authorize(token, origin)
            normalized = {
                "memory_id": payload["memory_id"],
                "related_memory_id": payload["related_memory_id"],
                "winner_memory_id": payload.get("winner_memory_id"),
                "confirm_protected": payload.get("confirm_protected") is True,
            }
            result = await elefante._handle_home_resolve_plan(normalized)
            if result.get("success") is not True:
                return JSONResponse(result, status_code=400)
            plan = dict(result["plan"])
            record_sha256 = plan.pop("record_sha256", None)
            plan_id = None
            if plan.get("applicable") is True:
                resolution = plan.get("resolution")
                if not isinstance(resolution, Mapping):
                    raise HomeControlError(
                        "Home Resolve plan is incomplete.",
                        code="CONTROL_PLAN_INVALID",
                        status_code=500,
                    )
                plan_id = elefante.home_control.create_resolve_plan_for_session(
                    session,
                    left_memory_id=str(normalized["memory_id"]),
                    right_memory_id=str(normalized["related_memory_id"]),
                    winner_memory_id=(
                        str(resolution.get("winner_memory_id"))
                        if resolution.get("winner_memory_id")
                        else None
                    ),
                    confirm_protected=bool(normalized["confirm_protected"]),
                    record_sha256=record_sha256 or {},
                )
            return JSONResponse(
                {
                    "success": True,
                    "plan_id": plan_id,
                    "plan": plan,
                }
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_resolve_apply(request: Request) -> JSONResponse:
        """Consume one exact plan and execute Verified Resolve once."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            allowed = {
                "plan_id",
                "confirm",
                "reason",
                "verification_question",
            }
            if set(payload) - allowed:
                raise HomeControlError(
                    "Home Resolve apply contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if payload.get("confirm") is not True:
                raise HomeControlError(
                    "Explicit confirmation is required before correction.",
                    code="CONFIRMATION_REQUIRED",
                    status_code=400,
                )
            plan_id = payload.get("plan_id")
            reason = payload.get("reason")
            verification_question = payload.get("verification_question")
            if not isinstance(plan_id, str) or not 8 <= len(plan_id) <= 256:
                raise HomeControlError(
                    "Home Resolve plan ID is invalid.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=400,
                )
            if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
                raise HomeControlError(
                    "A bounded audit reason is required.",
                    code="AUDIT_REASON_REQUIRED",
                    status_code=400,
                )
            if not isinstance(verification_question, str) or not (
                1 <= len(verification_question.strip()) <= 1000
            ):
                raise HomeControlError(
                    "A bounded disposable Recall question is required.",
                    code="VERIFICATION_QUESTION_REQUIRED",
                    status_code=400,
                )
            ticket = elefante.home_control.consume_resolve_plan(
                token,
                origin,
                plan_id,
            )
            result = await elefante._handle_home_resolve_apply(
                ticket,
                reason=reason,
                verification_question=verification_question,
            )
            status = str(result.get("resolution_status") or "")
            status_code = (
                200
                if status in {"VERIFIED_COMPLETE", "FAILED_ROLLED_BACK"}
                else 500
                if status == "UNSAFE"
                else 409
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_correction_plan(request: Request) -> JSONResponse:
        """Inspect one exact customer correction, including advanced deletion."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            allowed = {
                "memory_id",
                "correction",
                "content",
                "confirm_protected",
            }
            if set(payload) - allowed:
                raise HomeControlError(
                    "Home Correct plan contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            memory_id = payload.get("memory_id")
            correction = payload.get("correction")
            content = payload.get("content")
            if not isinstance(memory_id, str):
                raise HomeControlError(
                    "Home Correct requires one memory ID.",
                    code="CORRECTION_INPUT_INVALID",
                    status_code=400,
                )
            if not isinstance(correction, str) or correction not in {
                "edit",
                "replace",
                "archive",
                "restore",
                "permanent_delete",
            }:
                raise HomeControlError(
                    "Home correction action is invalid.",
                    code="CORRECTION_ACTION_INVALID",
                    status_code=400,
                )
            if correction in {"edit", "replace"}:
                if not isinstance(content, str) or not 1 <= len(content.strip()) <= 10000:
                    raise HomeControlError(
                        "Edit and Replace require bounded corrected text.",
                        code="CORRECTION_CONTENT_REQUIRED",
                        status_code=400,
                    )
            elif "content" in payload:
                raise HomeControlError(
                    "This correction does not accept replacement text.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if not isinstance(payload.get("confirm_protected", False), bool):
                raise HomeControlError(
                    "Home Correct protected confirmation is invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            session = elefante.home_control.authorize(token, origin)
            normalized = {
                "memory_id": memory_id,
                "correction": correction,
                "confirm_protected": payload.get("confirm_protected") is True,
            }
            if isinstance(content, str):
                normalized["content"] = content
            result = await elefante._handle_home_correction_plan(normalized)
            if result.get("success") is not True:
                return JSONResponse(result, status_code=400)
            plan = dict(result["plan"])
            record_sha256 = plan.pop("record_sha256", None)
            graph_sha256 = plan.pop("graph_sha256", None)
            content_sha256 = plan.pop("content_sha256", None)
            plan_id = None
            if plan.get("applicable") is True:
                plan_id = elefante.home_control.create_correction_plan_for_session(
                    session,
                    memory_id=memory_id,
                    action=correction,
                    confirm_protected=bool(normalized["confirm_protected"]),
                    record_sha256=(
                        record_sha256 if isinstance(record_sha256, Mapping) else {}
                    ),
                    graph_sha256=(
                        graph_sha256 if isinstance(graph_sha256, Mapping) else {}
                    ),
                    content_sha256=(
                        str(content_sha256)
                        if isinstance(content_sha256, str)
                        else None
                    ),
                )
            return JSONResponse(
                {
                    "success": True,
                    "plan_id": plan_id,
                    "plan": plan,
                    "privacy_redactions": result.get("privacy_redactions", 0),
                    "privacy_redacted_types": result.get(
                        "privacy_redacted_types",
                        [],
                    ),
                }
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_correction_apply(request: Request) -> JSONResponse:
        """Consume one exact Correct plan and execute it once."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            allowed = {
                "plan_id",
                "confirm",
                "content",
                "reason",
                "verification_question",
                "confirm_permanent",
            }
            if set(payload) - allowed:
                raise HomeControlError(
                    "Home Correct apply contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if payload.get("confirm") is not True:
                raise HomeControlError(
                    "Explicit confirmation is required before correction.",
                    code="CONFIRMATION_REQUIRED",
                    status_code=400,
                )
            plan_id = payload.get("plan_id")
            reason = payload.get("reason")
            verification_question = payload.get("verification_question")
            content = payload.get("content")
            if not isinstance(plan_id, str) or not 8 <= len(plan_id) <= 256:
                raise HomeControlError(
                    "Home Correct plan ID is invalid.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=400,
                )
            if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
                raise HomeControlError(
                    "A bounded audit reason is required.",
                    code="AUDIT_REASON_REQUIRED",
                    status_code=400,
                )
            if not isinstance(verification_question, str) or not (
                1 <= len(verification_question.strip()) <= 1000
            ):
                raise HomeControlError(
                    "A bounded disposable Recall question is required.",
                    code="VERIFICATION_QUESTION_REQUIRED",
                    status_code=400,
                )
            if content is not None and (
                not isinstance(content, str) or not 1 <= len(content.strip()) <= 10000
            ):
                raise HomeControlError(
                    "Corrected text is invalid.",
                    code="CORRECTION_CONTENT_REQUIRED",
                    status_code=400,
                )
            if "confirm_permanent" in payload and not isinstance(
                payload["confirm_permanent"],
                bool,
            ):
                raise HomeControlError(
                    "Permanent deletion confirmation is invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            ticket = elefante.home_control.consume_correction_plan(
                token,
                origin,
                plan_id,
                confirm_permanent=payload.get("confirm_permanent") is True,
            )
            result = await elefante._handle_home_correction_apply(
                ticket,
                content=(str(content) if isinstance(content, str) else None),
                reason=reason,
                verification_question=verification_question,
                confirm_permanent=payload.get("confirm_permanent") is True,
            )
            status = str(result.get("correction_status") or "")
            status_code = (
                200
                if status in {"VERIFIED_COMPLETE", "FAILED_ROLLED_BACK"}
                else 500
                if status == "UNSAFE"
                else 409
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_recovery_plan(request: Request) -> JSONResponse:
        """Inspect one configured Recover operation and issue a one-use ticket."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) - {"action", "archive_name"}:
                raise HomeControlError(
                    "Home Recover plan contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            action = payload.get("action")
            if action not in {"health", "backup", "restore", "support_report"}:
                raise HomeControlError(
                    "Home Recover action is unsupported.",
                    code="RECOVERY_ACTION_UNSUPPORTED",
                    status_code=400,
                )
            archive_name = payload.get("archive_name")
            if action != "restore" and archive_name is not None:
                raise HomeControlError(
                    "This Recover action does not accept a restore archive.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if archive_name is not None and not isinstance(archive_name, str):
                raise HomeControlError(
                    "Recover archive selection is invalid.",
                    code="RECOVERY_ARCHIVE_NAME_INVALID",
                    status_code=400,
                )
            session = elefante.home_control.authorize(token, origin)
            result = await elefante._handle_home_recovery_plan(
                action=str(action),
                archive_name=archive_name,
                project_id=session.project_id,
            )
            if result.get("success") is not True:
                return JSONResponse(result, status_code=400)
            recovery_project_id = result.pop("_recovery_project_id", None)
            recovery_workspace_sha256 = result.pop(
                "_recovery_workspace_sha256",
                None,
            )
            raw_plan = result.get("plan")
            plan = dict(raw_plan) if isinstance(raw_plan, dict) else None
            plan_id = None
            if plan is not None:
                layout_sha256 = plan.pop("layout_sha256", None)
                archive_sha256 = plan.pop("archive_sha256", None)
                report_sha256 = plan.pop("report_sha256", None)
                plan.pop("source_sha256", None)
            else:
                layout_sha256 = None
                archive_sha256 = None
                report_sha256 = None
            if plan is not None and plan.get("applicable") is True:
                if action == "support_report" and not isinstance(
                    report_sha256,
                    str,
                ):
                    raise HomeControlError(
                        "Home support-report plan is incomplete.",
                        code="CONTROL_PLAN_INVALID",
                        status_code=500,
                    )
                if action != "support_report" and not isinstance(
                    layout_sha256,
                    str,
                ):
                    raise HomeControlError(
                        "Home Recover plan is incomplete.",
                        code="CONTROL_PLAN_INVALID",
                        status_code=500,
                    )
                plan_id = elefante.home_control.create_recovery_plan_for_session(
                    session,
                    action=str(action),
                    layout_sha256=layout_sha256,
                    archive_name=(
                        str(plan.get("archive_name"))
                        if action == "restore"
                        else None
                    ),
                    archive_sha256=(
                        archive_sha256 if action == "restore" else None
                    ),
                    report_sha256=(
                        report_sha256 if action == "support_report" else None
                    ),
                    project_id=(
                        recovery_project_id if action == "restore" else None
                    ),
                    workspace_sha256=(
                        recovery_workspace_sha256
                        if action == "restore"
                        else None
                    ),
                )
            safe_backups = []
            for item in result.get("available_backups", []):
                if not isinstance(item, dict):
                    continue
                safe_item = dict(item)
                safe_item.pop("archive_sha256", None)
                safe_item.pop("source_sha256", None)
                safe_backups.append(safe_item)
            return JSONResponse(
                {
                    "success": True,
                    "plan_id": plan_id,
                    "plan": plan,
                    "health": result.get("health"),
                    "available_backups": safe_backups,
                    "recovery_history": result.get("recovery_history", []),
                }
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_recovery_apply(request: Request) -> JSONResponse:
        """Consume one exact Recover plan and execute it once."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) - {
                "plan_id",
                "action",
                "confirm",
                "verification_question",
            }:
                raise HomeControlError(
                    "Home Recover apply contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if payload.get("confirm") is not True:
                raise HomeControlError(
                    "Explicit confirmation is required before Recover applies.",
                    code="CONFIRMATION_REQUIRED",
                    status_code=400,
                )
            action = payload.get("action", "backup")
            if action not in {"backup", "restore", "support_report"}:
                raise HomeControlError(
                    "Home Recover action is unsupported.",
                    code="RECOVERY_ACTION_UNSUPPORTED",
                    status_code=400,
                )
            verification_question = payload.get("verification_question")
            if action == "restore" and (
                not isinstance(verification_question, str)
                or not 1 <= len(verification_question.strip()) <= 500
            ):
                raise HomeControlError(
                    "Restore requires a private Recall verification question.",
                    code="RECOVERY_VERIFICATION_QUESTION_REQUIRED",
                    status_code=400,
                )
            if action in {"backup", "support_report"} and verification_question is not None:
                raise HomeControlError(
                    "This Recover action does not accept a restore verification question.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            plan_id = payload.get("plan_id")
            if not isinstance(plan_id, str) or not 8 <= len(plan_id) <= 256:
                raise HomeControlError(
                    "Home Recover plan ID is invalid.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=400,
                )
            ticket = elefante.home_control.consume_recovery_plan(
                token,
                origin,
                plan_id,
            )
            if ticket.action != action:
                raise HomeControlError(
                    "Recover apply does not match the inspected action.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=409,
                )
            result = await elefante._handle_home_recovery_apply(
                ticket,
                verification_question=(
                    verification_question if action == "restore" else None
                ),
            )
            status = str(result.get("recovery_status") or "")
            status_code = (
                200
                if status in {"VERIFIED_COMPLETE", "FAILED_ROLLED_BACK"}
                else 500
                if status == "UNSAFE"
                else 409
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_support_report_download(request: Request) -> Response:
        """Download one verified, managed support report through authenticated Home."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) != {"archive_name"} or not isinstance(
                payload.get("archive_name"),
                str,
            ):
                raise HomeControlError(
                    "Support-report download selection is invalid.",
                    code="RECOVERY_SUPPORT_REPORT_NAME_INVALID",
                    status_code=400,
                )
            elefante.home_control.authorize(token, origin)
            archive_name = str(payload["archive_name"])
            try:
                report = elefante._verified_recovery_service().support_report_bytes(
                    archive_name
                )
            except FileNotFoundError as error:
                raise HomeControlError(
                    "The selected support report is no longer available.",
                    code="RECOVERY_SUPPORT_REPORT_NOT_FOUND",
                    status_code=404,
                ) from error
            except (OSError, ValueError) as error:
                raise HomeControlError(
                    "The selected support report failed verification.",
                    code="RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID",
                    status_code=409,
                ) from error
            return Response(
                report,
                media_type="application/zip",
                headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": f'attachment; filename="{archive_name}"',
                    "X-Content-Type-Options": "nosniff",
                },
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_project_review_list(request: Request) -> JSONResponse:
        """List bounded legacy project-review items without memory content."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) != {"offset", "limit"} or not all(
                isinstance(payload.get(key), int) and not isinstance(payload.get(key), bool)
                for key in ("offset", "limit")
            ):
                raise HomeControlError(
                    "Project review pagination is invalid.",
                    code="PROJECT_REVIEW_PAGE_INVALID",
                    status_code=400,
                )
            elefante.home_control.authorize(token, origin)
            result = await elefante._legacy_unscoped_review(
                offset=int(payload["offset"]),
                limit=int(payload["limit"]),
            )
            return JSONResponse(
                result,
                status_code=200 if result.get("success") is True else 409,
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_project_assignment_plan(request: Request) -> JSONResponse:
        """Inspect one exact unassigned memory and mint a one-use ticket."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) != {
                "memory_id",
                "project_id",
                "confirm_protected",
            }:
                raise HomeControlError(
                    "Project assignment fields are invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if (
                not isinstance(payload.get("memory_id"), str)
                or not isinstance(payload.get("project_id"), str)
                or not isinstance(payload.get("confirm_protected"), bool)
            ):
                raise HomeControlError(
                    "Project assignment input is invalid.",
                    code="PROJECT_ASSIGNMENT_INPUT_INVALID",
                    status_code=400,
                )
            session = elefante.home_control.authorize(token, origin)
            result = await elefante._handle_home_project_assignment_plan(
                dict(payload)
            )
            raw_plan = result.get("plan")
            plan = dict(raw_plan) if isinstance(raw_plan, dict) else None
            plan_id = None
            if plan is not None:
                record_sha256 = plan.pop("record_sha256", None)
                graph_sha256 = plan.pop("graph_sha256", None)
                relationship_sha256 = plan.pop("relationship_sha256", None)
                target_scope_sha256 = plan.pop("target_scope_sha256", None)
                graph_existed = plan.pop("graph_existed", None)
                if (
                    plan.get("applicable") is True
                    and isinstance(record_sha256, str)
                    and isinstance(graph_existed, bool)
                    and (graph_sha256 is None or isinstance(graph_sha256, str))
                    and isinstance(relationship_sha256, str)
                    and isinstance(target_scope_sha256, str)
                ):
                    plan_id = elefante.home_control.create_project_assignment_plan_for_session(
                        session,
                        memory_id=str(plan.get("memory_id") or ""),
                        project_id=str(plan.get("project_id") or ""),
                        confirm_protected=payload["confirm_protected"] is True,
                        record_sha256=record_sha256,
                        graph_existed=graph_existed,
                        graph_sha256=graph_sha256,
                        relationship_sha256=relationship_sha256,
                        target_scope_sha256=target_scope_sha256,
                    )
            safe_result = dict(result)
            if plan is not None:
                safe_result["plan"] = plan
            safe_result["plan_id"] = plan_id
            return JSONResponse(
                safe_result,
                status_code=200 if result.get("success") is True else 409,
            )
        except HomeControlError as error:
            return _control_error(error)

    async def control_project_assignment_apply(request: Request) -> JSONResponse:
        """Consume one assignment ticket and return content-free proof."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            if set(payload) != {"plan_id", "confirm"}:
                raise HomeControlError(
                    "Project assignment apply fields are invalid.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            if (
                not isinstance(payload.get("plan_id"), str)
                or not 8 <= len(str(payload["plan_id"])) <= 256
                or payload.get("confirm") is not True
            ):
                raise HomeControlError(
                    "Project assignment requires explicit confirmation.",
                    code="CONFIRMATION_REQUIRED",
                    status_code=400,
                )
            ticket = elefante.home_control.consume_project_assignment_plan(
                token,
                origin,
                str(payload["plan_id"]),
            )
            result = await elefante._handle_home_project_assignment_apply(ticket)
            status = str(result.get("assignment_status") or result.get("status") or "")
            status_code = (
                200
                if status == "VERIFIED_COMPLETE"
                else 500
                if status == "UNSAFE"
                else 409
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    async def control_projects_manage(request: Request) -> JSONResponse:
        """Apply one explicit, bounded Project Registry action from Home."""
        try:
            token, origin = _control_credentials(request)
            payload = _strict_json_object(await request.body())
            allowed = {
                "action",
                "project_id",
                "name",
                "root",
                "active",
                "mode",
                "confirm",
            }
            if set(payload) - allowed:
                raise HomeControlError(
                    "Home project action contains unsupported fields.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            action = payload.get("action")
            if not isinstance(action, str) or action not in {
                "register",
                "update",
                "remove",
                "set_mode",
            }:
                raise HomeControlError(
                    "Home project action is invalid.",
                    code="PROJECT_ACTION_INVALID",
                    status_code=400,
                )
            if "active" in payload and not isinstance(payload["active"], bool):
                raise HomeControlError(
                    "Project active state must be true or false.",
                    code="PROJECT_ACTIVE_INVALID",
                    status_code=400,
                )
            if "confirm" in payload and not isinstance(payload["confirm"], bool):
                raise HomeControlError(
                    "Project confirmation must be true or false.",
                    code="CONFIRMATION_REQUIRED",
                    status_code=400,
                )
            for key in ("project_id", "name", "root", "mode"):
                if key in payload and not isinstance(payload[key], str):
                    raise HomeControlError(
                        "Home project text fields are invalid.",
                        code="PROJECT_INPUT_INVALID",
                        status_code=400,
                    )

            action_fields = {
                "register": {"action", "name", "root"},
                "update": {"action", "project_id", "name", "root", "active"},
                "remove": {"action", "project_id", "confirm"},
                "set_mode": {"action", "mode", "confirm"},
            }[action]
            if set(payload) - action_fields:
                raise HomeControlError(
                    "Fields do not match the selected project action.",
                    code="CONTROL_FIELDS_INVALID",
                    status_code=400,
                )
            required = {
                "register": {"name", "root"},
                "update": {"project_id"},
                "remove": {"project_id", "confirm"},
                "set_mode": {"mode", "confirm"},
            }[action]
            if not required.issubset(payload):
                raise HomeControlError(
                    "Home project action is incomplete.",
                    code="PROJECT_INPUT_INVALID",
                    status_code=400,
                )

            elefante.home_control.authorize(token, origin)
            result = await elefante._handle_home_project_action(dict(payload))
            status_code = (
                200
                if result.get("success") is True
                else 500
                if result.get("changed") is True
                else 409
            )
            return JSONResponse(result, status_code=status_code)
        except HomeControlError as error:
            return _control_error(error)

    control_app = Starlette(
        routes=[
            Route("/session", control_session, methods=["POST"]),
            Route("/remember", control_remember, methods=["POST"]),
            Route("/remember/apply", control_remember_apply, methods=["POST"]),
            Route("/recall/test", control_recall_test, methods=["POST"]),
            Route("/resolve/plan", control_resolve_plan, methods=["POST"]),
            Route("/resolve/apply", control_resolve_apply, methods=["POST"]),
            Route("/corrections/plan", control_correction_plan, methods=["POST"]),
            Route("/corrections/apply", control_correction_apply, methods=["POST"]),
            Route("/recovery/plan", control_recovery_plan, methods=["POST"]),
            Route("/recovery/apply", control_recovery_apply, methods=["POST"]),
            Route(
                "/recovery/support-report/download",
                control_support_report_download,
                methods=["POST"],
            ),
            Route(
                "/projects/unscoped/list",
                control_project_review_list,
                methods=["POST"],
            ),
            Route(
                "/projects/unscoped/plan",
                control_project_assignment_plan,
                methods=["POST"],
            ),
            Route(
                "/projects/unscoped/apply",
                control_project_assignment_apply,
                methods=["POST"],
            ),
            Route("/projects/manage", control_projects_manage, methods=["POST"]),
        ]
    )
    control_app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(DEFAULT_HOME_ORIGINS),
        allow_credentials=False,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/events/surface", event_surface, methods=["POST"]),
            Route("/events/usage", event_usage, methods=["POST"]),
            Mount("/control", app=control_app),
            Mount("/mcp", app=BoundedRequestBody(sessions.handle_request)),
        ],
        lifespan=lifespan,
    )
    return app


def daemon_port() -> int:
    """Read an explicit, valid local TCP port from the environment."""
    raw_port = os.environ.get("ELEFANTE_DAEMON_PORT", str(DEFAULT_DAEMON_PORT)).strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError("ELEFANTE_DAEMON_PORT must be an integer from 1 to 65535") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("ELEFANTE_DAEMON_PORT must be an integer from 1 to 65535")
    return port


def main() -> None:
    """Run the local daemon; remote exposure is intentionally unsupported."""
    host = os.environ.get("ELEFANTE_DAEMON_HOST", DEFAULT_DAEMON_HOST).strip()
    if host != DEFAULT_DAEMON_HOST:
        raise RuntimeError("Elefante daemon must bind to 127.0.0.1")
    port = daemon_port()
    from src.dashboard.server import serve_dashboard_in_thread

    serve_dashboard_in_thread(port=8000)
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
