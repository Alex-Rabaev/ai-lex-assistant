"""Request and Response schemas for Connections API."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re

from app.modules.connections.models import ConnectionChannel, ConnectionStatus


# ============================================================================
# CONNECTION SCHEMAS
# ============================================================================

class CreateTelegramConnectionRequest(BaseModel):
    """Request schema for creating a Telegram connection."""
    
    bot_token: str = Field(
        ..., 
        min_length=45,
        max_length=60,
        description="Telegram bot token from @BotFather"
    )
    
    @field_validator('bot_token')
    @classmethod
    def validate_bot_token(cls, v):
        """Validate Telegram bot token format."""
        # Telegram bot token format: <bot_id>:<secret>
        # Example: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890
        # Bot ID is 8-12 digits, secret is exactly 35 alphanumeric characters with - and _
        pattern = r'^\d{8,12}:[A-Za-z0-9_-]{35,}$'
        
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid bot token format. Expected format: <bot_id>:<secret> "
                "Example: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
            )
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
            }
        }
    }


class ConnectionResponse(BaseModel):
    """Response schema for connection data."""
    
    id: str = Field(..., description="Connection ID")
    assistant_id: str = Field(..., description="Assistant ID")
    channel: ConnectionChannel = Field(..., description="Channel type")
    status: ConnectionStatus = Field(..., description="Connection status")
    
    # Public bot info (not sensitive)
    bot_username: Optional[str] = Field(None, description="Bot username")
    bot_first_name: Optional[str] = Field(None, description="Bot display name")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    
    # Health info
    last_error: Optional[str] = Field(None, description="Last error if any")
    last_checked_at: Optional[datetime] = Field(None, description="Last health check")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "assistant_id": "507f1f77bcf86cd799439012",
                "channel": "telegram",
                "status": "connected",
                "bot_username": "@my_survey_bot",
                "bot_first_name": "Survey Bot",
                "webhook_url": "https://platform.marguru.com/webhook/telegram/507f1f77bcf86cd799439012",
                "last_error": None,
                "last_checked_at": "2025-11-11T10:00:00Z",
                "created_at": "2025-11-11T09:00:00Z",
                "updated_at": "2025-11-11T10:00:00Z"
            }
        }
    }
    
    @classmethod
    def from_model(cls, connection) -> "ConnectionResponse":
        """Convert Connection model to response DTO."""
        return cls(
            id=str(connection.id),
            assistant_id=str(connection.assistant_id),
            channel=connection.channel,
            status=connection.status,
            bot_username=connection.settings.bot_username if connection.settings else None,
            bot_first_name=connection.settings.bot_first_name if connection.settings else None,
            webhook_url=connection.settings.webhook_url if connection.settings else None,
            last_error=connection.last_error,
            last_checked_at=connection.last_checked_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )


class ConnectionListResponse(BaseModel):
    """Response schema for list of connections with pagination."""
    
    items: List[ConnectionResponse] = Field(..., description="List of connections")
    total: int = Field(..., description="Total count")
    skip: int = Field(0, description="Items skipped")
    limit: int = Field(20, description="Items per page")
    assistant_id: str = Field(..., description="Assistant ID these connections belong to")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": "507f1f77bcf86cd799439011",
                        "assistant_id": "507f1f77bcf86cd799439012",
                        "channel": "telegram",
                        "status": "connected",
                        "bot_username": "@my_survey_bot",
                        "bot_first_name": "Survey Bot",
                        "created_at": "2025-11-11T09:00:00Z",
                        "updated_at": "2025-11-11T10:00:00Z"
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 20,
                "assistant_id": "507f1f77bcf86cd799439012"
            }
        }
    }


# ============================================================================
# UTILITY SCHEMAS
# ============================================================================

class ConnectionHealthCheckResponse(BaseModel):
    """Response for health check operation."""
    
    id: str = Field(..., description="Connection ID")
    status: ConnectionStatus = Field(..., description="Current status")
    is_healthy: bool = Field(..., description="Whether connection is healthy")
    checked_at: datetime = Field(..., description="Check timestamp")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "status": "connected",
                "is_healthy": True,
                "checked_at": "2025-11-11T10:30:00Z",
                "error": None
            }
        }
    }


class BotInfo(BaseModel):
    """Telegram bot information from getMe API."""
    
    id: int = Field(..., description="Bot ID")
    is_bot: bool = Field(True, description="Always true for bots")
    first_name: str = Field(..., description="Bot display name")
    username: str = Field(..., description="Bot username without @")
    can_join_groups: Optional[bool] = Field(None, description="Can be added to groups")
    can_read_all_group_messages: Optional[bool] = Field(None, description="Can read all messages in groups")
    supports_inline_queries: Optional[bool] = Field(None, description="Supports inline mode")


class ConnectionHealthCheckResponse(BaseModel):
    """Response for connection health check."""
    
    id: str = Field(..., description="Connection ID")
    status: ConnectionStatus = Field(..., description="Current connection status")
    is_healthy: bool = Field(..., description="Whether connection is healthy")
    last_error: Optional[str] = Field(None, description="Last error message if any")
    checked_at: Optional[datetime] = Field(None, description="When health check was performed")


class CreateWhatsAppConnectionRequest(BaseModel):
    """Request schema for creating a WhatsApp connection."""
    
    phone_number_id: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="WhatsApp Phone Number ID from Meta Developer Portal"
    )
    access_token: str = Field(
        ...,
        min_length=50,
        description="Meta Graph API access token"
    )
    app_secret: str = Field(
        ...,
        min_length=20,
        description="App Secret for webhook signature verification"
    )
    verify_token: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Custom token for webhook verification challenge"
    )
    
    @field_validator('phone_number_id')
    @classmethod
    def validate_phone_number_id(cls, v):
        """Validate phone number ID is numeric."""
        if not v.isdigit():
            raise ValueError("Phone Number ID must contain only digits")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone_number_id": "123456789012345",
                "access_token": "EAABs...",
                "app_secret": "abc123def456...",
                "verify_token": "my_verify_token_123"
            }
        }
    }
