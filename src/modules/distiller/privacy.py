"""
Elefante Session Distiller — Privacy Filter
Responsibility: Scrub secrets, API keys, passwords, and tokens BEFORE storage.

This is a CRITICAL trust feature. If Elefante stores someone's AWS_SECRET_ACCESS_KEY
in a vector database, the product is dead on arrival.

Runs BEFORE any content reaches the configured vector store or knowledge graph.
"""

from __future__ import annotations

import re
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, List, Tuple

logger = logging.getLogger("elefante.distiller.privacy")


@dataclass
class ScrubResult:
    """What the scrubber found and redacted."""
    original_length: int
    scrubbed_length: int
    redactions: int
    redacted_types: List[str] = field(default_factory=list)


# Each pattern: (name, compiled regex, replacement)
_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    # AWS
    ("AWS_ACCESS_KEY", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}", re.IGNORECASE), "[REDACTED:AWS_KEY]"),
    ("AWS_SECRET_KEY", re.compile(r"(?:aws_secret_access_key|secret_key)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?", re.IGNORECASE), "[REDACTED:AWS_SECRET]"),

    # Generic API Keys (long hex/alphanum strings after key= or api_key= etc.)
    ("API_KEY", re.compile(r"(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,})['\"]?", re.IGNORECASE), "[REDACTED:API_KEY]"),

    # Bearer tokens
    ("BEARER_TOKEN", re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE), "Bearer [REDACTED:TOKEN]"),

    # GitHub tokens
    ("GITHUB_TOKEN", re.compile(r"(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{36,}"), "[REDACTED:GITHUB_TOKEN]"),

    # Token prefixes must start outside a word. Otherwise ordinary paths such
    # as "task-intelligence-program" are redacted and lose their exact scope.
    ("OPENAI_KEY", re.compile(r"(?<!\w)sk-(?!ant-)[A-Za-z0-9_\-]{20,}"), "[REDACTED:OPENAI_KEY]"),

    # Anthropic keys
    ("ANTHROPIC_KEY", re.compile(r"(?<!\w)sk-ant-[A-Za-z0-9\-]{20,}"), "[REDACTED:ANTHROPIC_KEY]"),

    # Generic passwords in config-like contexts
    ("PASSWORD", re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*['\"]?([^\s'\"]{4,})['\"]?", re.IGNORECASE), "[REDACTED:PASSWORD]"),

    # SSH private keys
    ("SSH_KEY", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "[REDACTED:SSH_PRIVATE_KEY]"),

    # Connection strings (postgres, mysql, mongo, redis)
    ("CONN_STRING", re.compile(r"(?:postgres|mysql|mongodb|redis)://[^\s\"']+", re.IGNORECASE), "[REDACTED:CONNECTION_STRING]"),

    # .env file values (KEY=value where key looks sensitive)
    ("ENV_SECRET", re.compile(r"(?:SECRET|TOKEN|KEY|PASSWORD|CREDENTIAL)[A-Z_]*\s*=\s*['\"]?([^\s'\"]{8,})['\"]?", re.IGNORECASE), "[REDACTED:ENV_SECRET]"),

    # IP addresses with ports (likely internal servers)
    ("INTERNAL_IP", re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}:\d{2,5}\b"), "[REDACTED:INTERNAL_IP]"),
]

# Structured payloads lose the ``key=value`` context used by text patterns.
# Match explicit credential field names, not benign counters or public keys.
_SECRET_FIELD = re.compile(
    r"(?:[a-z0-9]+[_-])*(?:api[_-]?key|secret|secret[_-]?key|secret[_-]access[_-]key|"
    r"access[_-]token|auth[_-]token|refresh[_-]token|secret[_-]token|"
    r"access[_-]key(?:[_-]id)?|password|passwd|pwd|"
    r"private[_-]key|credentials?|authorization)", re.IGNORECASE,
)
_REDACTED_VALUE = re.compile(r"\[REDACTED:[A-Z_]+\]")


def _merge_redaction_types(kinds: List[str]) -> List[str]:
    totals: Counter[str] = Counter()
    for kind in kinds:
        name, _, count = kind.rpartition("(")
        totals[name] += int(count.removesuffix(")"))
    return [f"{name}({totals[name]})" for name in sorted(totals)]


class PrivacyFilter:
    """Scrubs sensitive data from text before it enters the memory pipeline."""

    def __init__(self, extra_patterns: List[Tuple[str, str, str]] | None = None):
        self.patterns = list(_PATTERNS)
        if extra_patterns:
            for name, regex_str, replacement in extra_patterns:
                self.patterns.append((name, re.compile(regex_str), replacement))

    def scrub(self, text: str) -> Tuple[str, ScrubResult]:
        """
        Returns (scrubbed_text, result).
        The result tells you what was redacted and how many times.
        """
        if not isinstance(text, str):
            return (str(text) if text is not None else "", ScrubResult(
                original_length=0, scrubbed_length=0, redactions=0
            ))

        result = ScrubResult(
            original_length=len(text),
            scrubbed_length=0,
            redactions=0,
        )

        scrubbed = text
        for name, pattern, replacement in self.patterns:
            matches = pattern.findall(scrubbed)
            if matches:
                count = len(matches)
                scrubbed = pattern.sub(replacement, scrubbed)
                result.redactions += count
                result.redacted_types.append(f"{name}({count})")
                logger.info(f"Redacted {count}x {name}")

        result.scrubbed_length = len(scrubbed)

        if result.redactions > 0:
            logger.warning(f"Privacy filter scrubbed {result.redactions} secrets: {result.redacted_types}")

        return scrubbed, result

    def scrub_payload(self, value: Any) -> tuple[Any, int, list[str]]:
        """Recursively scrub secret-shaped strings in ingestion payloads."""
        if isinstance(value, str):
            scrubbed, result = self.scrub(value)
            return scrubbed, result.redactions, result.redacted_types
        if isinstance(value, list):
            output: list[Any] = []
            count = 0
            kinds: list[str] = []
            for item in value:
                clean, item_count, item_kinds = self.scrub_payload(item)
                output.append(clean)
                count += item_count
                kinds.extend(item_kinds)
            return output, count, _merge_redaction_types(kinds)
        if isinstance(value, dict):
            output_dict: dict[Any, Any] = {}
            count = 0
            kinds: list[str] = []
            for key, item in value.items():
                field_name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key) if isinstance(key, str) else ""
                if (
                    _SECRET_FIELD.fullmatch(field_name)
                    and item is not None and item != ""
                    and not (isinstance(item, str) and _REDACTED_VALUE.fullmatch(item))
                ):
                    output_dict[key] = "[REDACTED:CREDENTIAL_FIELD]"
                    count += 1
                    kinds.append("CREDENTIAL_FIELD(1)")
                    continue
                clean, item_count, item_kinds = self.scrub_payload(item)
                output_dict[key] = clean
                count += item_count
                kinds.extend(item_kinds)
            return output_dict, count, _merge_redaction_types(kinds)
        return value, 0, []
