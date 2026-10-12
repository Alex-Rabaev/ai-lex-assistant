"""Telegram message sender with retry logic."""

import logging
from typing import Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.modules.outbound.base.sender import BaseSender
from app.modules.outbound.vendors.telegram.client import TelegramClient
from app.modules.outbound.schemas import SendResult
from app.modules.outbound.exceptions import TemporaryError, SendError
from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.models import Connection

logger = logging.getLogger(__name__)


class TelegramSender(BaseSender):
    """
    High-level Telegram message sender with automatic retry.
    
    Implements the BaseSender interface for Telegram channel.
    Provides retry logic for temporary failures and connection
    status updates on critical errors.
    """
    
    def __init__(
        self,
        connection: Connection,
        connection_repo: ConnectionRepository
    ):
        """
        Initialize Telegram sender.
        
        Args:
            connection: Connection object with bot credentials
            connection_repo: Repository for updating connection status
        """
        # Get decrypted token from connection
        bot_token = connection.get_decrypted_token()
        
        self.client = TelegramClient(bot_token)
        self.connection = connection
        self.connection_repo = connection_repo
    
    def _extract_chat_id(self, user_id: str) -> int:
        """
        Extract Telegram chat_id from user_id.
        
        Args:
            user_id: User ID in format 'telegram_123456'
            
        Returns:
            Chat ID as integer
            
        Raises:
            ValueError: If user_id format is invalid
        """
        if not user_id.startswith("telegram_"):
            raise ValueError(f"Invalid user_id format: {user_id}. Expected 'telegram_<chat_id>'")
        
        chat_id_str = user_id.split("_", 1)[1]
        
        try:
            return int(chat_id_str)
        except ValueError:
            raise ValueError(f"Invalid chat_id in user_id: {user_id}")
    
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
        parse_mode: Optional[str] = "HTML",
        **kwargs
    ) -> SendResult:
        """
        Send message with automatic retry on temporary failures.
        
        Implements BaseSender.send_message() interface.
        Retries up to 3 times with exponential backoff for TemporaryError.
        Other exceptions (UserBlockedError, InvalidTokenError) are not retried.
        
        Args:
            user_id: User ID in format 'telegram_123456'
            text: Message text to send
            parse_mode: Parse mode (HTML or Markdown)
            **kwargs: Additional parameters (reply_markup, assistant_id, etc. - ignored)
            
        Returns:
            SendResult with operation outcome
        """
        try:
            chat_id = self._extract_chat_id(user_id)
            
            logger.info(f"Sending message to user_id={user_id} (chat_id={chat_id})")
            
            response = await self.client.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=kwargs.get("reply_markup")
            )
            
            message_id = response.get("result", {}).get("message_id")
            
            return SendResult(
                success=True,
                message_id=str(message_id) if message_id else None,
                retry_count=0
            )
            
        except TemporaryError as e:
            logger.warning(f"Temporary error sending message, will retry: {e}")
            raise  # Let tenacity handle retry
            
        except SendError as e:
            # Non-retryable errors (UserBlockedError, InvalidTokenError, etc.)
            logger.error(f"Failed to send message to {user_id}: {e}", exc_info=True)
            return SendResult(
                success=False,
                error=str(e),
                retry_count=0
            )
            
        except Exception as e:
            logger.error(f"Unexpected error sending message to {user_id}: {e}", exc_info=True)
            return SendResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                retry_count=0
            )
    
    async def _send_callback_response(
        self,
        user_id: str,
        callback_id: str,
        text: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Respond to callback query (button press).
        
        This is a Telegram-specific method for handling inline button presses.
        First answers the callback query to remove loading state,
        then optionally sends a text message if text is provided.
        
        Note: This is a private method, not part of BaseSender interface.
        
        Args:
            user_id: User ID in format 'telegram_123456'
            callback_id: Callback query ID from Telegram
            text: Optional response text to send
            **kwargs: Additional parameters
            
        Returns:
            SendResult with operation outcome
        """
        try:
            # Answer callback query to remove loading state
            await self.client.answer_callback_query(
                callback_query_id=callback_id,
                text=text if text and len(text) <= 200 else None,  # Telegram limit
                show_alert=kwargs.get("show_alert", False)
            )
            
            logger.info(f"Answered callback query: {callback_id}")
            
            # If text is provided and longer than 200 chars, send as message
            if text and len(text) > 200:
                return await self.send_message(user_id, text)
            
            return SendResult(success=True)
            
        except SendError as e:
            logger.error(f"Failed to answer callback query {callback_id}: {e}", exc_info=True)
            return SendResult(
                success=False,
                error=str(e)
            )
            
        except Exception as e:
            logger.error(f"Unexpected error answering callback query {callback_id}: {e}", exc_info=True)
            return SendResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    async def send_typing_indicator(self, user_id: str, **kwargs) -> SendResult:
        """
        Send typing indicator to user.
        
        Shows "typing..." status in the chat for ~5 seconds.
        This is a non-critical operation - failures are logged as warnings
        and don't affect the main message flow.
        
        Note: No retry logic - if it fails, we just continue.
        
        Args:
            user_id: User ID in format 'telegram_123456'
            **kwargs: Additional parameters (assistant_id, etc. - ignored)
            
        Returns:
            SendResult with operation outcome
        """
        try:
            chat_id = self._extract_chat_id(user_id)
            
            logger.debug(f"Sending typing indicator to user_id={user_id} (chat_id={chat_id})")
            
            await self.client.send_chat_action(
                chat_id=chat_id,
                action="typing"
            )
            
            return SendResult(success=True)
            
        except Exception as e:
            # Log as warning - typing indicator is not critical
            logger.warning(f"Failed to send typing indicator to {user_id}: {e}")
            return SendResult(
                success=False,
                error=str(e)
            )

