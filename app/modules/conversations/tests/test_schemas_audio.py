"""Tests for audio metadata in conversation schemas."""

import pytest
from datetime import datetime

from app.modules.conversations.schemas import (
    IncomingMessage,
    MessageItem,
)


class TestIncomingMessageAudio:
    """Tests for audio fields in IncomingMessage."""
    
    def test_default_message_type_is_text(self):
        """Test that message_type defaults to 'text'."""
        msg = IncomingMessage(
            assistant_id="test_assistant",
            connection_id="test_connection",
            user_id="telegram_123",
            type="message",
            text="Hello"
        )
        
        assert msg.message_type == "text"
        assert msg.audio_duration_seconds is None
        assert msg.audio_language is None
    
    def test_voice_message_with_metadata(self):
        """Test creating a voice message with audio metadata."""
        msg = IncomingMessage(
            assistant_id="test_assistant",
            connection_id="test_connection",
            user_id="telegram_123",
            type="message",
            text="Transcribed voice content",
            message_type="voice",
            audio_duration_seconds=15,
            audio_language="en"
        )
        
        assert msg.message_type == "voice"
        assert msg.audio_duration_seconds == 15
        assert msg.audio_language == "en"
    
    def test_audio_file_message(self):
        """Test creating an audio file message."""
        msg = IncomingMessage(
            assistant_id="test_assistant",
            connection_id="test_connection",
            user_id="telegram_123",
            type="message",
            text="Transcribed audio file",
            message_type="audio",
            audio_duration_seconds=180
        )
        
        assert msg.message_type == "audio"
        assert msg.audio_duration_seconds == 180
    
    def test_message_type_validation(self):
        """Test that only valid message_type values are accepted."""
        # Valid values
        for msg_type in ["text", "voice", "audio"]:
            msg = IncomingMessage(
                assistant_id="test",
                connection_id="test",
                user_id="test",
                type="message",
                message_type=msg_type
            )
            assert msg.message_type == msg_type
        
        # Invalid value
        with pytest.raises(Exception):  # Pydantic ValidationError
            IncomingMessage(
                assistant_id="test",
                connection_id="test",
                user_id="test",
                type="message",
                message_type="invalid"
            )
    
    def test_backward_compatibility_without_audio_fields(self):
        """Test that messages without audio fields work (backward compatibility)."""
        # Simulate old message format
        msg = IncomingMessage(
            assistant_id="test",
            connection_id="test",
            user_id="test",
            type="message",
            text="Old format message"
        )
        
        assert msg.message_type == "text"
        assert msg.audio_duration_seconds is None


class TestMessageItemAudio:
    """Tests for audio fields in MessageItem (admin API response)."""
    
    def test_text_message_defaults(self):
        """Test text message has correct defaults."""
        item = MessageItem(
            id="msg_123",
            role="user",
            content="Hello",
            created_at=datetime.now()
        )
        
        assert item.message_type == "text"
        assert item.audio_duration_seconds is None
    
    def test_voice_message_item(self):
        """Test voice message item with audio metadata."""
        item = MessageItem(
            id="msg_456",
            role="user",
            content="This is a voice message transcript",
            created_at=datetime.now(),
            message_type="voice",
            audio_duration_seconds=30
        )
        
        assert item.message_type == "voice"
        assert item.audio_duration_seconds == 30
        assert item.content == "This is a voice message transcript"
    
    def test_audio_file_message_item(self):
        """Test audio file message item."""
        item = MessageItem(
            id="msg_789",
            role="user",
            content="Audio file transcript",
            created_at=datetime.now(),
            message_type="audio",
            audio_duration_seconds=240
        )
        
        assert item.message_type == "audio"
        assert item.audio_duration_seconds == 240
    
    def test_serialization_includes_audio_fields(self):
        """Test that serialization includes audio metadata."""
        item = MessageItem(
            id="msg_123",
            role="user",
            content="Voice transcript",
            created_at=datetime.now(),
            message_type="voice",
            audio_duration_seconds=15
        )
        
        data = item.model_dump()
        
        assert "message_type" in data
        assert data["message_type"] == "voice"
        assert "audio_duration_seconds" in data
        assert data["audio_duration_seconds"] == 15
    
    def test_legacy_message_defaults(self):
        """Test that legacy messages (from DB without audio fields) get defaults."""
        # Simulate creating from DB document without audio fields
        item = MessageItem(
            id="old_msg",
            role="user",
            content="Old message",
            created_at=datetime.now()
            # No message_type or audio_duration_seconds
        )
        
        assert item.message_type == "text"
        assert item.audio_duration_seconds is None
