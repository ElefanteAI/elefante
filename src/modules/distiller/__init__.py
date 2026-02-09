"""
Elefante Session Distiller

A pipeline that extracts high-value knowledge from VS Code Copilot chat sessions
and ingests them into Elefante's persistent memory system.

Module Structure:
    models.py    — Typed data models (ChatSession, ChatTurn, ResponseChunk)
    parser.py    — JSON/JSONL → ChatSession converter
    scanner.py   — Cross-platform session discovery & workspace mapping
    privacy.py   — Secret/token scrubber (runs before any storage)
    tracker.py   — Idempotency tracking (processed_sessions.json)
    __main__.py  — CLI entry point

Usage:
    python -m modules.distiller list
    python -m modules.distiller search "OpenClaw"
    python -m modules.distiller distill latest --dry-run
    python -m modules.distiller distill all
    python -m modules.distiller stats
"""

from .models import (
    ChatSession,
    ChatTurn,
    ResponseChunk,
    ResponseKind,
    DistilledInsight,
    DistillationResult,
    InsightType,
)
from .parser import ChatParser
from .scanner import SessionScanner, SessionInfo
from .privacy import PrivacyFilter
from .tracker import SessionTracker
from .engine import DistillerEngine
from .ingester import MemoryIngester

__all__ = [
    "ChatSession",
    "ChatTurn",
    "ResponseChunk",
    "ResponseKind",
    "DistilledInsight",
    "DistillationResult",
    "InsightType",
    "ChatParser",
    "SessionScanner",
    "SessionInfo",
    "PrivacyFilter",
    "SessionTracker",
    "DistillerEngine",
    "MemoryIngester",
]
