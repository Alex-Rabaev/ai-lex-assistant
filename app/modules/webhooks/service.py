"""Service layer for webhook operations."""

import logging
from typing import Optional, Dict, Any

from app.modules.webhooks.repository import WebhookRepository

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for webhook-related operations.
    
    Provides methods for accessing webhook data that can be used
    by other modules (e.g., ConversationsService).
    """
    
    def __init__(self):
        """Initialize service without database dependency."""
        pass
    
    async def get_user_info_from_event(
        self,
        user_id: str,
        message_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get user info from webhook_events collection.
        
        This method is used by ConversationsService to extract
        user details (name, username, language) from the original
        webhook event when processing messages.
        
        Args:
            user_id: User ID
            message_id: Message ID from channel
            
        Returns:
            User info dict or None
        """
        if not message_id:
            logger.warning(f"No message_id provided for user {user_id}")
            return None
        
        webhook_repo = WebhookRepository()
        
        try:
            # Find webhook event by message_id and user_id
            webhook_event = await webhook_repo.find_by_user_and_message(
                user_id=user_id,
                message_id=message_id
            )
            
            if not webhook_event:
                logger.warning(
                    f"Webhook event not found: "
                    f"message_id={message_id}, user_id={user_id}"
                )
                return None
            
            # Extract user info from content.from_user (Pydantic model attribute)
            user_data = webhook_event.content.from_user if webhook_event.content else None
            
            if not user_data:
                logger.warning(f"No user in webhook event: {message_id}")
                return None
            
            user_info = {
                "first_name": user_data.get("first_name") if isinstance(user_data, dict) else None,
                "last_name": user_data.get("last_name") if isinstance(user_data, dict) else None,
                "username": user_data.get("username") if isinstance(user_data, dict) else None,
                "language_code": user_data.get("language_code") if isinstance(user_data, dict) else None
            }
            
            logger.debug(f"Extracted user info: {user_info}")
            
            return user_info
        
        except Exception as e:
            logger.error(f"Error getting user info from webhook: {e}", exc_info=True)
            return None
