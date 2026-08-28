"""Pure, fail-closed normalization for host context events.

The adapters in this module deliberately stop at an in-memory event envelope.
They do not read host configuration, write host configuration, persist events,
or call the Elefante daemon.  A primary integration layer can pass
``EventEnvelope.to_surface_context()`` to the existing read-only
``surface_context`` retrieval input.

Host payloads are intentionally small allowlists.  Vendor-specific fields not
listed in a family contract are ignored rather than copied into retrieval
context.  This keeps a future host adapter from silently widening the privacy
and token boundary.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, TypedDict, TypeAlias

from src.modules.distiller.privacy import PrivacyFilter


# The MCP surface currently accepts ``surface_context`` as a string of at most
# 1,000 characters.  The event layer keeps a smaller per-field budget so the
# rendered context has room for its event label and file/command metadata.
MAX_SURFACE_CONTEXT_CHARS = 1_000
MAX_SURFACE_CONTEXT_BYTES = 4_096
MAX_EVENT_FIELD_CHARS = 4_096
MAX_EVENT_TEXT_CHARS = 800
MAX_EVENT_IDENTIFIER_CHARS = 256
MAX_SERIALIZED_PAYLOAD_BYTES = 8_192
MAX_LINE_NUMBER = 1_000_000
MAX_EXIT_CODE = 2**31 - 1


class EventAdapterError(ValueError):
    """Base class for fail-closed event normalization errors."""


class UnknownHostError(EventAdapterError):
    """Raised when no explicit host contract exists for an input host."""


class UnknownEventError(EventAdapterError):
    """Raised when a known host does not declare an input event alias."""


class EventContractError(EventAdapterError):
    """Raised when a known event violates its typed input contract."""


class EventBoundsError(EventContractError):
    """Raised before normalization can consume an unbounded input value."""


class EventKind(str, Enum):
    """Event kinds that can be converted to retrieval ``surface_context``."""

    FILE = "file"
    TERMINAL_ERROR = "terminal-error"
    CONVERSATION = "conversation"


# Backward-friendly name for callers that prefer the longer term.
HostEventKind = EventKind


class HostFamily(str, Enum):
    """Explicit input-protocol families represented by the host matrix."""

    VSCODE = "vscode"
    JSON = "json"
    CLI = "cli"
    IDE = "ide"
    EXTENSION = "extension"
    COMMUNITY = "community"


class FileEventInput(TypedDict, total=False):
    """Allowlisted file-event fields accepted from a host adapter."""

    path: str
    operation: str
    change: str
    content: str
    text: str
    diff: str
    language: str
    language_id: str
    line_start: int
    line_end: int


class TerminalErrorInput(TypedDict, total=False):
    """Allowlisted terminal-error fields accepted from a host adapter."""

    command: str
    command_line: str
    message: str
    error: str
    stderr: str
    output: str
    exit_code: int
    cwd: str
    working_directory: str


class ConversationEventInput(TypedDict, total=False):
    """Allowlisted conversation-event fields accepted from a host adapter."""

    role: str
    content: str
    message: str
    text: str
    conversation_id: str
    session_id: str
    message_id: str


EventPayloadInput: TypeAlias = (
    FileEventInput | TerminalErrorInput | ConversationEventInput
)


class HostEventInput(TypedDict, total=False):
    """Wire-level envelope accepted by :func:`normalize_host_event`.

    ``host``, ``event``, ``source``, ``timestamp``, and ``payload`` are
    required at runtime.  ``provenance`` is an explicitly supported nested
    spelling for bridges that already group provenance fields.
    """

    host: str
    event: str
    type: str
    source: str
    timestamp: datetime | str
    instance_id: str
    workspace: str
    session_id: str
    payload: Mapping[str, object]
    provenance: Mapping[str, object]


class PrivacyHook(Protocol):
    """Callable hook for replacing secret-shaped text before envelope build."""

    def __call__(self, value: str) -> object:
        """Return scrubbed text or ``(scrubbed_text, redaction_metadata)``."""


@dataclass(frozen=True, slots=True)
class FileEventPayload:
    """Normalized file event with bounded, scrubbed text fields."""

    path: str
    operation: str = "changed"
    content: str | None = None
    language: str | None = None
    line_start: int | None = None
    line_end: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.path, "path", max_chars=MAX_EVENT_FIELD_CHARS)
        if self.operation not in FILE_OPERATIONS:
            raise EventContractError(f"Unsupported file operation: {self.operation!r}")
        _validate_optional_text(self.content, "content", max_chars=MAX_EVENT_TEXT_CHARS)
        _validate_optional_text(self.language, "language", max_chars=128)
        _validate_line_range(self.line_start, self.line_end)


@dataclass(frozen=True, slots=True)
class TerminalErrorPayload:
    """Normalized terminal failure with bounded command and diagnostic text."""

    message: str
    command: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    cwd: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.message, "message", max_chars=MAX_EVENT_TEXT_CHARS)
        _validate_optional_text(self.command, "command", max_chars=MAX_EVENT_TEXT_CHARS)
        _validate_optional_text(self.stderr, "stderr", max_chars=MAX_EVENT_TEXT_CHARS)
        _validate_optional_text(self.cwd, "cwd", max_chars=MAX_EVENT_FIELD_CHARS)
        _validate_exit_code(self.exit_code)


@dataclass(frozen=True, slots=True)
class ConversationEventPayload:
    """Normalized user/assistant/system conversation message."""

    role: str
    content: str
    conversation_id: str | None = None
    message_id: str | None = None

    def __post_init__(self) -> None:
        if self.role not in CONVERSATION_ROLES:
            raise EventContractError(f"Unsupported conversation role: {self.role!r}")
        _require_text(self.content, "content", max_chars=MAX_EVENT_TEXT_CHARS)
        _validate_optional_text(
            self.conversation_id,
            "conversation_id",
            max_chars=MAX_EVENT_IDENTIFIER_CHARS,
        )
        _validate_optional_text(
            self.message_id,
            "message_id",
            max_chars=MAX_EVENT_IDENTIFIER_CHARS,
        )


EventPayload: TypeAlias = (
    FileEventPayload | TerminalErrorPayload | ConversationEventPayload
)


@dataclass(frozen=True, slots=True)
class EventProvenance:
    """Source, canonical host, and timestamp carried with every event."""

    source: str
    host: str
    timestamp: datetime
    instance_id: str | None = None
    workspace: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.source, "source", max_chars=MAX_EVENT_IDENTIFIER_CHARS)
        _require_text(self.host, "host", max_chars=MAX_EVENT_IDENTIFIER_CHARS)
        object.__setattr__(self, "timestamp", _validate_timestamp(self.timestamp))
        _validate_optional_text(
            self.instance_id,
            "instance_id",
            max_chars=MAX_EVENT_IDENTIFIER_CHARS,
        )
        _validate_optional_text(self.workspace, "workspace", max_chars=MAX_EVENT_FIELD_CHARS)
        _validate_optional_text(
            self.session_id,
            "session_id",
            max_chars=MAX_EVENT_IDENTIFIER_CHARS,
        )


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Immutable, non-persistent event envelope for retrieval adaptation."""

    kind: EventKind
    payload: EventPayload
    provenance: EventProvenance
    redacted_fields: tuple[str, ...] = ()
    surface_context: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EventKind):
            try:
                object.__setattr__(self, "kind", EventKind(self.kind))
            except (TypeError, ValueError) as error:
                raise EventContractError("Envelope kind is invalid") from error

        expected_payload = {
            EventKind.FILE: FileEventPayload,
            EventKind.TERMINAL_ERROR: TerminalErrorPayload,
            EventKind.CONVERSATION: ConversationEventPayload,
        }[self.kind]
        if not isinstance(self.payload, expected_payload):
            raise EventContractError(
                f"{self.kind.value} event has the wrong payload type"
            )
        if not isinstance(self.provenance, EventProvenance):
            raise EventContractError("Envelope provenance is invalid")

        rendered = self.surface_context or _render_surface_context(
            self.kind, self.payload
        )
        _validate_context(rendered)
        object.__setattr__(self, "surface_context", rendered)
        object.__setattr__(
            self,
            "redacted_fields",
            tuple(sorted(set(self.redacted_fields))),
        )
        serialized = json.dumps(asdict(self.payload), sort_keys=True, default=str)
        if len(serialized.encode("utf-8")) > MAX_SERIALIZED_PAYLOAD_BYTES:
            raise EventBoundsError("Normalized event payload exceeds its byte limit")

    @property
    def source(self) -> str:
        """Convenience access to the provenance source."""

        return self.provenance.source

    @property
    def host(self) -> str:
        """Convenience access to the canonical provenance host."""

        return self.provenance.host

    @property
    def timestamp(self) -> datetime:
        """Convenience access to the UTC provenance timestamp."""

        return self.provenance.timestamp

    def to_surface_context(self) -> str:
        """Return the bounded string accepted by ``surface_context`` search."""

        return self.surface_context

    # Explicit alias for callers that name the target retrieval input.
    def to_retrieval_input(self) -> str:
        """Return the existing retrieval input representation."""

        return self.to_surface_context()


