"""WebChat message sender - saves to DB and publishes to WebSocket queue."""

import logging
from typing import Optional

from app.modules.outbound.base.sender import BaseSender
from app.modules.outbound.schemas import SendResult
from app.modules.connections.vendors.webchat.service import WebchatChannelService
from app.modules.connections.vendors.webchat.publisher import WebsocketPublisher
from app.modules.conversations.repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class WebchatSender(BaseSender):
    """
    WebChat message sender.
    
    Unlike Telegram/WhatsApp senders that call external APIs,
    WebchatSender:
    1. Saves assistant response to webchat_messages collection
    2. Publishes to websocket_messages queue (handled by WebchatChannelService)
    
    The WebSocket Worker then delivers the message to connected clients.
    """
    
    def __init__(self, websocket_publisher: Optional[WebsocketPublisher] = None):
        """Initialize WebChat sender."""
        self._webchat_service = WebchatChannelService(
            websocket_publisher=websocket_publisher
        )
        self._conversation_repo = ConversationRepository()
    
    def _extract_user_id(self, user_id: str) -> str:
        """
        Extract actual user ID from prefixed format.
        
        Args:
            user_id: User ID in format 'webchat_xxx'
            
        Returns:
            User ID (keeps prefix for consistency)
        """
        # Keep the full user_id with prefix for consistency
        return user_id
    
    async def _get_conversation_id(self, user_id: str, assistant_id: str) -> Optional[str]:
        """
        Get conversation ID for user and assistant.
        
        Args:
            user_id: User ID
            assistant_id: Assistant ID
            
        Returns:
            Conversation ID or None
        """
        # Find conversation by looking up interlocutor first
        from app.modules.conversations.repositories.interlocutor_repository import InterlocutorRepository
        
        interlocutor_repo = InterlocutorRepository()
        interlocutor = await interlocutor_repo.get_by_user_id(user_id)
        
        if not interlocutor:
            logger.warning(f"Interlocutor not found for user_id={user_id}")
            return None
        
        conversation = await self._conversation_repo.get_by_interlocutor_and_assistant(
            str(interlocutor.id),
            assistant_id
        )
        
        if not conversation:
            logger.warning(f"Conversation not found for user_id={user_id}, assistant_id={assistant_id}")
            return None
        
        return str(conversation.id)
    
    async def send_message(
        self,
        user_id: str,
        text: str,
        assistant_id: str,
        conversation_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send message via WebChat.
        
        This saves the message to webchat_messages and publishes to
        websocket_messages queue for delivery to the client.
        
        Args:
            user_id: User ID in format 'webchat_xxx'
            text: Message text to send
            assistant_id: Assistant ID (required for webchat)
            conversation_id: Optional conversation ID (will look up if not provided)
            parse_mode: Ignored for webchat (no special formatting)
            **kwargs: Additional parameters (ignored)
            
        Returns:
            SendResult with operation outcome
        """
        try:
            formatted_user_id = self._extract_user_id(user_id)
            
            # Get conversation_id if not provided
            if not conversation_id:
                conversation_id = await self._get_conversation_id(formatted_user_id, assistant_id)
                if not conversation_id:
                    return SendResult(
                        success=False,
                        error=f"Conversation not found for user {user_id}"
                    )
            
            logger.info(f"Sending webchat message to user_id={formatted_user_id}")
            
            # Save to webchat_messages and publish to websocket queue
            # WebchatChannelService handles both operations
            message = await self._webchat_service.save_assistant_message(
                assistant_id=assistant_id,
                user_id=formatted_user_id,
                content=text,
                conversation_id=conversation_id
            )
            
            return SendResult(
                success=True,
                message_id=str(message.id),
                retry_count=0
            )
            
        except Exception as e:
            logger.error(f"Failed to send webchat message to {user_id}: {e}", exc_info=True)
            return SendResult(
                success=False,
                error=str(e),
                retry_count=0
            )
    
    async def send_typing_indicator(
        self,
        user_id: str,
        assistant_id: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send typing indicator via WebChat.
        
        Publishes typing indicator to websocket_messages queue.
        
        Args:
            user_id: User ID in format 'webchat_xxx'
            assistant_id: Assistant ID (required for webchat)
            **kwargs: Additional parameters (ignored)
            
        Returns:
            SendResult with operation outcome
        """
        try:
            formatted_user_id = self._extract_user_id(user_id)
            
            logger.debug(f"Sending webchat typing indicator to user_id={formatted_user_id}")
            
            # Publish typing indicator to websocket queue
            await self._webchat_service.publish_typing_indicator(
                assistant_id=assistant_id,
                user_id=formatted_user_id,
                is_typing=True
            )
            
            return SendResult(success=True)
            
        except Exception as e:
            # Log as warning - typing indicator is not critical
            logger.warning(f"Failed to send webchat typing indicator to {user_id}: {e}")
            return SendResult(
                success=False,
                error=str(e)
            )

