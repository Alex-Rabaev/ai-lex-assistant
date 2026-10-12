"""Models for follow-ups (v4 append-only log)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.common.models.base import MongoBaseModel, PyObjectId


class FollowUpReasonCode(str, Enum):
    """v4 reason codes returned when a follow-up cannot be sent."""

    conversation_not_found = "conversation_not_found"
    interlocutor_not_found = "interlocutor_not_found"
    connection_not_found = "connection_not_found"
    opted_out = "opted_out"
    blocked = "blocked"
    whatsapp_24h_passed = "whatsapp_24h_passed"
    max_attempts_reached = "max_attempts_reached"
    no_delivery_channel = "no_delivery_channel"
    agent_declined = "agent_declined"
    llm_error = "llm_error"


@dataclass
class SendReminderResult:
    """Internal result of manual / automatic reminder send."""

    sent: bool
    reason: Optional[str] = None


class SendReminderResponse(BaseModel):
    """API response for POST /conversations/{id}/send-reminder."""

    sent: bool = Field(..., description="True if the reminder was successfully published to outbound")
    conversation_id: str = Field(..., description="Conversation ID the reminder was requested for")
    reason: Optional[FollowUpReasonCode] = Field(
        None,
        description="Reason code when sent=false; absent when sent=true",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"sent": True, "conversation_id": "507f1f77bcf86cd799439012"},
                {"sent": False, "conversation_id": "507f1f77bcf86cd799439012", "reason": "max_attempts_reached"},
            ]
        }
    )


class FollowUpLogEntry(MongoBaseModel):
    """
    One successful reminder delivery (append-only).

    A new document is inserted only after outbound delivery succeeds.
    """

    conversation_id: PyObjectId = Field(..., description="Conversation this reminder belongs to")
    assistant_id: PyObjectId = Field(..., description="Assistant that owns the conversation")
    interlocutor_id: PyObjectId = Field(..., description="Recipient interlocutor")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "conversation_id": "507f1f77bcf86cd799439012",
                "assistant_id": "507f1f77bcf86cd799439013",
                "interlocutor_id": "507f1f77bcf86cd799439014",
                "created_at": "2025-11-25T10:00:00Z",
            }
        }
    )
