"""
Elefante Session Distiller — LLM Distillation Engine
Responsibility: Send a ChatSession through an LLM to extract high-value insights.

Supports multiple backends:
  - ollama   (default, local, free)
  - openai   (GPT-4o, GPT-4o-mini)
  - anthropic (Claude)
  - lmstudio (local, OpenAI-compatible)

The prompt is loaded from a tunable markdown file (not hardcoded).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    ChatSession,
    DistilledInsight,
    DistillationResult,
    InsightType,
)

logger = logging.getLogger("elefante.distiller.engine")

# Where the prompt lives — relative to this file
_PROMPT_DIR = Path(__file__).parent / "prompts"
_DEFAULT_PROMPT = _PROMPT_DIR / "extract_signal.md"

# Max chars to send to the LLM (prevents token overflow)
_MAX_INPUT_CHARS = 120_000  # ~30k tokens for GPT-4o


class DistillerEngine:
    """
    Sends a ChatSession through an LLM and returns structured DistillationResult.

    Usage:
        engine = DistillerEngine(backend="ollama", model="llama3.1")
        result = engine.distill(session)
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: Optional[str] = None,
        prompt_path: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.backend = backend.lower().strip()
        self.model = model or self._default_model()
        self.prompt_path = Path(prompt_path) if prompt_path else _DEFAULT_PROMPT
        self.api_key = api_key
        self.base_url = base_url

        # Load the extraction prompt
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {self.prompt_path}")
        self.system_prompt = self.prompt_path.read_text(encoding="utf-8")

        logger.info(f"DistillerEngine: backend={self.backend}, model={self.model}")

    def distill(self, session: ChatSession) -> DistillationResult:
        """
        Run the full distillation pipeline on a session.
        Returns typed DistillationResult with insights.
        """
        # Prepare input
        flat_text = session.to_flat_text()
        total_lines = flat_text.count("\n") + 1

        # Truncate if needed
        if len(flat_text) > _MAX_INPUT_CHARS:
            logger.warning(
                f"Session {session.session_id[:12]}... has {len(flat_text)} chars, "
                f"truncating to {_MAX_INPUT_CHARS}"
            )
            flat_text = flat_text[:_MAX_INPUT_CHARS] + "\n\n[TRUNCATED]"

        # Call the LLM
        raw_response = self._call_llm(flat_text)

        # Parse the response
        insights = self._parse_response(raw_response, session.session_id)

        signal_lines = sum(len(i.content.split("\n")) for i in insights)
        noise_lines = total_lines - signal_lines

        return DistillationResult(
            session_id=session.session_id,
            insights=insights,
            noise_lines_dropped=max(0, noise_lines),
            signal_lines_kept=signal_lines,
        )

    # ─── LLM Backends ────────────────────────────────────────────────────

    def _call_llm(self, user_content: str) -> str:
        """Route to the correct backend."""
        dispatch = {
            "ollama": self._call_ollama,
            "openai": self._call_openai,
            "anthropic": self._call_anthropic,
            "lmstudio": self._call_lmstudio,
        }

        handler = dispatch.get(self.backend)
        if handler is None:
            raise ValueError(
                f"Unknown backend: '{self.backend}'. "
                f"Supported: {', '.join(dispatch.keys())}"
            )
        return handler(user_content)

    def _call_ollama(self, user_content: str) -> str:
        """Local Ollama inference."""
        import httpx

        url = self.base_url or "http://localhost:11434"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 4096},
        }

        try:
            resp = httpx.post(
                f"{url}/api/chat",
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}") from e

    def _call_openai(self, user_content: str) -> str:
        """OpenAI API call."""
        import httpx

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY or pass api_key=")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_anthropic(self, user_content: str) -> str:
        """Anthropic Claude API call."""
        import httpx

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key=")

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": self.system_prompt,
            "messages": [
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
        }

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Anthropic returns content as a list of blocks
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    def _call_lmstudio(self, user_content: str) -> str:
        """LM Studio (OpenAI-compatible local server)."""
        import httpx

        url = self.base_url or "http://localhost:1234"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        resp = httpx.post(
            f"{url}/v1/chat/completions",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ─── Response Parsing ─────────────────────────────────────────────────

    def _parse_response(self, raw: str, session_id: str) -> List[DistilledInsight]:
        """Parse the LLM's JSON response into typed DistilledInsight objects."""
        # Strip markdown code fences if the LLM wrapped them
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        if not cleaned or cleaned == "[]":
            logger.info(f"Session {session_id[:12]}... produced zero insights (all noise)")
            return []

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON for {session_id[:12]}...: {e}")
            logger.debug(f"Raw response: {raw[:500]}")
            return []

        if not isinstance(items, list):
            logger.error(f"LLM returned non-array for {session_id[:12]}...: {type(items)}")
            return []

        insights: List[DistilledInsight] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dict insight at index {idx}")
                continue

            try:
                insight_type_str = item.get("type", "fact")
                try:
                    insight_type = InsightType(insight_type_str)
                except ValueError:
                    logger.warning(f"Unknown insight type '{insight_type_str}', defaulting to 'fact'")
                    insight_type = InsightType.FACT

                content = item.get("content", "").strip()
                if not content:
                    continue

                confidence = max(0.0, min(1.0, float(item.get("confidence", 0.7))))
                tags = item.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                tags = [str(t) for t in tags if t]

                source_turn = item.get("source_turn")
                if source_turn is not None:
                    try:
                        source_turn = int(source_turn)
                    except (ValueError, TypeError):
                        source_turn = None

                insights.append(DistilledInsight(
                    insight_type=insight_type,
                    content=content,
                    suggested_tags=tags,
                    source_turn=source_turn,
                    confidence=confidence,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse insight at index {idx}: {e}")
                continue

        logger.info(f"Parsed {len(insights)} insights from LLM response for {session_id[:12]}...")
        return insights

    # ─── Defaults ─────────────────────────────────────────────────────────

    def _default_model(self) -> str:
        defaults = {
            "ollama": "llama3.1",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "lmstudio": "default",
        }
        return defaults.get(self.backend, "default")
