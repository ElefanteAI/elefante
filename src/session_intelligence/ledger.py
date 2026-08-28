"""A local, metadata-only Session Intelligence event ledger.

This module deliberately has no network, credential, model, or MCP imports.
It keeps three evidence planes separate:

* usage facts are either provider-actual or locally estimated;
* money is known only for complete provider-actual usage plus a matching,
  versioned local rate card; and
* accepted-outcome evidence is a separate, explicitly recorded record.

The ledger is disabled until a caller grants an explicit purpose.  Raw prompts,
transcripts, responses, arbitrary tool arguments, and hidden reasoning are not
accepted by the event boundary and have no database columns.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4


SCHEMA_VERSION = 1
UNKNOWN = "UNKNOWN"
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 3650
DEFAULT_DB_PATH = Path.home() / ".elefante" / "data" / "session_intelligence.db"

PURPOSE_USAGE_ANALYTICS = "usage_analytics"
PURPOSE_PROVIDER_USAGE = "provider_usage"
PURPOSE_ENTERPRISE_TRAINING = "enterprise_training"
SUPPORTED_PURPOSES = frozenset(
    {
        PURPOSE_USAGE_ANALYTICS,
        PURPOSE_PROVIDER_USAGE,
        PURPOSE_ENTERPRISE_TRAINING,
    }
)


class SessionIntelligenceError(ValueError):
    """Base error for fail-closed Session Intelligence operations."""


class ConsentRequiredError(SessionIntelligenceError):
    """Raised before a usage or outcome record can be persisted."""


class PrivacyViolationError(SessionIntelligenceError):
    """Raised when an event attempts to cross the metadata-only boundary."""


class IdempotencyConflictError(SessionIntelligenceError):
    """Raised when an identifier is reused with different metadata."""


class SchemaVersionError(SessionIntelligenceError):
    """Raised when a database was created by an unsupported schema version."""


class AntiSurveillanceError(SessionIntelligenceError):
    """Raised for employee ranking or sensitive-trait inference requests."""


class UnknownEventError(SessionIntelligenceError):
    """Raised when an event or session control targets an unknown identifier."""


class EvidenceClass(str, Enum):
    """Non-interchangeable evidence classes used in output and storage."""

    PROVIDER_ACTUAL = "provider_actual"
    LOCAL_MEASURED = "local_measured"
    LOCAL_ESTIMATED = "local_estimated"
    USER_ASSERTED = "user_asserted"
    CAUSALLY_EVALUATED = "causally_evaluated"
    UNKNOWN = UNKNOWN


class UsageKind(str, Enum):
    """The mutually exclusive usage payload variants."""

    PROVIDER_ACTUAL = "provider_actual"
    ESTIMATED = "estimated"


class EventStatus(str, Enum):
    """Bounded invocation result statuses from the PRD."""

    SUCCESS = "success"
    ERROR = "error"
    IGNORED = "ignored"
    BLOCKED = "blocked"


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_IDENTIFIER_CHARACTERS = re.compile(r"[^a-z0-9_.:-]+")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_PROVIDER_USAGE_KEYS = frozenset(
    {
        "provider",
        "model",
        "provider_input_tokens",
        "provider_cached_input_tokens",
        "provider_output_tokens",
        "usage_source",
    }
)
_ESTIMATED_USAGE_KEYS = frozenset(
    {
        "estimated_input_tokens",
        "estimated_output_tokens",
        "estimated_overhead_tokens",
        "estimated_signal_ratio",
        "estimator",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "argument",
        "arguments",
        "chat",
        "completion",
        "content",
        "conversation",
        "prompt",
        "query",
        "raw_prompt",
        "raw_response",
        "reasoning",
        "response",
        "text",
        "thought",
        "thoughts",
        "transcript",
        "tool_arguments",
    }
)
_SENSITIVE_TRAIT_TERMS = frozenset(
    {
        "age",
        "belief",
        "disability",
        "ethnicity",
        "gender",
        "health",
        "immigration",
        "medical",
        "politics",
        "pregnancy",
        "race",
        "religion",
        "sex",
        "sexuality",
        "union",
    }
)
_PROHIBITED_GROUP_TERMS = frozenset(
    {
        "employee",
        "employee_id",
        "person",
        "person_id",
        "user",
        "user_id",
        "worker",
        "worker_id",
    }
)
_CURRENCY_EXPONENTS = {
    "BHD": 3,
    "JOD": 3,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
    "JPY": 0,
    "KRW": 0,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: datetime | str | None, *, default_now: bool = False) -> datetime:
    if value is None:
        if not default_now:
            raise SessionIntelligenceError("A timestamp is required.")
        value = _utc_now()
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            value = datetime.fromisoformat(text)
        except ValueError as exc:
            raise SessionIntelligenceError("Timestamp must be ISO-8601.") from exc
    if not isinstance(value, datetime):
        raise SessionIntelligenceError("Timestamp must be a datetime or ISO-8601 string.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | str) -> str:
    return _as_datetime(value).isoformat(timespec="microseconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _bounded_text(
    value: Any,
    *,
    label: str,
    maximum: int,
    default: str | None = None,
) -> str:
    if value is None:
        if default is None:
            raise SessionIntelligenceError(f"{label} is required.")
        return default
    if not isinstance(value, str):
        raise SessionIntelligenceError(f"{label} must be text.")
    text = value.strip()
    if not text:
        if default is None:
            raise SessionIntelligenceError(f"{label} is required.")
        return default
    if len(text) > maximum:
        raise SessionIntelligenceError(f"{label} must contain at most {maximum} characters.")
    if _CONTROL_CHARACTERS.search(text):
        raise PrivacyViolationError(f"{label} contains control characters.")
    return text


def _normalize_client(value: Any) -> str:
    text = _bounded_text(value, label="client_name", maximum=128, default="unknown")
    normalized = _IDENTIFIER_CHARACTERS.sub("-", text.lower()).strip("-")
    return normalized or "unknown"


def _normalize_ids(values: Iterable[Any]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise SessionIntelligenceError("Memory IDs must be a sequence, not text.")
    result = []
    for value in values:
        result.append(_bounded_text(value, label="memory_id", maximum=256))
    return tuple(sorted(set(result)))


def _normalize_purposes(purposes: Iterable[str] | str) -> tuple[str, ...]:
    if isinstance(purposes, str):
        purposes = (purposes,)
    return tuple(sorted(set(str(purpose).strip() for purpose in purposes)))


def _nonnegative_int(value: Any, *, label: str, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SessionIntelligenceError(f"{label} must be a non-negative integer.")
    if value < 0:
        raise SessionIntelligenceError(f"{label} must be a non-negative integer.")
    return value


def _enum_value(enum_type: type[Enum], value: Any, *, label: str) -> Enum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise SessionIntelligenceError(f"{label} must be one of: {allowed}.") from exc


def _decimal(value: Any, *, label: str, allow_none: bool = False) -> Decimal | None:
    if value is None and allow_none:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SessionIntelligenceError(f"{label} must be a decimal number.") from exc
    if not result.is_finite() or result < 0:
        raise SessionIntelligenceError(f"{label} must be finite and non-negative.")
    return result


def _format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def fingerprint_query(query: str, key: bytes | str) -> str:
    """Create a keyed local query fingerprint without persisting the query."""

    query_text = _bounded_text(query, label="query", maximum=100_000)
    if isinstance(key, str):
        key_bytes = key.encode("utf-8")
    elif isinstance(key, bytes):
        key_bytes = key
    else:
        raise SessionIntelligenceError("The fingerprint key must be text or bytes.")
    if not key_bytes:
        raise SessionIntelligenceError("The fingerprint key must not be empty.")
    return hmac.new(key_bytes, query_text.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class UsageProvenance:
    """Typed provenance for a usage measurement."""

    evidence_class: EvidenceClass
    source: str
    provider: str | None = None
    model: str | None = None
    source_id: str | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        evidence = _enum_value(
            EvidenceClass,
            self.evidence_class,
            label="usage evidence class",
        )
        source = _bounded_text(self.source, label="usage source", maximum=256)
        object.__setattr__(self, "evidence_class", evidence)
        object.__setattr__(self, "source", source)
        if self.provider is not None:
            object.__setattr__(
                self,
                "provider",
                _bounded_text(self.provider, label="provider", maximum=128),
            )
        if self.model is not None:
            object.__setattr__(
                self,
                "model",
                _bounded_text(self.model, label="model", maximum=256),
            )
        if self.source_id is not None:
            object.__setattr__(
                self,
                "source_id",
                _bounded_text(self.source_id, label="usage source id", maximum=256),
            )
        if self.observed_at is not None:
            object.__setattr__(self, "observed_at", _as_datetime(self.observed_at))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "evidence_class": self.evidence_class.value,
            "source": self.source,
        }
        if self.provider is not None:
            result["provider"] = self.provider
        if self.model is not None:
            result["model"] = self.model
        if self.source_id is not None:
            result["source_id"] = self.source_id
        if self.observed_at is not None:
            result["observed_at"] = _iso(self.observed_at)
        return result


@dataclass(frozen=True)
class ProviderUsage:
    """Provider-returned, actual usage.  All token fields are required."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    provider: str
    model: str
    usage_source: str = "provider"
    source_id: str | None = None

    def __post_init__(self) -> None:
        input_tokens = _nonnegative_int(self.input_tokens, label="input_tokens")
        cached = _nonnegative_int(
            self.cached_input_tokens,
            label="cached_input_tokens",
        )
        output = _nonnegative_int(self.output_tokens, label="output_tokens")
        assert input_tokens is not None and cached is not None and output is not None
        if cached > input_tokens:
            raise SessionIntelligenceError(
                "cached_input_tokens cannot exceed input_tokens."
            )
        object.__setattr__(self, "input_tokens", input_tokens)
        object.__setattr__(self, "cached_input_tokens", cached)
        object.__setattr__(self, "output_tokens", output)
        object.__setattr__(
            self,
            "provider",
            _bounded_text(self.provider, label="provider", maximum=128),
        )
        object.__setattr__(
            self,
            "model",
            _bounded_text(self.model, label="model", maximum=256),
        )
        object.__setattr__(
            self,
            "usage_source",
            _bounded_text(self.usage_source, label="usage_source", maximum=256),
        )
        if self.source_id is not None:
            object.__setattr__(
                self,
                "source_id",
                _bounded_text(self.source_id, label="usage source id", maximum=256),
            )

    @property
    def kind(self) -> UsageKind:
        return UsageKind.PROVIDER_ACTUAL

    @property
    def evidence_class(self) -> EvidenceClass:
        return EvidenceClass.PROVIDER_ACTUAL

    @property
    def uncached_input_tokens(self) -> int:
        return self.input_tokens - self.cached_input_tokens

    @property
    def provenance(self) -> UsageProvenance:
        return UsageProvenance(
            evidence_class=self.evidence_class,
            source=self.usage_source,
            provider=self.provider,
            model=self.model,
            source_id=self.source_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "evidence_class": self.evidence_class.value,
            "provenance": self.provenance.to_dict(),
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "uncached_input_tokens": self.uncached_input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass(frozen=True)
class EstimatedUsage:
    """Locally estimated usage, kept separate from provider-actual fields."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    overhead_tokens: int | None = 0
    estimator: str = "local"
    source_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_tokens",
            _nonnegative_int(
                self.input_tokens,
                label="estimated input_tokens",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "output_tokens",
            _nonnegative_int(
                self.output_tokens,
                label="estimated output_tokens",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "overhead_tokens",
            _nonnegative_int(
                self.overhead_tokens,
                label="estimated overhead_tokens",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "estimator",
            _bounded_text(self.estimator, label="estimator", maximum=256),
        )
        if self.source_id is not None:
            object.__setattr__(
                self,
                "source_id",
                _bounded_text(self.source_id, label="usage source id", maximum=256),
            )

    @property
    def kind(self) -> UsageKind:
        return UsageKind.ESTIMATED

    @property
    def evidence_class(self) -> EvidenceClass:
        return EvidenceClass.LOCAL_ESTIMATED

    @property
    def signal_ratio(self) -> float | None:
        if self.output_tokens is None or self.overhead_tokens is None:
            return None
        if self.output_tokens == 0:
            return 0.0
        return round(
            max(0, self.output_tokens - self.overhead_tokens) / self.output_tokens,
            6,
        )

    @property
    def provenance(self) -> UsageProvenance:
        return UsageProvenance(
            evidence_class=self.evidence_class,
            source=self.estimator,
            source_id=self.source_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "evidence_class": self.evidence_class.value,
            "provenance": self.provenance.to_dict(),
            "estimated_input_tokens": self.input_tokens,
            "estimated_output_tokens": self.output_tokens,
            "estimated_overhead_tokens": self.overhead_tokens,
            "estimated_signal_ratio": self.signal_ratio,
        }


ActualUsage = ProviderUsage
UsagePayload = ProviderUsage | EstimatedUsage


@dataclass(frozen=True)
class InvocationEvent:
    """Metadata-only record for one tool invocation."""

    event_id: str
    session_id: str
    client_name: str
    tool_name: str
    started_at: datetime
    finished_at: datetime
    usage: UsagePayload
    status: EventStatus | str = EventStatus.SUCCESS
    duration_ms: int | None = None
    result_count: int = 0
    returned_memory_ids: tuple[str, ...] = ()
    query_fingerprint: str | None = None
    invocation_id: str | None = None
    idempotency_key: str | None = None
    rate_card_id: str | None = None
    rate_card_version: str | None = None

    def __post_init__(self) -> None:
        event_id = _bounded_text(self.event_id, label="event_id", maximum=256)
        session_id = _bounded_text(self.session_id, label="session_id", maximum=256)
        tool_name = _bounded_text(self.tool_name, label="tool_name", maximum=128)
        if not isinstance(self.usage, (ProviderUsage, EstimatedUsage)):
            raise SessionIntelligenceError(
                "usage must be ProviderUsage or EstimatedUsage, never both."
            )
        started = _as_datetime(self.started_at)
        finished = _as_datetime(self.finished_at)
        if finished < started:
            raise SessionIntelligenceError("finished_at cannot precede started_at.")
        duration = self.duration_ms
        if duration is None:
            duration = int(round((finished - started).total_seconds() * 1000))
        duration = _nonnegative_int(duration, label="duration_ms")
        result_count = _nonnegative_int(self.result_count, label="result_count")
        assert duration is not None and result_count is not None
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "client_name", _normalize_client(self.client_name))
        object.__setattr__(self, "tool_name", tool_name)
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)
        object.__setattr__(self, "duration_ms", duration)
        object.__setattr__(self, "result_count", result_count)
        object.__setattr__(
            self,
            "status",
            _enum_value(EventStatus, self.status, label="status"),
        )
        object.__setattr__(
            self,
            "returned_memory_ids",
            _normalize_ids(self.returned_memory_ids),
        )
        if self.query_fingerprint is not None:
            fingerprint = _bounded_text(
                self.query_fingerprint,
                label="query_fingerprint",
                maximum=128,
            )
            if not _HEX_64.fullmatch(fingerprint):
                raise PrivacyViolationError(
                    "query_fingerprint must be a keyed SHA-256 fingerprint."
                )
            object.__setattr__(self, "query_fingerprint", fingerprint)
        object.__setattr__(
            self,
            "invocation_id",
            _bounded_text(
                self.invocation_id or event_id,
                label="invocation_id",
                maximum=256,
            ),
        )
        if self.idempotency_key is not None:
            object.__setattr__(
                self,
                "idempotency_key",
                _bounded_text(
                    self.idempotency_key,
                    label="idempotency_key",
                    maximum=256,
                ),
            )
        if self.rate_card_id is not None:
            object.__setattr__(
                self,
                "rate_card_id",
                _bounded_text(self.rate_card_id, label="rate_card_id", maximum=128),
            )
        if self.rate_card_version is not None:
            object.__setattr__(
                self,
                "rate_card_version",
                _bounded_text(
                    self.rate_card_version,
                    label="rate_card_version",
                    maximum=64,
                ),
            )
        if isinstance(self.usage, EstimatedUsage) and (
            self.rate_card_id is not None or self.rate_card_version is not None
        ):
            raise PrivacyViolationError(
                "Estimated usage cannot carry provider rate-card provenance."
            )

    @property
    def usage_kind(self) -> UsageKind:
        return self.usage.kind

    @property
    def evidence_class(self) -> EvidenceClass:
        return self.usage.evidence_class

    @classmethod
    def provider_actual(
        cls,
        *,
        event_id: str,
        session_id: str,
        client_name: str,
        tool_name: str,
        started_at: datetime,
        finished_at: datetime,
        provider: str,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
        usage_source: str = "provider",
        source_id: str | None = None,
        **kwargs: Any,
    ) -> "InvocationEvent":
        return cls(
            event_id=event_id,
            session_id=session_id,
            client_name=client_name,
            tool_name=tool_name,
            started_at=started_at,
            finished_at=finished_at,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                provider=provider,
                model=model,
                usage_source=usage_source,
                source_id=source_id,
            ),
            **kwargs,
        )

    @classmethod
    def estimated(
        cls,
        *,
        event_id: str,
        session_id: str,
        client_name: str,
        tool_name: str,
        started_at: datetime,
        finished_at: datetime,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        overhead_tokens: int | None = 0,
        estimator: str = "local",
        source_id: str | None = None,
        **kwargs: Any,
    ) -> "InvocationEvent":
        return cls(
            event_id=event_id,
            session_id=session_id,
            client_name=client_name,
            tool_name=tool_name,
            started_at=started_at,
            finished_at=finished_at,
            usage=EstimatedUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                overhead_tokens=overhead_tokens,
                estimator=estimator,
                source_id=source_id,
            ),
            **kwargs,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InvocationEvent":
        _reject_forbidden_keys(value)
        usage_value = value.get("usage")
        if isinstance(usage_value, Mapping):
            _reject_forbidden_keys(usage_value)
            kind = usage_value.get("kind", value.get("usage_kind"))
            kind_value = getattr(kind, "value", kind)
            if kind_value == UsageKind.PROVIDER_ACTUAL.value and any(
                (key in value and value[key] is not None)
                or (key in usage_value and usage_value[key] is not None)
                for key in _ESTIMATED_USAGE_KEYS
            ):
                raise SessionIntelligenceError(
                    "An actual usage event cannot also contain estimated usage fields."
                )
            if kind_value == UsageKind.ESTIMATED.value and any(
                (key in value and value[key] is not None)
                or (key in usage_value and usage_value[key] is not None)
                for key in _PROVIDER_USAGE_KEYS
            ):
                raise SessionIntelligenceError(
                    "An estimated usage event cannot also contain provider usage fields."
                )
            declared_evidence = usage_value.get("evidence_class")
            declared_evidence_value = getattr(
                declared_evidence, "value", declared_evidence
            )
            if declared_evidence_value is not None and declared_evidence_value not in {
                EvidenceClass.PROVIDER_ACTUAL.value,
                EvidenceClass.LOCAL_ESTIMATED.value,
            }:
                raise SessionIntelligenceError(
                    "Usage evidence_class must match the usage kind."
                )
            if kind_value == UsageKind.PROVIDER_ACTUAL.value:
                usage: UsagePayload = ProviderUsage(
                    input_tokens=usage_value.get(
                        "input_tokens",
                        value.get("provider_input_tokens"),
                    ),
                    cached_input_tokens=usage_value.get(
                        "cached_input_tokens",
                        value.get("provider_cached_input_tokens", 0),
                    ),
                    output_tokens=usage_value.get(
                        "output_tokens",
                        value.get("provider_output_tokens"),
                    ),
                    provider=usage_value.get("provider", value.get("provider")),
                    model=usage_value.get("model", value.get("model")),
                    usage_source=usage_value.get(
                        "usage_source",
                        value.get("usage_source", "provider"),
                    ),
                    source_id=usage_value.get("source_id", value.get("source_id")),
                )
            elif kind_value == UsageKind.ESTIMATED.value:
                usage = EstimatedUsage(
                    input_tokens=usage_value.get(
                        "estimated_input_tokens",
                        value.get("estimated_input_tokens"),
                    ),
                    output_tokens=usage_value.get(
                        "estimated_output_tokens",
                        value.get("estimated_output_tokens"),
                    ),
                    overhead_tokens=usage_value.get(
                        "estimated_overhead_tokens",
                        value.get("estimated_overhead_tokens", 0),
                    ),
                    estimator=usage_value.get(
                        "estimator",
                        value.get("estimator", "local"),
                    ),
                    source_id=usage_value.get("source_id", value.get("source_id")),
                )
            else:
                raise SessionIntelligenceError("usage.kind must be explicit.")
        else:
            kind = value.get("usage_kind")
            kind_value = getattr(kind, "value", kind)
            if kind_value == UsageKind.PROVIDER_ACTUAL.value and any(
                key in value and value[key] is not None for key in _ESTIMATED_USAGE_KEYS
            ):
                raise SessionIntelligenceError(
                    "An actual usage event cannot also contain estimated usage fields."
                )
            if kind_value == UsageKind.ESTIMATED.value and any(
                key in value and value[key] is not None for key in _PROVIDER_USAGE_KEYS
            ):
                raise SessionIntelligenceError(
                    "An estimated usage event cannot also contain provider usage fields."
                )
            declared_evidence = value.get("evidence_class")
            declared_evidence_value = getattr(
                declared_evidence, "value", declared_evidence
            )
            expected_evidence = {
                UsageKind.PROVIDER_ACTUAL.value: EvidenceClass.PROVIDER_ACTUAL.value,
                UsageKind.ESTIMATED.value: EvidenceClass.LOCAL_ESTIMATED.value,
            }.get(kind_value)
            if declared_evidence_value is not None and declared_evidence_value != expected_evidence:
                raise SessionIntelligenceError(
                    "Usage evidence_class must match the usage kind."
                )
            if kind_value == UsageKind.PROVIDER_ACTUAL.value:
                usage = ProviderUsage(
                    input_tokens=value.get("provider_input_tokens"),
                    cached_input_tokens=value.get("provider_cached_input_tokens", 0),
                    output_tokens=value.get("provider_output_tokens"),
                    provider=value.get("provider"),
                    model=value.get("model"),
                    usage_source=value.get("usage_source", "provider"),
                    source_id=value.get("source_id"),
                )
            elif kind_value == UsageKind.ESTIMATED.value:
                usage = EstimatedUsage(
                    input_tokens=value.get("estimated_input_tokens"),
                    output_tokens=value.get("estimated_output_tokens"),
                    overhead_tokens=value.get("estimated_overhead_tokens", 0),
                    estimator=value.get("estimator", "local"),
                    source_id=value.get("source_id"),
                )
            else:
                raise SessionIntelligenceError(
                    "An event mapping must identify provider_actual or estimated usage."
                )
        ignored = {
            "usage",
            "usage_kind",
            "provider_input_tokens",
            "provider_cached_input_tokens",
            "provider_output_tokens",
            "estimated_input_tokens",
            "estimated_output_tokens",
            "estimated_overhead_tokens",
            "provider",
            "model",
            "usage_source",
            "estimator",
            "source_id",
            "schema_version",
            "cost",
        }
        kwargs = {key: item for key, item in value.items() if key not in ignored}
        kwargs["usage"] = usage
        return cls(**kwargs)

    def to_safe_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "event_id": self.event_id,
            "invocation_id": self.invocation_id,
            "session_id": self.session_id,
            "client_name": self.client_name,
            "tool_name": self.tool_name,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "result_count": self.result_count,
            "returned_memory_ids": list(self.returned_memory_ids),
            "usage": self.usage.to_dict(),
        }
        if self.query_fingerprint is not None:
            result["query_fingerprint"] = self.query_fingerprint
        if self.rate_card_id is not None:
            result["rate_card_id"] = self.rate_card_id
        if self.rate_card_version is not None:
            result["rate_card_version"] = self.rate_card_version
        return result


UsageEvent = InvocationEvent


def _reject_forbidden_keys(value: Mapping[str, Any]) -> None:
    for key in value:
        normalized = str(key).strip().lower().replace("-", "_")
        if normalized in _FORBIDDEN_KEYS:
            raise PrivacyViolationError(
                f"{key} is not accepted in metadata-only Session Intelligence records."
            )


@dataclass(frozen=True)
class RateCard:
    """Versioned, local pricing authority for one provider/model pair."""

    rate_card_id: str
    version: str
    provider: str
    model: str
    currency: str
    effective_from: datetime
    source: str
    input_uncached_per_million: Decimal | str | int | float | None
    input_cached_per_million: Decimal | str | int | float | None
    output_per_million: Decimal | str | int | float | None
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rate_card_id",
            _bounded_text(self.rate_card_id, label="rate_card_id", maximum=128),
        )
        object.__setattr__(
            self,
            "version",
            _bounded_text(self.version, label="rate_card version", maximum=64),
        )
        object.__setattr__(
            self,
            "provider",
            _bounded_text(self.provider, label="rate-card provider", maximum=128),
        )
        object.__setattr__(
            self,
            "model",
            _bounded_text(self.model, label="rate-card model", maximum=256),
        )
        currency = _bounded_text(self.currency, label="currency", maximum=3).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise SessionIntelligenceError("currency must be a three-letter ISO code.")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "effective_from", _as_datetime(self.effective_from))
        if self.effective_to is not None:
            effective_to = _as_datetime(self.effective_to)
            if effective_to < self.effective_from:
                raise SessionIntelligenceError("effective_to cannot precede effective_from.")
            object.__setattr__(self, "effective_to", effective_to)
        object.__setattr__(
            self,
            "source",
            _bounded_text(self.source, label="rate-card source", maximum=512),
        )
        object.__setattr__(
            self,
            "input_uncached_per_million",
            _decimal(
                self.input_uncached_per_million,
                label="input_uncached_per_million",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "input_cached_per_million",
            _decimal(
                self.input_cached_per_million,
                label="input_cached_per_million",
                allow_none=True,
            ),
        )
        object.__setattr__(
            self,
            "output_per_million",
            _decimal(
                self.output_per_million,
                label="output_per_million",
                allow_none=True,
            ),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RateCard":
        _reject_forbidden_keys(value)
        return cls(
            rate_card_id=value["rate_card_id"],
            version=value["version"],
            provider=value["provider"],
            model=value["model"],
            currency=value["currency"],
            effective_from=value["effective_from"],
            effective_to=value.get("effective_to"),
            source=value["source"],
            input_uncached_per_million=value.get(
                "input_uncached_per_million",
                value.get("input_rate_per_million"),
            ),
            input_cached_per_million=value.get(
                "input_cached_per_million",
                value.get("cached_input_rate_per_million"),
            ),
            output_per_million=value.get("output_per_million"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rate_card_id": self.rate_card_id,
            "version": self.version,
            "provider": self.provider,
            "model": self.model,
            "currency": self.currency,
            "effective_from": _iso(self.effective_from),
            "effective_to": _iso(self.effective_to) if self.effective_to else None,
            "source": self.source,
            "input_uncached_per_million": _format_decimal(
                self.input_uncached_per_million
            ),
            "input_cached_per_million": _format_decimal(self.input_cached_per_million),
            "output_per_million": _format_decimal(self.output_per_million),
        }


RateCardSnapshot = RateCard


@dataclass(frozen=True)
class CostResult:
    """A cost result that never presents an estimate as currency fact."""

    status: str
    amount: Decimal | None
    currency: str | None
    usage_evidence_class: EvidenceClass
    rate_card_id: str | None = None
    rate_card_version: str | None = None
    rate_card_source: str | None = None
    reason: str | None = None

    @property
    def known(self) -> bool:
        return self.status != UNKNOWN and self.amount is not None

    @classmethod
    def unknown(
        cls,
        *,
        usage_evidence_class: EvidenceClass,
        reason: str,
        rate_card_id: str | None = None,
        rate_card_version: str | None = None,
    ) -> "CostResult":
        return cls(
            status=UNKNOWN,
            amount=None,
            currency=None,
            usage_evidence_class=usage_evidence_class,
            rate_card_id=rate_card_id,
            rate_card_version=rate_card_version,
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        amount = _format_decimal(self.amount) if self.known else UNKNOWN
        return {
            "status": self.status,
            "amount": amount,
            "cost": amount,
            "currency": self.currency if self.known else None,
            "usage_evidence_class": self.usage_evidence_class.value,
            "rate_card_id": self.rate_card_id,
            "rate_card_version": self.rate_card_version,
            "rate_card_source": self.rate_card_source,
            "unknown_reason": None if self.known else self.reason,
        }


def calculate_provider_cost(
    usage: UsagePayload,
    rate_card: RateCard | None,
    *,
    rate_card_id: str | None = None,
    rate_card_version: str | None = None,
) -> CostResult:
    """Calculate deterministic currency cost for complete actual usage only."""

    if isinstance(usage, EstimatedUsage):
        return CostResult.unknown(
            usage_evidence_class=usage.evidence_class,
            reason="estimated_usage_is_not_provider_billing",
        )
    if rate_card is None:
        return CostResult.unknown(
            usage_evidence_class=usage.evidence_class,
            reason="matching_rate_card_is_missing",
            rate_card_id=rate_card_id,
            rate_card_version=rate_card_version,
        )
    if rate_card_id is not None and rate_card.rate_card_id != rate_card_id:
        return CostResult.unknown(
            usage_evidence_class=usage.evidence_class,
            reason="rate_card_id_mismatch",
            rate_card_id=rate_card_id,
            rate_card_version=rate_card_version,
        )
    if rate_card_version is not None and rate_card.version != rate_card_version:
        return CostResult.unknown(
            usage_evidence_class=usage.evidence_class,
            reason="rate_card_version_mismatch",
            rate_card_id=rate_card.rate_card_id,
            rate_card_version=rate_card_version,
        )
    if rate_card.provider != usage.provider or rate_card.model != usage.model:
        return CostResult.unknown(
            usage_evidence_class=usage.evidence_class,
            reason="rate_card_provider_or_model_mismatch",
            rate_card_id=rate_card.rate_card_id,
            rate_card_version=rate_card.version,
        )
    if (
        rate_card.input_uncached_per_million is None
        or rate_card.input_cached_per_million is None
        or rate_card.output_per_million is None
    ):
        return CostResult.unknown(
            usage_evidence_class=usage.evidence_class,
            reason="rate_card_input_is_incomplete",
            rate_card_id=rate_card.rate_card_id,
            rate_card_version=rate_card.version,
        )
    million = Decimal(1_000_000)
    amount = (
        Decimal(usage.uncached_input_tokens)
        * rate_card.input_uncached_per_million
        / million
        + Decimal(usage.cached_input_tokens)
        * rate_card.input_cached_per_million
        / million
        + Decimal(usage.output_tokens) * rate_card.output_per_million / million
    )
    exponent = _CURRENCY_EXPONENTS.get(rate_card.currency, 2)
    quantum = Decimal(1).scaleb(-exponent)
    amount = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    return CostResult(
        status="known",
        amount=amount,
        currency=rate_card.currency,
        usage_evidence_class=usage.evidence_class,
        rate_card_id=rate_card.rate_card_id,
        rate_card_version=rate_card.version,
        rate_card_source=rate_card.source,
    )


class RateCardAuthority:
    """In-memory versioned rate-card authority used by the local ledger."""

    def __init__(self, cards: Iterable[RateCard] | None = None) -> None:
        self._cards: dict[tuple[str, str], RateCard] = {}
        for card in cards or ():
            self.register(card)

    def register(self, card: RateCard) -> RateCard:
        if not isinstance(card, RateCard):
            card = RateCard.from_dict(card)  # type: ignore[arg-type]
        key = (card.rate_card_id, card.version)
        prior = self._cards.get(key)
        if prior is not None and prior.to_dict() != card.to_dict():
            raise IdempotencyConflictError(
                "Rate-card id and version already exist with different inputs."
            )
        self._cards[key] = card
        return card

    add = register

    def get(self, rate_card_id: str, version: str | None = None) -> RateCard | None:
        if version is not None:
            return self._cards.get((rate_card_id, version))
        matches = [
            card for (card_id, _), card in self._cards.items() if card_id == rate_card_id
        ]
        return matches[0] if len(matches) == 1 else None

    def cards(self) -> tuple[RateCard, ...]:
        return tuple(
            self._cards[key] for key in sorted(self._cards, key=lambda item: (item[0], item[1]))
        )

    def calculate(
        self,
        usage: UsagePayload,
        *,
        rate_card_id: str | None,
        rate_card_version: str | None,
    ) -> CostResult:
        card = (
            self.get(rate_card_id, rate_card_version)
            if rate_card_id is not None
            else None
        )
        return calculate_provider_cost(
            usage,
            card,
            rate_card_id=rate_card_id,
            rate_card_version=rate_card_version,
        )


@dataclass(frozen=True)
class OutcomeEvidence:
    """Separate metadata-only accepted-outcome evidence."""

    outcome_id: str
    session_id: str
    evidence_class: EvidenceClass | str
    evidence_source: str
    accepted: bool | None = None
    invocation_id: str | None = None
    comparison_id: str | None = None
    comparable: bool = False
    retries: int = 0
    corrections: int = 0
    total_tokens: int | None = None
    created_at: datetime = field(default_factory=_utc_now)
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outcome_id",
            _bounded_text(self.outcome_id, label="outcome_id", maximum=256),
        )
        object.__setattr__(
            self,
            "session_id",
            _bounded_text(self.session_id, label="outcome session_id", maximum=256),
        )
        evidence = _enum_value(
            EvidenceClass,
            self.evidence_class,
            label="outcome evidence class",
        )
        if evidence not in {
            EvidenceClass.USER_ASSERTED,
            EvidenceClass.CAUSALLY_EVALUATED,
            EvidenceClass.UNKNOWN,
        }:
            raise SessionIntelligenceError(
                "Outcome evidence must be user_asserted, causally_evaluated, or UNKNOWN."
            )
        object.__setattr__(self, "evidence_class", evidence)
        object.__setattr__(
            self,
            "evidence_source",
            _bounded_text(self.evidence_source, label="evidence_source", maximum=256),
        )
        if self.accepted is not None and not isinstance(self.accepted, bool):
            raise SessionIntelligenceError("accepted must be true, false, or UNKNOWN.")
        if self.invocation_id is not None:
            object.__setattr__(
                self,
                "invocation_id",
                _bounded_text(self.invocation_id, label="outcome invocation_id", maximum=256),
            )
        if self.comparison_id is not None:
            object.__setattr__(
                self,
                "comparison_id",
                _bounded_text(self.comparison_id, label="comparison_id", maximum=256),
            )
        if evidence is EvidenceClass.CAUSALLY_EVALUATED and (
            not self.comparison_id or not self.comparable
        ):
            raise SessionIntelligenceError(
                "Causally evaluated outcomes require a comparable comparison_id."
            )
        for name in ("retries", "corrections"):
            object.__setattr__(
                self,
                name,
                _nonnegative_int(getattr(self, name), label=name),
            )
        object.__setattr__(
            self,
            "total_tokens",
            _nonnegative_int(
                self.total_tokens,
                label="outcome total_tokens",
                allow_none=True,
            ),
        )
        object.__setattr__(self, "created_at", _as_datetime(self.created_at))
        if self.idempotency_key is not None:
            object.__setattr__(
                self,
                "idempotency_key",
                _bounded_text(
                    self.idempotency_key,
                    label="outcome idempotency_key",
                    maximum=256,
                ),
            )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OutcomeEvidence":
        _reject_forbidden_keys(value)
        accepted = value.get("accepted")
        if accepted is None and "status" in value:
            status = value["status"]
            accepted = True if status in {"accepted", "success", "succeeded"} else None
            if status in {"rejected", "failed", "failure"}:
                accepted = False
        return cls(
            outcome_id=value["outcome_id"],
            session_id=value["session_id"],
            invocation_id=value.get("invocation_id"),
            evidence_class=value.get("evidence_class", UNKNOWN),
            evidence_source=value.get("evidence_source", "unknown"),
            accepted=accepted,
            comparison_id=value.get("comparison_id"),
            comparable=bool(value.get("comparable", False)),
            retries=value.get("retries", 0),
            corrections=value.get("corrections", 0),
            total_tokens=value.get("total_tokens"),
            created_at=value.get("created_at", _utc_now()),
            idempotency_key=value.get("idempotency_key"),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "outcome_id": self.outcome_id,
            "session_id": self.session_id,
            "invocation_id": self.invocation_id,
            "evidence_class": self.evidence_class.value,
            "evidence_source": self.evidence_source,
            "accepted": self.accepted,
            "comparison_id": self.comparison_id,
            "comparable": self.comparable,
            "retries": self.retries,
            "corrections": self.corrections,
            "total_tokens": self.total_tokens,
            "created_at": _iso(self.created_at),
        }


@dataclass(frozen=True)
class IngestReceipt:
    event_id: str
    invocation_id: str
    persisted: bool
    duplicate: bool
    usage_kind: UsageKind
    evidence_class: EvidenceClass

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "invocation_id": self.invocation_id,
            "persisted": self.persisted,
            "duplicate": self.duplicate,
            "usage_kind": self.usage_kind.value,
            "evidence_class": self.evidence_class.value,
        }


@dataclass(frozen=True)
class OutcomeReceipt:
    outcome_id: str
    persisted: bool
    duplicate: bool
    evidence_class: EvidenceClass

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "persisted": self.persisted,
            "duplicate": self.duplicate,
            "evidence_class": self.evidence_class.value,
        }


@dataclass(frozen=True)
class UsageFacts:
    event_count: int
    session_count: int
    statuses: Mapping[str, int]
    duration_ms: int
    actual: Mapping[str, Any]
    estimated: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "session_count": self.session_count,
            "statuses": dict(self.statuses),
            "duration_ms": self.duration_ms,
            "actual": dict(self.actual),
            "estimated": dict(self.estimated),
        }


@dataclass(frozen=True)
class CostFacts:
    status: str
    amount: Decimal | None
    currency: str | None
    known_event_count: int
    unknown_event_count: int
    rate_cards: tuple[tuple[str, str], ...]
    evidence_class: EvidenceClass
    unknown_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        amount = _format_decimal(self.amount) if self.status != UNKNOWN else UNKNOWN
        return {
            "status": self.status,
            "amount": amount,
            "cost": amount,
            "currency": self.currency if self.status != UNKNOWN else None,
            "known_event_count": self.known_event_count,
            "unknown_event_count": self.unknown_event_count,
            "rate_cards": [
                {"rate_card_id": card_id, "version": version}
                for card_id, version in self.rate_cards
            ],
            "evidence_class": self.evidence_class.value,
            "unknown_reason": self.unknown_reason,
        }


@dataclass(frozen=True)
class OutcomeFacts:
    outcome_count: int
    causal_outcome_count: int
    user_asserted_outcome_count: int
    accepted_count: int
    rejected_count: int
    accepted: bool | None
    evidence_class: EvidenceClass
    comparison_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_count": self.outcome_count,
            "causal_outcome_count": self.causal_outcome_count,
            "user_asserted_outcome_count": self.user_asserted_outcome_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "accepted": self.accepted,
            "accepted_outcome_status": (
                "known" if self.accepted is not None else UNKNOWN
            ),
            "evidence_class": self.evidence_class.value,
            "comparison_ids": list(self.comparison_ids),
        }


@dataclass(frozen=True)
class SignalCard:
    """Deterministic derived signal; never a source-of-truth ledger."""

    card_id: str
    scope: Mapping[str, Any]
    usage_facts: UsageFacts
    cost_facts: CostFacts
    outcome_facts: OutcomeFacts
    unknowns: tuple[str, ...]
    hypothesis: str

    @property
    def usage(self) -> dict[str, Any]:
        return self.usage_facts.to_dict()

    @property
    def cost(self) -> dict[str, Any]:
        return self.cost_facts.to_dict()

    @property
    def accepted_outcome_evidence(self) -> dict[str, Any]:
        return self.outcome_facts.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "card_id": self.card_id,
            "scope": dict(self.scope),
            "usage": self.usage_facts.to_dict(),
            "cost": self.cost_facts.to_dict(),
            "accepted_outcome_evidence": self.outcome_facts.to_dict(),
            "unknowns": list(self.unknowns),
            "hypothesis": self.hypothesis,
        }


class SignalCardBuilder:
    """Small adapter for callers that prefer a builder object."""

    def __init__(self, ledger: "SessionIntelligenceLedger") -> None:
        self.ledger = ledger

    def build(self, **kwargs: Any) -> SignalCard:
        return self.ledger.build_signal_card(**kwargs)


@dataclass(frozen=True)
class TrainingHypothesis:
    hypothesis_id: str
    aggregate_key: str
    statement: str
    basis: Mapping[str, Any]
    evidence_classes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "aggregate_key": self.aggregate_key,
            "statement": self.statement,
            "basis": dict(self.basis),
            "evidence_classes": list(self.evidence_classes),
            "hypothesis_only": True,
        }


@dataclass(frozen=True)
class EnterpriseReport:
    purpose: str
    aggregation: str
    scope: Mapping[str, Any]
    groups: tuple[Mapping[str, Any], ...]
    hypotheses: tuple[TrainingHypothesis, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "purpose": self.purpose,
            "aggregation": self.aggregation,
            "scope": dict(self.scope),
            "groups": [dict(group) for group in self.groups],
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
            "hypotheses_only": True,
            "employee_ranking": False,
            "sensitive_trait_inference": False,
            "prohibited_uses": [
                "employee_ranking",
                "sensitive_trait_inference",
                "employment_decisions",
            ],
        }


class SessionIntelligenceLedger:
    """SQLite-backed, consent-gated local event ledger."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        if (
            isinstance(retention_days, bool)
            or not isinstance(retention_days, int)
            or retention_days < 1
            or retention_days > MAX_RETENTION_DAYS
        ):
            raise SessionIntelligenceError(
                f"retention_days must be between 1 and {MAX_RETENTION_DAYS}."
            )
        self.retention_days = retention_days
        self.path = ":memory:" if path == ":memory:" else Path(path or DEFAULT_DB_PATH)
        if self.path != ":memory:":
            assert isinstance(self.path, Path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection_target = str(self.path)
        else:
            connection_target = ":memory:"
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            connection_target,
            timeout=5,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._initialize_schema()
        self.rate_cards = RateCardAuthority()
        self._load_rate_cards()
        if self.path != ":memory:":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        self.prune()

    def __enter__(self) -> "SessionIntelligenceLedger":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            current_user_version = int(
                self._connection.execute("PRAGMA user_version").fetchone()[0]
            )
            stored_row = self._connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if stored_row is not None:
                stored_version = int(stored_row[0])
                if stored_version != SCHEMA_VERSION:
                    raise SchemaVersionError(
                        f"Unsupported Session Intelligence schema {stored_version}; "
                        f"expected {SCHEMA_VERSION}."
                    )
            if current_user_version not in (0, SCHEMA_VERSION):
                raise SchemaVersionError(
                    f"Unsupported SQLite user_version {current_user_version}."
                )
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS consent_records (
                    purpose TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
                    consent_version TEXT NOT NULL,
                    granted_at TEXT,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS session_records (
                    session_id TEXT PRIMARY KEY,
                    client_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    client_session_id TEXT,
                    payload_sha256 TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rate_cards (
                    rate_card_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    effective_from TEXT NOT NULL,
                    effective_to TEXT,
                    source TEXT NOT NULL,
                    input_uncached_per_million TEXT,
                    input_cached_per_million TEXT,
                    output_per_million TEXT,
                    PRIMARY KEY (rate_card_id, version)
                );

                CREATE TABLE IF NOT EXISTS usage_events (
                    event_id TEXT PRIMARY KEY,
                    invocation_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    returned_memory_ids_json TEXT NOT NULL,
                    query_fingerprint TEXT,
                    usage_kind TEXT NOT NULL,
                    usage_evidence_class TEXT NOT NULL,
                    usage_source TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    actual_input_tokens INTEGER,
                    actual_cached_input_tokens INTEGER,
                    actual_output_tokens INTEGER,
                    estimated_input_tokens INTEGER,
                    estimated_output_tokens INTEGER,
                    estimated_overhead_tokens INTEGER,
                    estimated_signal_ratio REAL,
                    rate_card_id TEXT,
                    rate_card_version TEXT,
                    payload_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    idempotency_sha256 TEXT
                );

                CREATE TABLE IF NOT EXISTS outcome_evidence (
                    outcome_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    invocation_id TEXT,
                    evidence_class TEXT NOT NULL,
                    evidence_source TEXT NOT NULL,
                    accepted INTEGER,
                    comparison_id TEXT,
                    comparable INTEGER NOT NULL CHECK (comparable IN (0, 1)),
                    retries INTEGER NOT NULL,
                    corrections INTEGER NOT NULL,
                    total_tokens INTEGER,
                    created_at TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    idempotency_sha256 TEXT,
                    UNIQUE (session_id, idempotency_sha256)
                );

                CREATE INDEX IF NOT EXISTS idx_usage_events_session
                    ON usage_events(session_id, finished_at, event_id);
                CREATE INDEX IF NOT EXISTS idx_usage_events_finished
                    ON usage_events(finished_at);
                CREATE INDEX IF NOT EXISTS idx_outcome_evidence_session
                    ON outcome_evidence(session_id, created_at, outcome_id);
                """
            )
            self._connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _load_rate_cards(self) -> None:
        rows = self._connection.execute(
            "SELECT * FROM rate_cards ORDER BY rate_card_id, version"
        ).fetchall()
        for row in rows:
            self.rate_cards.register(
                RateCard(
                    rate_card_id=row["rate_card_id"],
                    version=row["version"],
                    provider=row["provider"],
                    model=row["model"],
                    currency=row["currency"],
                    effective_from=row["effective_from"],
                    effective_to=row["effective_to"],
                    source=row["source"],
                    input_uncached_per_million=row["input_uncached_per_million"],
                    input_cached_per_million=row["input_cached_per_million"],
                    output_per_million=row["output_per_million"],
                )
            )

    def _consent_rows(self) -> list[sqlite3.Row]:
        return self._connection.execute(
            "SELECT * FROM consent_records ORDER BY purpose"
        ).fetchall()

    def consent_status(self) -> dict[str, Any]:
        with self._lock:
            rows = self._consent_rows()
        enabled = tuple(row["purpose"] for row in rows if row["enabled"])
        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": PURPOSE_USAGE_ANALYTICS in enabled,
            "purposes": list(enabled),
        }

    @property
    def enabled(self) -> bool:
        return bool(self.consent_status()["enabled"])

    def grant_consent(
        self,
        purposes: Iterable[str] | str = (PURPOSE_USAGE_ANALYTICS,),
        *,
        consent_version: str = "1",
        at: datetime | str | None = None,
    ) -> dict[str, Any]:
        normalized = _normalize_purposes(purposes)
        if not normalized or PURPOSE_USAGE_ANALYTICS not in normalized:
            raise ConsentRequiredError(
                "Explicit consent must include the usage_analytics purpose."
            )
        unknown = set(normalized) - SUPPORTED_PURPOSES
        if unknown:
            raise SessionIntelligenceError(
                f"Unsupported consent purpose(s): {', '.join(sorted(unknown))}."
            )
        version = _bounded_text(consent_version, label="consent_version", maximum=64)
        timestamp = _iso(at or _utc_now())
        with self._lock, self._connection:
            for purpose in normalized:
                self._connection.execute(
                    """
                    INSERT INTO consent_records(
                        purpose, enabled, consent_version, granted_at, revoked_at
                    ) VALUES (?, 1, ?, ?, NULL)
                    ON CONFLICT(purpose) DO UPDATE SET
                        enabled = 1,
                        consent_version = excluded.consent_version,
                        granted_at = excluded.granted_at,
                        revoked_at = NULL
                    """,
                    (purpose, version, timestamp),
                )
        return self.consent_status()

    enable = grant_consent

    def revoke_consent(
        self,
        purposes: Iterable[str] | str | None = None,
        *,
        delete_events: bool = False,
        at: datetime | str | None = None,
    ) -> dict[str, Any]:
        selected = (
            _normalize_purposes(purposes)
            if purposes is not None
            else tuple(SUPPORTED_PURPOSES)
        )
        unknown = set(selected) - SUPPORTED_PURPOSES
        if unknown:
            raise SessionIntelligenceError(
                f"Unsupported consent purpose(s): {', '.join(sorted(unknown))}."
            )
        timestamp = _iso(at or _utc_now())
        with self._lock, self._connection:
            for purpose in selected:
                self._connection.execute(
                    """
                    INSERT INTO consent_records(
                        purpose, enabled, consent_version, granted_at, revoked_at
                    ) VALUES (?, 0, '1', NULL, ?)
                    ON CONFLICT(purpose) DO UPDATE SET
                        enabled = 0,
                        revoked_at = excluded.revoked_at
                    """,
                    (purpose, timestamp),
                )
        if delete_events:
            self.delete_all(confirm=True)
        return self.consent_status()

    disable = revoke_consent

    def _has_purpose(self, purpose: str) -> bool:
        row = self._connection.execute(
            "SELECT enabled FROM consent_records WHERE purpose = ?", (purpose,)
        ).fetchone()
        return bool(row and row["enabled"])

    def _require_consent(self, purpose: str) -> None:
        with self._lock:
            enabled = self._has_purpose(PURPOSE_USAGE_ANALYTICS)
            purpose_enabled = self._has_purpose(purpose)
        if not enabled or not purpose_enabled:
            raise ConsentRequiredError(
                f"Session Intelligence is disabled until explicit '{purpose}' consent is granted."
            )

    def _ensure_session(
        self,
        *,
        session_id: str,
        client_name: str,
        started_at: datetime,
        client_session_id: str | None = None,
    ) -> None:
        session_id = _bounded_text(session_id, label="session_id", maximum=256)
        client = _normalize_client(client_name)
        started = _iso(started_at)
        payload = {
            "session_id": session_id,
            "client_name": client,
            "started_at": started,
            "client_session_id": client_session_id,
        }
        digest = _digest(payload)
        existing = self._connection.execute(
            "SELECT * FROM session_records WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing is None:
            self._connection.execute(
                """
                INSERT INTO session_records(
                    session_id, client_name, started_at, ended_at,
                    client_session_id, payload_sha256
                ) VALUES (?, ?, ?, NULL, ?, ?)
                """,
                (session_id, client, started, client_session_id, digest),
            )
            return
        updates: list[str] = []
        parameters: list[Any] = []
        if existing["client_name"] == "unknown" and client != "unknown":
            updates.append("client_name = ?")
            parameters.append(client)
        if started < existing["started_at"]:
            updates.append("started_at = ?")
            parameters.append(started)
        if updates:
            parameters.append(session_id)
            self._connection.execute(
                f"UPDATE session_records SET {', '.join(updates)} WHERE session_id = ?",
                parameters,
            )

    def start_session(
        self,
        *,
        session_id: str | None = None,
        client_name: str = "unknown",
        started_at: datetime | str | None = None,
        client_session_id: str | None = None,
    ) -> str:
        self._require_consent(PURPOSE_USAGE_ANALYTICS)
        session = _bounded_text(session_id or str(uuid4()), label="session_id", maximum=256)
        client_session = (
            _bounded_text(client_session_id, label="client_session_id", maximum=256)
            if client_session_id is not None
            else None
        )
        with self._lock, self._connection:
            self._ensure_session(
                session_id=session,
                client_name=client_name,
                started_at=_as_datetime(started_at, default_now=True),
                client_session_id=client_session,
            )
        return session

    def end_session(
        self,
        session_id: str,
        *,
        ended_at: datetime | str | None = None,
    ) -> bool:
        self._require_consent(PURPOSE_USAGE_ANALYTICS)
        session = _bounded_text(session_id, label="session_id", maximum=256)
        ended = _iso(ended_at or _utc_now())
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT started_at, ended_at FROM session_records WHERE session_id = ?",
                (session,),
            ).fetchone()
            if row is None:
                raise UnknownEventError("Unknown session_id.")
            if _as_datetime(ended) < _as_datetime(row["started_at"]):
                raise SessionIntelligenceError("ended_at cannot precede session start.")
            if row["ended_at"] == ended:
                return False
            self._connection.execute(
                "UPDATE session_records SET ended_at = ? WHERE session_id = ?",
                (ended, session),
            )
        return True

    def register_rate_card(self, card: RateCard | Mapping[str, Any]) -> RateCard:
        if not isinstance(card, RateCard):
            card = RateCard.from_dict(card)
        self.rate_cards.register(card)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO rate_cards(
                    rate_card_id, version, provider, model, currency,
                    effective_from, effective_to, source,
                    input_uncached_per_million, input_cached_per_million,
                    output_per_million
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rate_card_id, version) DO UPDATE SET
                    provider = excluded.provider,
                    model = excluded.model,
                    currency = excluded.currency,
                    effective_from = excluded.effective_from,
                    effective_to = excluded.effective_to,
                    source = excluded.source,
                    input_uncached_per_million = excluded.input_uncached_per_million,
                    input_cached_per_million = excluded.input_cached_per_million,
                    output_per_million = excluded.output_per_million
                """,
                (
                    card.rate_card_id,
                    card.version,
                    card.provider,
                    card.model,
                    card.currency,
                    _iso(card.effective_from),
                    _iso(card.effective_to) if card.effective_to else None,
                    card.source,
                    _format_decimal(card.input_uncached_per_million),
                    _format_decimal(card.input_cached_per_million),
                    _format_decimal(card.output_per_million),
                ),
            )
        return card

    add_rate_card = register_rate_card

    def ingest_event(self, event: InvocationEvent | Mapping[str, Any]) -> IngestReceipt:
        if not isinstance(event, InvocationEvent):
            event = InvocationEvent.from_dict(event)
        purpose = (
            PURPOSE_PROVIDER_USAGE
            if event.usage_kind is UsageKind.PROVIDER_ACTUAL
            else PURPOSE_USAGE_ANALYTICS
        )
        self._require_consent(purpose)
        safe = event.to_safe_dict()
        payload_digest = _digest(safe)
        idempotency_digest = (
            hashlib.sha256(event.idempotency_key.encode("utf-8")).hexdigest()
            if event.idempotency_key
            else None
        )
        with self._lock, self._connection:
            self.prune(now=event.finished_at)
            prior = self._connection.execute(
                "SELECT * FROM usage_events WHERE event_id = ?", (event.event_id,)
            ).fetchone()
            if prior is not None:
                if prior["payload_sha256"] != payload_digest:
                    raise IdempotencyConflictError(
                        "event_id was already used with different metadata."
                    )
                return IngestReceipt(
                    event_id=event.event_id,
                    invocation_id=event.invocation_id or event.event_id,
                    persisted=False,
                    duplicate=True,
                    usage_kind=event.usage_kind,
                    evidence_class=event.evidence_class,
                )
            prior_invocation = self._connection.execute(
                "SELECT event_id, payload_sha256 FROM usage_events WHERE invocation_id = ?",
                (event.invocation_id,),
            ).fetchone()
            if prior_invocation is not None:
                if prior_invocation["payload_sha256"] != payload_digest:
                    raise IdempotencyConflictError(
                        "invocation_id was already used with different metadata."
                    )
                return IngestReceipt(
                    event_id=prior_invocation["event_id"],
                    invocation_id=event.invocation_id or event.event_id,
                    persisted=False,
                    duplicate=True,
                    usage_kind=event.usage_kind,
                    evidence_class=event.evidence_class,
                )
            if idempotency_digest is not None:
                prior_key = self._connection.execute(
                    """
                    SELECT event_id, payload_sha256 FROM usage_events
                    WHERE idempotency_sha256 = ?
                    """,
                    (idempotency_digest,),
                ).fetchone()
                if prior_key is not None:
                    if prior_key["payload_sha256"] != payload_digest:
                        raise IdempotencyConflictError(
                            "idempotency_key was already used with different metadata."
                        )
                    return IngestReceipt(
                        event_id=prior_key["event_id"],
                        invocation_id=event.invocation_id or event.event_id,
                        persisted=False,
                        duplicate=True,
                        usage_kind=event.usage_kind,
                        evidence_class=event.evidence_class,
                    )
            self._ensure_session(
                session_id=event.session_id,
                client_name=event.client_name,
                started_at=event.started_at,
            )
            actual_input = actual_cached = actual_output = None
            estimated_input = estimated_output = estimated_overhead = None
            estimated_ratio = None
            provider = model = usage_source = None
            if isinstance(event.usage, ProviderUsage):
                actual_input = event.usage.input_tokens
                actual_cached = event.usage.cached_input_tokens
                actual_output = event.usage.output_tokens
                provider = event.usage.provider
                model = event.usage.model
                usage_source = event.usage.usage_source
            else:
                estimated_input = event.usage.input_tokens
                estimated_output = event.usage.output_tokens
                estimated_overhead = event.usage.overhead_tokens
                estimated_ratio = event.usage.signal_ratio
                usage_source = event.usage.estimator
            self._connection.execute(
                """
                INSERT INTO usage_events(
                    event_id, invocation_id, session_id, client_name, tool_name,
                    started_at, finished_at, duration_ms, status, result_count,
                    returned_memory_ids_json, query_fingerprint, usage_kind,
                    usage_evidence_class, usage_source, provider, model,
                    actual_input_tokens, actual_cached_input_tokens,
                    actual_output_tokens, estimated_input_tokens,
                    estimated_output_tokens, estimated_overhead_tokens,
                    estimated_signal_ratio, rate_card_id, rate_card_version,
                    payload_sha256, created_at, idempotency_sha256
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    event.event_id,
                    event.invocation_id,
                    event.session_id,
                    event.client_name,
                    event.tool_name,
                    _iso(event.started_at),
                    _iso(event.finished_at),
                    event.duration_ms,
                    event.status.value,
                    event.result_count,
                    _canonical_json(list(event.returned_memory_ids)),
                    event.query_fingerprint,
                    event.usage_kind.value,
                    event.evidence_class.value,
                    usage_source,
                    provider,
                    model,
                    actual_input,
                    actual_cached,
                    actual_output,
                    estimated_input,
                    estimated_output,
                    estimated_overhead,
                    estimated_ratio,
                    event.rate_card_id,
                    event.rate_card_version,
                    payload_digest,
                    _iso(event.finished_at),
                    idempotency_digest,
                ),
            )
        return IngestReceipt(
            event_id=event.event_id,
            invocation_id=event.invocation_id or event.event_id,
            persisted=True,
            duplicate=False,
            usage_kind=event.usage_kind,
            evidence_class=event.evidence_class,
        )

    ingest = ingest_event
    record_event = ingest_event

    def ingest_outcome(
        self,
        outcome: OutcomeEvidence | Mapping[str, Any],
    ) -> OutcomeReceipt:
        if not isinstance(outcome, OutcomeEvidence):
            outcome = OutcomeEvidence.from_dict(outcome)
        self._require_consent(PURPOSE_USAGE_ANALYTICS)
        safe = outcome.to_safe_dict()
        payload_digest = _digest(safe)
        idempotency_digest = (
            hashlib.sha256(outcome.idempotency_key.encode("utf-8")).hexdigest()
            if outcome.idempotency_key
            else None
        )
        with self._lock, self._connection:
            self.prune(now=outcome.created_at)
            prior = self._connection.execute(
                "SELECT * FROM outcome_evidence WHERE outcome_id = ?",
                (outcome.outcome_id,),
            ).fetchone()
            if prior is not None:
                if prior["payload_sha256"] != payload_digest:
                    raise IdempotencyConflictError(
                        "outcome_id was already used with different evidence."
                    )
                return OutcomeReceipt(
                    outcome_id=outcome.outcome_id,
                    persisted=False,
                    duplicate=True,
                    evidence_class=outcome.evidence_class,
                )
            if idempotency_digest is not None:
                prior_key = self._connection.execute(
                    """
                    SELECT outcome_id, payload_sha256 FROM outcome_evidence
                    WHERE session_id = ? AND idempotency_sha256 = ?
                    """,
                    (outcome.session_id, idempotency_digest),
                ).fetchone()
                if prior_key is not None:
                    if prior_key["payload_sha256"] != payload_digest:
                        raise IdempotencyConflictError(
                            "outcome idempotency_key was reused with different evidence."
                        )
                    return OutcomeReceipt(
                        outcome_id=prior_key["outcome_id"],
                        persisted=False,
                        duplicate=True,
                        evidence_class=outcome.evidence_class,
                    )
            self._connection.execute(
                """
                INSERT INTO outcome_evidence(
                    outcome_id, session_id, invocation_id, evidence_class,
                    evidence_source, accepted, comparison_id, comparable,
                    retries, corrections, total_tokens, created_at,
                    payload_sha256, idempotency_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.outcome_id,
                    outcome.session_id,
                    outcome.invocation_id,
                    outcome.evidence_class.value,
                    outcome.evidence_source,
                    None if outcome.accepted is None else int(outcome.accepted),
                    outcome.comparison_id,
                    int(outcome.comparable),
                    outcome.retries,
                    outcome.corrections,
                    outcome.total_tokens,
                    _iso(outcome.created_at),
                    payload_digest,
                    idempotency_digest,
                ),
            )
        return OutcomeReceipt(
            outcome_id=outcome.outcome_id,
            persisted=True,
            duplicate=False,
            evidence_class=outcome.evidence_class,
        )

    record_outcome = ingest_outcome

    def _row_to_event(self, row: sqlite3.Row) -> InvocationEvent:
        if row["usage_kind"] == UsageKind.PROVIDER_ACTUAL.value:
            usage: UsagePayload = ProviderUsage(
                input_tokens=row["actual_input_tokens"],
                cached_input_tokens=row["actual_cached_input_tokens"],
                output_tokens=row["actual_output_tokens"],
                provider=row["provider"],
                model=row["model"],
                usage_source=row["usage_source"],
            )
        else:
            usage = EstimatedUsage(
                input_tokens=row["estimated_input_tokens"],
                output_tokens=row["estimated_output_tokens"],
                overhead_tokens=row["estimated_overhead_tokens"],
                estimator=row["usage_source"],
            )
        return InvocationEvent(
            event_id=row["event_id"],
            invocation_id=row["invocation_id"],
            session_id=row["session_id"],
            client_name=row["client_name"],
            tool_name=row["tool_name"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration_ms=row["duration_ms"],
            status=row["status"],
            result_count=row["result_count"],
            returned_memory_ids=tuple(json.loads(row["returned_memory_ids_json"])),
            query_fingerprint=row["query_fingerprint"],
            usage=usage,
            rate_card_id=row["rate_card_id"],
            rate_card_version=row["rate_card_version"],
        )

    def _cost_for_event(self, event: InvocationEvent) -> CostResult:
        if isinstance(event.usage, EstimatedUsage):
            return CostResult.unknown(
                usage_evidence_class=event.evidence_class,
                reason="estimated_usage_is_not_provider_billing",
            )
        rate_card = (
            self.rate_cards.get(event.rate_card_id, event.rate_card_version)
            if event.rate_card_id is not None
            else None
        )
        if rate_card is not None and (
            event.finished_at < rate_card.effective_from
            or (
                rate_card.effective_to is not None
                and event.finished_at > rate_card.effective_to
            )
        ):
            return CostResult.unknown(
                usage_evidence_class=event.evidence_class,
                reason="rate_card_not_effective_at_event_time",
                rate_card_id=event.rate_card_id,
                rate_card_version=event.rate_card_version,
            )
        return self.rate_cards.calculate(
            event.usage,
            rate_card_id=event.rate_card_id,
            rate_card_version=event.rate_card_version,
        )

    def calculate_cost(
        self,
        event_or_id: InvocationEvent | str,
        *,
        rate_card: RateCard | None = None,
    ) -> CostResult:
        if isinstance(event_or_id, InvocationEvent):
            event = event_or_id
            if rate_card is not None:
                return calculate_provider_cost(
                    event.usage,
                    rate_card,
                    rate_card_id=event.rate_card_id,
                    rate_card_version=event.rate_card_version,
                )
            return self._cost_for_event(event)
        event = self.get_event(event_or_id)
        if event is None:
            raise UnknownEventError("Unknown event_id.")
        if rate_card is not None:
            return calculate_provider_cost(
                event.usage,
                rate_card,
                rate_card_id=event.rate_card_id,
                rate_card_version=event.rate_card_version,
            )
        return self._cost_for_event(event)

    cost_for_event = calculate_cost

    def get_event(self, event_id: str) -> InvocationEvent | None:
        identifier = _bounded_text(event_id, label="event_id", maximum=256)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM usage_events WHERE event_id = ?", (identifier,)
            ).fetchone()
        return self._row_to_event(row) if row is not None else None

    def _event_rows(
        self,
        *,
        session_id: str | None = None,
        client_name: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        event_ids: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["1 = 1"]
        parameters: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            parameters.append(_bounded_text(session_id, label="session_id", maximum=256))
        if client_name is not None:
            clauses.append("client_name = ?")
            parameters.append(_normalize_client(client_name))
        if start is not None:
            clauses.append("finished_at >= ?")
            parameters.append(_iso(start))
        if end is not None:
            clauses.append("finished_at <= ?")
            parameters.append(_iso(end))
        if event_ids is not None:
            ids = _normalize_ids(event_ids)
            if not ids:
                return []
            placeholders = ", ".join("?" for _ in ids)
            clauses.append(f"event_id IN ({placeholders})")
            parameters.extend(ids)
        bounded_limit = ""
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
                raise SessionIntelligenceError("limit must be a positive integer.")
            bounded_limit = " LIMIT ?"
            parameters.append(limit)
        query = (
            "SELECT * FROM usage_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY finished_at, event_id"
            + bounded_limit
        )
        with self._lock:
            return self._connection.execute(query, parameters).fetchall()

    def _outcome_rows(
        self,
        *,
        session_id: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["1 = 1"]
        parameters: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            parameters.append(_bounded_text(session_id, label="session_id", maximum=256))
        if start is not None:
            clauses.append("created_at >= ?")
            parameters.append(_iso(start))
        if end is not None:
            clauses.append("created_at <= ?")
            parameters.append(_iso(end))
        with self._lock:
            return self._connection.execute(
                "SELECT * FROM outcome_evidence WHERE "
                + " AND ".join(clauses)
                + " ORDER BY created_at, outcome_id",
                parameters,
            ).fetchall()

    def _safe_event_dict(self, event: InvocationEvent) -> dict[str, Any]:
        result = event.to_safe_dict()
        result["cost"] = self._cost_for_event(event).to_dict()
        return result

    def inspect_events(self, **filters: Any) -> list[dict[str, Any]]:
        rows = self._event_rows(**filters)
        return [self._safe_event_dict(self._row_to_event(row)) for row in rows]

    inspect = inspect_events

    def inspect_session(self, session_id: str) -> dict[str, Any]:
        identifier = _bounded_text(session_id, label="session_id", maximum=256)
        with self._lock:
            session = self._connection.execute(
                "SELECT * FROM session_records WHERE session_id = ?", (identifier,)
            ).fetchone()
        if session is None:
            raise UnknownEventError("Unknown session_id.")
        events = self.inspect_events(session_id=identifier)
        outcomes = self._outcome_rows(session_id=identifier)
        safe_outcomes = [
            {
                "schema_version": SCHEMA_VERSION,
                "outcome_id": row["outcome_id"],
                "session_id": row["session_id"],
                "invocation_id": row["invocation_id"],
                "evidence_class": row["evidence_class"],
                "evidence_source": row["evidence_source"],
                "accepted": None if row["accepted"] is None else bool(row["accepted"]),
                "comparison_id": row["comparison_id"],
                "comparable": bool(row["comparable"]),
                "retries": row["retries"],
                "corrections": row["corrections"],
                "total_tokens": row["total_tokens"],
                "created_at": row["created_at"],
            }
            for row in outcomes
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "session": {
                "session_id": session["session_id"],
                "client_name": session["client_name"],
                "started_at": session["started_at"],
                "ended_at": session["ended_at"],
                "client_session_id": session["client_session_id"],
            },
            "events": events,
            "outcomes": safe_outcomes,
            "signal_card": self.build_signal_card(session_id=identifier).to_dict(),
        }

    def export_data(
        self,
        *,
        session_id: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        as_json: bool = False,
    ) -> dict[str, Any] | str:
        events = self.inspect_events(session_id=session_id, start=start, end=end)
        outcomes = self._outcome_rows(session_id=session_id, start=start, end=end)
        safe_outcomes = [
            {
                "schema_version": SCHEMA_VERSION,
                "outcome_id": row["outcome_id"],
                "session_id": row["session_id"],
                "invocation_id": row["invocation_id"],
                "evidence_class": row["evidence_class"],
                "evidence_source": row["evidence_source"],
                "accepted": None if row["accepted"] is None else bool(row["accepted"]),
                "comparison_id": row["comparison_id"],
                "comparable": bool(row["comparable"]),
                "retries": row["retries"],
                "corrections": row["corrections"],
                "total_tokens": row["total_tokens"],
                "created_at": row["created_at"],
            }
            for row in outcomes
        ]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "consent": self.consent_status(),
            "events": events,
            "outcomes": safe_outcomes,
            "rate_cards": [card.to_dict() for card in self.rate_cards.cards()],
        }
        if as_json:
            return _canonical_json(payload)
        return payload

    export = export_data

    def export_json(self, **filters: Any) -> str:
        filters["as_json"] = True
        result = self.export_data(**filters)
        assert isinstance(result, str)
        return result

    def delete_event(self, event_id: str) -> bool:
        identifier = _bounded_text(event_id, label="event_id", maximum=256)
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT invocation_id FROM usage_events WHERE event_id = ?",
                (identifier,),
            ).fetchone()
            if row is None:
                return False
            self._connection.execute(
                "DELETE FROM outcome_evidence WHERE invocation_id = ?", (row["invocation_id"],)
            )
            self._connection.execute(
                "DELETE FROM usage_events WHERE event_id = ?", (identifier,)
            )
        return True

    def delete_session(self, session_id: str) -> int:
        identifier = _bounded_text(session_id, label="session_id", maximum=256)
        with self._lock, self._connection:
            event_count = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM usage_events WHERE session_id = ?",
                    (identifier,),
                ).fetchone()[0]
            )
            self._connection.execute(
                "DELETE FROM outcome_evidence WHERE session_id = ?", (identifier,)
            )
            self._connection.execute(
                "DELETE FROM usage_events WHERE session_id = ?", (identifier,)
            )
            self._connection.execute(
                "DELETE FROM session_records WHERE session_id = ?", (identifier,)
            )
        return event_count

    def delete_events(
        self,
        event_ids: Sequence[str] | None = None,
        *,
        session_id: str | None = None,
        before: datetime | str | None = None,
    ) -> int:
        if event_ids is None and session_id is None and before is None:
            raise SessionIntelligenceError("A deletion scope is required.")
        rows = self._event_rows(
            event_ids=event_ids,
            session_id=session_id,
            end=before,
        )
        deleted = 0
        for row in rows:
            if self.delete_event(row["event_id"]):
                deleted += 1
        return deleted

    def delete_all(self, *, confirm: bool = False) -> int:
        if confirm is not True:
            raise SessionIntelligenceError(
                "delete_all requires confirm=True because it removes event history."
            )
        with self._lock, self._connection:
            count = int(self._connection.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0])
            self._connection.execute("DELETE FROM outcome_evidence")
            self._connection.execute("DELETE FROM usage_events")
            self._connection.execute("DELETE FROM session_records")
        return count

    reset = delete_all

    def prune(self, *, now: datetime | str | None = None) -> int:
        current = _as_datetime(now, default_now=True)
        cutoff = current - timedelta(days=self.retention_days)
        cutoff_text = _iso(cutoff)
        with self._lock, self._connection:
            event_count = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM usage_events WHERE finished_at < ?",
                    (cutoff_text,),
                ).fetchone()[0]
            )
            outcome_count = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM outcome_evidence WHERE created_at < ?",
                    (cutoff_text,),
                ).fetchone()[0]
            )
            self._connection.execute(
                "DELETE FROM outcome_evidence WHERE created_at < ?", (cutoff_text,)
            )
            self._connection.execute(
                "DELETE FROM usage_events WHERE finished_at < ?", (cutoff_text,)
            )
            self._connection.execute(
                """
                DELETE FROM session_records
                WHERE COALESCE(ended_at, started_at) < ?
                  AND session_id NOT IN (
                      SELECT DISTINCT session_id FROM usage_events
                  )
                """,
                (cutoff_text,),
            )
        return event_count + outcome_count

    purge = prune

    def _scope_bounds(
        self,
        *,
        start: datetime | str | None,
        end: datetime | str | None,
    ) -> tuple[datetime | None, datetime | None]:
        start_dt = _as_datetime(start) if start is not None else None
        end_dt = _as_datetime(end) if end is not None else None
        if start_dt is not None and end_dt is not None and end_dt < start_dt:
            raise SessionIntelligenceError("end cannot precede start.")
        return start_dt, end_dt

    def build_signal_card(
        self,
        *,
        session_id: str | None = None,
        client_name: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> SignalCard:
        start_dt, end_dt = self._scope_bounds(start=start, end=end)
        requested_start_dt, requested_end_dt = start_dt, end_dt
        rows = self._event_rows(
            session_id=session_id,
            client_name=client_name,
            start=start_dt,
            end=end_dt,
        )
        events = [self._row_to_event(row) for row in rows]
        if start_dt is None and events:
            start_dt = min(event.started_at for event in events)
        if end_dt is None and events:
            end_dt = max(event.finished_at for event in events)
        scope: dict[str, Any] = {
            "session_id": session_id,
            "client_name": _normalize_client(client_name) if client_name else None,
            "window_start": _iso(start_dt) if start_dt else None,
            "window_end": _iso(end_dt) if end_dt else None,
        }
        statuses: dict[str, int] = {}
        actual_events = [event for event in events if isinstance(event.usage, ProviderUsage)]
        estimated_events = [
            event for event in events if isinstance(event.usage, EstimatedUsage)
        ]
        for event in events:
            statuses[event.status.value] = statuses.get(event.status.value, 0) + 1
        actual_input = sum(event.usage.input_tokens for event in actual_events)
        actual_cached = sum(event.usage.cached_input_tokens for event in actual_events)
        actual_output = sum(event.usage.output_tokens for event in actual_events)
        estimated_input_values = [
            event.usage.input_tokens
            for event in estimated_events
            if event.usage.input_tokens is not None
        ]
        estimated_output_values = [
            event.usage.output_tokens
            for event in estimated_events
            if event.usage.output_tokens is not None
        ]
        estimated_overhead_values = [
            event.usage.overhead_tokens
            for event in estimated_events
            if event.usage.overhead_tokens is not None
        ]
        ratio_values = [
            event.usage.signal_ratio
            for event in estimated_events
            if event.usage.signal_ratio is not None
        ]
        actual_providers = sorted(
            {(event.usage.provider, event.usage.model) for event in actual_events}
        )
        usage_facts = UsageFacts(
            event_count=len(events),
            session_count=len({event.session_id for event in events}),
            statuses=dict(sorted(statuses.items())),
            duration_ms=sum(event.duration_ms or 0 for event in events),
            actual={
                "event_count": len(actual_events),
                "input_tokens": actual_input,
                "cached_input_tokens": actual_cached,
                "uncached_input_tokens": actual_input - actual_cached,
                "output_tokens": actual_output,
                "evidence_class": (
                    EvidenceClass.PROVIDER_ACTUAL.value
                    if actual_events
                    else UNKNOWN
                ),
                "providers": [
                    {"provider": provider, "model": model}
                    for provider, model in actual_providers
                ],
            },
            estimated={
                "event_count": len(estimated_events),
                "input_tokens": sum(estimated_input_values)
                if len(estimated_input_values) == len(estimated_events)
                else None,
                "output_tokens": sum(estimated_output_values)
                if len(estimated_output_values) == len(estimated_events)
                else None,
                "overhead_tokens": sum(estimated_overhead_values)
                if len(estimated_overhead_values) == len(estimated_events)
                else None,
                "average_signal_ratio": (
                    round(sum(ratio_values) / len(ratio_values), 6)
                    if ratio_values
                    else None
                ),
                "evidence_class": (
                    EvidenceClass.LOCAL_ESTIMATED.value
                    if estimated_events
                    else UNKNOWN
                ),
            },
        )
        costs = [self._cost_for_event(event) for event in events]
        known_costs = [cost for cost in costs if cost.known]
        unknown_costs = [cost for cost in costs if not cost.known]
        currencies = {cost.currency for cost in known_costs}
        card_rates = sorted(
            {
                (cost.rate_card_id, cost.rate_card_version)
                for cost in known_costs
                if cost.rate_card_id and cost.rate_card_version
            }
        )
        if events and not unknown_costs and len(currencies) == 1:
            currency = next(iter(currencies))
            amount = sum(
                (cost.amount for cost in known_costs if cost.amount is not None),
                Decimal("0"),
            )
            cost_facts = CostFacts(
                status="known",
                amount=amount,
                currency=currency,
                known_event_count=len(known_costs),
                unknown_event_count=0,
                rate_cards=tuple(card_rates),
                evidence_class=EvidenceClass.PROVIDER_ACTUAL,
            )
        else:
            reasons = sorted({cost.reason for cost in unknown_costs if cost.reason})
            if len(currencies) > 1:
                reasons.append("mixed_currencies")
            cost_facts = CostFacts(
                status=UNKNOWN,
                amount=None,
                currency=None,
                known_event_count=len(known_costs),
                unknown_event_count=len(unknown_costs),
                rate_cards=tuple(card_rates),
                evidence_class=(
                    EvidenceClass.PROVIDER_ACTUAL
                    if known_costs and not unknown_costs
                    else EvidenceClass.UNKNOWN
                ),
                unknown_reason=", ".join(sorted(set(reasons)))
                if reasons
                else "no_complete_provider_actual_cost",
            )
        outcome_rows = self._outcome_rows(
            session_id=session_id,
            start=requested_start_dt,
            end=requested_end_dt,
        )
        if session_id is None:
            relevant_sessions = {event.session_id for event in events}
            outcome_rows = [
                row for row in outcome_rows if row["session_id"] in relevant_sessions
            ]
        causal_rows = [
            row
            for row in outcome_rows
            if row["evidence_class"] == EvidenceClass.CAUSALLY_EVALUATED.value
            and row["comparable"]
        ]
        user_rows = [
            row
            for row in outcome_rows
            if row["evidence_class"] == EvidenceClass.USER_ASSERTED.value
        ]
        accepted_count = sum(row["accepted"] == 1 for row in causal_rows)
        rejected_count = sum(row["accepted"] == 0 for row in causal_rows)
        causal_accepted: bool | None
        if causal_rows and accepted_count + rejected_count == len(causal_rows):
            if accepted_count == len(causal_rows):
                causal_accepted = True
            elif rejected_count == len(causal_rows):
                causal_accepted = False
            else:
                causal_accepted = None
        else:
            causal_accepted = None
        if causal_rows:
            outcome_class = EvidenceClass.CAUSALLY_EVALUATED
        elif user_rows:
            outcome_class = EvidenceClass.USER_ASSERTED
        else:
            outcome_class = EvidenceClass.UNKNOWN
        outcome_facts = OutcomeFacts(
            outcome_count=len(outcome_rows),
            causal_outcome_count=len(causal_rows),
            user_asserted_outcome_count=len(user_rows),
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            accepted=causal_accepted,
            evidence_class=outcome_class,
            comparison_ids=tuple(
                sorted(
                    {
                        row["comparison_id"]
                        for row in causal_rows
                        if row["comparison_id"]
                    }
                )
            ),
        )
        unknowns: set[str] = set()
        if not events:
            unknowns.add("no_usage_events")
        if estimated_events:
            unknowns.add("provider_actual_usage_missing_for_estimated_events")
        if unknown_costs:
            unknowns.add("currency_cost_unknown_without_complete_rate_provenance")
        if not causal_rows:
            unknowns.add("accepted_outcome_evidence=UNKNOWN")
        if user_rows and not causal_rows:
            unknowns.add("causal_outcome_evidence=UNKNOWN")
        if len(currencies) > 1:
            unknowns.add("mixed_currency_cost=UNKNOWN")
        if cost_facts.status == UNKNOWN and events and not unknown_costs:
            unknowns.add("cost_aggregation=UNKNOWN")
        if outcome_facts.accepted is None and causal_rows:
            unknowns.add("accepted_outcome_is_mixed_or_incomplete")
        if cost_facts.status == UNKNOWN:
            hypothesis = (
                "Treat currency cost as UNKNOWN until provider-actual usage and a "
                "matching versioned rate card are present."
            )
        elif not causal_rows:
            hypothesis = (
                "Usage and cost are diagnostic facts; accepted value remains UNKNOWN "
                "until comparable outcome evidence is linked."
            )
        elif any(event.status is not EventStatus.SUCCESS for event in events):
            hypothesis = (
                "Review retries or blocked/error invocations as a reversible "
                "workflow-improvement hypothesis, not a user judgment."
            )
        else:
            hypothesis = (
                "Compare this bounded window with a comparable control before "
                "interpreting accepted-value or cost effects."
            )
        card_without_id = {
            "scope": scope,
            "usage": usage_facts.to_dict(),
            "cost": cost_facts.to_dict(),
            "accepted_outcome_evidence": outcome_facts.to_dict(),
            "unknowns": sorted(unknowns),
            "hypothesis": hypothesis,
        }
        return SignalCard(
            card_id=_digest(card_without_id),
            scope=scope,
            usage_facts=usage_facts,
            cost_facts=cost_facts,
            outcome_facts=outcome_facts,
            unknowns=tuple(sorted(unknowns)),
            hypothesis=hypothesis,
        )

    signal_card = build_signal_card

    def build_enterprise_report(
        self,
        *,
        group_by: str = "tool",
        purpose: str = PURPOSE_ENTERPRISE_TRAINING,
        session_id: str | None = None,
        client_name: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        rank_employees: bool = False,
        infer_sensitive_traits: bool = False,
        requested_dimensions: Iterable[str] = (),
    ) -> EnterpriseReport:
        if rank_employees or infer_sensitive_traits:
            raise AntiSurveillanceError(
                "Enterprise output cannot rank employees or infer sensitive traits."
            )
        normalized_group = str(group_by).strip().lower().replace("-", "_")
        if normalized_group in _PROHIBITED_GROUP_TERMS:
            raise AntiSurveillanceError(
                "Enterprise output is aggregate-only and cannot group by employee identity."
            )
        if normalized_group not in {"tool", "client", "day"}:
            raise AntiSurveillanceError(
                "Enterprise output may aggregate only by tool, client, or day."
            )
        requested = {
            str(dimension).strip().lower().replace("-", "_")
            for dimension in requested_dimensions
        }
        if requested & _SENSITIVE_TRAIT_TERMS:
            raise AntiSurveillanceError(
                "Sensitive-trait inference is prohibited in enterprise output."
            )
        if purpose != PURPOSE_ENTERPRISE_TRAINING:
            raise ConsentRequiredError(
                "Enterprise hypotheses require the enterprise_training purpose."
            )
        self._require_consent(PURPOSE_ENTERPRISE_TRAINING)
        start_dt, end_dt = self._scope_bounds(start=start, end=end)
        rows = self._event_rows(
            session_id=session_id,
            client_name=client_name,
            start=start_dt,
            end=end_dt,
        )
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            event = self._row_to_event(row)
            if normalized_group == "tool":
                key = event.tool_name
            elif normalized_group == "client":
                key = event.client_name
            else:
                key = event.finished_at.date().isoformat()
            group = groups.setdefault(
                key,
                {
                    "aggregate_key": key,
                    "event_count": 0,
                    "actual_event_count": 0,
                    "estimated_event_count": 0,
                    "actual_input_tokens": 0,
                    "actual_output_tokens": 0,
                    "estimated_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "unknown_cost_events": 0,
                },
            )
            group["event_count"] += 1
            if isinstance(event.usage, ProviderUsage):
                group["actual_event_count"] += 1
                group["actual_input_tokens"] += event.usage.input_tokens
                group["actual_output_tokens"] += event.usage.output_tokens
            else:
                group["estimated_event_count"] += 1
                if event.usage.input_tokens is not None:
                    group["estimated_input_tokens"] += event.usage.input_tokens
                if event.usage.output_tokens is not None:
                    group["estimated_output_tokens"] += event.usage.output_tokens
            if not self._cost_for_event(event).known:
                group["unknown_cost_events"] += 1
        groups_tuple = tuple(
            {**groups[key], "evidence_boundary": "aggregate_usage_facts_only"}
            for key in sorted(groups)
        )
        hypotheses = tuple(
            TrainingHypothesis(
                hypothesis_id=_digest(
                    {"purpose": purpose, "group_by": normalized_group, "key": key}
                ),
                aggregate_key=key,
                statement=(
                    f"Aggregate activity for {normalized_group} '{key}' may indicate "
                    "a training opportunity; validate with users before acting."
                ),
                basis={
                    "event_count": groups[key]["event_count"],
                    "actual_event_count": groups[key]["actual_event_count"],
                    "estimated_event_count": groups[key]["estimated_event_count"],
                    "accepted_outcome": UNKNOWN,
                },
                evidence_classes=tuple(
                    sorted(
                        {
                            EvidenceClass.PROVIDER_ACTUAL.value
                            if groups[key]["actual_event_count"]
                            else "",
                            EvidenceClass.LOCAL_ESTIMATED.value
                            if groups[key]["estimated_event_count"]
                            else "",
                            UNKNOWN,
                        }
                        - {""}
                    )
                ),
            )
            for key in sorted(groups)
        )
        scope = {
            "session_id": session_id,
            "client_name": _normalize_client(client_name) if client_name else None,
            "window_start": _iso(start_dt) if start_dt else None,
            "window_end": _iso(end_dt) if end_dt else None,
        }
        return EnterpriseReport(
            purpose=purpose,
            aggregation=normalized_group,
            scope=scope,
            groups=groups_tuple,
            hypotheses=hypotheses,
        )

    enterprise_report = build_enterprise_report
    training_hypotheses = build_enterprise_report


SessionIntelligence = SessionIntelligenceLedger
LocalEventLedger = SessionIntelligenceLedger
