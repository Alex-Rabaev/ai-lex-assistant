"""Abstract base class for message senders."""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.outbound.schemas import SendResult


class BaseSender(ABC):
    """
    Abstract interface for sending messages to users.
    
    Each communication channel (Telegram, WhatsApp, etc.) must implement
    this interface to provide a consistent way to send messages.
    
    The sender is responsible for:
    - Formatting messages for the specific channel
    - Handling channel-specific API calls
    - Managing retries for temporary failures
    - Reporting success/failure results
    
    All methods accept a unified set of parameters. Each implementation
    uses only the parameters it needs and ignores the rest.
    """
    
    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        text: str,
        assistant_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a message to a user.
        
        This is the main method that all channel implementations must provide.
        Channel-specific logic (e.g., callback queries for Telegram) should be
        handled internally by the implementation.
        
        Args:
            user_id: User identifier in format 'channel_id' (e.g., 'telegram_123456')
            text: Message text to send
            assistant_id: Assistant ID (used by webchat, ignored by others)
            conversation_id: Conversation ID (used by webchat, ignored by others)
            parse_mode: Parse mode for formatting (used by Telegram, ignored by others)
            **kwargs: Additional channel-specific parameters (reply_markup, etc.)
            
        Returns:
            SendResult with operation outcome
            
        Raises:
            SendError: If message cannot be sent
            UserBlockedError: If user has blocked the bot
            InvalidTokenError: If bot credentials are invalid
            TemporaryError: If a temporary error occurs (will be retried)
        """
        pass
    
    @abstractmethod
    async def send_typing_indicator(
        self,
        user_id: str,
        assistant_id: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send typing indicator to user.
        
        Args:
            user_id: User identifier
            assistant_id: Assistant ID (used by webchat, ignored by others)
            **kwargs: Additional parameters (ignored)
            
        Returns:
            SendResult with operation outcome
        """
        pass

