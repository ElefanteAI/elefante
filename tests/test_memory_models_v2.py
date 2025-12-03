"""
Test suite for Memory V2.0 schema models
Tests validation, enums, and backward compatibility
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.models.memory import (
    Memory,
    MemoryMetadata,
    DomainType,
    MemoryType,
    IntentType,
    MemoryStatus,
    RelationshipType,
    SourceType,
    create_v1_compatible_memory,
    SOURCE_RELIABILITY_SCORES,
)


class TestEnums:
    """Test all enum types"""
    
    def test_domain_type_values(self):
        """Test DomainType enum has expected values"""
        assert DomainType.WORK.value == "work"
        assert DomainType.PERSONAL.value == "personal"
        assert DomainType.LEARNING.value == "learning"
        assert DomainType.PROJECT.value == "project"
        assert DomainType.REFERENCE.value == "reference"
        assert DomainType.SYSTEM.value == "system"
    
    def test_memory_type_expanded(self):
        """Test MemoryType has new types"""
        assert MemoryType.QUESTION.value == "question"
        assert MemoryType.ANSWER.value == "answer"
        assert MemoryType.HYPOTHESIS.value == "hypothesis"
        assert MemoryType.OBSERVATION.value == "observation"
    
    def test_intent_type_values(self):
        """Test IntentType enum"""
        assert IntentType.REFERENCE.value == "reference"
        assert IntentType.REMINDER.value == "reminder"
        assert IntentType.LEARNING.value == "learning"
        assert IntentType.DECISION_LOG.value == "decision_log"
    
    def test_relationship_type_values(self):
        """Test RelationshipType enum"""
        assert RelationshipType.EXTENDS.value == "extends"
        assert RelationshipType.CONTRADICTS.value == "contradicts"
        assert RelationshipType.SUPERSEDES.value == "supersedes"
    
    def test_source_type_values(self):
        """Test SourceType enum"""
        assert SourceType.USER_INPUT.value == "user_input"
        assert SourceType.AGENT_GENERATED.value == "agent_generated"
        assert SourceType.DOCUMENT.value == "document"


class TestMemoryMetadata:
    """Test MemoryMetadata model"""
    
    def test_default_values(self):
        """Test metadata defaults"""
        metadata = MemoryMetadata()
        
        assert metadata.domain == DomainType.REFERENCE
        assert metadata.category == "general"
        assert metadata.memory_type == MemoryType.CONVERSATION
        assert metadata.intent == IntentType.REFERENCE
        assert metadata.importance == 5
        assert metadata.urgency == 5
        assert metadata.confidence == 0.7
        assert metadata.status == MemoryStatus.NEW
        assert metadata.source == SourceType.USER_INPUT
        assert metadata.verified is False
        assert metadata.version == 1
        assert metadata.deprecated is False
    
    def test_source_reliability_auto_set(self):
        """Test source reliability is auto-set based on source type"""
        metadata = MemoryMetadata(source=SourceType.USER_INPUT)
        assert metadata.source_reliability == SOURCE_RELIABILITY_SCORES[SourceType.USER_INPUT]
        
        metadata = MemoryMetadata(source=SourceType.WEB_SCRAPE)
        assert metadata.source_reliability == SOURCE_RELIABILITY_SCORES[SourceType.WEB_SCRAPE]
    
    def test_validation_importance(self):
        """Test importance validation (1-10)"""
        with pytest.raises(ValueError):
            MemoryMetadata(importance=0)
        
        with pytest.raises(ValueError):
            MemoryMetadata(importance=11)
        
        # Valid values
        MemoryMetadata(importance=1)
        MemoryMetadata(importance=10)
    
    def test_validation_confidence(self):
        """Test confidence validation (0.0-1.0)"""
        with pytest.raises(ValueError):
            MemoryMetadata(confidence=-0.1)
        
        with pytest.raises(ValueError):
            MemoryMetadata(confidence=1.1)
        
        # Valid values
        MemoryMetadata(confidence=0.0)
        MemoryMetadata(confidence=1.0)
    
    def test_3_level_taxonomy(self):
        """Test 3-level taxonomy structure"""
        metadata = MemoryMetadata(
            domain=DomainType.WORK,
            category="ai-projects",
            memory_type=MemoryType.DECISION,
            subcategory="chromadb-schema"
        )
        
        assert metadata.domain == DomainType.WORK
        assert metadata.category == "ai-projects"
        assert metadata.memory_type == MemoryType.DECISION
        assert metadata.subcategory == "chromadb-schema"


class TestMemory:
    """Test Memory model"""
    
    def test_create_basic_memory(self):
        """Test creating a basic memory"""
        memory = Memory(content="Test memory content")
        
        assert memory.id is not None
        assert memory.content == "Test memory content"
        assert memory.metadata is not None
        assert memory.embedding is None
        assert memory.related_entities == []
    
    def test_content_validation(self):
        """Test content length validation"""
        # Too short
        with pytest.raises(ValueError):
            Memory(content="")
        
        # Too long (>10000 chars)
        with pytest.raises(ValueError):
            Memory(content="x" * 10001)
        
        # Valid
        Memory(content="Valid content")
        Memory(content="x" * 10000)
    
    def test_calculate_relevance_score(self):
        """Test temporal relevance score calculation"""
        memory = Memory(
            content="Test",
            metadata=MemoryMetadata(importance=8, access_count=5)
        )
        
        score = memory.calculate_relevance_score()
        
        assert isinstance(score, float)
        assert score > 0
        assert score <= 1.0
    
    def test_record_access(self):
        """Test access recording"""
        memory = Memory(content="Test")
        
        initial_count = memory.metadata.access_count
        initial_time = memory.metadata.last_accessed
        
        memory.record_access()
        
        assert memory.metadata.access_count == initial_count + 1
        assert memory.metadata.last_accessed >= initial_time
    
    def test_to_dict(self):
        """Test memory serialization"""
        memory = Memory(
            content="Test",
            metadata=MemoryMetadata(
                domain=DomainType.WORK,
                memory_type=MemoryType.FACT
            )
        )
        
        data = memory.to_dict()
        
        assert isinstance(data, dict)
        assert "id" in data
        assert "content" in data
        assert "metadata" in data
        assert data["content"] == "Test"
    
    def test_from_dict(self):
        """Test memory deserialization"""
        data = {
            "id": str(uuid4()),
            "content": "Test content",
            "metadata": {
                "domain": "work",
                "category": "test",
                "memory_type": "fact",
                "importance": 7
            }
        }
        
        memory = Memory.from_dict(data)
        
        assert memory.content == "Test content"
        assert memory.metadata.domain == DomainType.WORK
        assert memory.metadata.memory_type == MemoryType.FACT
        assert memory.metadata.importance == 7


class TestBackwardCompatibility:
    """Test V1 to V2 compatibility"""
    
    def test_create_v1_compatible_memory(self):
        """Test creating V2 memory from V1 parameters"""
        memory = create_v1_compatible_memory(
            content="Test content",
            memory_type="fact",
            importance=8,
            tags=["work", "important"],
            source="user",
            project="elefante"
        )
        
        assert memory.content == "Test content"
        assert memory.metadata.memory_type == MemoryType.FACT
        assert memory.metadata.importance == 8
        assert memory.metadata.tags == ["work", "important"]
        assert memory.metadata.source == SourceType.USER_INPUT
        assert memory.metadata.project == "elefante"
        
        # V2 fields should have defaults
        assert memory.metadata.domain == DomainType.PROJECT  # Inferred from project
        assert memory.metadata.category == "work"  # Inferred from first tag
        assert memory.metadata.intent == IntentType.REFERENCE
    
    def test_v1_source_mapping(self):
        """Test V1 source strings map to V2 SourceType"""
        memory_user = create_v1_compatible_memory(content="Test", source="user")
        assert memory_user.metadata.source == SourceType.USER_INPUT
        
        memory_agent = create_v1_compatible_memory(content="Test", source="agent")
        assert memory_agent.metadata.source == SourceType.AGENT_GENERATED
        
        memory_system = create_v1_compatible_memory(content="Test", source="system")
        assert memory_system.metadata.source == SourceType.SYSTEM_INFERRED
    
    def test_v1_domain_inference(self):
        """Test domain inference from V1 parameters"""
        # Project -> PROJECT domain
        memory = create_v1_compatible_memory(content="Test", project="my-project")
        assert memory.metadata.domain == DomainType.PROJECT
        
        # Work tags -> WORK domain
        memory = create_v1_compatible_memory(content="Test", tags=["work"])
        assert memory.metadata.domain == DomainType.WORK
        
        # Learning tags -> LEARNING domain
        memory = create_v1_compatible_memory(content="Test", tags=["learning"])
        assert memory.metadata.domain == DomainType.LEARNING
        
        # Default -> REFERENCE domain
        memory = create_v1_compatible_memory(content="Test")
        assert memory.metadata.domain == DomainType.REFERENCE


class TestRelationships:
    """Test relationship tracking"""
    
    def test_relationship_fields(self):
        """Test relationship tracking fields"""
        parent_id = uuid4()
        related_id = uuid4()
        conflict_id = uuid4()
        
        metadata = MemoryMetadata(
            parent_id=parent_id,
            related_memory_ids=[related_id],
            conflict_ids=[conflict_id],
            relationship_type=RelationshipType.EXTENDS
        )
        
        assert metadata.parent_id == parent_id
        assert related_id in metadata.related_memory_ids
        assert conflict_id in metadata.conflict_ids
        assert metadata.relationship_type == RelationshipType.EXTENDS
    
    def test_supersedes_relationship(self):
        """Test supersedes/superseded_by tracking"""
        old_id = uuid4()
        new_id = uuid4()
        
        old_memory = Memory(
            content="Old version",
            metadata=MemoryMetadata(superseded_by_id=new_id)
        )
        
        new_memory = Memory(
            content="New version",
            metadata=MemoryMetadata(supersedes_id=old_id)
        )
        
        assert old_memory.metadata.superseded_by_id == new_id
        assert new_memory.metadata.supersedes_id == old_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
