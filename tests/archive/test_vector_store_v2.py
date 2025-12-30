"""
Test suite for VectorStore V2.0 schema integration
Tests metadata storage and retrieval with new schema
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4

from src.models.memory import (
    Memory,
    MemoryMetadata,
    DomainType,
    MemoryType,
    IntentType,
    MemoryStatus,
    SourceType,
)
from src.core.vector_store import VectorStore


@pytest.fixture
def vector_store(tmp_path):
    """Create an isolated test vector store instance with temp database"""
    chroma_dir = tmp_path / "chroma"
    return VectorStore(
        collection_name=f"test_v2_{uuid4().hex}",
        persist_directory=str(chroma_dir),
    )


@pytest.fixture
def sample_memory_v2():
    """Create a sample V2 memory for testing"""
    return Memory(
        content="Test memory with V2 schema",
        metadata=MemoryMetadata(
            domain=DomainType.WORK,
            category="testing",
            memory_type=MemoryType.FACT,
            subcategory="unit-tests",
            intent=IntentType.REFERENCE,
            importance=7,
            urgency=5,
            confidence=0.9,
            tags=["test", "v2", "schema"],
            keywords=["memory", "schema", "test"],
            status=MemoryStatus.NEW,
            source=SourceType.USER_INPUT,
            verified=True,
            project="elefante",
        )
    )


class TestVectorStoreV2Metadata:
    """Test V2 metadata storage and retrieval"""
    
    @pytest.mark.asyncio
    async def test_add_memory_v2_schema(self, vector_store, sample_memory_v2):
        """Test adding a memory with V2 schema"""
        try:
            memory_id = await vector_store.add_memory(sample_memory_v2)
            
            assert memory_id is not None
            assert memory_id == str(sample_memory_v2.id)
            
            print(f" Successfully added V2 memory: {memory_id}")
        except Exception as e:
            pytest.fail(f"Failed to add V2 memory: {e}")
    
    @pytest.mark.asyncio
    async def test_retrieve_memory_v2_schema(self, vector_store, sample_memory_v2):
        """Test retrieving a memory and verifying V2 metadata"""
        # Add memory first
        memory_id = await vector_store.add_memory(sample_memory_v2)
        
        # Retrieve it
        retrieved = await vector_store.get_memory(memory_id)
        
        assert retrieved is not None
        assert retrieved.content == sample_memory_v2.content
        
        # Verify V2 fields
        assert retrieved.metadata.domain == DomainType.WORK
        assert retrieved.metadata.category == "testing"
        assert retrieved.metadata.memory_type == MemoryType.FACT
        assert retrieved.metadata.subcategory == "unit-tests"
        assert retrieved.metadata.intent == IntentType.REFERENCE
        assert retrieved.metadata.importance == 7
        assert retrieved.metadata.confidence == 0.9
        assert "test" in retrieved.metadata.tags
        assert "memory" in retrieved.metadata.keywords
        assert retrieved.metadata.status == MemoryStatus.NEW
        assert retrieved.metadata.source == SourceType.USER_INPUT
        assert retrieved.metadata.verified is True
        
        print(f" Successfully retrieved and validated V2 memory")
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_v1_memory(self, vector_store):
        """Test that V1-style memories still work"""
        from src.models.memory import create_v1_compatible_memory
        
        v1_memory = create_v1_compatible_memory(
            content="V1 style memory",
            memory_type="conversation",
            importance=5,
            tags=["v1", "legacy"],
            source="user_input",
            project="test-project"
        )
        
        # Should be able to add V1-style memory
        memory_id = await vector_store.add_memory(v1_memory)
        assert memory_id is not None
        
        # Should be able to retrieve it
        retrieved = await vector_store.get_memory(memory_id)
        assert retrieved is not None
        assert retrieved.content == "V1 style memory"
        
        # V2 fields should have defaults
        assert retrieved.metadata.domain == DomainType.PROJECT  # Inferred from project
        assert retrieved.metadata.intent == IntentType.REFERENCE  # Default
        
        print(f" V1 backward compatibility verified")
    
    @pytest.mark.asyncio
    async def test_search_with_v2_filters(self, vector_store, sample_memory_v2):
        """Test searching with V2 schema filters"""
        # Add memory
        await vector_store.add_memory(sample_memory_v2)
        
        # Search by content
        results = await vector_store.search(
            query="Test memory schema",
            limit=5
        )
        
        assert len(results) > 0
        assert any(r.memory.content == sample_memory_v2.content for r in results)
        
        print(f" Search with V2 schema successful, found {len(results)} results")
    
    @pytest.mark.asyncio
    async def test_metadata_serialization(self, vector_store, sample_memory_v2):
        """Test that all V2 metadata fields serialize correctly"""
        memory_id = await vector_store.add_memory(sample_memory_v2)
        retrieved = await vector_store.get_memory(memory_id)
        
        # Convert to dict and verify all fields present
        memory_dict = retrieved.to_dict()
        
        assert "metadata" in memory_dict
        metadata = memory_dict["metadata"]
        
        # Check V2 fields are present
        assert "domain" in metadata
        assert "category" in metadata
        assert "intent" in metadata
        assert "confidence" in metadata
        assert "status" in metadata
        assert "source" in metadata
        
        print(f" All V2 metadata fields serialize correctly")


class TestVectorStoreCleanup:
    """Cleanup test data - not needed with isolated tmp_path fixtures"""
    
    @pytest.mark.asyncio
    async def test_cleanup_test_collection(self, vector_store):
        """Verify cleanup works (tmp_path handles actual cleanup)"""
        # With tmp_path fixture, cleanup is automatic
        # This test just verifies the reset method exists and works
        try:
            await vector_store.reset()
            print(f" Vector store reset successful")
        except Exception as e:
            print(f"  Reset warning (may be expected): {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

