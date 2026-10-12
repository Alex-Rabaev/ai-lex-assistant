"""Pydantic schemas for conversations module."""

from typing import Optional, Literal, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# MESSAGE PROCESSING SCHEMAS
# ============================================================================

class IncomingMessage(BaseModel):
    """
    Message received from incoming_messages queue (from webhooks).
    
    This represents a user message that needs to be processed
    and responded to. Supports both text and audio (voice) messages.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trace_id": "abc123def456",
                "assistant_id": "691ccd8225eee2a50317434a",
                "connection_id": "691ccd8325eee2a50317434b",
                "user_id": "telegram_284639219",
                "type": "message",
                "text": "Hello bot",
                "message_id": "123",
                "message_type": "text",
                "audio_duration_seconds": None
            }
        }
    )
    
    # Tracing
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking through pipeline")
    
    assistant_id: str = Field(..., description="Assistant ID handling this message")
    connection_id: str = Field(..., description="Connection ID for the channel")
    user_id: str = Field(..., description="User ID in format 'channel_id'")
    type: Literal["message", "callback_query"] = Field(..., description="Message type")
    
    # Optional fields depending on message type
    text: Optional[str] = Field(None, description="Message text (for type='message')")
    message_id: Optional[str] = Field(None, description="Original message ID")
    callback_data: Optional[str] = Field(None, description="Callback data (for type='callback_query')")
    callback_id: Optional[str] = Field(None, description="Callback query ID")
    
    # Audio message metadata (from voice/audio transcription)
    message_type: Literal["text", "voice", "audio"] = Field(
        default="text",
        description="Content type: 'text' for regular, 'voice' for voice recordings, 'audio' for audio files"
    )
    audio_duration_seconds: Optional[int] = Field(
        default=None,
        description="Duration of audio message in seconds (null for text messages)"
    )
    audio_language: Optional[str] = Field(
        default=None,
        description="Detected language of audio message (from Whisper)"
    )


class OutgoingMessage(BaseModel):
    """
    Message to be sent to outbound_messages queue (to outbound module).
    
    This represents a response that needs to be delivered to the user
    via the appropriate communication channel.
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
                "original_message_id": "123"
            }
        }
    )
    
    # Tracing
    trace_id: Optional[str] = Field(None, description="Trace ID for request tracking through pipeline")
    
    assistant_id: str = Field(..., description="Assistant ID")
    connection_id: str = Field(..., description="Connection ID")
    user_id: str = Field(..., description="User ID in format 'channel_id'")
    type: Literal["message", "callback_query"] = Field(..., description="Message type")
    response_text: str = Field(..., description="Response text to send to user")
    
    # Optional fields
    original_message_id: Optional[str] = Field(None, description="Original message ID")
    parse_mode: Optional[str] = Field("HTML", description="Parse mode (HTML or Markdown)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class ProcessingResult(BaseModel):
    """Result of message processing."""
    
    success: bool = Field(..., description="Whether processing was successful")
    response_generated: bool = Field(False, description="Whether response was generated")
    error: Optional[str] = Field(None, description="Error message if failed")


class AgentResponse(BaseModel):
    """
    Response from agent after processing message.
    
    Agent returns only response_text (or None if no response needed).
    Agent updates conversation.state internally.
    """
    
    response_text: Optional[str] = Field(
        None,
        description="Response text to send to user (None if no response needed)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "response_text": "Thank you for your answer!"
            }
        }
    )


# ============================================================================
# INTERLOCUTOR ADMIN SCHEMAS
# ============================================================================

class InterlocutorListQuery(BaseModel):
    """Query parameters for listing interlocutors."""
    
    q: Optional[str] = Field(None, description="Search in first_name, username, email")
    stage: Optional[List[str]] = Field(None, description="Filter by stages (lang, intro, profile, goals, closing, completed)")
    language: Optional[List[str]] = Field(None, description="Filter by language")
    has_email: Optional[bool] = Field(None, description="Filter by email presence")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    sort: str = Field("-created_at", description="Sort field (prefix '-' for DESC)")
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum items to return")


