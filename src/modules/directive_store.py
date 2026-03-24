"""
Universal Spec Architect — Directive Store
Responsibility: Manage persistent, always-on behavioral constraints.

Directives are unconditional rules injected into every MCP tool response,
ensuring the agent sees them at the decision boundary.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("universal_spec_mcp.directive_store")

class DirectiveStore:
    def __init__(self, storage_dir: Path):
        self.storage_file = storage_dir / "directives.json"
        self.directives: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r") as f:
                    self.directives = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load directives: {e}")
                self.directives = []
        else:
            # Initialize with default EARS directive
            self.directives = [
                {
                    "id": "DIR-001",
                    "content": "All requirements MUST be written in strict EARS notation: [WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL <response>.",
                    "active": True
                }
            ]
            self._save()

    def _save(self):
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_file, "w") as f:
            json.dump(self.directives, f, indent=2)

    def add_directive(self, content: str) -> str:
        new_id = f"DIR-{len(self.directives) + 1:03d}"
        self.directives.append({
            "id": new_id,
            "content": content,
            "active": True
        })
        self._save()
        return new_id

    def get_active_directives(self) -> str:
        active = [d["content"] for d in self.directives if d.get("active", True)]
        if not active:
            return ""
        return "\n\nCRITICAL DIRECTIVES:\n" + "\n".join(f"- {d}" for d in active)

    def list_directives(self) -> List[Dict[str, Any]]:
        return self.directives

    def remove_directive(self, directive_id: str) -> bool:
        initial_len = len(self.directives)
        self.directives = [d for d in self.directives if d["id"] != directive_id]
        if len(self.directives) < initial_len:
            self._save()
            return True
        return False
