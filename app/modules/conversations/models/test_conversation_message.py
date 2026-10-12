"""Tests for ConversationMessage model."""

import pytest
from bson import ObjectId

from app.modules.conversations.models.conversation_message import ConversationMessage


class TestConversationMessageModel:
    """Tests for ConversationMessage model fields and defaults."""
    
    @pytest.fixture
    def base_message_data(self):
        """Base data for creating a conversation message."""
        return {
            "conversation_id": ObjectId(),
            "assistant_id": ObjectId(),
            "interlocutor_id": ObjectId(),
            "role": "user",
            "content": "Hello, this is a test message",
        }
    
    def test_text_message_default_type(self, base_message_data):
        """Test that message_type defaults to 'text'."""
        message = ConversationMessage(**base_message_data)
        
        assert message.message_type == "text"
    
    def test_text_message_default_duration(self, base_message_data):
        """Test that audio_duration_seconds defaults to None."""
        message = ConversationMessage(**base_message_data)
        
        assert message.audio_duration_seconds is None
    
    def test_voice_message_explicit_type(self, base_message_data):
        """Test creating a voice message with explicit type."""
        base_message_data["message_type"] = "voice"
        base_message_data["audio_duration_seconds"] = 15
        base_message_data["content"] = "This is transcribed voice message"
        
        message = ConversationMessage(**base_message_data)
        
        assert message.message_type == "voice"
        assert message.audio_duration_seconds == 15
    
    def test_audio_message_explicit_type(self, base_message_data):
        """Test creating an audio file message with explicit type."""
        base_message_data["message_type"] = "audio"
        base_message_data["audio_duration_seconds"] = 180
        base_message_data["content"] = "This is transcribed audio file"
        
        message = ConversationMessage(**base_message_data)
        
        assert message.message_type == "audio"
        assert message.audio_duration_seconds == 180
    
    def test_backward_compatibility_without_new_fields(self, base_message_data):
        """Test that existing messages without new fields work (backward compatibility)."""
        # Simulate loading old message without message_type and audio_duration_seconds
        message = ConversationMessage(**base_message_data)
        
        # Should have defaults
        assert message.message_type == "text"
        assert message.audio_duration_seconds is None
        assert message.content == "Hello, this is a test message"
    
    def test_message_type_validation_invalid(self, base_message_data):
        """Test that invalid message_type raises validation error."""
        base_message_data["message_type"] = "invalid_type"
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConversationMessage(**base_message_data)
    
    def test_message_type_validation_text(self, base_message_data):
        """Test that 'text' is a valid message_type."""
        base_message_data["message_type"] = "text"
        
        message = ConversationMessage(**base_message_data)
        assert message.message_type == "text"
    
    def test_message_type_validation_voice(self, base_message_data):
        """Test that 'voice' is a valid message_type."""
        base_message_data["message_type"] = "voice"
        
        message = ConversationMessage(**base_message_data)
        assert message.message_type == "voice"
    
    def test_message_type_validation_audio(self, base_message_data):
        """Test that 'audio' is a valid message_type."""
        base_message_data["message_type"] = "audio"
        
        message = ConversationMessage(**base_message_data)
        assert message.message_type == "audio"
    
    def test_audio_duration_can_be_zero(self, base_message_data):
        """Test that audio_duration_seconds can be 0 (edge case)."""
        base_message_data["message_type"] = "voice"
        base_message_data["audio_duration_seconds"] = 0
        
        message = ConversationMessage(**base_message_data)
        
        assert message.audio_duration_seconds == 0
    
    def test_audio_duration_large_value(self, base_message_data):
        """Test that audio_duration_seconds accepts large values."""
        base_message_data["message_type"] = "audio"
        base_message_data["audio_duration_seconds"] = 7200  # 2 hours
        
        message = ConversationMessage(**base_message_data)
        
        assert message.audio_duration_seconds == 7200
    
    def test_assistant_role_with_text(self, base_message_data):
        """Test assistant message defaults to text type."""
        base_message_data["role"] = "assistant"
        
        message = ConversationMessage(**base_message_data)
        
        assert message.role == "assistant"
        assert message.message_type == "text"
    
    def test_model_serialization(self, base_message_data):
        """Test model serialization includes new fields."""
        base_message_data["message_type"] = "voice"
        base_message_data["audio_duration_seconds"] = 30
        
        message = ConversationMessage(**base_message_data)
        data = message.model_dump()
        
        assert "message_type" in data
        assert data["message_type"] == "voice"
        assert "audio_duration_seconds" in data
        assert data["audio_duration_seconds"] == 30
    
    def test_model_serialization_text_message(self, base_message_data):
        """Test text message serialization has correct defaults."""
        message = ConversationMessage(**base_message_data)
        data = message.model_dump()
        
        assert data["message_type"] == "text"
        assert data["audio_duration_seconds"] is None
