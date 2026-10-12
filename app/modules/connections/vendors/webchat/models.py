"""WebChat message model for storing chat history for UI."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import Field

from app.common.models.base import MongoBaseModel, PyObjectId


class WebchatMessage(MongoBaseModel):
    """
    Message for webchat UI display.
    
    Separate from conversation_history which is for analytics.
    This collection allows users to delete/edit their messages
    without affecting the analytics data.
    """
    
    conversation_id: PyObjectId = Field(..., description="Reference to conversation")
    assistant_id: PyObjectId = Field(..., description="Reference to assistant")
    user_id: str = Field(..., description="User ID from frontend (auth0 or anonymous)")
    
    role: Literal["user", "assistant"] = Field(..., description="Message sender role")
    content: str = Field(..., description="Message content")
    
    is_deleted: bool = Field(False, description="Soft delete flag for user")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439012",
                "conversation_id": "507f1f77bcf86cd799439011",
                "assistant_id": "507f1f77bcf86cd799439010",
                "user_id": "auth0|123456789",
                "role": "user",
                "content": "Hello!",
                "is_deleted": False,
                "created_at": "2024-12-29T10:00:00Z",
                "updated_at": "2024-12-29T10:00:00Z"
            }
        }

