"""
Elefante Session Distiller — Chat Parser
Responsibility: Parse VS Code's JSON/JSONL chat formats into typed ChatSession objects.

Key improvement over v1: Returns ChatSession (typed), not List[Dict] (raw).
Handles ALL known response kinds. Logs warnings instead of swallowing errors.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ChatSession, ChatTurn, ResponseChunk, SessionFormat

logger = logging.getLogger("elefante.distiller.parser")


class ChatParser:
    """Parses VS Code chat session files into structured ChatSession objects."""

    def parse(self, file_path: str) -> ChatSession:
        """
        Main entry point. Accepts .json or .jsonl.
        Returns a fully typed ChatSession with all turns parsed.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Chat file not found: {file_path}")

        ext = path.suffix.lower()
        if ext == ".jsonl":
            raw_requests = self._extract_from_jsonl(path)
            fmt = SessionFormat.JSONL
        elif ext == ".json":
            raw_requests = self._extract_from_json(path)
            fmt = SessionFormat.JSON
        else:
            raise ValueError(f"Unsupported format: {ext}. Expected .json or .jsonl")

        session_id = path.stem  # UUID filename without extension
        workspace_id = self._extract_workspace_id(path)

        turns = self._convert_requests_to_turns(raw_requests)

        return ChatSession(
            session_id=session_id,
            source_path=str(path),
            source_format=fmt,
            workspace_id=workspace_id,
            turns=turns,
        )

    # ─── Format-Specific Extraction ───────────────────────────────────────

    def _extract_from_json(self, path: Path) -> List[Dict[str, Any]]:
        """JSON files are simple snapshots containing a 'requests' array."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupt JSON in {path}: {e}")
            return []

        if isinstance(data, dict) and "requests" in data:
            return data["requests"]

        logger.warning(f"JSON file {path.name} has no 'requests' key. Keys: {list(data.keys()) if isinstance(data, dict) else 'not-a-dict'}")
        return []

    def _extract_from_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        """
        JSONL files are incremental update logs.
        Strategy: Read ALL entries, find the last one that contains a full 'requests' array.
        This is how VS Code works: each write is a full state replacement for the 'requests' key.
        """
        entries: List[Dict[str, Any]] = []
        line_num = 0

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_num += 1
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entries.append(json.loads(stripped))
                except json.JSONDecodeError as e:
                    logger.warning(f"Bad JSON at {path.name}:{line_num}: {e}")
                    continue

        if not entries:
            logger.warning(f"JSONL file {path.name} is empty or fully corrupt.")
            return []

        # Strategy 1: Walk backwards to find the last entry with 'requests'
        for entry in reversed(entries):
            val = entry.get("v")

            # Pattern A: v is a dict with 'requests' key
            if isinstance(val, dict) and "requests" in val:
                reqs = val["requests"]
                if isinstance(reqs, list):
                    logger.info(f"Extracted {len(reqs)} requests from {path.name} (dict pattern)")
                    return reqs

            # Pattern B: v is directly a list of request objects
            if isinstance(val, list) and val and isinstance(val[0], dict) and "message" in val[0]:
                logger.info(f"Extracted {len(val)} requests from {path.name} (list pattern)")
                return val

        # Strategy 2: Deep fallback — recursively find message-like objects
        logger.info(f"Using deep search fallback for {path.name}")
        return self._deep_find_requests(entries)

    def _deep_find_requests(self, entries: List[Any]) -> List[Dict[str, Any]]:
        """Last resort: recursively search all structures for request-like objects."""
        found: List[Dict[str, Any]] = []
        seen_texts: set = set()

        def _recurse(obj: Any) -> None:
            if isinstance(obj, dict):
                # A 'request' object has a 'message' dict with a 'text' key
                msg = obj.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("text"), str):
                    text = msg["text"]
                    if text not in seen_texts:
                        seen_texts.add(text)
                        found.append(obj)
                    return  # Don't recurse INTO a request object
                for v in obj.values():
                    _recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    _recurse(item)

        _recurse(entries)
        logger.info(f"Deep search found {len(found)} unique request objects")
        return found

    # ─── Conversion to Typed Models ───────────────────────────────────────

    def _convert_requests_to_turns(self, raw_requests: List[Dict[str, Any]]) -> List[ChatTurn]:
        """Convert raw VS Code request dicts into typed ChatTurn objects."""
        turns: List[ChatTurn] = []

        for idx, req in enumerate(raw_requests):
            if not isinstance(req, dict):
                logger.warning(f"Skipping non-dict request at index {idx}: {type(req)}")
                continue

            # Extract user message
            message = req.get("message", {})
            if isinstance(message, dict):
                user_text = message.get("text", "")
            elif isinstance(message, str):
                user_text = message
            else:
                user_text = str(message)

            if not user_text.strip():
                logger.debug(f"Skipping request {idx} with empty user message")
                continue

            # Extract response chunks — using the typed ResponseChunk.from_vscode factory
            raw_responses = req.get("response", [])
            chunks: List[ResponseChunk] = []
            if isinstance(raw_responses, list):
                for resp_obj in raw_responses:
                    try:
                        chunks.append(ResponseChunk.from_vscode(resp_obj))
                    except Exception as e:
                        logger.warning(f"Failed to parse response chunk in request {idx}: {e}")
                        chunks.append(ResponseChunk(value=str(resp_obj)))

            # Extract model info if available
            model = req.get("chatModel", req.get("model", None))
            if isinstance(model, dict):
                model = model.get("id", model.get("name", None))

            turns.append(ChatTurn(
                user_text=user_text,
                response_chunks=chunks,
                model=str(model) if model else None,
            ))

        return turns

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_workspace_id(path: Path) -> Optional[str]:
        """
        Extract the workspace UUID from the file path.
        Expected: .../workspaceStorage/<UUID>/chatSessions/<file>
        """
        parts = path.parts
        try:
            idx = parts.index("chatSessions")
            if idx >= 1:
                return parts[idx - 1]
        except ValueError:
            pass
        return None
