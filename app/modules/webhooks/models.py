"""Models for webhooks module."""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import Field

from app.common.models.base import MongoBaseModel, PyObjectId


class WebhookContent(MongoBaseModel):
    """Content of the webhook message."""
    
    text: Optional[str] = Field(None, description="Text content of the message")
    from_user: Optional[Dict[str, Any]] = Field(None, description="Information about sender")
    chat: Optional[Dict[str, Any]] = Field(None, description="Information about chat/conversation")
    command: Optional[str] = Field(None, description="Command name (for command type messages)")
    args: Optional[str] = Field(None, description="Command arguments (for command type messages)")
    callback_data: Optional[str] = Field(None, description="Callback data (for callback_query type)")
    callback_id: Optional[str] = Field(None, description="Callback query ID (for callback_query type)")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Full raw update from channel")


class WebhookResponse(MongoBaseModel):
    """Response from webhook processing (not the message sent to user)."""
    
    success: bool = Field(..., description="Whether webhook processing was successful")
    message: str = Field(..., description="Status message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data (event_id, etc.)")
    error: Optional[str] = Field(None, description="Error message if processing failed")


class WebhookEvent(MongoBaseModel):
    """
    Webhook event received from a channel (Telegram, WhatsApp, etc).
    Vendor-agnostic model that stores all incoming webhook data.
    """
    
    # References
    assistant_id: PyObjectId = Field(..., description="Reference to assistant")
    connection_id: PyObjectId = Field(..., description="Reference to connection")
    
    # Channel information
    channel: Literal["telegram", "whatsapp", "webchat"] = Field(..., description="Channel type")
    user_id: str = Field(..., description="User ID in channel format (e.g., telegram_123456)")
    message_id: Optional[str] = Field(None, description="Message ID in the channel")
    update_id: Optional[int] = Field(None, description="Telegram update_id for deduplication")
    
    # Message type and content
    type: Literal["message", "callback_query", "edited_message", "command"] = Field(
        ..., 
        description="Type of webhook event"
    )
    content: WebhookContent = Field(..., description="Extracted message content")
    
    # Processing status
    processed: bool = Field(False, description="Whether event has been processed")
    response_sent: bool = Field(False, description="Whether response has been sent")
    response: Optional[WebhookResponse] = Field(None, description="Response sent to user")
    error: Optional[str] = Field(None, description="Error during processing if any")
    
    # Timestamps
    processed_at: Optional[datetime] = Field(None, description="When event was processed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "assistant_id": "507f1f77bcf86cd799439012",
                "connection_id": "507f1f77bcf86cd799439013",
                "channel": "telegram",
                "user_id": "telegram_123456",
                "message_id": "msg_789",
                "update_id": 987654,
                "type": "message",
                "content": {
                    "text": "Hello bot!",
                    "from_user": {"id": 123456, "first_name": "John"},
                    "chat": {"id": 123456, "type": "private"},
                    "raw": {}
                },
                "processed": True,
                "response_sent": True,
                "response": {
                    "text": "Hello! How can I help you?",
                    "sent_at": "2025-11-16T10:00:00Z",
                    "message_id": "response_123"
                },
                "created_at": "2025-11-16T10:00:00Z",
                "processed_at": "2025-11-16T10:00:01Z"
            }
        }
    }
