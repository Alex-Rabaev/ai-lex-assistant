"""Schemas (DTOs) for WebChat channel."""

from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field

from app.modules.connections.models import ConnectionStatus


# === Connection management schemas ===

class EnableWebchatRequest(BaseModel):
    """Request to enable webchat for an assistant."""
    # No fields required for MVP - just enable the channel
    pass


class UpdateWebchatSettingsRequest(BaseModel):
    """Request to update webchat settings."""
    allow_anonymous: Optional[bool] = Field(None, description="Allow anonymous users (post-MVP)")


class WebchatConnectionResponse(BaseModel):
    """Response for webchat connection status."""
    id: str = Field(..., description="Connection ID")
    assistant_id: str = Field(..., description="Assistant ID")
    status: ConnectionStatus = Field(..., description="Connection status")
    enabled: bool = Field(..., description="Whether webchat is enabled")
    allow_anonymous: bool = Field(False, description="Whether anonymous users are allowed")
    chat_url: str = Field(..., description="URL for accessing the webchat")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "assistant_id": "507f1f77bcf86cd799439010",
                "status": "connected",
                "enabled": True,
                "allow_anonymous": False,
                "chat_url": "https://chat.ai-lex.dev/507f1f77bcf86cd799439010",
                "created_at": "2024-12-29T10:00:00Z",
                "updated_at": "2024-12-29T10:00:00Z"
            }
        }
    
    @classmethod
    def from_connection(cls, connection, chat_base_url: str = "https://chat.ai-lex.dev") -> "WebchatConnectionResponse":
        """Create response from Connection model."""
        settings = connection.settings
        return cls(
            id=str(connection.id),
            assistant_id=str(connection.assistant_id),
            status=connection.status,
            enabled=connection.status == ConnectionStatus.CONNECTED,
            allow_anonymous=settings.allow_anonymous if settings and settings.allow_anonymous else False,
            chat_url=f"{chat_base_url}/{connection.assistant_id}",
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )


# === Message request schemas ===

class SendMessageRequest(BaseModel):
    """Request to send a message via webchat."""
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")


class UpdateMessageRequest(BaseModel):
    """Request to update a message."""
    content: str = Field(..., min_length=1, max_length=10000, description="New message content")


# === Response schemas ===

class WebchatMessageResponse(BaseModel):
    """Response for a single webchat message."""
    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    assistant_id: str = Field(..., description="Assistant ID")
    user_id: str = Field(..., description="User ID")
    role: Literal["user", "assistant"] = Field(..., description="Message sender role")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439012",
                "conversation_id": "507f1f77bcf86cd799439011",
                "assistant_id": "507f1f77bcf86cd799439010",
                "user_id": "auth0|123456789",
                "role": "user",
                "content": "Hello!",
                "created_at": "2024-12-29T10:00:00Z",
                "updated_at": "2024-12-29T10:00:00Z"
            }
        }


class MessageListResponse(BaseModel):
    """Response for message list."""
    messages: List[WebchatMessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {
                        "id": "507f1f77bcf86cd799439012",
                        "conversation_id": "507f1f77bcf86cd799439011",
                        "assistant_id": "507f1f77bcf86cd799439010",
                        "user_id": "auth0|123456789",
                        "role": "user",
                        "content": "Hello!",
                        "created_at": "2024-12-29T10:00:00Z",
                        "updated_at": "2024-12-29T10:00:00Z"
                    }
                ],
                "total": 1
            }
        }


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    message_id: str = Field(..., description="Created message ID")
    status: str = Field("queued", description="Message status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "507f1f77bcf86cd799439012",
                "status": "queued"
            }
        }


class AssistantInfoResponse(BaseModel):
    """Response with assistant info for webchat."""
    id: str = Field(..., description="Assistant ID")
    name: str = Field(..., description="Assistant name")
    description: Optional[str] = Field(None, description="Assistant description")
    webchat_enabled: bool = Field(..., description="Whether webchat is enabled for this assistant")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439010",
                "name": "Survey Assistant",
                "description": "Helpful survey assistant",
                "webchat_enabled": True
            }
        }


# === WebSocket message schemas ===

class WebSocketMessage(BaseModel):
    """Base WebSocket message format."""
    type: str = Field(..., description="Message type (chat_message, typing, notification)")
    assistant_id: Optional[str] = Field(None, description="Assistant ID")
    user_id: Optional[str] = Field(None, description="User ID")
    payload: dict = Field(..., description="Message payload")


class ChatMessagePayload(BaseModel):
    """Payload for chat_message type."""
    message_id: str = Field(..., description="Message ID")
    role: Literal["user", "assistant"] = Field(..., description="Sender role")
    content: str = Field(..., description="Message content")


class TypingPayload(BaseModel):
    """Payload for typing indicator."""
    is_typing: bool = Field(..., description="Whether assistant is typing")


# === Session claiming schemas ===

class ClaimSessionRequest(BaseModel):
    """Request to claim anonymous session after login."""
    anonymous_user_id: str = Field(
        ..., 
        description="Anonymous user ID to claim (format: anon_{uuid})",
        pattern="^anon_.+"
    )
    assistant_id: str = Field(..., description="Assistant ID for the session")
    
    class Config:
        json_schema_extra = {
            "example": {
                "anonymous_user_id": "anon_550e8400-e29b-41d4-a716-446655440000",
                "assistant_id": "507f1f77bcf86cd799439010"
            }
        }


class ClaimSessionResponse(BaseModel):
    """Response after claiming anonymous session."""
    success: bool = Field(..., description="Whether claim was successful")
    messages_transferred: int = Field(..., description="Number of messages transferred")
    interlocutor_updated: bool = Field(..., description="Whether interlocutor was updated")
    anonymous_user_id: str = Field(..., description="Original anonymous ID")
    authenticated_user_id: str = Field(..., description="Authenticated user ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "messages_transferred": 5,
                "interlocutor_updated": True,
                "anonymous_user_id": "anon_550e8400-e29b-41d4-a716-446655440000",
                "authenticated_user_id": "user@example.com"
            }
        }
