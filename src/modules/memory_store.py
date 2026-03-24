"""
Universal Spec Architect — Memory Store
Responsibility: Provide a lightweight SQLite-based persistent memory layer.

This allows the assistant to store and retrieve architectural decisions,
patterns, and context across different features and sessions.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("universal_spec_mcp.memory_store")

class MemoryStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # FTS5 virtual table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content,
                    feature_name UNINDEXED,
                    category UNINDEXED,
                    content='memories',
                    content_rowid='id'
                )
            """)
            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content, feature_name, category)
                    VALUES (new.id, new.content, new.feature_name, new.category);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, feature_name, category)
                    VALUES ('delete', old.id, old.content, old.feature_name, old.category);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, feature_name, category)
                    VALUES ('delete', old.id, old.content, old.feature_name, old.category);
                    INSERT INTO memories_fts(rowid, content, feature_name, category)
                    VALUES (new.id, new.content, new.feature_name, new.category);
                END;
            """)
            conn.commit()

    def add_memory(self, feature_name: str, category: str, content: str) -> int:
        """Add a new memory to the store."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO memories (feature_name, category, content) VALUES (?, ?, ?)",
                (feature_name, category, content)
            )
            conn.commit()
            return cursor.lastrowid

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memories using full-text search."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT m.id, m.feature_name, m.category, m.content, m.created_at,
                       bm25(memories_fts) as score
                FROM memories_fts f
                JOIN memories m ON f.rowid = m.id
                WHERE memories_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """, (query, limit))
            
            return [dict(row) for row in cursor.fetchall()]

    def get_memories_by_feature(self, feature_name: str) -> List[Dict[str, Any]]:
        """Get all memories for a specific feature."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM memories WHERE feature_name = ? ORDER BY created_at DESC",
                (feature_name,)
            )
            return [dict(row) for row in cursor.fetchall()]
            
    def get_recent_memories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recently added memories."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
