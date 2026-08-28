"""Focused contracts for pure host-event normalization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.integrations.event_adapters import (
    EventBoundsError,
    EventContractError,
    EventKind,
    EventEnvelope,
    EventProvenance,
    FileEventPayload,
    HostFamily,
    HOST_FAMILY_BY_ID,
    MAX_EVENT_TEXT_CHARS,
    MAX_SURFACE_CONTEXT_CHARS,
    SUPPORTED_HOSTS,
    UnknownEventError,
    UnknownHostError,
    adapt_host_event,
    get_host_adapter,
    normalize_host_event,
)


STAMP = datetime(2026, 8, 28, 15, 30, tzinfo=timezone.utc)
MANIFEST_HOST_IDS = {
    "vscode-copilot",
    "claude-code",
    "cursor",
    "windsurf",
    "bob",
    "kiro",
    "kiro-steering",
    "cline",
    "roo",
    "kilo",
    "continue",
    "zed",
    "gemini",
    "antigravity",
    "codex",
    "aider",
    "openclaw",
    "agent-zero",
}


def _adapt(host: str, event: str, payload: dict[str, object]):
    return adapt_host_event(
        host,
        event,
        payload,
        source="test-host",
        timestamp=STAMP,
        workspace="/workspace/project",
    )


def test_file_event_is_typed_bounded_and_surface_context_compatible() -> None:
    envelope = _adapt(
        "vscode-copilot",
        "file_changed",
        {
            "path": "src/example.py",
            "change": "modified",
            "content": "return decision_context",
            "language_id": "python",
            "line_start": 12,
            "line_end": 14,
            "vendor_private_field": "ignored",
        },
    )

    assert isinstance(envelope, EventEnvelope)
    assert envelope.kind is EventKind.FILE
    assert envelope.host == "vscode-copilot"
    assert envelope.source == "test-host"
    assert envelope.timestamp == STAMP
    assert envelope.payload == FileEventPayload(
        path="src/example.py",
        operation="modified",
        content="return decision_context",
        language="python",
        line_start=12,
        line_end=14,
    )
    assert "vendor_private_field" not in envelope.to_surface_context()
    assert len(envelope.to_surface_context()) <= MAX_SURFACE_CONTEXT_CHARS
    assert len(envelope.to_surface_context().encode("utf-8")) <= 4096


def test_terminal_error_and_conversation_events_have_distinct_typed_payloads() -> None:
    terminal = _adapt(
        "codex",
        "terminal_error",
        {
            "command_line": "pytest tests/test_example.py",
            "error": "command failed",
            "output": "AssertionError",
            "exit_code": 1,
            "working_directory": "/workspace/project",
        },
    )
    conversation = _adapt(
        "cursor",
        "chat-message",
        {"role": "human", "text": "Remember the release boundary."},
    )

    assert terminal.kind is EventKind.TERMINAL_ERROR
    assert terminal.payload.message == "command failed"
    assert terminal.payload.stderr == "AssertionError"
    assert terminal.payload.exit_code == 1
    assert terminal.to_surface_context().startswith("terminal error: command failed")
    assert conversation.kind is EventKind.CONVERSATION
    assert conversation.payload.role == "user"
    assert conversation.payload.content == "Remember the release boundary."
    assert conversation.to_retrieval_input() == conversation.to_surface_context()


@pytest.mark.parametrize("host", sorted(SUPPORTED_HOSTS))
def test_every_manifest_host_has_an_explicit_family_adapter(host: str) -> None:
    envelope = _adapt(
        host,
        "file",
        {"path": "README.md", "operation": "opened"},
    )

    assert envelope.host == host
    assert HOST_FAMILY_BY_ID[host] in set(HostFamily)
    assert get_host_adapter(host) is not None


def test_manifest_planned_host_ids_are_all_mapped() -> None:
    assert MANIFEST_HOST_IDS <= SUPPORTED_HOSTS


def test_known_host_aliases_are_explicitly_canonicalized() -> None:
    assert _adapt("ibm-bob", "file", {"path": "README.md"}).host == "bob"
    assert _adapt("open-claw", "conversation", {"role": "user", "content": "Hi"}).host == "openclaw"


def test_wire_event_supports_nested_provenance_without_persistence() -> None:
    envelope = normalize_host_event(
        {
            "host": "gemini-cli",
            "event": "conversation_message",
            "payload": {"role": "assistant", "content": "A bounded answer."},
            "provenance": {
                "source": "gemini",
                "timestamp": "2026-08-28T15:30:00Z",
                "instance_id": "session-1",
            },
        }
    )

    assert envelope.host == "gemini"
    assert envelope.timestamp == STAMP
    assert envelope.provenance.instance_id == "session-1"


def test_timestamp_provenance_is_normalized_to_utc() -> None:
    envelope = _adapt(
        "cursor",
        "file",
        {"path": "README.md"},
    )
    offset_provenance = EventProvenance(
        source=envelope.source,
        host=envelope.host,
        timestamp=datetime(
            2026, 8, 28, 17, 30, tzinfo=timezone(timedelta(hours=2))
        ),
    )

    assert offset_provenance.timestamp == datetime(
        2026, 8, 28, 15, 30, tzinfo=timezone.utc
    )


def test_default_privacy_scrubber_redacts_secret_before_surface_context() -> None:
    envelope = _adapt(
        "claude-code",
        "terminal-error",
        {
            "message": "request failed token=abcdefghijklmnopqrstuvwxyz1234567890",
            "command": "curl https://example.test",
        },
    )

    context = envelope.to_surface_context()
    assert "abcdefghijklmnopqrstuvwxyz1234567890" not in context
    assert "[REDACTED:ENV_SECRET]" in context
    assert "message" in envelope.redacted_fields


def test_custom_privacy_scrubbing_hook_is_applied_to_all_text_fields() -> None:
    def scrub(value: str) -> str:
        return value.replace("PRIVATE", "[scrubbed]")

    envelope = adapt_host_event(
        "agent-zero",
        "conversation",
        {"role": "user", "content": "PRIVATE decision"},
        source="PRIVATE-source",
        timestamp=STAMP,
        scrubber=scrub,
    )

    assert "PRIVATE" not in envelope.to_surface_context()
    assert envelope.source == "[scrubbed]-source"
    assert set(envelope.redacted_fields) == {"content", "source"}


def test_oversized_input_and_rendered_context_fail_closed() -> None:
    with pytest.raises(EventBoundsError, match="content exceeds"):
        _adapt(
            "codex",
            "conversation",
            {"role": "user", "content": "x" * (MAX_EVENT_TEXT_CHARS + 1)},
        )

    with pytest.raises(EventBoundsError, match="surface context exceeds"):
        _adapt("codex", "file", {"path": "x" * 1001})


def test_unknown_hosts_events_and_malformed_contracts_fail_closed() -> None:
    with pytest.raises(UnknownHostError):
        _adapt("unknown-editor", "file", {"path": "README.md"})
    with pytest.raises(UnknownEventError):
        _adapt("codex", "screen-capture", {"path": "README.md"})
    with pytest.raises(EventContractError, match="message or stderr"):
        _adapt("codex", "terminal-error", {"command": "false"})
    with pytest.raises(EventContractError, match="timezone-aware"):
        adapt_host_event(
            "codex",
            "file",
            {"path": "README.md"},
            source="test",
            timestamp=datetime(2026, 8, 28),
        )


def test_conflicting_aliases_and_invalid_line_range_are_rejected() -> None:
    with pytest.raises(EventContractError, match="Conflicting values"):
        _adapt(
            "cursor",
            "file",
            {"path": "README.md", "content": "one", "text": "two"},
        )
    with pytest.raises(EventContractError, match="line_end"):
        _adapt(
            "cursor",
            "file",
            {"path": "README.md", "line_start": 10, "line_end": 2},
        )


def test_envelope_is_immutable_and_carries_provenance_without_io(tmp_path) -> None:
    envelope = _adapt("kiro", "file", {"path": "README.md"})
    assert envelope.provenance == EventProvenance(
        source="test-host",
        host="kiro",
        timestamp=STAMP,
        workspace="/workspace/project",
    )
    with pytest.raises(AttributeError):
        envelope.surface_context = "changed"  # type: ignore[misc]
    assert list(tmp_path.iterdir()) == []