FILE_OPERATIONS = frozenset(
    {"created", "modified", "deleted", "renamed", "opened", "saved", "changed"}
)
CONVERSATION_ROLES = frozenset({"user", "assistant", "system"})


# Canonical host IDs mirror the current integration manifest, including
# compatible, partial, planned, and community surfaces.  Configuration status
# is deliberately not inferred by this module: this is only an input contract.
HOST_FAMILY_BY_ID: Mapping[str, HostFamily] = {
    "vscode-copilot": HostFamily.VSCODE,
    "bob": HostFamily.VSCODE,
    "cursor": HostFamily.JSON,
    "kiro": HostFamily.JSON,
    "gemini": HostFamily.JSON,
    "kiro-steering": HostFamily.IDE,
    "claude-code": HostFamily.CLI,
    "codex": HostFamily.CLI,
    "openclaw": HostFamily.CLI,
    "aider": HostFamily.CLI,
    "windsurf": HostFamily.IDE,
    "zed": HostFamily.IDE,
    "antigravity": HostFamily.IDE,
    "cline": HostFamily.EXTENSION,
    "roo": HostFamily.EXTENSION,
    "kilo": HostFamily.EXTENSION,
    "continue": HostFamily.EXTENSION,
    "agent-zero": HostFamily.COMMUNITY,
}
SUPPORTED_HOSTS = frozenset(HOST_FAMILY_BY_ID)

