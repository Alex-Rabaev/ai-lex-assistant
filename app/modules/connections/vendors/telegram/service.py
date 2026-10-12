"""Telegram-specific connection service."""

import logging
from typing import Optional, Tuple
from pymongo.errors import DuplicateKeyError

from app.modules.connections.vendors.telegram.client import TelegramClient
from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.security import encrypt_token, decrypt_token
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)
from app.modules.connections.exceptions import (
    DuplicateConnectionError,
    InvalidBotTokenError
)
from app.config import config

logger = logging.getLogger(__name__)


class TelegramConnectionService:
    """Service for Telegram-specific connection operations."""
    
    def __init__(self):
        """Initialize service with client and repository."""
        self._client = TelegramClient()
        self._repository = ConnectionRepository()
    
    async def create_connection(
        self,
        assistant_id: str,
        bot_token: str
    ) -> Connection:
        """
        Create Telegram connection with full flow:
        1. Check uniqueness
        2. Validate bot token with Telegram
        3. Encrypt token
        4. Save to database
        5. Setup webhook
        
        Note: Assistant access verification should be done by caller (ConnectionService).
        
        Args:
            assistant_id: Assistant ID to connect
            bot_token: Telegram bot token from BotFather
            
        Returns:
            Created connection
            
        Raises:
            DuplicateConnectionError: If Telegram already connected
            InvalidBotTokenError: If token validation fails
        """
        logger.info(f"Creating Telegram connection for assistant {assistant_id}")
        
        # 1. Check if Telegram connection already exists
        existing = await self._repository.exists_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.TELEGRAM
        )
        if existing:
            raise DuplicateConnectionError(
                f"Assistant {assistant_id} already has a Telegram connection"
            )
        
        # 2. Validate bot token with Telegram API
        try:
            bot_info = await self._client.validate_token(bot_token)
            logger.info(f"Validated bot @{bot_info.username} (ID: {bot_info.id})")
        except InvalidBotTokenError as e:
            logger.error(f"Bot token validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating token: {e}")
            raise InvalidBotTokenError(f"Failed to validate bot token: {e}")
        
        # 3. Encrypt bot token
        try:
            encrypted_token = encrypt_token(bot_token, config.ENCRYPTION_KEY)
        except Exception as e:
            logger.error(f"Failed to encrypt token: {e}")
            raise ValueError(f"Token encryption failed: {e}")
        
        # 4. Prepare connection settings
        settings = ConnectionSettings(
            bot_token=encrypted_token,
            bot_username=f"@{bot_info.username}" if bot_info.username else None,
            bot_id=bot_info.id,
            bot_first_name=bot_info.first_name,
            bot_info={
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries
            }
        )
        
        # 5. Save to database (status = PENDING)
        try:
            connection = await self._repository.create(
                assistant_id,
                ConnectionChannel.TELEGRAM,
                settings
            )
            logger.info(f"Created connection {connection.id} for assistant {assistant_id}")
        except DuplicateKeyError:
            # Race condition - connection was created between our check and create
            raise DuplicateConnectionError(
                f"Assistant {assistant_id} already has a Telegram connection"
            )
        except Exception as e:
            logger.error(f"Failed to save connection: {e}")
            raise
        
        # 6. Setup webhook
        webhook_url = f"{config.WEBHOOK_BASE_URL}/webhook/telegram/{assistant_id}"
        
        try:
            success = await self._client.setup_webhook(
                bot_token,
                webhook_url,
                secret_token=None,  # TODO: Add secret token in future
                allowed_updates=["message", "callback_query"]
            )
            
            if success:
                # Update connection status to CONNECTED
                settings.webhook_url = webhook_url
                connection = await self._repository.update_status(
                    str(connection.id),
                    ConnectionStatus.CONNECTED
                )
                
                # Update settings with webhook URL
                await self._repository.update(
                    str(connection.id),
                    {"settings": settings}
                )
                
                logger.info(f"Webhook setup successful for connection {connection.id}")
                
                # Reload to get updated data
                connection = await self._repository.get_by_id(str(connection.id))
                
        except Exception as e:
            logger.error(f"Webhook setup failed: {e}")
            # Update connection status to ERROR
            await self._repository.update_status(
                str(connection.id),
                ConnectionStatus.ERROR,
                f"Webhook setup failed: {e}"
            )
            # Don't raise - connection is created but webhook failed
            # User can retry webhook setup later
            connection = await self._repository.get_by_id(str(connection.id))
        
        return connection
    
    async def delete_webhook(self, connection: Connection) -> bool:
        """
        Delete Telegram webhook for connection.
        
        Args:
            connection: Connection to delete webhook for
            
        Returns:
            True if deleted successfully, False if failed
        """
        if not connection.settings or not connection.settings.bot_token:
            logger.warning(f"No bot token for connection {connection.id}")
            return False
        
        try:
            # Decrypt token
            encrypted_token = connection.settings.bot_token
            bot_token = decrypt_token(encrypted_token, config.ENCRYPTION_KEY)
            
            # Delete webhook
            await self._client.delete_webhook(bot_token)
            logger.info(f"Deleted webhook for connection {connection.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete webhook for connection {connection.id}: {e}")
            return False
    
    async def check_health(self, connection: Connection) -> Tuple[bool, Optional[str]]:
        """
        Check Telegram connection health.
        
        Args:
            connection: Connection to check
            
        Returns:
            Tuple of (is_healthy, error_message)
            
        Raises:
            InvalidBotTokenError: If token is invalid (critical error)
        """
        if not connection.settings or not connection.settings.bot_token:
            return False, "No bot token configured"
        
        try:
            encrypted_token = connection.settings.bot_token
            bot_token = decrypt_token(encrypted_token, config.ENCRYPTION_KEY)
            
            webhook_info = await self._client.get_webhook_info(bot_token)
            
            # Check that Telegram webhook is subscribed to our URL
            webhook_url = connection.settings.webhook_url
            if webhook_url:
                webhook_url_from_telegram = webhook_info.get("url", "")
                if webhook_url_from_telegram != webhook_url:
                    return False, f"Webhook URL mismatch: Telegram has '{webhook_url_from_telegram}', expected '{webhook_url}'"
            
            # Check for other issues
            if webhook_info.get("pending_update_count", 0) > 100:
                return False, f"Too many pending updates: {webhook_info['pending_update_count']}"
            
            if webhook_info.get("last_error_message") and webhook_info.get("pending_update_count", 0) > 0:
                return False, webhook_info["last_error_message"]
            
            return True, None
            
        except InvalidBotTokenError:
            # Re-raise - this is a critical error
            raise
        except Exception as e:
            logger.warning(f"Could not check Telegram webhook status: {e}")
            # Don't fail health check if we can't reach Telegram API
            return True, None

