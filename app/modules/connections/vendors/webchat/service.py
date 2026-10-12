"""WebChat channel service - central service for webchat operations."""

import logging
from typing import List, Optional

from app.modules.connections.vendors.webchat.models import WebchatMessage
from app.modules.connections.vendors.webchat.repository import WebchatMessageRepository
from app.modules.connections.vendors.webchat.publisher import WebsocketPublisher
from app.modules.connections.vendors.webchat.schemas import WebchatMessageResponse
from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.models import ConnectionChannel, ConnectionStatus
from app.common.auth import is_anonymous_user, validate_anonymous_user_id

logger = logging.getLogger(__name__)


class WebchatValidationError(Exception):
    """Raised when webchat message validation fails."""
    pass


class WebchatMessageNotFoundError(Exception):
    """Raised when webchat message is not found."""
    pass


class WebchatChannelService:
    """
    Central service for WebChat channel.
    
    Responsibilities:
    - Validate messages
    - Save messages to webchat_messages collection
    - Publish to websocket_messages queue (for delivering responses)
    - API for history, editing, deletion
    
    NOT responsible for:
    - Publishing to incoming_messages (done by Webhook)
    """
    
    def __init__(self, websocket_publisher: Optional[WebsocketPublisher] = None):
        """Initialize service with repository and publisher."""
        self._repository = WebchatMessageRepository()
        self._assistant_service = AssistantService()
        self._connection_repository = ConnectionRepository()
        self._websocket_publisher = websocket_publisher or WebsocketPublisher()
    
    # === Validation ===
    
    async def validate_message(
        self,
        assistant_id: str,
        user_id: str,
        content: str
    ) -> None:
        """
        Validate incoming message.
        
        Checks:
        - Assistant exists
        - WebChat is enabled for assistant
        - Content is not empty
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID from frontend
            content: Message content
            
        Raises:
            WebchatValidationError: If validation fails
        """
        # Check content
        if not content or not content.strip():
            raise WebchatValidationError("Message content cannot be empty")
        
        # Check assistant exists
        try:
            await self._assistant_service.get_assistant_internal(assistant_id)
        except AssistantNotFoundError:
            raise WebchatValidationError(f"Assistant {assistant_id} not found")
        
        # Check webchat connection exists and is enabled
        connection = await self._connection_repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
        
        if not connection:
            raise WebchatValidationError(f"WebChat not enabled for assistant {assistant_id}")
        
        if connection.status == ConnectionStatus.ERROR:
            raise WebchatValidationError(f"WebChat connection is in error state")
        
        logger.debug(f"Validated webchat message for assistant {assistant_id}, user {user_id}")
    
    # === Save messages ===
    
    async def save_user_message(
        self,
        assistant_id: str,
        user_id: str,
        content: str,
        conversation_id: str
    ) -> WebchatMessage:
        """
        Save user message to webchat_messages.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID from frontend
            content: Message content
            conversation_id: Conversation ID
            
        Returns:
            Created WebchatMessage
        """
        message = await self._repository.create(
            conversation_id=conversation_id,
            assistant_id=assistant_id,
            user_id=user_id,
            role="user",
            content=content
        )
        
        logger.info(f"Saved user webchat message {message.id} for assistant {assistant_id}")
        return message
    
    async def save_assistant_message(
        self,
        assistant_id: str,
        user_id: str,
        content: str,
        conversation_id: str
    ) -> WebchatMessage:
        """
        Save assistant response to webchat_messages and publish to websocket queue.
        
        Called from Outbound Worker.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID
            content: Response content
            conversation_id: Conversation ID
            
        Returns:
            Created WebchatMessage
        """
        # Save to database
        message = await self._repository.create(
            conversation_id=conversation_id,
            assistant_id=assistant_id,
            user_id=user_id,
            role="assistant",
            content=content
        )
        
        logger.info(f"Saved assistant webchat message {message.id}")
        
        # Publish to websocket queue for delivery to client
        await self._publish_to_websocket(message)
        
        return message
    
    # === Publish to WebSocket ===
    
    async def _publish_to_websocket(self, message: WebchatMessage) -> None:
        """
        Publish message to websocket_messages queue for delivery to client.
        
        Args:
            message: WebchatMessage to publish
        """
        await self._websocket_publisher.publish_chat_message(
            assistant_id=str(message.assistant_id),
            user_id=message.user_id,
            message_id=str(message.id),
            role=message.role,
            content=message.content
        )
        
        logger.debug(f"Published webchat message {message.id} to websocket queue")
    
    async def publish_typing_indicator(
        self,
        assistant_id: str,
        user_id: str,
        is_typing: bool = True
    ) -> None:
        """
        Publish typing indicator to websocket queue.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID
            is_typing: Whether assistant is typing
        """
        await self._websocket_publisher.publish_typing_indicator(
            assistant_id=assistant_id,
            user_id=user_id,
            is_typing=is_typing
        )
        
        logger.debug(f"Published typing indicator for assistant {assistant_id}")
    
    # === API for history ===
    
    async def get_messages(
        self,
        assistant_id: str,
        user_id: str,
        limit: int = 50,
        skip: int = 0
    ) -> tuple[List[WebchatMessage], int]:
        """
        Get message history for user and assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID
            limit: Maximum messages to return
            skip: Number to skip for pagination
            
        Returns:
            Tuple of (messages list, total count)
        """
        messages = await self._repository.get_messages(
            assistant_id=assistant_id,
            user_id=user_id,
            limit=limit,
            skip=skip,
            include_deleted=False
        )
        
        total = await self._repository.count_messages(
            assistant_id=assistant_id,
            user_id=user_id,
            include_deleted=False
        )
        
        return messages, total
    
    async def get_message(
        self,
        message_id: str,
        user_id: str
    ) -> WebchatMessage:
        """
        Get single message by ID with user ownership check.
        
        Args:
            message_id: Message ID
            user_id: User ID for ownership check
            
        Returns:
            WebchatMessage
            
        Raises:
            WebchatMessageNotFoundError: If not found or no access
        """
        message = await self._repository.get_by_id(message_id)
        
        if not message:
            raise WebchatMessageNotFoundError(f"Message {message_id} not found")
        
        if message.user_id != user_id:
            raise WebchatMessageNotFoundError(f"Message {message_id} not found")
        
        if message.is_deleted:
            raise WebchatMessageNotFoundError(f"Message {message_id} not found")
        
        return message
    
    # === Edit/Delete ===
    
    async def update_message(
        self,
        message_id: str,
        user_id: str,
        content: str
    ) -> WebchatMessage:
        """
        Update message content.
        
        Only user messages can be updated.
        
        Args:
            message_id: Message ID
            user_id: User ID for ownership check
            content: New content
            
        Returns:
            Updated WebchatMessage
            
        Raises:
            WebchatMessageNotFoundError: If not found or no access
            WebchatValidationError: If message cannot be edited
        """
        # Get and verify ownership
        message = await self.get_message(message_id, user_id)
        
        # Only user messages can be edited
        if message.role != "user":
            raise WebchatValidationError("Cannot edit assistant messages")
        
        # Validate content
        if not content or not content.strip():
            raise WebchatValidationError("Message content cannot be empty")
        
        # Update
        updated = await self._repository.update_content(message_id, content.strip())
        
        if not updated:
            raise WebchatMessageNotFoundError(f"Message {message_id} not found")
        
        logger.info(f"Updated webchat message {message_id}")
        return updated
    
    async def delete_message(
        self,
        message_id: str,
        user_id: str
    ) -> bool:
        """
        Soft delete a message.
        
        Args:
            message_id: Message ID
            user_id: User ID for ownership check
            
        Returns:
            True if deleted
            
        Raises:
            WebchatMessageNotFoundError: If not found or no access
        """
        # Get and verify ownership
        await self.get_message(message_id, user_id)
        
        # Soft delete
        deleted = await self._repository.soft_delete(message_id)
        
        if deleted:
            logger.info(f"Soft deleted webchat message {message_id}")
        
        return deleted
    
    # === Helper: Convert to response ===
    
    @staticmethod
    def to_response(message: WebchatMessage) -> WebchatMessageResponse:
        """Convert WebchatMessage to response schema."""
        return WebchatMessageResponse(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            assistant_id=str(message.assistant_id),
            user_id=message.user_id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            updated_at=message.updated_at
        )
    
    # === Anonymous Session Claiming ===
    
    async def claim_anonymous_session(
        self,
        anonymous_user_id: str,
        authenticated_user_id: str,
        assistant_id: str
    ) -> dict:
        """
        Transfer anonymous session to authenticated user.
        
        This is called after user logs in to merge their anonymous
        chat history with their authenticated account.
        
        Operations:
        1. Validate anonymous user ID format
        2. Update all webchat_messages.user_id: anon_xxx → authenticated_email
        3. Update interlocutor.user_id: anon_xxx → authenticated_email
        
        Args:
            anonymous_user_id: Anonymous user ID (anon_{uuid} format)
            authenticated_user_id: Authenticated user ID (email)
            assistant_id: Assistant ID for the session
            
        Returns:
            Dict with transfer statistics
            
        Raises:
            WebchatValidationError: If invalid anonymous ID or transfer fails
        """
        # Validate anonymous ID
        if not validate_anonymous_user_id(anonymous_user_id):
            raise WebchatValidationError(
                f"Invalid anonymous user ID format: {anonymous_user_id}"
            )
        
        # Validate authenticated user is not anonymous
        if is_anonymous_user(authenticated_user_id):
            raise WebchatValidationError(
                "Cannot claim session: target user is also anonymous"
            )
        
        logger.info(
            f"Claiming anonymous session: {anonymous_user_id} → {authenticated_user_id} "
            f"for assistant {assistant_id}"
        )
        
        # Update webchat messages
        messages_updated = await self._repository.update_user_id(
            old_user_id=anonymous_user_id,
            new_user_id=authenticated_user_id,
            assistant_id=assistant_id
        )
        
        # Update interlocutor
        from app.modules.conversations.repositories.interlocutor_repository import InterlocutorRepository
        interlocutor_repo = InterlocutorRepository()
        
        interlocutor_updated = await interlocutor_repo.update_user_id(
            old_user_id=anonymous_user_id,
            new_user_id=authenticated_user_id
        )
        
        logger.info(
            f"Session claimed: {messages_updated} messages updated, "
            f"interlocutor updated: {interlocutor_updated}"
        )
        
        return {
            "messages_transferred": messages_updated,
            "interlocutor_updated": interlocutor_updated,
            "anonymous_user_id": anonymous_user_id,
            "authenticated_user_id": authenticated_user_id
        }

