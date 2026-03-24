"""
Universal Spec Architect — Privacy Filter
Responsibility: Scrub secrets, API keys, passwords, and tokens BEFORE they are written to spec files.

This ensures that AI-generated specifications do not accidentally leak sensitive credentials
into the project's git repository.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

logger = logging.getLogger("universal_spec_mcp.privacy")

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

    # OpenAI keys
    ("OPENAI_KEY", re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED:OPENAI_KEY]"),

    # Anthropic keys
    ("ANTHROPIC_KEY", re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"), "[REDACTED:ANTHROPIC_KEY]"),

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


class PrivacyFilter:
    """Scrubs sensitive data from text before it is written to spec files."""

    def __init__(self, extra_patterns: Optional[List[Tuple[str, str, str]]] = None):
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

# Global instance for easy use
privacy_filter = PrivacyFilter()
