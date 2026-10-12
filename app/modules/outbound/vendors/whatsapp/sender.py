"""WhatsApp message sender with retry logic."""

import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.modules.outbound.base.sender import BaseSender
from app.modules.outbound.vendors.whatsapp.client import WhatsAppClient
from app.modules.outbound.schemas import SendResult
from app.modules.outbound.exceptions import TemporaryError, SendError
from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.models import Connection
from app.modules.connections.security import decrypt_token
from app.config import config

logger = logging.getLogger(__name__)


class WhatsAppSender(BaseSender):
    """WhatsApp message sender with automatic retry."""
    
    def __init__(
        self,
        connection: Connection,
        connection_repo: ConnectionRepository
    ):
        """
        Initialize WhatsApp sender.
        
        Args:
            connection: Connection object with credentials
            connection_repo: Repository for updating connection status
        """
        # Get phone_number_id and decrypt access_token
        phone_number_id = connection.settings.bot_info.get("phone_number_id")
        access_token = decrypt_token(connection.settings.bot_token, config.ENCRYPTION_KEY)
        
        if not phone_number_id:
            raise ValueError("Missing phone_number_id in connection settings")
        
        self.client = WhatsAppClient(phone_number_id, access_token)
        self.connection = connection
        self.connection_repo = connection_repo
    
    def _extract_phone_number(self, user_id: str) -> str:
        """
        Extract phone number from user_id.
        
        Args:
            user_id: User ID in format 'whatsapp_972501234567'
            
        Returns:
            Phone number without prefix
        """
        if not user_id.startswith("whatsapp_"):
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        return user_id.split("_", 1)[1]
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(TemporaryError),
        reraise=True
    )
    async def send_message(
        self,
        user_id: str,
        text: str,
        **kwargs
    ) -> SendResult:
        """
        Send message with automatic retry on temporary failures.
        
        Args:
            user_id: User ID in format 'whatsapp_972501234567'
            text: Message text
            **kwargs: Additional parameters (assistant_id, parse_mode, etc. - ignored)
            
        Returns:
            SendResult with operation outcome
        """
        try:
            phone = self._extract_phone_number(user_id)
            
            logger.info(f"Sending WhatsApp message to {user_id}")
            
            response = await self.client.send_text_message(
                to=phone,
                text=text
            )
            
            messages = response.get("messages", [])
            message_id = messages[0].get("id") if messages else None
            
            return SendResult(
                success=True,
                message_id=message_id,
                retry_count=0
            )
            
        except TemporaryError as e:
            logger.warning(f"Temporary error, will retry: {e}")
            raise
            
        except SendError as e:
            logger.error(f"Failed to send: {e}")
            return SendResult(success=False, error=str(e))
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return SendResult(success=False, error=str(e))
    
    async def send_typing_indicator(self, user_id: str, **kwargs) -> SendResult:
        """
        WhatsApp typing indicator is handled in webhook service.
        
        WhatsApp API requires message_id of incoming message to show typing,
        so it's sent together with mark_as_read when message is received.
        This method exists for BaseSender interface compatibility.
        
        Args:
            user_id: User ID (ignored)
            **kwargs: Additional parameters (assistant_id, etc. - ignored)
        """
        return SendResult(success=True)

