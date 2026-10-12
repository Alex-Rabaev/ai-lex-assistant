"""WebChat webhook service implementation."""

import logging
from typing import Optional

from app.modules.webhooks.models import WebhookEvent, WebhookResponse
from app.modules.webhooks.repository import WebhookRepository
from app.modules.webhooks.publisher import WebhookPublisher
from app.modules.connections.vendors.webchat.service import (
    WebchatChannelService,
    WebchatValidationError
)
from app.modules.conversations.repositories.interlocutor_repository import InterlocutorRepository
from app.modules.conversations.repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class WebchatWebhookService:
    """
    Service for processing WebChat webhook messages.
    
    Flow:
    1. Validate message via WebchatChannelService
    2. Get or create conversation
    3. Save user message to webchat_messages via WebchatChannelService
    4. Save webhook event for audit
    5. Publish to incoming_messages queue
    """
    
    def __init__(
        self,
        webhook_repository: WebhookRepository,
        webhook_publisher: Optional[WebhookPublisher] = None
    ):
        """
        Initialize WebChat webhook service.
        
        Args:
            webhook_repository: Repository for webhook events
            webhook_publisher: Webhook publisher for RabbitMQ
        """
        self.webhook_repo = webhook_repository
        self.webhook_publisher = webhook_publisher
        self._webchat_service = WebchatChannelService()
        self._interlocutor_repo = InterlocutorRepository()
        self._conversation_repo = ConversationRepository()
    
    async def process_message(
        self,
        assistant_id: str,
        connection_id: str,
        user_id: str,
        content: str
    ) -> WebhookResponse:
        """
        Process incoming webchat message.
        
        This method:
        1. Validates message via WebchatChannelService
        2. Gets or creates conversation
        3. Saves user message to webchat_messages
        4. Publishes to incoming_messages queue for agent processing
        
        Args:
            assistant_id: Assistant ID from URL path
            connection_id: Connection ID (looked up in router)
            user_id: User ID (already authenticated in router)
            content: Message content from request body
            
        Returns:
            WebhookResponse with message_id if successful
        """
        logger.info(f"📨 WEBCHAT: Processing message for assistant {assistant_id} from user {user_id}")
        
        try:
            # 1. Validate message via WebchatChannelService
            try:
                await self._webchat_service.validate_message(
                    assistant_id=assistant_id,
                    user_id=user_id,
                    content=content
                )
            except WebchatValidationError as e:
                logger.warning(f"Validation failed: {e}")
                return WebhookResponse(
                    success=False,
                    message=str(e)
                )
            
            # 2. Get or create interlocutor and conversation
            interlocutor = await self._interlocutor_repo.get_or_create(
                user_id=user_id,
                user_info={"source": "webchat"}
            )
            
            conversation = await self._conversation_repo.get_or_create(
                interlocutor_id=str(interlocutor.id),
                assistant_id=assistant_id,
                connection_id=connection_id
            )
            conversation_id = str(conversation.id)
            
            # 3. Save user message to webchat_messages via WebchatChannelService
            webchat_message = await self._webchat_service.save_user_message(
                assistant_id=assistant_id,
                user_id=user_id,
                content=content,
                conversation_id=conversation_id
            )
            message_id = str(webchat_message.id)
            
            # 4. Save webhook event for audit
            webhook_event = WebhookEvent(
                assistant_id=assistant_id,
                connection_id=connection_id,
                channel="webchat",
                user_id=user_id,
                type="message",
                content={
                    "text": content,
                    "user": {"id": user_id, "source": "webchat"},
                    "type": "message"
                },
                raw_data={
                    "assistant_id": assistant_id,
                    "user_id": user_id,
                    "content": content
                },
                message_id=message_id,
                processed=False
            )
            
            await self.webhook_repo.save_event(webhook_event)
            
            # 5. Publish to incoming_messages queue
            if self.webhook_publisher:
                try:
                    await self.webhook_publisher.publish_message(
                        assistant_id=assistant_id,
                        connection_id=connection_id,
                        user_id=user_id,
                        channel="webchat",
                        message_data={
                            "type": "message",
                            "text": content,
                            "message_id": message_id
                        }
                    )
                    
                    logger.info(
                        f"WebChat message queued: "
                        f"assistant={assistant_id}, "
                        f"user={user_id}, "
                        f"message_id={message_id}"
                    )
                except Exception as e:
                    logger.error(f"Error publishing to queue: {e}", exc_info=True)
                    # Don't fail - message is saved, can be processed later
            
            return WebhookResponse(
                success=True,
                message="Message received and queued",
                data={
                    "message_id": message_id,
                    "conversation_id": conversation_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing webchat message: {e}", exc_info=True)
            
            # Try to save error event for debugging
            try:
                error_event = WebhookEvent(
                    assistant_id=assistant_id,
                    connection_id=connection_id,
                    channel="webchat",
                    user_id=user_id,
                    type="error",
                    content={"error": str(e)},
                    raw_data={
                        "assistant_id": assistant_id,
                        "user_id": user_id,
                        "content": content
                    },
                    processed=False,
                    error=str(e)
                )
                await self.webhook_repo.save_event(error_event)
            except Exception:
                pass  # Best effort
            
            return WebhookResponse(
                success=False,
                message=f"Processing error: {str(e)}"
            )
