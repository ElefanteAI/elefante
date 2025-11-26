"""
Unit tests for conversation models

Tests the Message and SearchCandidate data structures.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.models.conversation import Message, SearchCandidate


class TestMessage:
    """Test Message model"""
    
    def test_create_message_with_required_fields(self):
        """Test creating a message with only required fields"""
        session_id = uuid4()
        message = Message(
            session_id=session_id,
            role="user",
            content="Hello, world!"
        )
        
        assert message.session_id == session_id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert isinstance(message.id, type(uuid4()))
        assert isinstance(message.timestamp, datetime)
        assert message.metadata == {}
    
    def test_create_message_with_all_fields(self):
        """Test creating a message with all fields"""
        session_id = uuid4()
        message_id = uuid4()
        timestamp = datetime.utcnow()
        metadata = {"key": "value"}
        
        message = Message(
            id=message_id,
            session_id=session_id,
            role="assistant",
            content="Test content",
            timestamp=timestamp,
            metadata=metadata
        )
        
        assert message.id == message_id
        assert message.timestamp == timestamp
        assert message.metadata == metadata
    
    def test_message_role_validation(self):
        """Test that invalid roles are rejected"""
        session_id = uuid4()
        
        # Valid roles should work
        for role in ["user", "assistant", "system"]:
            message = Message(
                session_id=session_id,
                role=role,
                content="Test"
            )
            assert message.role == role
        
        # Invalid role should fail
        with pytest.raises(Exception):  # Pydantic validation error
            Message(
                session_id=session_id,
                role="invalid_role",
                content="Test"
            )
    
    def test_message_to_dict(self):
        """Test converting message to dictionary"""
        session_id = uuid4()
        message = Message(
            session_id=session_id,
            role="user",
            content="Test content"
        )
        
        data = message.to_dict()
        
        assert isinstance(data, dict)
        assert "id" in data
        assert "session_id" in data
        assert "role" in data
        assert "content" in data
        assert "timestamp" in data
        assert data["content"] == "Test content"
    
    def test_message_from_dict(self):
        """Test creating message from dictionary"""
        session_id = uuid4()
        message_id = uuid4()
        
        data = {
            "id": str(message_id),
            "session_id": str(session_id),
            "role": "user",
            "content": "Test",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {}
        }
        
        message = Message.from_dict(data)
        
        assert message.id == message_id
        assert message.session_id == session_id
        assert message.role == "user"
        assert message.content == "Test"


class TestSearchCandidate:
    """Test SearchCandidate model"""
    
    def test_create_candidate_with_required_fields(self):
        """Test creating a candidate with only required fields"""
        candidate = SearchCandidate(
            text="Test content",
            score=0.85,
            source="conversation"
        )
        
        assert candidate.text == "Test content"
        assert candidate.score == 0.85
        assert candidate.source == "conversation"
        assert candidate.metadata == {}
        assert candidate.embedding is None
        assert candidate.memory_id is None
    
    def test_create_candidate_with_all_fields(self):
        """Test creating a candidate with all fields"""
        memory_id = uuid4()
        embedding = [0.1, 0.2, 0.3]
        metadata = {"key": "value"}
        
        candidate = SearchCandidate(
            text="Test",
            score=0.9,
            source="semantic",
            metadata=metadata,
            embedding=embedding,
            memory_id=memory_id
        )
        
        assert candidate.embedding == embedding
        assert candidate.memory_id == memory_id
        assert candidate.metadata == metadata
    
    def test_candidate_score_validation(self):
        """Test that scores are validated to be between 0 and 1"""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            candidate = SearchCandidate(
                text="Test",
                score=score,
                source="conversation"
            )
            assert candidate.score == score
        
        # Invalid scores should fail
        with pytest.raises(Exception):  # Pydantic validation error
            SearchCandidate(
                text="Test",
                score=1.5,  # Too high
                source="conversation"
            )
        
        with pytest.raises(Exception):
            SearchCandidate(
                text="Test",
                score=-0.1,  # Too low
                source="conversation"
            )
    
    def test_candidate_source_validation(self):
        """Test that source is validated"""
        # Valid sources
        for source in ["conversation", "semantic", "graph"]:
            candidate = SearchCandidate(
                text="Test",
                score=0.5,
                source=source
            )
            assert candidate.source == source
        
        # Invalid source should fail
        with pytest.raises(Exception):
            SearchCandidate(
                text="Test",
                score=0.5,
                source="invalid_source"
            )
    
    def test_candidate_to_dict(self):
        """Test converting candidate to dictionary"""
        memory_id = uuid4()
        candidate = SearchCandidate(
            text="Test",
            score=0.75,
            source="semantic",
            memory_id=memory_id
        )
        
        data = candidate.to_dict()
        
        assert isinstance(data, dict)
        assert data["text"] == "Test"
        assert data["score"] == 0.75
        assert data["source"] == "semantic"
        assert data["memory_id"] == str(memory_id)
        assert "has_embedding" in data
    
    def test_candidate_from_dict(self):
        """Test creating candidate from dictionary"""
        memory_id = uuid4()
        
        data = {
            "text": "Test content",
            "score": 0.8,
            "source": "graph",
            "metadata": {"key": "value"},
            "memory_id": str(memory_id)
        }
        
        candidate = SearchCandidate.from_dict(data)
        
        assert candidate.text == "Test content"
        assert candidate.score == 0.8
        assert candidate.source == "graph"
        assert candidate.memory_id == memory_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
