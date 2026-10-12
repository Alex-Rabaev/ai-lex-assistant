"""Interlocutor model - represents a user communicating with assistants."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import Field

from app.common.models.base import MongoBaseModel


class Interlocutor(MongoBaseModel):
    """
    Interlocutor - собеседник, пользователь, общающийся с ассистентами.
    
    Один user_id = один interlocutor (уникальный по каналу).
    Например: telegram_123 и whatsapp_123 - это разные interlocutors.
    """
    
    user_id: str = Field(
        ...,
        description="Unique user ID in format 'channel_chatid' (e.g., telegram_284639219)"
    )
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    username: Optional[str] = Field(None, description="Username (e.g., @johndoe)")
    language: Optional[str] = Field(None, description="User's preferred language (e.g., 'English', 'Русский')")
    profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional profile data (email, business info, etc.)"
    )
    is_mock: bool = Field(
        default=False,
        description="True if this interlocutor was created for mock respondents (test data)."
    )
    opted_out: bool = Field(
        default=False,
        description="True if user unsubscribed from follow-up reminders (e.g. via email link)"
    )
    blocked: bool = Field(
        default=False,
        description="True if user blocked the bot (e.g. Telegram 403)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "telegram_284639219",
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "language": "English",
                "profile": {
                    "email": "john@example.com",
                    "profile_summary": "John, hairdresser with salon in London, works alone"
                },
                "created_at": "2025-11-25T10:00:00Z",
                "updated_at": "2025-11-25T10:00:00Z"
            }
        }
    }
    

