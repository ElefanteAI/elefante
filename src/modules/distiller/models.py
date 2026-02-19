"""
Elefante Session Distiller — Data Models
All structured types used across the distiller pipeline.

Design Principle: The parser MUST produce these types. No raw dicts leak out.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


# ─── Enums ────────────────────────────────────────────────────────────────────

class ResponseKind(str, Enum):
    """Known VS Code chat response chunk types."""
    TEXT = "text"
    MARKDOWN = "markdown"
    THINKING = "thinking"
    CODE_BLOCK = "codeBlock"
    TOOL_INVOCATION = "toolInvocationSerialized"
    INLINE_REFERENCE = "inlineReference"
    COMMAND = "command"
    PROGRESS = "progressMessage"
    UNKNOWN = "unknown"


class SessionFormat(str, Enum):
    JSON = "json"
    JSONL = "jsonl"


class InsightType(str, Enum):
    """Categories of distilled knowledge."""
    DECISION = "decision"
    ROOT_CAUSE = "root_cause"
    PREFERENCE = "preference"
    ARCHITECTURE_RULE = "architecture_rule"
    FACT = "fact"
    CODE_SNIPPET = "code_snippet"
    ERROR_FIX = "error_fix"
    WORKFLOW = "workflow"


# ─── Core Models ──────────────────────────────────────────────────────────────

class ResponseChunk(BaseModel):
    """A single piece of an assistant response (text, code, tool call, etc.)."""
    kind: ResponseKind = ResponseKind.UNKNOWN
    value: str = ""
    language: Optional[str] = None           # For codeBlock
    tool_name: Optional[str] = None          # For toolInvocationSerialized
    tool_result: Optional[str] = None        # For tool output
    raw: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_vscode(cls, obj: Any) -> "ResponseChunk":
        """Factory: parse a single VS Code response object into a typed chunk."""
        if isinstance(obj, str):
            return cls(kind=ResponseKind.TEXT, value=obj)
        if not isinstance(obj, dict):
            return cls(kind=ResponseKind.UNKNOWN, value=str(obj), raw={"original_type": type(obj).__name__})

        raw_kind = obj.get("kind", "unknown")
        try:
            kind = ResponseKind(raw_kind)
        except ValueError:
            kind = ResponseKind.UNKNOWN

        chunk = cls(kind=kind, raw=obj)

        if kind in (ResponseKind.TEXT, ResponseKind.MARKDOWN, ResponseKind.THINKING, ResponseKind.PROGRESS):
            chunk.value = obj.get("value", "")

        elif kind == ResponseKind.CODE_BLOCK:
            chunk.value = obj.get("value", obj.get("code", ""))
            chunk.language = obj.get("language", obj.get("languageId", ""))

        elif kind == ResponseKind.TOOL_INVOCATION:
            inv_msg = obj.get("invocationMessage", {})
            chunk.tool_name = obj.get("toolId", "")
            chunk.value = inv_msg.get("value", str(inv_msg)) if isinstance(inv_msg, dict) else str(inv_msg)
            result = obj.get("result", obj.get("confirmationMessages", None))
            if result:
                chunk.tool_result = str(result) if not isinstance(result, str) else result

        elif kind == ResponseKind.INLINE_REFERENCE:
            uri = obj.get("uri", obj.get("value", ""))
            chunk.value = uri if isinstance(uri, str) else str(uri)

        elif kind == ResponseKind.COMMAND:
            chunk.value = obj.get("command", {}).get("title", str(obj))

        else:
            chunk.value = str(obj.get("value", obj))

        return chunk


class ChatTurn(BaseModel):
    """A single User -> Assistant exchange."""
    user_text: str
    response_chunks: List[ResponseChunk] = Field(default_factory=list)
    model: Optional[str] = None
    timestamp: Optional[datetime] = None

    @computed_field
    @property
    def agent_text(self) -> str:
        """Flattened text from all response chunks (for embedding / search)."""
        parts = []
        for chunk in self.response_chunks:
            if chunk.kind == ResponseKind.THINKING:
                continue  # Thinking is noise for flat text
            if chunk.kind == ResponseKind.CODE_BLOCK:
                parts.append(f"```{chunk.language or ''}\n{chunk.value}\n```")
            elif chunk.kind == ResponseKind.TOOL_INVOCATION:
                parts.append(f"[Tool: {chunk.tool_name}]")
            elif chunk.value:
                parts.append(chunk.value)
        return "\n".join(parts)

    @computed_field
    @property
    def has_code(self) -> bool:
        return any(c.kind == ResponseKind.CODE_BLOCK for c in self.response_chunks)

    @computed_field
    @property
    def has_thinking(self) -> bool:
        return any(c.kind == ResponseKind.THINKING for c in self.response_chunks)

    def to_markdown(self) -> str:
        md = f"## User\n{self.user_text}\n\n## Assistant\n"
        for chunk in self.response_chunks:
            if chunk.kind == ResponseKind.THINKING:
                preview = chunk.value[:200] + "..." if len(chunk.value) > 200 else chunk.value
                md += f"> **Thinking:** {preview}\n\n"
            elif chunk.kind == ResponseKind.CODE_BLOCK:
                md += f"```{chunk.language or ''}\n{chunk.value}\n```\n\n"
            elif chunk.kind == ResponseKind.TOOL_INVOCATION:
                md += f"*[Tool: {chunk.tool_name} — {chunk.value}]*\n\n"
            elif chunk.value:
                md += f"{chunk.value}\n\n"
        md += "---\n\n"
        return md


class ChatSession(BaseModel):
    """A complete conversation extracted from VS Code."""
    session_id: str
    source_path: str
    source_format: SessionFormat
    workspace_id: Optional[str] = None      # The UUID folder name
    workspace_name: Optional[str] = None    # Resolved from workspace.json
    turns: List[ChatTurn] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: Optional[str] = None

    @computed_field
    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @computed_field
    @property
    def content_hash(self) -> str:
        """Deterministic hash for dedup — based on user messages only."""
        user_texts = "|".join(t.user_text for t in self.turns)
        return hashlib.sha256(user_texts.encode()).hexdigest()[:16]

    def to_markdown(self) -> str:
        header = (
            f"# Chat Session: {self.session_id}\n"
            f"Workspace: {self.workspace_name or self.workspace_id or 'unknown'}\n"
            f"Turns: {self.turn_count}\n"
            f"Extracted: {self.extracted_at.isoformat()}\n\n"
        )
        body = "".join(turn.to_markdown() for turn in self.turns)
        return header + body

    def to_flat_text(self) -> str:
        """Plain text for LLM distillation input. No markdown formatting."""
        lines = []
        for i, turn in enumerate(self.turns, 1):
            lines.append(f"[Turn {i}] USER: {turn.user_text}")
            lines.append(f"[Turn {i}] ASSISTANT: {turn.agent_text}")
            lines.append("")
        return "\n".join(lines)


# ─── Distillation Output ─────────────────────────────────────────────────────

class DistilledInsight(BaseModel):
    """A single piece of knowledge extracted by the LLM Distiller."""
    insight_type: InsightType
    content: str
    suggested_tags: List[str] = Field(default_factory=list)
    source_turn: Optional[int] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class DistillationResult(BaseModel):
    """Output of the distillation pipeline for one session."""
    session_id: str
    insights: List[DistilledInsight] = Field(default_factory=list)
    noise_lines_dropped: int = 0
    signal_lines_kept: int = 0
    distilled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def signal_ratio(self) -> str:
        total = self.noise_lines_dropped + self.signal_lines_kept
        if total == 0:
            return "N/A"
        return f"1:{total // max(len(self.insights), 1)}"
