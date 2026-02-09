"""
Elefante Session Distiller — Session Tracker
Responsibility: Track which sessions have been processed to ensure idempotency (F6).

No session gets distilled twice. If you run the distiller 100 times,
the 2nd through 100th runs produce zero new memories.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("elefante.distiller.tracker")

_DEFAULT_TRACKER_PATH = "~/.elefante/processed_sessions.json"


class SessionTracker:
    """Persistent index of which chat sessions we've already processed."""

    def __init__(self, tracker_path: Optional[str] = None):
        self.path = Path(tracker_path or _DEFAULT_TRACKER_PATH).expanduser()
        self._data: Dict[str, dict] = {}
        self._load()

    def is_processed(self, session_id: str, content_hash: str) -> bool:
        """
        Check if a session has been processed.
        Uses BOTH session_id AND content_hash — a session that has been updated
        since last processing should be re-processed.
        """
        entry = self._data.get(session_id)
        if entry is None:
            return False
        # If the content hash changed, the session has new turns — needs reprocessing
        if entry.get("content_hash") != content_hash:
            logger.info(f"Session {session_id[:8]}... content changed, needs re-processing")
            return False
        return True

    def mark_processed(self, session_id: str, content_hash: str, insights_count: int = 0) -> None:
        """Record that a session has been processed."""
        self._data[session_id] = {
            "content_hash": content_hash,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "insights_count": insights_count,
        }
        self._save()
        logger.info(f"Marked session {session_id[:8]}... as processed ({insights_count} insights)")

    def get_stats(self) -> dict:
        """Return summary statistics."""
        return {
            "total_processed": len(self._data),
            "total_insights": sum(e.get("insights_count", 0) for e in self._data.values()),
        }

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self._data = json.load(f)
                logger.debug(f"Loaded tracker: {len(self._data)} sessions")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Corrupt tracker file, starting fresh: {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)