HOST_ALIASES: Mapping[str, str] = {
    "vscode": "vscode-copilot",
    "vs-code": "vscode-copilot",
    "github-copilot": "vscode-copilot",
    "ibm-bob": "bob",
    "gemini-cli": "gemini",
    "claude": "claude-code",
    "open-claw": "openclaw",
    "agent_zero": "agent-zero",
}


# Each family gets an explicit event vocabulary.  Canonical names are included
# for all families; aliases cover only known vendor spellings and are not
# fuzzy-matched.
EVENT_ALIASES_BY_FAMILY: Mapping[HostFamily, Mapping[str, EventKind]] = {
    family: {
        "file": EventKind.FILE,
        "file-change": EventKind.FILE,
        "file_changed": EventKind.FILE,
        "file-changed": EventKind.FILE,
        "file_saved": EventKind.FILE,
        "file-saved": EventKind.FILE,
        "terminal-error": EventKind.TERMINAL_ERROR,
        "terminal_error": EventKind.TERMINAL_ERROR,
        "terminal-failure": EventKind.TERMINAL_ERROR,
        "command-error": EventKind.TERMINAL_ERROR,
        "conversation": EventKind.CONVERSATION,
        "conversation-message": EventKind.CONVERSATION,
        "conversation_message": EventKind.CONVERSATION,
        "chat-message": EventKind.CONVERSATION,
        "message": EventKind.CONVERSATION,
    }
    for family in HostFamily
}


