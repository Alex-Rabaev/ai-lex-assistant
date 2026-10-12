"""Base service for processing webhooks from different channels."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.modules.webhooks.models import WebhookResponse

logger = logging.getLogger(__name__)


class BaseWebhookService(ABC):
    """
    Abstract base class for webhook processing services.
    Each channel (Telegram, WhatsApp, etc.) should implement its own service.
    
    In the MVP with RabbitMQ architecture, the service is responsible for:
    1. Extracting data from updates
    2. Validating assistant and connection
    3. Saving webhook events for debugging/audit
    4. Publishing to RabbitMQ for async processing
    """
    
    @abstractmethod
    async def process_update(
        self, 
        update: Dict[str, Any],
        assistant_id: str
    ) -> WebhookResponse:
        """
        Process incoming webhook update from a channel.
        
        This method should:
        1. Extract data using the appropriate processor
        2. Validate assistant and connection exist
        3. Save webhook event to database (for debugging)
        4. Publish to RabbitMQ for async processing
        5. Return immediately (async processing)
        
        Args:
            update: Raw webhook update from channel
            assistant_id: ID of the assistant handling this webhook
            
        Returns:
            WebhookResponse with success status and message
            
        Raises:
            WebhookValidationError: If validation fails
            WebhookProcessingError: If processing fails
        """
        pass
    
    async def check_duplicate(
        self,
        update_id: Optional[int] = None,
        message_id: Optional[str] = None
    ) -> bool:
        """
        Check if this webhook is a duplicate.
        Default implementation can be overridden.
        
        Args:
            update_id: Telegram update_id or similar
            message_id: Message ID in the channel
            
        Returns:
            True if duplicate, False otherwise
        """
        # Default implementation - should be overridden
        return False
    
    async def get_assistant(
        self, 
        assistant_repository,
        assistant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get assistant by ID.
        Common method for all webhook services (Telegram, WhatsApp, etc.).
        
        Args:
            assistant_repository: Assistant repository instance
            assistant_id: Assistant ID
            
        Returns:
            Assistant document or None
        """
        try:
            from bson import ObjectId
            # For webhook context, we don't have user_id, 
            # so we directly query the database
            db = assistant_repository.db
            assistant = await db["assistants"].find_one({"_id": ObjectId(assistant_id)})
            return assistant
        except Exception as e:
            logger.error(f"Error getting assistant: {e}")
            return None
