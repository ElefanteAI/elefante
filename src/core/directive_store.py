"""
Directive Store — Persistent, always-on behavioral constraints.

Directives are NOT memories. They do not compete on similarity scores.
They are unconditional rules injected into every MCP tool response,
ensuring the agent sees them at the decision boundary — the last thing
read before acting on results.

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

logger = get_logger(__name__)

DIRECTIVES_FILE = DATA_DIR / "directives.json"


class Directive:
    """A single behavioral constraint."""

    __slots__ = ("id", "content", "created_at", "active")

    def __init__(
        self,
        content: str,
        *,
        directive_id: Optional[str] = None,
        created_at: Optional[str] = None,
        active: bool = True,
    ):
        self.id: str = directive_id or uuid.uuid4().hex[:12]
        self.content: str = content
        self.created_at: str = created_at or datetime.now(timezone.utc).isoformat()
        self.active: bool = active

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Directive":
        return cls(
            content=data["content"],
            directive_id=data.get("id"),
            created_at=data.get("created_at"),
            active=data.get("active", True),
        )


class DirectiveStore:
    """
    Manages the directives lifecycle: load, add, remove, list, persist.

    Thread-safe for the single-process MCP server model (no concurrent writes).
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or DIRECTIVES_FILE
        self._directives: List[Directive] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, content: str) -> Directive:
        """Add a new directive. Returns the created Directive."""
        content = content.strip()
        if not content:
            raise ValueError("Directive content cannot be empty")

        directive = Directive(content)
        self._directives.append(directive)
        self._persist()
        logger.info(f"Directive added: {directive.id}")
        return directive

    def remove(self, directive_id: str) -> bool:
        """Remove a directive by ID. Returns True if found and removed."""
        for i, d in enumerate(self._directives):
            if d.id == directive_id:
                self._directives.pop(i)
                self._persist()
                logger.info(f"Directive removed: {directive_id}")
                return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all directives as dicts."""
        return [d.to_dict() for d in self._directives]

    def get_active_texts(self) -> List[str]:
        """Return the content strings of all active directives.

        This is the method called on every tool response injection.
        It should be fast — just a list comprehension over cached objects.
        """
        return [d.content for d in self._directives if d.active]

    def count(self) -> int:
        return len(self._directives)

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
