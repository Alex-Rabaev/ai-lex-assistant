"""WebChat connection service - manages webchat channel configuration."""

import logging
from typing import Optional
from pymongo.errors import DuplicateKeyError

from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)
from app.modules.connections.exceptions import DuplicateConnectionError
from app.modules.assistants.service import AssistantService, AssistantNotFoundError

logger = logging.getLogger(__name__)


class WebchatConnectionService:
    """Service for managing WebChat connection configuration.
    
    WebChat is simpler than Telegram - no external API validation needed,
    just enable/disable the channel for an assistant.
    """
    
    def __init__(self):
        """Initialize service with repository."""
        self._repository = ConnectionRepository()
        self._assistant_service = AssistantService()
    
    async def _verify_assistant_access(self, assistant_id: str, user_id: str) -> None:
        """
        Verify user has access to assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        try:
            await self._assistant_service.get_assistant(assistant_id, user_id)
        except AssistantNotFoundError:
            raise AssistantNotFoundError(
                f"Assistant {assistant_id} not found or you don't have access"
            )
    
    async def enable_webchat(
        self,
        assistant_id: str,
        user_id: str
    ) -> Connection:
        """
        Enable webchat for an assistant.
        
        Creates a new webchat connection if it doesn't exist,
        or updates existing one to CONNECTED status.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            
        Returns:
            Created or updated Connection
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        logger.info(f"Enabling webchat for assistant {assistant_id} by user {user_id}")
        
        await self._verify_assistant_access(assistant_id, user_id)
        
        # Check if webchat connection already exists
        existing = await self._repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
        
        if existing:
            # Update existing connection to CONNECTED
            if existing.status != ConnectionStatus.CONNECTED:
                connection = await self._repository.update_status(
                    str(existing.id),
                    ConnectionStatus.CONNECTED
                )
                logger.info(f"Re-enabled existing webchat connection {existing.id}")
                return connection
            return existing
        
        # Create new connection with CONNECTED status
        settings = ConnectionSettings(
            enabled=True,
            allow_anonymous=False  # post-MVP
        )
        
        try:
            connection = await self._repository.create(
                assistant_id,
                ConnectionChannel.WEBCHAT,
                settings,
                status=ConnectionStatus.CONNECTED  # Create with correct status immediately
            )
            
            logger.info(f"Created and enabled webchat connection {connection.id}")
            return connection
            
        except DuplicateKeyError:
            # Race condition - try to get existing
            existing = await self._repository.get_by_assistant_and_channel(
                assistant_id,
                ConnectionChannel.WEBCHAT
            )
            if existing:
                return existing
            raise DuplicateConnectionError(
                f"Assistant {assistant_id} already has a WebChat connection"
            )
    
    async def disable_webchat(
        self,
        assistant_id: str,
        user_id: str
    ) -> bool:
        """
        Disable webchat for an assistant.
        
        Sets the connection status to PENDING (disabled but not deleted).
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            
        Returns:
            True if disabled, False if not found
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        logger.info(f"Disabling webchat for assistant {assistant_id} by user {user_id}")
        
        await self._verify_assistant_access(assistant_id, user_id)
        
        # Get existing connection
        connection = await self._repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
        
        if not connection:
            logger.warning(f"No webchat connection found for assistant {assistant_id}")
            return False
        
        # Set status to PENDING (disabled)
        await self._repository.update_status(
            str(connection.id),
            ConnectionStatus.PENDING,
            "Webchat disabled by user"
        )
        
        logger.info(f"Disabled webchat connection {connection.id}")
        return True
    
    async def get_connection(
        self,
        assistant_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Connection]:
        """
        Get webchat connection for an assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: Optional user ID for access control (None for internal use)
            
        Returns:
            Connection if found, None otherwise
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access (when user_id provided)
        """
        if user_id:
            await self._verify_assistant_access(assistant_id, user_id)
        
        return await self._repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
    
    async def is_webchat_enabled(self, assistant_id: str) -> bool:
        """
        Check if webchat is enabled for an assistant.
        
        For internal use (no access control).
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            True if webchat is enabled and connected
        """
        connection = await self._repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
        
        if not connection:
            return False
        
        return connection.status == ConnectionStatus.CONNECTED
    
    async def update_settings(
        self,
        assistant_id: str,
        user_id: str,
        allow_anonymous: Optional[bool] = None
    ) -> Optional[Connection]:
        """
        Update webchat connection settings.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            allow_anonymous: Whether to allow anonymous users
            
        Returns:
            Updated connection or None if not found
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        await self._verify_assistant_access(assistant_id, user_id)
        
        # Get existing connection
        connection = await self._repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
        
        if not connection:
            logger.warning(f"No webchat connection found for assistant {assistant_id}")
            return None
        
        # Prepare update data
        settings = connection.settings
        if settings is None:
            settings = ConnectionSettings(enabled=True)
        
        if allow_anonymous is not None:
            settings.allow_anonymous = allow_anonymous
        
        # Update
        updated = await self._repository.update(
            str(connection.id),
            {"settings": settings}
        )
        
        if updated:
            logger.info(f"Updated webchat settings for assistant {assistant_id}")
        
        return updated
