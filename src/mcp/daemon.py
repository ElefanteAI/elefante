"""Loopback-only Streamable HTTP daemon for the Elefante MCP surface."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Awaitable, Callable

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from src.mcp.server import ElefanteMCPServer
from src.utils.logger import get_logger

logger = get_logger(__name__)
DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 8765
MAX_DAEMON_REQUEST_BYTES = 1_048_576


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


def create_app() -> Starlette:
    """Create one HTTP application backed by one Elefante MCP server instance."""
    elefante = ElefanteMCPServer()
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

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/mcp", app=BoundedRequestBody(sessions.handle_request)),
        ],
        lifespan=lifespan,
    )


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
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
