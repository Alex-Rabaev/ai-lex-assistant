"""Models for conversation history."""

from datetime import datetime
from typing import Optional, Literal, Dict, Any
from pydantic import Field

from app.common.models.base import MongoBaseModel, PyObjectId


class ConversationMessage(MongoBaseModel):
    """Message in conversation history.
    
    Supports both text and audio messages. Audio messages (voice/audio)
    store the transcribed text in `content` with metadata in dedicated fields.
    """
    
    conversation_id: PyObjectId = Field(..., description="Reference to conversation")
    assistant_id: PyObjectId = Field(..., description="Reference to assistant")
    interlocutor_id: PyObjectId = Field(..., description="Reference to interlocutor")
    role: Literal["user", "assistant", "system"] = Field(..., description="Message sender role (system for tool results)")
    content: str = Field(..., description="Message text (or transcribed audio text)")
    state: Optional[str] = Field(None, description="Step key when message was sent (e.g., 'intro', 'profile')")
    
    # Audio message metadata (optional for backward compatibility)
    message_type: Literal["text", "voice", "audio"] = Field(
        default="text",
        description="Message type: 'text' for regular messages, 'voice' for voice recordings, 'audio' for audio files"
    )
    audio_duration_seconds: Optional[int] = Field(
        default=None,
        description="Duration of audio message in seconds (null for text messages)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata (e.g. follow_up, follow_up_attempt for reminder messages)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "conversation_id": "507f1f77bcf86cd799439012",
                "assistant_id": "507f1f77bcf86cd799439013",
                "interlocutor_id": "507f1f77bcf86cd799439014",
                "role": "user",
                "content": "I'm CEO of TechCorp",
                "state": "profile",
                "message_type": "text",
                "audio_duration_seconds": None,
                "created_at": "2025-11-25T10:00:00Z"
            }
        }
    }

