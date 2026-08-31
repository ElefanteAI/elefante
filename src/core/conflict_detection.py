"""Conservative, deterministic semantic conflict assessment.

This module deliberately does not try to understand arbitrary natural
language.  It extracts a small set of explicit proposition shapes and only
reports a conflict when the compared propositions have a high-confidence
identity:

* the same normalized proposition has opposite explicit polarity; or
* the same explicit subject and predicate have incompatible explicit values.

Everything else is an abstention.  In particular, shared keywords and a
negation marker without an anchored proposition are not evidence of conflict.
The implementation is pure, deterministic, and uses no model or persistence
side effects.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class ConflictOutcome(str, Enum):
    """The only outcomes produced by :func:`assess_conflict`."""

    CONFLICT = "CONFLICT"
    NO_CONFLICT = "NO_CONFLICT"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ConflictAssessment:
    """A deterministic conflict decision and its human-readable reason."""

    outcome: ConflictOutcome
    reason: str


@dataclass(frozen=True)
class _Proposition:
    subject: str
    predicate: str
    value: str
    positive: bool
    exclusive_value: bool


# These are intentionally small and explicit.  A broad English negation list
# would recreate the false-positive behavior this module is meant to replace.
_CONTRACTIONS = (
    (r"\bwon['’]t\b", "will not"),
    (r"\bcan['’]t\b", "cannot"),
    (r"\bdoesn['’]t\b", "does not"),
    (r"\bdon['’]t\b", "do not"),
    (r"\bdidn['’]t\b", "did not"),
    (r"\bisn['’]t\b", "is not"),
    (r"\baren['’]t\b", "are not"),
    (r"\bwasn['’]t\b", "was not"),
    (r"\bweren['’]t\b", "were not"),
)

_AMBIGUOUS_SUBJECTS = {
    "it",
    "this",
    "that",
    "there",
    "something",
    "someone",
    "somebody",
    "everything",
    "nothing",
}

# Words that make a copular/assignment key explicit enough for incompatible
# scalar values to be meaningful.  Generic descriptive predicates such as
# "is fast" remain abstentions when their values differ.
_EXCLUSIVE_KEY_HINTS = {
    "address",
    "backend",
    "branch",
    "channel",
    "city",
    "commit",
    "count",
    "database",
    "db",
    "directory",
    "environment",
    "engine",
    "file",
    "framework",
    "hash",
    "host",
    "hostname",
    "id",
    "identifier",
    "kind",
    "language",
    "license",
    "location",
    "model",
    "mode",
    "name",
    "namespace",
    "number",
    "owner",
    "path",
    "port",
    "primary",
    "provider",
    "release",
    "role",
    "state",
    "status",
    "store",
    "timezone",
    "type",
    "url",
    "value",
    "version",
    "workspace",
}

_EXCLUSIVE_QUALIFIERS = {
    "active",
    "configured",
    "current",
    "default",
    "only",
    "primary",
    "selected",
    "single",
}

_TECHNICAL_VALUES = {
    "chromadb",
    "chroma",
    "csv",
    "gpt",
    "json",
    "kuzu",
    "linux",
    "macos",
    "mongodb",
    "mysql",
    "node",
    "postgres",
    "postgresql",
    "python",
    "redis",
    "sqlite",
    "sqlite3",
    "toml",
    "windows",
    "yaml",
}

_EXPLICIT_IDENTIFIER_VALUES = {
    "alpha",
    "beta",
    "develop",
    "development",
    "legacy",
    "local",
    "main",
    "master",
    "primary",
    "production",
    "remote",
    "secondary",
    "selected",
    "staging",
    "test",
}

_OPPOSITE_VALUES = {
    "active": "inactive",
    "allowed": "forbidden",
    "available": "unavailable",
    "closed": "open",
    "complete": "incomplete",
    "enabled": "disabled",
    "failure": "success",
    "failed": "passed",
    "forbidden": "allowed",
    "healthy": "unhealthy",
    "inactive": "active",
    "incomplete": "complete",
    "invalid": "valid",
    "no": "yes",
    "off": "on",
    "on": "off",
    "open": "closed",
    "passed": "failed",
    "present": "absent",
    "success": "failure",
    "unavailable": "available",
    "unhealthy": "healthy",
    "valid": "invalid",
    "yes": "no",
}

# Longest/more specific forms must be tried first.  The values are base or
# inflected spellings accepted by the deliberately narrow parser.
_PREDICATE_PATTERNS = (
    ("listen_on_port", r"(?:listen|listens|listened)\s+on\s+port"),
    ("run_on_port", r"(?:run|runs|ran)\s+on\s+port"),
    ("located_in", r"(?:is|are|was|were)\s+located\s+in"),
    ("live_in", r"(?:live|lives|lived)\s+in"),
    ("reside_in", r"(?:reside|resides|resided)\s+in"),
    ("belong_to", r"(?:belong|belongs|belonged)\s+to"),
    ("store", r"(?:store|stores|stored)"),
    ("support", r"(?:support|supports|supported)"),
    ("use", r"(?:use|uses|used)"),
    ("require", r"(?:require|requires|required)"),
    ("allow", r"(?:allow|allows|allowed)"),
    ("contain", r"(?:contain|contains|contained)"),
    ("include", r"(?:include|includes|included)"),
    ("return", r"(?:return|returns|returned)"),
    ("have", r"(?:have|has|had)"),
    ("own", r"(?:own|owns|owned)"),
    ("prefer", r"(?:prefer|prefers|preferred)"),
    ("like", r"(?:like|likes|liked)"),
    ("avoid", r"(?:avoid|avoids|avoided)"),
)

_AUXILIARIES = r"(?:does|do|did|can|cannot|will|shall|must)"


def _normalize_phrase(value: str) -> str:
    """Normalize case, punctuation, and whitespace without semantic guesses."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_subject(value: str) -> str:
    normalized = _normalize_phrase(value)
    return re.sub(r"^(?:the|a|an)\s+", "", normalized)