class InterlocutorListItem(BaseModel):
    """Interlocutor item in list response."""
    
    id: str = Field(..., description="Interlocutor ID")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (use for export filters)")
    user_id: str = Field(..., description="Channel user ID (e.g., telegram_123)")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    username: Optional[str] = Field(None, description="Username (e.g., @johndoe)")
    language: Optional[str] = Field(None, description="Preferred language")
    email: Optional[str] = Field(None, description="Email from profile")
    stage: Optional[str] = Field(None, description="Current conversation stage")
    created_at: datetime = Field(..., description="When interlocutor was created")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")


class InterlocutorListResponse(BaseModel):
    """Paginated list of interlocutors."""
    
    items: List[InterlocutorListItem] = Field(..., description="List of interlocutors")
    total: int = Field(..., description="Total count")
    skip: int = Field(0, description="Items skipped")
    limit: int = Field(20, description="Items per page")
    assistant_id: str = Field(..., description="Assistant ID")


class ConversationInfo(BaseModel):
    """Conversation info for interlocutor detail."""
    
    id: str = Field(..., description="Conversation ID")
    state: Optional[str] = Field(None, description="Current stage")
    agent_metadata: Dict[str, Any] = Field(default_factory=dict, description="Full agent metadata")
    created_at: datetime = Field(..., description="Conversation start")
    updated_at: datetime = Field(..., description="Last update")


class MessageStats(BaseModel):
    """Message statistics for interlocutor."""
    
    total_messages: int = Field(0, description="Total message count")
    first_message_at: Optional[datetime] = Field(None, description="First message timestamp")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")


class InterlocutorDetail(BaseModel):
    """Detailed interlocutor information."""
    
    id: str = Field(..., description="Interlocutor ID")
    user_id: str = Field(..., description="Channel user ID")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    username: Optional[str] = Field(None, description="Username")
    language: Optional[str] = Field(None, description="Preferred language")
    profile: Dict[str, Any] = Field(default_factory=dict, description="Profile data")
    conversation: Optional[ConversationInfo] = Field(None, description="Conversation info")
    stats: MessageStats = Field(..., description="Message statistics")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")


class InterlocutorUpdate(BaseModel):
    """Request to update interlocutor data."""
    
    first_name: Optional[str] = Field(None, max_length=100, description="Updated first name")
    last_name: Optional[str] = Field(None, max_length=100, description="Updated last name")
    language: Optional[str] = Field(None, max_length=50, description="Updated language")
    profile: Optional[Dict[str, Any]] = Field(None, description="Profile data to merge")


# ============================================================================
# MESSAGE ADMIN SCHEMAS
# ============================================================================

class MessageListQuery(BaseModel):
    """Query parameters for listing messages."""
    
    state: Optional[List[str]] = Field(None, description="Filter by stages")
    role: Optional[List[str]] = Field(None, description="Filter by role (user, assistant, system)")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    sort: str = Field("created_at", description="Sort field (prefix '-' for DESC)")
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(50, ge=1, le=200, description="Maximum items to return")


class MessageItem(BaseModel):
    """Message item in list response.
    
    For voice messages, content contains the transcript.
    Frontend can display 🎤 indicator based on message_type.
    """
    
    id: str = Field(..., description="Message ID")
    role: Literal["user", "assistant", "system"] = Field(..., description="Message sender role")
    content: str = Field(..., description="Message text (or transcript for voice messages)")
    state: Optional[str] = Field(None, description="Stage when message was sent")
    created_at: datetime = Field(..., description="Message timestamp")
    
    # Audio metadata (for voice/audio messages)
    message_type: Literal["text", "voice", "audio"] = Field(
        default="text",
        description="Content type: 'text', 'voice' (voice recording), or 'audio' (audio file)"
    )
    audio_duration_seconds: Optional[int] = Field(
        default=None,
        description="Duration in seconds (null for text messages)"
    )


class MessageListResponse(BaseModel):
    """Paginated list of messages."""
    
    items: List[MessageItem] = Field(..., description="List of messages")
    total: int = Field(..., description="Total count")
    skip: int = Field(0, description="Items skipped")
    limit: int = Field(50, description="Items per page")
    conversation_id: str = Field(..., description="Conversation ID")
    interlocutor_id: str = Field(..., description="Interlocutor ID")
    assistant_id: str = Field(..., description="Assistant ID")
