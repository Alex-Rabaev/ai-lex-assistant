"""Service layer for managing assistant connections."""

import logging
from typing import List, Optional

from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.vendors.telegram.service import TelegramConnectionService
from app.modules.connections.vendors.whatsapp.service import WhatsAppConnectionService
from app.modules.connections.vendors.webchat.connection_service import WebchatConnectionService
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus
)
from app.modules.connections.exceptions import (
    ConnectionNotFoundError,
    InvalidBotTokenError,
    InvalidAccessTokenError
)

logger = logging.getLogger(__name__)


class ConnectionService:
    """Service for managing assistant connections business logic."""
    
    def __init__(self):
        """Initialize service with repository."""
        self._repository = ConnectionRepository()
        self._assistant_service = AssistantService()
        self._telegram_service = TelegramConnectionService()
        self._whatsapp_service = WhatsAppConnectionService()
        self._webchat_service = WebchatConnectionService()
    
    async def create_telegram_connection(
        self,
        assistant_id: str,
        user_id: str,
        bot_token: str
    ) -> Connection:
        """
        Create Telegram connection with full flow.
        
        Args:
            assistant_id: Assistant ID to connect
            user_id: User ID for access control
            bot_token: Telegram bot token from BotFather
            
        Returns:
            Created connection
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
            DuplicateConnectionError: If Telegram already connected
            InvalidBotTokenError: If token validation fails
        """
        logger.info(f"Creating Telegram connection for assistant {assistant_id} by user {user_id}")
        
        # Verify assistant exists and user has access
        try:
            await self._assistant_service.get_assistant(assistant_id, user_id)
        except AssistantNotFoundError:
            raise AssistantNotFoundError(
                f"Assistant {assistant_id} not found or you don't have access"
            )
        
        # Delegate to Telegram-specific service
        return await self._telegram_service.create_connection(assistant_id, bot_token)
    
    async def create_whatsapp_connection(
        self,
        assistant_id: str,
        user_id: str,
        phone_number_id: str,
        access_token: str,
        app_secret: str,
        verify_token: str
    ) -> Connection:
        """
        Create WhatsApp connection with full flow.
        
        Args:
            assistant_id: Assistant ID to connect
            user_id: User ID for access control
            phone_number_id: WhatsApp Phone Number ID
            access_token: Meta Graph API access token
            app_secret: App secret for webhook signature verification
            verify_token: Token for webhook verification challenge
            
        Returns:
            Created connection
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
            DuplicateConnectionError: If WhatsApp already connected
            InvalidAccessTokenError: If credentials validation fails
        """
        logger.info(f"Creating WhatsApp connection for assistant {assistant_id} by user {user_id}")
        
        # Verify assistant exists and user has access
        try:
            await self._assistant_service.get_assistant(assistant_id, user_id)
        except AssistantNotFoundError:
            raise AssistantNotFoundError(
                f"Assistant {assistant_id} not found or you don't have access"
            )
        
        # Delegate to WhatsApp-specific service
        return await self._whatsapp_service.create_connection(
            assistant_id,
            phone_number_id,
            access_token,
            app_secret,
            verify_token
        )
    
    # ==================== WebChat Methods ====================
    
    async def enable_webchat(
        self,
        assistant_id: str,
        user_id: str
    ) -> Connection:
        """
        Enable webchat for an assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            
        Returns:
            Created or updated Connection
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        return await self._webchat_service.enable_webchat(assistant_id, user_id)
    
    async def disable_webchat(
        self,
        assistant_id: str,
        user_id: str
    ) -> bool:
        """
        Disable webchat for an assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            
        Returns:
            True if disabled, False if not found
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        return await self._webchat_service.disable_webchat(assistant_id, user_id)
    
    async def get_webchat_connection(
        self,
        assistant_id: str,
        user_id: str
    ) -> Optional[Connection]:
        """
        Get webchat connection for an assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            
        Returns:
            Connection if found, None otherwise
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        return await self._webchat_service.get_connection(assistant_id, user_id)
    
    async def update_webchat_settings(
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
        return await self._webchat_service.update_settings(
            assistant_id, user_id, allow_anonymous
        )
    
    async def get_connection(
        self,
        connection_id: str,
        user_id: str
    ) -> Connection:
        """
        Get connection with access control.
        
        Args:
            connection_id: Connection ID
            user_id: User ID for access control
            
        Returns:
            Connection if found and user has access
            
        Raises:
            ConnectionNotFoundError: If not found or no access
        """
        # Get connection
        connection = await self._repository.get_by_id(connection_id)
        
        if not connection:
            raise ConnectionNotFoundError(f"Connection {connection_id} not found")
        
        # Verify user has access to the assistant
        try:
            await self._assistant_service.get_assistant(
                str(connection.assistant_id),
                user_id
            )
        except AssistantNotFoundError:
            raise ConnectionNotFoundError(
                f"Connection {connection_id} not found or you don't have access"
            )
        
        return connection
    
    async def list_connections(
        self,
        assistant_id: str,
        user_id: str,
        status: Optional[ConnectionStatus] = None
    ) -> List[Connection]:
        """
        List connections for an assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            status: Optional status filter
            
        Returns:
            List of connections
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        # Verify user has access to the assistant
        try:
            await self._assistant_service.get_assistant(assistant_id, user_id)
        except AssistantNotFoundError:
            raise AssistantNotFoundError(
                f"Assistant {assistant_id} not found or you don't have access"
            )
        
        # Get connections
        connections = await self._repository.find_by_assistant(
            assistant_id,
            status
        )
        
        return connections
    
    async def delete_connection(
        self,
        connection_id: str,
        user_id: str
    ) -> bool:
        """
        Delete connection and cleanup webhook.
        
        Args:
            connection_id: Connection ID
            user_id: User ID for access control
            
        Returns:
            True if deleted successfully
            
        Raises:
            ConnectionNotFoundError: If not found or no access
        """
        # Get connection with access check
        connection = await self.get_connection(connection_id, user_id)
        
        # If connected, try to delete webhook (channel-specific)
        if connection.status == ConnectionStatus.CONNECTED:
            if connection.channel == ConnectionChannel.TELEGRAM:
                await self._telegram_service.delete_webhook(connection)
        
        # Delete from database
        deleted = await self._repository.delete(connection_id)
        
        if deleted:
            logger.info(f"Deleted connection {connection_id}")
        
        return deleted
    
    async def check_connection_health(
        self,
        connection_id: str
    ) -> Connection:
        """
        Check and update connection health status.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Updated connection with current health status
            
        Raises:
            ConnectionNotFoundError: If connection not found
        """
        # Get connection (no user check - health check can be internal)
        connection = await self._repository.get_by_id(connection_id)
        
        if not connection:
            raise ConnectionNotFoundError(f"Connection {connection_id} not found")
        
        # Only check if status is not ERROR
        if connection.status == ConnectionStatus.ERROR:
            logger.info(f"Skipping health check for connection {connection_id} in ERROR status")
            return connection
        
        # Perform channel-specific health check
        try:
            is_healthy = True
            error_msg = None
            
            if connection.channel == ConnectionChannel.TELEGRAM:
                try:
                    is_healthy, error_msg = await self._telegram_service.check_health(connection)
                except InvalidBotTokenError as e:
                    # Invalid token is a critical ERROR, not DEGRADED
                    connection = await self._repository.update_status(
                        connection_id,
                        ConnectionStatus.ERROR,
                        f"Invalid bot token: {e}"
                    )
                    logger.error(f"Connection {connection_id} has invalid token: {e}")
                    return connection
            
            elif connection.channel == ConnectionChannel.WHATSAPP:
                try:
                    is_healthy, error_msg = await self._whatsapp_service.check_health(connection)
                except InvalidAccessTokenError as e:
                    connection = await self._repository.update_status(
                        connection_id,
                        ConnectionStatus.ERROR,
                        f"Invalid access token: {e}"
                    )
                    logger.error(f"Connection {connection_id} has invalid token: {e}")
                    return connection
            
            # Update status based on health
            if is_healthy:
                connection = await self._repository.update_status(
                    connection_id,
                    ConnectionStatus.CONNECTED
                )
                logger.info(f"Connection {connection_id} is healthy")
            else:
                connection = await self._repository.update_status(
                    connection_id,
                    ConnectionStatus.DEGRADED,
                    error_msg
                )
                logger.warning(f"Connection {connection_id} is degraded: {error_msg}")
                
        except Exception as e:
            # Unexpected error - mark as degraded
            connection = await self._repository.update_status(
                connection_id,
                ConnectionStatus.DEGRADED,
                f"Health check failed: {e}"
            )
            logger.error(f"Health check failed for connection {connection_id}: {e}")
        
        return connection
    
    async def get_connection_by_assistant_and_channel(
        self,
        assistant_id: str,
        channel: ConnectionChannel,
        user_id: str
    ) -> Optional[Connection]:
        """
        Get connection by assistant and channel with access control.
        
        Args:
            assistant_id: Assistant ID
            channel: Communication channel
            user_id: User ID for access control
            
        Returns:
            Connection if found and user has access, None otherwise
        """
        # Verify user has access to the assistant
        try:
            await self._assistant_service.get_assistant(assistant_id, user_id)
        except AssistantNotFoundError:
            return None
        
        # Get connection
        connection = await self._repository.get_by_assistant_and_channel(
            assistant_id,
            channel
        )
        
        return connection
    
    # ==================== Internal methods (no access control) ====================
    # These methods are used by internal services like webhooks that don't have user context
    
    async def get_connection_internal(self, connection_id: str) -> Optional[Connection]:
        """
        Get connection by ID without access control (for internal use).
        
        This method is used by workers and webhooks that don't have user context.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Connection if found, None otherwise
        """
        return await self._repository.get_by_id(connection_id)
    
    async def get_connection_by_assistant_and_channel_internal(
        self,
        assistant_id: str,
        channel: ConnectionChannel
    ) -> Optional[Connection]:
        """
        Get connection by assistant and channel without access control (for internal use).
        
        This method is used by webhooks that receive events from external services.
        
        Args:
            assistant_id: Assistant ID
            channel: Communication channel
            
        Returns:
            Connection if found, None otherwise
        """
        return await self._repository.get_by_assistant_and_channel(assistant_id, channel)
    
    async def update_connection_status_internal(
        self,
        connection_id: str,
        status: ConnectionStatus,
        error_message: Optional[str] = None
    ) -> Optional[Connection]:
        """
        Update connection status without access control (for internal use).
        
        This method is used by webhooks to update connection status.
        
        Args:
            connection_id: Connection ID
            status: New status
            error_message: Optional error message
            
        Returns:
            Updated connection if found, None otherwise
        """
        return await self._repository.update_status(connection_id, status, error_message)
