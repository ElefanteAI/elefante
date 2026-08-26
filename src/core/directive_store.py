# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/core/directive_store.py
# PURPOSE : Persistent behavioral constraints stored separately from memories
#           and injected into normal product-operation responses.
# ROLE    : Core — server.py injects directives on its normal response path;
#           management responses use a minimal path.
# TOUCHED : When changing directive persistence, injection rules, or the
#           elefante-DirectiveAdd/Remove/List tool contracts.
# ─────────────────────────────────────────────────────────────────────────────
"""
Directive Store — persistent behavioral constraints.

Directives are NOT memories. They do not compete on similarity scores.
Active directives are injected into normal product-operation responses.
System, dashboard, and directive-management responses use a minimal path and
do not recursively inject them.

Storage: ~/.elefante/data/directives.json (simple JSON file).
Loaded once at server init, cached in memory, persisted on mutation.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.config import DATA_DIR
from src.utils.logger import get_logger
from src.utils.runtime_profile import CLIENT_PROFILE, runtime_profile

logger = get_logger(__name__)

DIRECTIVES_FILE = DATA_DIR / "directives.json"

SYSTEM_DIRECTIVE_DEFINITIONS = (
    (
        "system-sdd-gate-0",
        "SDD Gate 0: Read the actual source file first. If debugging, route through workspace/ISSUES.md and the matching compendium/test path. Read CHANGELOG.md only to confirm or falsify a concrete assumption before naming a root cause.",
    ),
    (
        "system-sdd-critical-blocker",
        "SDD Critical Blocker: If a claim is not grounded in source, docs, tests, or user-provided logs, say UNKNOWN and stop.",
    ),
    (
        "system-sdd-gate-2",
        "SDD Gate 2: Scan leakage surfaces before shipping: MCP response contract, configured vector-store roundtrip, Kuzu schema and DML, stdout purity, compliance gate, dashboard snapshot, co-activation history, and documentation links.",
    ),
    (
        "system-sdd-gate-3",
        "SDD Gate 3: Verify formulas, scores, and logic from source code with real values; do not quote remembered docs as proof.",
    ),
    (
        "system-sdd-gate-4",
        "SDD Gate 4: Run scripts/verify/verify_health.py, scripts/verify/verify_mcp_handshake.py, and targeted regression coverage before claiming completion.",
    ),
    (
        "system-sdd-stdout-purity",
        "SDD STDOUT Purity Law: Never print to stdout from MCP server code paths; stdout is reserved for JSON-RPC only.",
    ),
    (
        "system-elefante-search-first",
        "ELEFANTE Search-First: Search memory before asserting preferences, conventions, or past decisions.",
    ),
    (
        "system-elefante-tool-contract",
        "ELEFANTE Tool Contract: Read any ENTRYPOINT_SEQUENCE_READ_THIS_FIRST, MANDATORY_PROTOCOLS_READ_THIS_FIRST, DIRECTIVES, and RELEVANT_CONTEXT blocks present in a tool response; RELEVANT_CONTEXT and policy blocks are conditional.",
    ),
    (
        "system-elefante-minimal-patch",
        "ELEFANTE Minimal Patch: Fix root cause with the smallest coherent change and avoid unrelated refactors.",
    ),
    (
        "system-elefante-docs-sync",
        "ELEFANTE Docs Sync: Update README, technical docs, and CHANGELOG when behavior or architecture changes. CHANGELOG entries must use the current Keep a Changelog headings `### Added`, `### Fixed`, or `### Changed`, not retired headings.",
    ),
    (
        "system-elefante-cleanup",
        "ELEFANTE Cleanup: Delete scratch files, temp scripts, and dead code before completion.",
    ),
    (
        "system-elefante-versioning",
        "ELEFANTE Versioning: Use scripts/ci/advise_version_bump.py to choose the next semver when needed and scripts/ci/bump_version.py to apply the cascade; do not hand-edit scattered version strings.",
    ),
    (
        "system-elefante-verification",
        "ELEFANTE Verification: Read back or actively test every write path instead of trusting success flags.",
    ),
)

CLIENT_SYSTEM_DIRECTIVE_DEFINITIONS = (
    (
        "system-client-critical-thinking",
        "ELEFANTE Critical Thinking: Agreement is not evidence. Identify the governing objective, inspect current evidence, state material uncertainty or contradictions, test the strongest competing explanation, and choose the smallest change that addresses the root cause. Do not claim improvement without a measured comparison.",
    ),
    (
        "system-client-grounding",
        "ELEFANTE Grounding: Use stored memory and current task evidence for project-specific claims; identify material uncertainty instead of guessing.",
    ),
    (
        "system-client-search-first",
        "ELEFANTE Search-First: Search memory before asserting preferences, conventions, decisions, or prior context.",
    ),
    (
        "system-client-conflicts",
        "ELEFANTE Conflict Safety: Surface conflicting or stale memories and prefer verified current evidence over silent assumptions.",
    ),
    (
        "system-client-secrets",
        "ELEFANTE Secret Safety: Never store passwords, API keys, access tokens, or other secrets in memory.",
    ),
)


class Directive:
    """A single behavioral constraint."""

    __slots__ = ("id", "content", "created_at", "active", "source", "removable")

    def __init__(
        self,
        content: str,
        *,
        directive_id: Optional[str] = None,
        created_at: Optional[str] = None,
        active: bool = True,
        source: str = "user",
        removable: bool = True,
    ):
        self.id: str = directive_id or uuid.uuid4().hex[:12]
        self.content: str = content
        self.created_at: str = created_at or datetime.now(timezone.utc).isoformat()
        self.active: bool = active
        self.source: str = source
        self.removable: bool = removable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
            "active": self.active,
            "source": self.source,
            "removable": self.removable,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Directive":
        return cls(
            content=data["content"],
            directive_id=data.get("id"),
            created_at=data.get("created_at"),
            active=data.get("active", True),
            source=data.get("source", "user"),
            removable=data.get("removable", True),
        )


class DirectiveStore:
    """
    Manages the directives lifecycle: load, add, remove, list, persist.

    Thread-safe for the single-process MCP server model (no concurrent writes).
    """

    def __init__(self, path: Optional[Path] = None, *, profile: Optional[str] = None):
        self._path = path or DIRECTIVES_FILE
        self._profile = profile or runtime_profile()
        self._directives: List[Directive] = []
        self._system_directives: List[Directive] = self._build_system_directives()
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, content: str) -> Directive:
        """Add a new directive. Returns the created Directive."""
        content = content.strip()
        if not content:
            raise ValueError("Directive content cannot be empty")

        existing = self._find_by_content(content)
        if existing is not None:
            return existing

        directive = Directive(content)
        self._directives.append(directive)
        self._persist()
        logger.info(f"Directive added: {directive.id}")
        return directive

    def remove(self, directive_id: str) -> bool:
        """Remove a directive by ID. Returns True if found and removed."""
        if self.is_system_directive(directive_id):
            logger.warning(f"Attempted to remove system directive: {directive_id}")
            return False

        for i, d in enumerate(self._directives):
            if d.id == directive_id:
                self._directives.pop(i)
                self._persist()
                logger.info(f"Directive removed: {directive_id}")
                return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all directives as dicts."""
        return [d.to_dict() for d in self._all_directives()]

    def get_active_texts(self) -> List[str]:
        """Return the content strings of all active directives.

        This is called when the server builds a normal response injection.
        It should be fast — just a list comprehension over cached objects.
        """
        return [d.content for d in self._all_directives() if d.active]

    def count(self) -> int:
        return len(self._all_directives())

    def system_count(self) -> int:
        return len(self._system_directives)

    def user_count(self) -> int:
        return len(self._directives)

    def is_system_directive(self, directive_id: str) -> bool:
        return any(d.id == directive_id for d in self._system_directives)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load directives from disk."""
        if not self._path.exists():
            self._directives = []
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._directives = [Directive.from_dict(d) for d in data]
            logger.info(f"Loaded {len(self._directives)} directives from {self._path}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Corrupt directives file, starting fresh: {e}")
            self._directives = []

    def _build_system_directives(self) -> List[Directive]:
        directives = []
        definitions = (
            CLIENT_SYSTEM_DIRECTIVE_DEFINITIONS
            if self._profile == CLIENT_PROFILE
            else SYSTEM_DIRECTIVE_DEFINITIONS
        )
        for directive_id, content in definitions:
            directives.append(
                Directive(
                    content=content,
                    directive_id=directive_id,
                    source="system",
                    removable=False,
                )
            )
        return directives

    def _all_directives(self) -> List[Directive]:
        return [*self._system_directives, *self._directives]

    def _find_by_content(self, content: str) -> Optional[Directive]:
        normalized = content.strip()
        for directive in self._all_directives():
            if directive.content == normalized:
                return directive
        return None

    def _persist(self) -> None:
        """Write current directives to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [d.to_dict() for d in self._directives],
            indent=2,
            ensure_ascii=False,
        )
        self._path.write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[DirectiveStore] = None


def get_directive_store() -> DirectiveStore:
    """Get the global DirectiveStore singleton."""
    global _store
    if _store is None:
        _store = DirectiveStore()
    return _store
