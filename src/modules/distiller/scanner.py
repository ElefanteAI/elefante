"""
Elefante Session Distiller — Session Scanner
Responsibility: Find, enumerate, and map VS Code chat sessions to their workspaces.

Key improvements over v1 "watcher.py":
  - Cross-platform detection (macOS/Linux/Windows)
  - Workspace name resolution via workspace.json
  - Buffered keyword search (no full-file-into-memory for large files)
  - Session metadata without full parse (size, mtime, format)
  - Proper logging, no silent failures
"""

from __future__ import annotations

import glob
import json
import logging
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, List, Optional

logger = logging.getLogger("elefante.distiller.scanner")

# Max bytes to read when doing keyword search (prevents OOM on huge files)
_KEYWORD_SCAN_CHUNK = 4 * 1024 * 1024  # 4 MB


@dataclass
class SessionInfo:
    """Lightweight metadata about a session file (no full parse required)."""
    file_path: str
    session_id: str                         # UUID (filename stem)
    format: str                             # "json" or "jsonl"
    workspace_id: str                       # UUID folder name
    workspace_name: Optional[str] = None    # Resolved human-readable name
    size_bytes: int = 0
    modified_at: Optional[datetime] = None


class SessionScanner:
    """Discovers and enumerates VS Code chat sessions across all workspaces."""

    def __init__(self, storage_root: Optional[str] = None):
        self.root = Path(storage_root) if storage_root else self._detect_root()
        self._workspace_name_cache: Dict[str, Optional[str]] = {}

    # ─── Public API ───────────────────────────────────────────────────────

    def list_sessions(self, limit: int = 50) -> List[SessionInfo]:
        """Return session metadata sorted by modification time (newest first)."""
        sessions: List[SessionInfo] = []

        if not self.root.exists():
            logger.warning(f"Storage root does not exist: {self.root}")
            return []

        for ws_folder in self.root.iterdir():
            if not ws_folder.is_dir():
                continue
            chat_dir = ws_folder / "chatSessions"
            if not chat_dir.exists():
                continue

            workspace_id = ws_folder.name
            workspace_name = self._resolve_workspace_name(ws_folder)

            for fpath in chat_dir.iterdir():
                if fpath.suffix not in (".json", ".jsonl"):
                    continue
                try:
                    stat = fpath.stat()
                    sessions.append(SessionInfo(
                        file_path=str(fpath),
                        session_id=fpath.stem,
                        format=fpath.suffix.lstrip("."),
                        workspace_id=workspace_id,
                        workspace_name=workspace_name,
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    ))
                except OSError as e:
                    logger.warning(f"Cannot stat {fpath}: {e}")

        sessions.sort(key=lambda s: s.modified_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return sessions[:limit]

    def search(self, keyword: str, limit: int = 20) -> List[SessionInfo]:
        """
        Search for sessions containing a keyword.
        Uses buffered reads to avoid OOM on large files.
        """
        matches: List[SessionInfo] = []
        all_sessions = self.list_sessions(limit=500)  # Get all, then filter

        for info in all_sessions:
            if self._file_contains_keyword(info.file_path, keyword):
                matches.append(info)
                if len(matches) >= limit:
                    break

        return matches

    def watch(self, interval: int = 30) -> Generator[SessionInfo, None, None]:
        """
        Yields SessionInfo objects for files that have been modified since last check.
        Blocking generator — run in a background thread.
        """
        import time
        known_mtimes: Dict[str, float] = {}

        # Baseline
        for info in self.list_sessions(limit=200):
            known_mtimes[info.file_path] = info.modified_at.timestamp() if info.modified_at else 0

        while True:
            for info in self.list_sessions(limit=200):
                mtime = info.modified_at.timestamp() if info.modified_at else 0
                prev = known_mtimes.get(info.file_path, 0)
                if mtime > prev:
                    known_mtimes[info.file_path] = mtime
                    yield info
            time.sleep(interval)

    # ─── Private ──────────────────────────────────────────────────────────

    def _detect_root(self) -> Path:
        """Detect VS Code workspaceStorage path for the current OS."""
        system = platform.system()
        home = Path.home()

        paths = {
            "Darwin":  home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage",
            "Linux":   home / ".config" / "Code" / "User" / "workspaceStorage",
            "Windows": home / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage",
        }

        root = paths.get(system)
        if root is None:
            raise OSError(f"Unsupported OS: {system}")
        return root

    def _resolve_workspace_name(self, ws_folder: Path) -> Optional[str]:
        """Read workspace.json to get the human-readable workspace path/name."""
        ws_id = ws_folder.name
        if ws_id in self._workspace_name_cache:
            return self._workspace_name_cache[ws_id]

        ws_json = ws_folder / "workspace.json"
        name = None
        if ws_json.exists():
            try:
                with open(ws_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                folder = data.get("folder", "")
                # folder is typically a URI like "file:///Users/jay/Documents/VSCODE/Chile2026"
                if folder.startswith("file://"):
                    name = folder.replace("file://", "").rstrip("/").split("/")[-1]
                else:
                    name = folder.split("/")[-1] or folder
            except Exception as e:
                logger.debug(f"Could not read workspace.json in {ws_id}: {e}")

        self._workspace_name_cache[ws_id] = name
        return name

    @staticmethod
    def _file_contains_keyword(file_path: str, keyword: str) -> bool:
        """Buffered keyword search — reads in chunks, not full file."""
        keyword_lower = keyword.lower()
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                overlap = ""
                while True:
                    chunk = f.read(_KEYWORD_SCAN_CHUNK)
                    if not chunk:
                        break
                    # Search with overlap to handle keywords split across chunks
                    search_text = (overlap + chunk).lower()
                    if keyword_lower in search_text:
                        return True
                    # Keep last N chars as overlap for next iteration
                    overlap = chunk[-len(keyword):] if len(chunk) > len(keyword) else chunk
        except OSError as e:
            logger.warning(f"Cannot read {file_path}: {e}")
        return False