# Explicit field allowlists are part of the adapter contract.  Unknown vendor
# fields are ignored; only these names/aliases can affect the envelope.
INPUT_FIELDS_BY_KIND: Mapping[EventKind, frozenset[str]] = {
    EventKind.FILE: frozenset(
        {
            "path",
            "operation",
            "change",
            "content",
            "text",
            "diff",
            "language",
            "language_id",
            "line_start",
            "line_end",
        }
    ),
    EventKind.TERMINAL_ERROR: frozenset(
        {
            "command",
            "command_line",
            "message",
            "error",
            "stderr",
            "output",
            "exit_code",
            "cwd",
            "working_directory",
        }
    ),
    EventKind.CONVERSATION: frozenset(
        {
            "role",
            "content",
            "message",
            "text",
            "conversation_id",
            "session_id",
            "message_id",
        }
    ),
}


def _require_text(value: object, field_name: str, *, max_chars: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EventContractError(f"{field_name} must be a non-empty string")
    if len(value) > max_chars:
        raise EventBoundsError(
            f"{field_name} exceeds the {max_chars}-character limit"
        )
    return value


def _validate_optional_text(
    value: object | None,
    field_name: str,
    *,
    max_chars: int,
) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise EventContractError(f"{field_name} must be a string when provided")
    if len(value) > max_chars:
        raise EventBoundsError(
            f"{field_name} exceeds the {max_chars}-character limit"
        )


def _validate_line_range(line_start: int | None, line_end: int | None) -> None:
    for field_name, value in (("line_start", line_start), ("line_end", line_end)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise EventContractError(f"{field_name} must be an integer")
        if value < 1 or value > MAX_LINE_NUMBER:
            raise EventBoundsError(f"{field_name} is outside the supported range")
    if line_start is not None and line_end is not None and line_end < line_start:
        raise EventContractError("line_end cannot be before line_start")


def _validate_exit_code(exit_code: int | None) -> None:
    if exit_code is None:
        return
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise EventContractError("exit_code must be an integer")
    if exit_code < -MAX_EXIT_CODE - 1 or exit_code > MAX_EXIT_CODE:
        raise EventBoundsError("exit_code is outside the supported range")


def _validate_timestamp(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise EventContractError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise EventContractError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return _validate_timestamp(value)
    if not isinstance(value, str):
        raise EventContractError("timestamp must be an ISO string or datetime")
    if len(value) > MAX_EVENT_IDENTIFIER_CHARS:
        raise EventBoundsError("timestamp exceeds its character limit")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise EventContractError("timestamp is not valid ISO-8601") from error
    return _validate_timestamp(parsed)


def _normalize_host(host: object) -> str:
    if not isinstance(host, str):
        raise UnknownHostError("host must be a string")
    normalized = host.strip().casefold()
    canonical = HOST_ALIASES.get(normalized, normalized)
    if canonical not in SUPPORTED_HOSTS:
        raise UnknownHostError(f"Unsupported host: {host!r}")
    return canonical


def _normalize_event(event: object, family: HostFamily) -> EventKind:
    if not isinstance(event, str):
        raise UnknownEventError("event must be a string")
    normalized = event.strip().casefold()
    try:
        return EVENT_ALIASES_BY_FAMILY[family][normalized]
    except KeyError as error:
        raise UnknownEventError(
            f"Unsupported {family.value} event: {event!r}"
        ) from error


def _invoke_scrubber(value: str, scrubber: PrivacyHook | Callable[[str], object] | None) -> tuple[str, tuple[str, ...]]:
    hook: object = scrubber or _default_privacy_hook
    if hasattr(hook, "scrub") and callable(getattr(hook, "scrub")):
        result = getattr(hook, "scrub")(value)
    elif callable(hook):
        result = hook(value)
    else:
        raise EventContractError("privacy scrubber must be callable or expose scrub()")

    redaction_types: tuple[str, ...] = ()
    if isinstance(result, tuple):
        if len(result) != 2:
            raise EventContractError("privacy scrubber tuple result must have two items")
        clean, metadata = result
        if hasattr(metadata, "redacted_types"):
            raw_types = getattr(metadata, "redacted_types")
            redaction_types = tuple(str(item) for item in raw_types)
        elif isinstance(metadata, Sequence) and not isinstance(metadata, (str, bytes)):
            redaction_types = tuple(str(item) for item in metadata)
    else:
        clean = result

    if not isinstance(clean, str):
        raise EventContractError("privacy scrubber must return scrubbed text")
    return clean, redaction_types


def _default_privacy_hook(value: str) -> tuple[str, tuple[str, ...]]:
    clean, result = PrivacyFilter().scrub(value)
    return clean, tuple(result.redacted_types)


def _clean_text(
    value: object,
    field_name: str,
    redacted_fields: set[str],
    *,
    scrubber: PrivacyHook | Callable[[str], object] | None,
    required: bool = False,
    max_chars: int = MAX_EVENT_TEXT_CHARS,
) -> str | None:
    if value is None:
        if required:
            raise EventContractError(f"{field_name} is required")
        return None
    if not isinstance(value, str):
        raise EventContractError(f"{field_name} must be a string")
    if required and not value.strip():
        raise EventContractError(f"{field_name} is required")
    if len(value) > min(MAX_EVENT_FIELD_CHARS, max_chars):
        raise EventBoundsError(
            f"{field_name} exceeds the {min(MAX_EVENT_FIELD_CHARS, max_chars)}-character limit"
        )
    clean, redaction_types = _invoke_scrubber(value, scrubber)
    if clean != value or redaction_types:
        redacted_fields.add(field_name)
    if required and not clean.strip():
        raise EventContractError(f"{field_name} is empty after privacy scrubbing")
    if len(clean) > max_chars:
        raise EventBoundsError(
            f"scrubbed {field_name} exceeds the {max_chars}-character limit"
        )
    return clean


def _lookup_field(payload: Mapping[str, object], names: Sequence[str]) -> object | None:
    present = [name for name in names if name in payload]
    if not present:
        return None
    value = payload[present[0]]
    for name in present[1:]:
        if payload[name] != value:
            raise EventContractError(
                f"Conflicting values supplied for aliases: {', '.join(present)}"
            )
    return value


def _normalize_operation(value: object, *, default: str = "changed") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise EventContractError("file operation must be a string")
    operation = value.strip().casefold().replace("_", "-")
    aliases = {
        "change": "changed",
        "modify": "modified",
        "write": "modified",
        "save": "saved",
        "delete": "deleted",
        "create": "created",
        "rename": "renamed",
        "open": "opened",
    }
    normalized = aliases.get(operation, operation)
    if normalized not in FILE_OPERATIONS:
        raise EventContractError(f"Unsupported file operation: {value!r}")
    return normalized


def _normalize_integer(value: object | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventContractError(f"{field_name} must be an integer")
    return value


def _adapt_file_payload(
    payload: Mapping[str, object],
    *,
    scrubber: PrivacyHook | Callable[[str], object] | None,
    redacted_fields: set[str],
) -> FileEventPayload:
    path = _clean_text(
        _lookup_field(payload, ("path",)),
        "path",
        redacted_fields,
        scrubber=scrubber,
        required=True,
        max_chars=MAX_EVENT_FIELD_CHARS,
    )
    operation = _normalize_operation(
        _lookup_field(payload, ("operation", "change"))
    )
    content = _clean_text(
        _lookup_field(payload, ("content", "text", "diff")),
        "content",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_TEXT_CHARS,
    )
    language = _clean_text(
        _lookup_field(payload, ("language", "language_id")),
        "language",
        redacted_fields,
        scrubber=scrubber,
        max_chars=128,
    )
    line_start = _normalize_integer(
        _lookup_field(payload, ("line_start",)), "line_start"
    )
    line_end = _normalize_integer(_lookup_field(payload, ("line_end",)), "line_end")
    _validate_line_range(line_start, line_end)
    return FileEventPayload(
        path=path or "",
        operation=operation,
        content=content,
        language=language,
        line_start=line_start,
        line_end=line_end,
    )


def _adapt_terminal_payload(
    payload: Mapping[str, object],
    *,
    scrubber: PrivacyHook | Callable[[str], object] | None,
    redacted_fields: set[str],
) -> TerminalErrorPayload:
    message = _clean_text(
        _lookup_field(payload, ("message", "error")),
        "message",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_TEXT_CHARS,
    )
    stderr = _clean_text(
        _lookup_field(payload, ("stderr", "output")),
        "stderr",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_TEXT_CHARS,
    )
    if not message and not stderr:
        raise EventContractError("terminal-error requires message or stderr")
    command = _clean_text(
        _lookup_field(payload, ("command", "command_line")),
        "command",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_TEXT_CHARS,
    )
    cwd = _clean_text(
        _lookup_field(payload, ("cwd", "working_directory")),
        "cwd",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_FIELD_CHARS,
    )
    exit_code = _normalize_integer(_lookup_field(payload, ("exit_code",)), "exit_code")
    _validate_exit_code(exit_code)
    return TerminalErrorPayload(
        message=message or stderr or "",
        command=command,
        stderr=stderr,
        exit_code=exit_code,
        cwd=cwd,
    )


def _adapt_conversation_payload(
    payload: Mapping[str, object],
    *,
    scrubber: PrivacyHook | Callable[[str], object] | None,
    redacted_fields: set[str],
) -> ConversationEventPayload:
    role_value = _lookup_field(payload, ("role",))
    if not isinstance(role_value, str):
        raise EventContractError("conversation role is required")
    role_aliases = {"human": "user", "bot": "assistant"}
    role = role_aliases.get(role_value.strip().casefold(), role_value.strip().casefold())
    if role not in CONVERSATION_ROLES:
        raise EventContractError(f"Unsupported conversation role: {role_value!r}")
    content = _clean_text(
        _lookup_field(payload, ("content", "message", "text")),
        "content",
        redacted_fields,
        scrubber=scrubber,
        required=True,
        max_chars=MAX_EVENT_TEXT_CHARS,
    )
    conversation_id = _clean_text(
        _lookup_field(payload, ("conversation_id", "session_id")),
        "conversation_id",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_IDENTIFIER_CHARS,
    )
    message_id = _clean_text(
        _lookup_field(payload, ("message_id",)),
        "message_id",
        redacted_fields,
        scrubber=scrubber,
        max_chars=MAX_EVENT_IDENTIFIER_CHARS,
    )
    return ConversationEventPayload(
        role=role,
        content=content or "",
        conversation_id=conversation_id,
        message_id=message_id,
    )


def _render_surface_context(kind: EventKind, payload: EventPayload) -> str:
    if kind is EventKind.FILE:
        assert isinstance(payload, FileEventPayload)
        fields = [f"file change: {payload.path}", f"operation={payload.operation}"]
        if payload.language:
            fields.append(f"language={payload.language}")
        if payload.line_start is not None:
            line_range = str(payload.line_start)
            if payload.line_end is not None:
                line_range += f"-{payload.line_end}"
            fields.append(f"lines={line_range}")
        if payload.content:
            fields.append(f"content={payload.content}")
        return " | ".join(fields)

    if kind is EventKind.TERMINAL_ERROR:
        assert isinstance(payload, TerminalErrorPayload)
        fields = [f"terminal error: {payload.message}"]
        if payload.command:
            fields.append(f"command={payload.command}")
        if payload.stderr and payload.stderr != payload.message:
            fields.append(f"stderr={payload.stderr}")
        if payload.exit_code is not None:
            fields.append(f"exit_code={payload.exit_code}")
        if payload.cwd:
            fields.append(f"cwd={payload.cwd}")
        return " | ".join(fields)

    assert isinstance(payload, ConversationEventPayload)
    fields = [f"{payload.role}: {payload.content}"]
    if payload.conversation_id:
        fields.append(f"conversation_id={payload.conversation_id}")
    return " | ".join(fields)


def _validate_context(context: str) -> None:
    if not isinstance(context, str) or not context:
        raise EventContractError("surface context must be non-empty text")
    if len(context) > MAX_SURFACE_CONTEXT_CHARS:
        raise EventBoundsError(
            f"surface context exceeds the {MAX_SURFACE_CONTEXT_CHARS}-character limit"
        )
    if len(context.encode("utf-8")) > MAX_SURFACE_CONTEXT_BYTES:
        raise EventBoundsError("surface context exceeds its UTF-8 byte limit")


def _normalize_provenance_text(
    value: object | None,
    field_name: str,
    *,
    scrubber: PrivacyHook | Callable[[str], object] | None,
    redacted_fields: set[str],
    max_chars: int,
) -> str | None:
    return _clean_text(
        value,
        field_name,
        redacted_fields,
        scrubber=scrubber,
        max_chars=max_chars,
    )


def _build_envelope(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None,
    workspace: str | None,
    session_id: str | None,
    family: HostFamily,
    scrubber: PrivacyHook | Callable[[str], object] | None,
) -> EventEnvelope:
    if not isinstance(payload, Mapping):
        raise EventContractError("payload must be an object/map")
    canonical_host = _normalize_host(host)
    actual_family = HOST_FAMILY_BY_ID[canonical_host]
    if actual_family is not family:
        raise EventContractError(
            f"host {canonical_host!r} does not belong to {family.value} family"
        )
    kind = _normalize_event(event, family)
    redacted_fields: set[str] = set()
    clean_source = _normalize_provenance_text(
        source,
        "source",
        scrubber=scrubber,
        redacted_fields=redacted_fields,
        max_chars=MAX_EVENT_IDENTIFIER_CHARS,
    )
    clean_instance = _normalize_provenance_text(
        instance_id,
        "instance_id",
        scrubber=scrubber,
        redacted_fields=redacted_fields,
        max_chars=MAX_EVENT_IDENTIFIER_CHARS,
    )
    clean_workspace = _normalize_provenance_text(
        workspace,
        "workspace",
        scrubber=scrubber,
        redacted_fields=redacted_fields,
        max_chars=MAX_EVENT_FIELD_CHARS,
    )
    clean_session = _normalize_provenance_text(
        session_id,
        "session_id",
        scrubber=scrubber,
        redacted_fields=redacted_fields,
        max_chars=MAX_EVENT_IDENTIFIER_CHARS,
    )
    if not clean_source:
        raise EventContractError("source is required")

    if kind is EventKind.FILE:
        normalized_payload: EventPayload = _adapt_file_payload(
            payload, scrubber=scrubber, redacted_fields=redacted_fields
        )
    elif kind is EventKind.TERMINAL_ERROR:
        normalized_payload = _adapt_terminal_payload(
            payload, scrubber=scrubber, redacted_fields=redacted_fields
        )
    else:
        normalized_payload = _adapt_conversation_payload(
            payload, scrubber=scrubber, redacted_fields=redacted_fields
        )

    provenance = EventProvenance(
        source=clean_source,
        host=canonical_host,
        timestamp=_parse_timestamp(timestamp),
        instance_id=clean_instance,
        workspace=clean_workspace,
        session_id=clean_session,
    )
    return EventEnvelope(
        kind=kind,
        payload=normalized_payload,
        provenance=provenance,
        redacted_fields=tuple(redacted_fields),
    )


def _family_adapter(
    family: HostFamily,
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    return _build_envelope(
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        family=family,
        scrubber=scrubber,
    )


def adapt_vscode_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Adapt VS Code/Copilot and IBM Bob event input."""

    return _family_adapter(
        HostFamily.VSCODE,
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


def adapt_json_host_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Adapt Cursor, Kiro, and Gemini JSON-host event input."""

    return _family_adapter(
        HostFamily.JSON,
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


def adapt_cli_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Adapt Claude Code, Codex, OpenClaw, or Aider event input."""

    return _family_adapter(
        HostFamily.CLI,
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


def adapt_ide_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Adapt Windsurf, Zed, and Antigravity event input."""

    return _family_adapter(
        HostFamily.IDE,
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


def adapt_extension_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Adapt Cline, Roo, Kilo, or Continue event input."""

    return _family_adapter(
        HostFamily.EXTENSION,
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


def adapt_community_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Adapt explicitly documented community-host event input."""

    return _family_adapter(
        HostFamily.COMMUNITY,
        host,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


FAMILY_ADAPTERS: Mapping[HostFamily, Callable[..., EventEnvelope]] = {
    HostFamily.VSCODE: adapt_vscode_event,
    HostFamily.JSON: adapt_json_host_event,
    HostFamily.CLI: adapt_cli_event,
    HostFamily.IDE: adapt_ide_event,
    HostFamily.EXTENSION: adapt_extension_event,
    HostFamily.COMMUNITY: adapt_community_event,
}


def get_host_adapter(host: str) -> Callable[..., EventEnvelope]:
    """Return the explicit family adapter for a known host, or fail closed."""

    canonical = _normalize_host(host)
    return FAMILY_ADAPTERS[HOST_FAMILY_BY_ID[canonical]]


def adapt_host_event(
    host: str,
    event: str,
    payload: Mapping[str, object],
    *,
    source: str,
    timestamp: datetime | str,
    instance_id: str | None = None,
    workspace: str | None = None,
    session_id: str | None = None,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Normalize one explicit host event through its registered family adapter."""

    canonical = _normalize_host(host)
    adapter = FAMILY_ADAPTERS[HOST_FAMILY_BY_ID[canonical]]
    return adapter(
        canonical,
        event,
        payload,
        source=source,
        timestamp=timestamp,
        instance_id=instance_id,
        workspace=workspace,
        session_id=session_id,
        scrubber=scrubber,
    )


def normalize_host_event(
    event: Mapping[str, object],
    *,
    scrubber: PrivacyHook | Callable[[str], object] | None = None,
) -> EventEnvelope:
    """Normalize a wire-level event object with explicit provenance fields."""

    if not isinstance(event, Mapping):
        raise EventContractError("host event must be an object/map")
    nested = event.get("provenance")
    provenance = nested if isinstance(nested, Mapping) else {}

    def value(name: str) -> object | None:
        return event.get(name, provenance.get(name))

    host = value("host")
    event_name = event.get("event", event.get("type"))
    source = value("source")
    timestamp = value("timestamp")
    payload = event.get("payload")
    if host is None or event_name is None or source is None or timestamp is None:
        raise EventContractError(
            "host, event, source, timestamp, and payload are required"
        )
    if not isinstance(payload, Mapping):
        raise EventContractError("payload must be an object/map")
    return adapt_host_event(
        host=str(host),
        event=str(event_name),
        payload=payload,
        source=source,
        timestamp=timestamp,
        instance_id=value("instance_id"),
        workspace=value("workspace"),
        session_id=value("session_id"),
        scrubber=scrubber,
    )


# Short aliases make the intended boundary easy to discover without creating
# a second implementation surface.
normalize_event = normalize_host_event
adapt_event = adapt_host_event


__all__ = [
    "ConversationEventInput",
    "ConversationEventPayload",
    "EVENT_ALIASES_BY_FAMILY",
    "EventAdapterError",
    "EventBoundsError",
    "EventContractError",
    "EventEnvelope",
    "EventKind",
    "EventPayload",
    "EventPayloadInput",
    "EventProvenance",
    "FileEventInput",
    "FileEventPayload",
    "FAMILY_ADAPTERS",
    "HOST_ALIASES",
    "HOST_FAMILY_BY_ID",
    "HostEventInput",
    "HostEventKind",
    "HostFamily",
    "INPUT_FIELDS_BY_KIND",
    "MAX_EVENT_FIELD_CHARS",
    "MAX_EVENT_TEXT_CHARS",
    "MAX_SERIALIZED_PAYLOAD_BYTES",
    "MAX_SURFACE_CONTEXT_BYTES",
    "MAX_SURFACE_CONTEXT_CHARS",
    "PrivacyHook",
    "SUPPORTED_HOSTS",
    "TerminalErrorInput",
    "TerminalErrorPayload",
    "UnknownEventError",
    "UnknownHostError",
    "adapt_cli_event",
    "adapt_community_event",
    "adapt_event",
    "adapt_extension_event",
    "adapt_host_event",
    "adapt_ide_event",
    "adapt_json_host_event",
    "adapt_vscode_event",
    "get_host_adapter",
    "normalize_event",
    "normalize_host_event",
]
