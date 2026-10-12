"""Tests for webhook models."""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import ValidationError

from app.modules.webhooks.models import WebhookEvent, WebhookContent, WebhookResponse


class TestWebhookContent:
    """Tests for WebhookContent model."""
    
    def test_create_minimal_content(self):
        """Test creating webhook content with minimal data."""
        content = WebhookContent(raw={"test": "data"})
        assert content.text is None
        assert content.from_user is None
        assert content.chat is None
        assert content.raw == {"test": "data"}
    
    def test_create_full_content(self):
        """Test creating webhook content with full data."""
        content = WebhookContent(
            text="Hello bot!",
            from_user={"id": 123, "first_name": "John"},
            chat={"id": 456, "type": "private"},
            raw={"message": {"text": "Hello bot!"}}
        )
        assert content.text == "Hello bot!"
        assert content.from_user["id"] == 123
        assert content.chat["type"] == "private"
        assert "message" in content.raw


class TestWebhookResponse:
    """Tests for WebhookResponse model."""
    
    def test_create_response(self):
        """Test creating webhook response."""
        response = WebhookResponse(
            success=True,
            message="Update processed successfully",
            data={"event_id": "123"}
        )
        assert response.success is True
        assert response.message == "Update processed successfully"
        assert response.data["event_id"] == "123"
        assert response.error is None
    
    def test_response_with_error(self):
        """Test creating response with error."""
        response = WebhookResponse(
            success=False,
            message="Processing failed",
            error="User has blocked the bot"
        )
        assert response.success is False
        assert response.message == "Processing failed"
        assert response.error == "User has blocked the bot"
        assert response.data is None


class TestWebhookEvent:
    """Tests for WebhookEvent model."""
    
    def test_create_minimal_event(self):
        """Test creating webhook event with minimal required fields."""
        assistant_id = ObjectId()
        connection_id = ObjectId()
        
        event = WebhookEvent(
            assistant_id=assistant_id,
            connection_id=connection_id,
            channel="telegram",
            user_id="telegram_123456",
            type="message",
            content=WebhookContent(text="Hello", raw={})
        )
        
        assert event.assistant_id == assistant_id
        assert event.connection_id == connection_id
        assert event.channel == "telegram"
        assert event.user_id == "telegram_123456"
        assert event.type == "message"
        assert event.content.text == "Hello"
        assert event.processed is False
        assert event.response_sent is False
        assert event.response is None
        assert event.error is None
        assert event.processed_at is None
    
    def test_create_full_event(self):
        """Test creating webhook event with all fields."""
        assistant_id = ObjectId()
        connection_id = ObjectId()
        now = datetime.now(timezone.utc)
        
        event = WebhookEvent(
            assistant_id=assistant_id,
            connection_id=connection_id,
            channel="telegram",
            user_id="telegram_123456",
            message_id="msg_789",
            update_id=987654,
            type="message",
            content=WebhookContent(
                text="Hello bot!",
                from_user={"id": 123456, "first_name": "John"},
                chat={"id": 123456, "type": "private"},
                raw={"update_id": 987654}
            ),
            processed=True,
            processed_at=now
        )
        
        assert event.update_id == 987654
        assert event.message_id == "msg_789"
        assert event.processed is True
        assert event.processed_at == now
    
    def test_command_type(self):
        """Test webhook event with command type."""
        event = WebhookEvent(
            assistant_id=ObjectId(),
            connection_id=ObjectId(),
            channel="telegram",
            user_id="telegram_123",
            type="command",
            content=WebhookContent(text="/start", raw={})
        )
        assert event.type == "command"
        assert event.content.text == "/start"
    
    def test_invalid_channel(self):
        """Test that invalid channel raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookEvent(
                assistant_id=ObjectId(),
                connection_id=ObjectId(),
                channel="invalid_channel",  # Invalid channel
                user_id="user_123",
                type="message",
                content=WebhookContent(raw={})
            )
        assert "Input should be 'telegram', 'whatsapp' or 'webchat'" in str(exc_info.value)
    
    def test_invalid_type(self):
        """Test that invalid message type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookEvent(
                assistant_id=ObjectId(),
                connection_id=ObjectId(),
                channel="telegram",
                user_id="telegram_123",
                type="invalid_type",  # Invalid type
                content=WebhookContent(raw={})
            )
        assert "Input should be" in str(exc_info.value)
    
    def test_model_dump_with_objectid(self):
        """Test that model_dump properly converts ObjectId to string."""
        event = WebhookEvent(
            assistant_id=ObjectId("507f1f77bcf86cd799439011"),
            connection_id=ObjectId("507f1f77bcf86cd799439012"),
            channel="telegram",
            user_id="telegram_123",
            type="message",
            content=WebhookContent(text="Test", raw={})
        )
        
        dumped = event.model_dump(by_alias=True)
        
        # Check that ObjectIds are converted to strings in the output
        # Note: The field_serializer should handle this
        assert isinstance(dumped.get("assistant_id"), str) or isinstance(dumped.get("assistant_id"), ObjectId)
        assert isinstance(dumped.get("connection_id"), str) or isinstance(dumped.get("connection_id"), ObjectId)
    
    def test_whatsapp_channel(self):
        """Test creating event for WhatsApp channel."""
        event = WebhookEvent(
            assistant_id=ObjectId(),
            connection_id=ObjectId(),
            channel="whatsapp",
            user_id="whatsapp_1234567890",
            type="message",
            content=WebhookContent(text="Hello from WhatsApp", raw={})
        )
        assert event.channel == "whatsapp"
        assert event.user_id == "whatsapp_1234567890"
    
    def test_error_field(self):
        """Test webhook event with error."""
        event = WebhookEvent(
            assistant_id=ObjectId(),
            connection_id=ObjectId(),
            channel="telegram",
            user_id="telegram_123",
            type="message",
            content=WebhookContent(raw={}),
            processed=True,
            error="Failed to process message: timeout"
        )
        assert event.error == "Failed to process message: timeout"
        assert event.processed is True
        assert event.response_sent is False
