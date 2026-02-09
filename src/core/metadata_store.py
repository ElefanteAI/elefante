"""
Fast Metadata Store (SQLite)
----------------------------
Provides high-performance local storage for memory metadata.
"""

import json
import aiosqlite
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from src.models.metadata import StandardizedMetadata
from src.utils.logger import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)

class MetadataStore:
    """
    SQLite-based store for fast metadata retrieval and filtering.
    Acts as the "Hot Layer" for context operations.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.config = get_config()
        if db_path:
            self.db_path = db_path
        else:
            # Default to data/metadata.db
            data_dir = Path(self.config.elefante.data_dir)
            self.db_path = data_dir / "metadata.db"
            
        self._ensure_db_dir()
        
    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    memory_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    timestamp TEXT,
                    type TEXT,
                    score INTEGER,
                    content TEXT,
                    json_data TEXT
                )
            """)
            
            # Create indices for fast lookup
            await db.execute("CREATE INDEX IF NOT EXISTS idx_session ON metadata(session_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON metadata(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_type ON metadata(type)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_score ON metadata(score)")
            
            await db.commit()
            logger.info(f"Metadata store initialized at {self.db_path}")

    async def add_metadata(self, memory_id: UUID, metadata: StandardizedMetadata, content: str):
        """Store metadata and content for a memory"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO metadata 
                    (memory_id, session_id, timestamp, type, score, content, json_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(memory_id),
                        str(metadata.context.session_id) if metadata.context.session_id else None,
                        metadata.system.created_at.isoformat(),
                        metadata.core.memory_type.value,
                        metadata.core.score,
                        content,
                        metadata.json()
                    )
                )
                await db.commit()
                logger.debug(f"Metadata stored for memory {memory_id}")
        except Exception as e:
            logger.error(f"Failed to store metadata: {e}")
            raise

    async def get_metadata(self, memory_id: UUID) -> Optional[tuple[StandardizedMetadata, str]]:
        """Retrieve metadata and content by memory ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT json_data, content FROM metadata WHERE memory_id = ?", 
                (str(memory_id),)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return StandardizedMetadata.parse_raw(row[0]), row[1]
        return None

    async def get_session_metadata(
        self, 
        session_id: UUID, 
        limit: int = 50
    ) -> List[tuple[str, StandardizedMetadata, str]]:
        """Retrieve recent metadata and content for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT memory_id, json_data, content FROM metadata 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (str(session_id), limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [(row[0], StandardizedMetadata.parse_raw(row[1]), row[2]) for row in rows]

    async def filter_metadata(
        self,
        memory_type: Optional[str] = None,
        min_importance: Optional[int] = None,
        limit: int = 20
    ) -> List[tuple[str, StandardizedMetadata, str]]:
        """Filter metadata by criteria"""
        query = "SELECT memory_id, json_data, content FROM metadata WHERE 1=1"
        params = []
        
        if memory_type:
            query += " AND type = ?"
            params.append(memory_type)
            
        if min_importance:
            query += " AND importance >= ?"
            params.append(min_importance)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [(row[0], StandardizedMetadata.parse_raw(row[1]), row[2]) for row in rows]

# Singleton instance
_metadata_store: Optional[MetadataStore] = None

def get_metadata_store() -> MetadataStore:
    """Get or create singleton metadata store"""
    global _metadata_store
    if _metadata_store is None:
        _metadata_store = MetadataStore()
    return _metadata_store
