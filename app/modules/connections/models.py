"""Connection models for managing assistant channel integrations."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from app.common.models.base import MongoBaseModel, PyObjectId
from app.modules.connections.security.crypto import decrypt_token
from app.config import config

if TYPE_CHECKING:
    from app.modules.connections.repository import ConnectionRepository

logger = logging.getLogger(__name__)


class ConnectionChannel(str, Enum):
    """Supported communication channels."""
    TELEGRAM = "telegram"
    WEBCHAT = "webchat"
    WHATSAPP = "whatsapp"  # Future


class ConnectionStatus(str, Enum):
    """Connection health status."""
    PENDING = "pending"        # Created but not verified
    CONNECTED = "connected"    # Active and working
    ERROR = "error"           # Failed connection
    DEGRADED = "degraded"     # Working with issues


class ConnectionSettings(BaseModel):
    """Settings specific to each channel type.
    
    This model supports multiple channel types:
    - Telegram: bot_token (required), bot_username, bot_id, webhook_url, etc.
    - WebChat: enabled, allow_anonymous
    - WhatsApp: phone_number_id, access_token, etc. (future)
    """
    
    # === Telegram-specific fields ===
    # Encrypted bot token (required for Telegram, optional for other channels)
    bot_token: Optional[str] = Field(None, description="Encrypted bot token (Telegram)")
    
    # Bot info from Telegram API
    bot_username: Optional[str] = Field(None, description="Bot username (e.g. @mybot)")
    bot_id: Optional[int] = Field(None, description="Telegram bot ID")
    bot_first_name: Optional[str] = Field(None, description="Bot display name")
    
    # Webhook configuration (Telegram)
    webhook_url: Optional[str] = Field(None, description="Registered webhook URL")
    webhook_secret: Optional[str] = Field(None, description="Webhook verification secret")
    
    # Additional metadata from provider
    bot_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Full bot info from API")
    
    # === WebChat-specific fields ===
    enabled: Optional[bool] = Field(None, description="Whether webchat is enabled")
    allow_anonymous: Optional[bool] = Field(False, description="Allow anonymous users (post-MVP)")


class Connection(MongoBaseModel):
    """Connection model - links assistant to communication channel."""
    
    assistant_id: PyObjectId = Field(..., description="Reference to assistant")
    channel: ConnectionChannel = Field(..., description="Communication channel type")
    status: ConnectionStatus = Field(ConnectionStatus.PENDING, description="Current connection status")
    
    # Channel-specific settings (encrypted tokens, webhook URLs, etc)
    settings: ConnectionSettings = Field(..., description="Channel-specific configuration")
    
    # Health monitoring
    last_error: Optional[str] = Field(None, description="Last error message if any")
    last_checked_at: Optional[datetime] = Field(None, description="Last health check timestamp")
    
    @field_validator('channel')
    @classmethod
    def validate_channel(cls, v):
        """Ensure channel is supported."""
        if v not in ConnectionChannel:
            raise ValueError(f"Unsupported channel: {v}")
        return v
    
    @field_validator('assistant_id')
    @classmethod
    def validate_assistant_id(cls, v):
        """Ensure assistant_id is valid ObjectId."""
        if not v:
            raise ValueError("Assistant ID is required")
        return v
    
    def get_decrypted_token(self) -> str:
        """
        Get decrypted bot token.
        
        Returns:
            Decrypted bot token string
            
        Raises:
            ValueError: If decryption fails
        """
        try:
            return decrypt_token(
                self.settings.bot_token,
                config.ENCRYPTION_KEY
            )
        except Exception as e:
            logger.error(f"Failed to decrypt token for connection {self.id}: {e}")
            raise ValueError(f"Failed to decrypt token: {e}")
    
    async def set_degraded(
        self,
        reason: str,
        repository: Optional['ConnectionRepository'] = None
    ) -> None:
        """
        Set connection status to DEGRADED.
        
        Args:
            reason: Reason for degradation
            repository: Optional repository instance for updating DB
        """
        self.status = ConnectionStatus.DEGRADED
        self.last_error = reason
        self.last_checked_at = datetime.now(timezone.utc)
        
        logger.warning(
            f"Connection {self.id} set to DEGRADED: {reason}"
        )
        
        if repository:
            await repository.update_status(
                str(self.id),
                ConnectionStatus.DEGRADED,
                reason
            )
    
    async def set_error_status(
        self,
        reason: str,
        repository: Optional['ConnectionRepository'] = None
    ) -> None:
        """
        Set connection status to ERROR.
        
        Args:
            reason: Error reason
            repository: Optional repository instance for updating DB
        """
        self.status = ConnectionStatus.ERROR
        self.last_error = reason
        self.last_checked_at = datetime.now(timezone.utc)
        
        logger.error(
            f"Connection {self.id} set to ERROR: {reason}"
        )
        
        if repository:
            await repository.update_status(
                str(self.id),
                ConnectionStatus.ERROR,
                reason
            )
    
    async def set_connected(
        self,
        repository: Optional['ConnectionRepository'] = None
    ) -> None:
        """
        Set connection status to CONNECTED.
        
        Args:
            repository: Optional repository instance for updating DB
        """
        self.status = ConnectionStatus.CONNECTED
        self.last_error = None
        self.last_checked_at = datetime.now(timezone.utc)
        
        logger.info(f"Connection {self.id} set to CONNECTED")
        
        if repository:
            await repository.update_status(
                str(self.id),
                ConnectionStatus.CONNECTED,
                None
            )
