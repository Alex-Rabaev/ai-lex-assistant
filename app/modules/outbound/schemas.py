"""Pydantic schemas for outbound message processing."""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class OutgoingMessage(BaseModel):
    """
    Message received from outbound_messages queue (from conversations module).
    
    This represents a response that needs to be sent to a user
    via a communication channel (Telegram, WhatsApp, etc.).
    
    Message types:
    - message: Regular text message to send
    - callback_query: Response to inline button press
    - typing_indicator: Show "typing..." status in chat (no response_text needed)
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trace_id": "abc123def456",
                "assistant_id": "691ccd8225eee2a50317434a",
                "connection_id": "691ccd8325eee2a50317434b",
                "user_id": "telegram_284639219",
                "type": "message",
                "response_text": "This is the bot response",
                "original_message_id": "123",
                "parse_mode": "HTML"
            }
        }
    )
    
    # Tracing
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking through pipeline")
    
    assistant_id: str = Field(..., description="Assistant ID")
    connection_id: str = Field(..., description="Connection ID for the channel")
    user_id: str = Field(..., description="User ID in format 'channel_id' (e.g., 'telegram_123456')")
    type: Literal["message", "callback_query", "typing_indicator"] = Field(..., description="Message type")
    response_text: Optional[str] = Field(None, description="Response text to send to user (not required for typing_indicator)")
    
    # Optional fields
    conversation_id: Optional[str] = Field(None, description="Conversation ID (for webchat)")
    original_message_id: Optional[str] = Field(None, description="Original message ID")
    parse_mode: Optional[str] = Field("HTML", description="Parse mode (HTML or Markdown)")
    callback_data: Optional[str] = Field(None, description="Callback data (for type='callback_query')")
    callback_id: Optional[str] = Field(None, description="Callback query ID (for type='callback_query')")


class SendResult(BaseModel):
    """
    Result of message send operation.
    
    Contains information about whether the message was sent successfully,
    the message ID if successful, and error details if failed.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message_id": "456",
                "error": None,
                "retry_count": 0
            }
        }
    )
    
    success: bool = Field(..., description="Whether message was sent successfully")
    message_id: Optional[str] = Field(None, description="Sent message ID (if successful)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    retry_count: int = Field(default=0, description="Number of retry attempts made")