def _normalize_value(value: str) -> str:
    normalized = _normalize_phrase(value)
    return re.sub(r"^(?:the|a|an)\s+", "", normalized)


def _prepare_statement(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    statement = unicodedata.normalize("NFKC", value).replace("’", "'").strip()
    for pattern, replacement in _CONTRACTIONS:
        statement = re.sub(pattern, replacement, statement, flags=re.IGNORECASE)
    statement = re.sub(r"\s+", " ", statement).strip().casefold()
    if not statement:
        return None

    # A single explicit proposition is the supported unit.  Multiple clauses,
    # hedging, and coordination are intentionally outside this detector.
    if re.search(r"[!?;]", statement):
        return None
    if re.search(r"\.\s+\w", statement):
        return None
    if re.search(
        r"\b(?:and|or|maybe|perhaps|probably|possibly|might|may|could|should|would)\b",
        statement,
    ):
        return None

    statement = re.sub(r"[.,]+$", "", statement).strip()
    return statement or None


def _valid_subject(value: str) -> bool:
    if not value or value in _AMBIGUOUS_SUBJECTS:
        return False
    words = value.split()
    if len(words) > 12:
        return False
    return not any(word in {"not", "never", "no"} for word in words)


def _valid_value(value: str) -> bool:
    return bool(value) and len(value.split()) <= 16


def _split_negation(value: str) -> tuple[bool, str]:
    match = re.match(r"^(?P<negation>not|never)\s+(?P<value>.+)$", value)
    if match:
        return False, match.group("value")
    return True, value


def _has_key_hint(value: str) -> bool:
    words = set(value.split())
    return bool(words & _EXCLUSIVE_KEY_HINTS)


def _has_exclusive_qualifier(value: str) -> bool:
    words = set(value.split())
    return bool(words & _EXCLUSIVE_QUALIFIERS)


def _is_explicit_identifier_value(value: str) -> bool:
    words = value.split()
    if not words or len(words) > 4:
        return False
    return any(
        word in _TECHNICAL_VALUES
        or word in _EXPLICIT_IDENTIFIER_VALUES
        or re.search(r"\d", word)
        for word in words
    )


def _is_exclusive_value_key(subject: str, predicate: str, value: str) -> bool:
    if predicate in {
        "belong_to",
        "live_in",
        "located_in",
        "listen_on_port",
        "reside_in",
        "run_on_port",
    }:
        return True
    if _has_key_hint(subject) or _has_key_hint(predicate):
        return _is_explicit_identifier_value(value)
    if _has_exclusive_qualifier(subject) and predicate == "use":
        return _is_explicit_identifier_value(value)
    return False


def _parse_statement(statement: object) -> _Proposition | None:
    prepared = _prepare_statement(statement)
    if prepared is None:
        return None

    # Explicit key/value assignments are allowed only for recognizable keys;
    # otherwise labels and prose fragments would look like propositions.
    assignment = re.match(r"^(?P<subject>[^:=]+?)\s*(?::|=)\s*(?P<value>.+)$", prepared)
    if assignment:
        subject = _normalize_subject(assignment.group("subject"))
        positive, raw_value = _split_negation(assignment.group("value"))
        value = _normalize_value(raw_value)
        if (
            _valid_subject(subject)
            and _valid_value(value)
            and _has_key_hint(subject)
        ):
            return _Proposition(
                subject=subject,
                predicate="be",
                value=value,
                positive=positive,
                exclusive_value=_is_exclusive_value_key(subject, "be", value),
            )

    # Location is a distinct predicate.  Treating "is in" as generic "be"
    # would make ordinary descriptive values look incompatible.
    location = re.match(
        r"^(?P<subject>.+?)\s+(?:is|are|was|were)\s+"
        r"(?:(?P<negation>not|never)\s+)?in\s+(?P<value>.+)$",
        prepared,
    )
    if location:
        subject = _normalize_subject(location.group("subject"))
        positive = location.group("negation") is None
        value = _normalize_value(location.group("value"))
        if _valid_subject(subject) and _valid_value(value):
            return _Proposition(
                subject=subject,
                predicate="located_in",
                value=value,
                positive=positive,
                exclusive_value=True,
            )

    # Keep this before the generic copula parser so "is located in" retains
    # its exclusive location predicate instead of becoming "be located in".
    located = re.match(
        r"^(?P<subject>.+?)\s+(?:is|are|was|were)\s+"
        r"(?:(?P<negation>not|never)\s+)?located\s+in\s+"
        r"(?P<value>.+)$",
        prepared,
    )
    if located:
        subject = _normalize_subject(located.group("subject"))
        value = _normalize_value(located.group("value"))
        if _valid_subject(subject) and _valid_value(value):
            return _Proposition(
                subject=subject,
                predicate="located_in",
                value=value,
                positive=located.group("negation") is None,
                exclusive_value=True,
            )

    # Mandatory rules are not hedges: "must be" and "must not be" are an
    # explicit proposition with stable polarity.  Keep this narrow to `must`
    # so advisory wording such as should/might continues to abstain.
    mandatory_copula = re.match(
        r"^(?P<subject>.+?)\s+must\s+"
        r"(?:(?P<negation>not|never)\s+)?be\s+(?P<value>.+)$",
        prepared,
    )
    if mandatory_copula:
        subject = _normalize_subject(mandatory_copula.group("subject"))
        value = _normalize_value(mandatory_copula.group("value"))
        if _valid_subject(subject) and _valid_value(value):
            return _Proposition(
                subject=subject,
                predicate="be",
                value=value,
                positive=mandatory_copula.group("negation") is None,
                exclusive_value=_is_exclusive_value_key(subject, "be", value),
            )

    copula = re.match(
        r"^(?P<subject>.+?)\s+(?P<copula>is|are|was|were|equals|equal)\s+"
        r"(?:(?P<negation>not|never)\s+)?(?P<value>.+)$",
        prepared,
    )
    if copula:
        subject = _normalize_subject(copula.group("subject"))
        value = _normalize_value(copula.group("value"))
        if _valid_subject(subject) and _valid_value(value):
            predicate = "be" if copula.group("copula") != "equal" else "equal"
            positive = copula.group("negation") is None
            return _Proposition(
                subject=subject,
                predicate=predicate,
                value=value,
                positive=positive,
                exclusive_value=_is_exclusive_value_key(subject, predicate, value),
            )

    # Auxiliary negation is accepted only when it anchors a known predicate.
    # This covers "does not store" and "cannot use" without treating any
    # occurrence of "not" as semantic evidence.
    for predicate, pattern in _PREDICATE_PATTERNS:
        auxiliary = re.match(
            rf"^(?P<subject>.+?)\s+(?P<auxiliary>{_AUXILIARIES})\s+"
            rf"(?P<negation>not|never)?\s*(?:{pattern})\s+"
            rf"(?P<value>.+)$",
            prepared,
        )
        if auxiliary:
            subject = _normalize_subject(auxiliary.group("subject"))
            value = _normalize_value(auxiliary.group("value"))
            if _valid_subject(subject) and _valid_value(value):
                positive = (
                    auxiliary.group("negation") is None
                    and auxiliary.group("auxiliary") != "cannot"
                )
                return _Proposition(
                    subject=subject,
                    predicate=predicate,
                    value=value,
                    positive=positive,
                    exclusive_value=_is_exclusive_value_key(subject, predicate, value),
                )

    # A direct "never <predicate>" is unambiguous only for a known predicate.
    for predicate, pattern in _PREDICATE_PATTERNS:
        direct = re.match(
            rf"^(?P<subject>.+?)\s+(?P<negation>never\s+)?(?:{pattern})\s+"
            rf"(?P<value>.+)$",
            prepared,
        )
        if direct:
            subject = _normalize_subject(direct.group("subject"))
            value = _normalize_value(direct.group("value"))
            if _valid_subject(subject) and _valid_value(value):
                positive = direct.group("negation") is None
                if predicate == "have" and value.startswith("no "):
                    positive = False
                    value = value[3:].strip()
                if not value:
                    return None
                return _Proposition(
                    subject=subject,
                    predicate=predicate,
                    value=value,
                    positive=positive,
                    exclusive_value=_is_exclusive_value_key(subject, predicate, value),
                )

    return None


def _values_are_incompatible(left: _Proposition, right: _Proposition) -> bool:
    if left.value == right.value:
        return False

    if (
        _OPPOSITE_VALUES.get(left.value) == right.value
        or _OPPOSITE_VALUES.get(right.value) == left.value
    ):
        return True

    if not (left.exclusive_value or right.exclusive_value):
        return False

    if left.predicate in {
        "belong_to",
        "live_in",
        "located_in",
        "listen_on_port",
        "reside_in",
        "run_on_port",
    }:
        return True

    # Numeric/technical scalar alternatives under an explicit key are
    # mutually exclusive enough to report.  Generic descriptive values are
    # intentionally not included here.
    return _is_explicit_identifier_value(left.value) and _is_explicit_identifier_value(
        right.value
    )


def assess_conflict(incoming: str, existing: str) -> ConflictAssessment:
    """Assess two statements without making a persistence or model call.

    ``NO_CONFLICT`` is reserved for the strongest positive control: both
    inputs resolve to the same normalized proposition and explicit polarity.
    When the statements cannot be compared with high confidence, this
    function returns ``ABSTAIN`` rather than guessing that they coexist or
    conflict.
    """

    incoming_proposition = _parse_statement(incoming)
    existing_proposition = _parse_statement(existing)
    if incoming_proposition is None or existing_proposition is None:
        return ConflictAssessment(
            ConflictOutcome.ABSTAIN,
            "ambiguous or unsupported proposition; shared keywords or loose negation are insufficient",
        )

    same_key = (
        incoming_proposition.subject == existing_proposition.subject
        and incoming_proposition.predicate == existing_proposition.predicate
    )
    if not same_key:
        return ConflictAssessment(
            ConflictOutcome.ABSTAIN,
            "different explicit subject or predicate; shared keywords do not establish a conflict",
        )

    if incoming_proposition.value == existing_proposition.value:
        if incoming_proposition.positive != existing_proposition.positive:
            return ConflictAssessment(
                ConflictOutcome.CONFLICT,
                "same normalized proposition with opposite explicit polarity",
            )
        return ConflictAssessment(
            ConflictOutcome.NO_CONFLICT,
            "same normalized proposition with matching explicit polarity",
        )

    if _values_are_incompatible(incoming_proposition, existing_proposition):
        return ConflictAssessment(
            ConflictOutcome.CONFLICT,
            "same explicit subject/predicate with incompatible explicit values",
        )

    return ConflictAssessment(
        ConflictOutcome.ABSTAIN,
        "same subject/predicate but the values are not proven incompatible",
    )


__all__ = ["ConflictAssessment", "ConflictOutcome", "assess_conflict"]
