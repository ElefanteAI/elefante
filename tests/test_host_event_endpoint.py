"""Read-only daemon integration for automatic host event surfacing."""

from datetime import datetime, timezone

import pytest

from src.mcp.daemon import surface_host_event


class _Server:
    def __init__(self):
        self.arguments = None

    async def _handle_search_memories(self, arguments):
        self.arguments = arguments
        return {"success": True, "count": 1, "results": [{"content": "matched"}]}


@pytest.mark.asyncio
async def test_host_event_is_scrubbed_adapted_and_retrieved_without_persistence():
    server = _Server()
    result = await surface_host_event(
        server,
        {
            "host": "codex",
            "event": "terminal_error",
            "source": "codex-hook",
            "timestamp": datetime(2026, 8, 28, tzinfo=timezone.utc).isoformat(),
            "payload": {
                "message": "migration failed token=abcdefghijklmnopqrstuvwxyz1234567890",
                "command": "python migrate.py",
                "exit_code": 1,
            },
        },
    )

    assert result["success"] is True
    assert result["event_kind"] == "terminal-error"
    assert result["event_persisted"] is False
    assert "abcdefghijklmnopqrstuvwxyz1234567890" not in result["surface_context"]
    assert server.arguments["surface_context"] == result["surface_context"]
    assert server.arguments["include_conversation"] is False
    assert server.arguments["limit"] == 3
