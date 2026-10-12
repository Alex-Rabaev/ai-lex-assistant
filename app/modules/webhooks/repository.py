"""Repository for webhook events."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.modules.webhooks.models import WebhookEvent
from app.modules.webhooks.exceptions import DuplicateWebhookError

logger = logging.getLogger(__name__)


class WebhookRepository:
    """Repository for managing webhook events in MongoDB."""
    
    def __init__(self):
        """Initialize webhook repository without database dependency."""
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._collection: Optional[AsyncIOMotorCollection] = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["webhook_events"]
    
    async def save_event(self, event: WebhookEvent) -> WebhookEvent:
        """
        Save webhook event to database.
        
        Args:
            event: WebhookEvent to save
            
        Returns:
            Saved WebhookEvent with generated ID
            
        Raises:
            DuplicateWebhookError: If event with same update_id already exists
        """
        await self._ensure_db()
        
        try:
            # Convert to dict for MongoDB
            event_dict = event.model_dump(by_alias=True, exclude_unset=True)
            
            # Ensure timestamps
            if "created_at" not in event_dict:
                event_dict["created_at"] = datetime.now(timezone.utc)
            event_dict["updated_at"] = datetime.now(timezone.utc)
            
            # Insert into database
            result = await self._collection.insert_one(event_dict)
            event_dict["_id"] = result.inserted_id
            
            # Return updated model
            return WebhookEvent(**event_dict)
            
        except DuplicateKeyError as e:
            logger.warning(f"Duplicate webhook event: {e}")
            raise DuplicateWebhookError(f"Webhook with update_id {event.update_id} already exists")
    
    async def get_event(self, event_id: str) -> Optional[WebhookEvent]:
        """
        Get webhook event by ID.
        
        Args:
            event_id: Event ID (as string)
            
        Returns:
            WebhookEvent if found, None otherwise
        """
        await self._ensure_db()
        
        try:
            object_id = ObjectId(event_id)
            doc = await self._collection.find_one({"_id": object_id})
            
            if doc:
                return WebhookEvent(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Error getting webhook event {event_id}: {e}")
            return None
    
    async def get_by_update_id(self, update_id: int) -> Optional[WebhookEvent]:
        """
        Get webhook event by Telegram update_id.
        
        Args:
            update_id: Telegram update ID
            
        Returns:
            WebhookEvent if found, None otherwise
        """
        await self._ensure_db()
        
        doc = await self._collection.find_one({"update_id": update_id})
        
        if doc:
            return WebhookEvent(**doc)
        return None
    
    
    async def mark_as_processed(
        self,
        event_id: str,
        response: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Mark webhook event as processed.
        
        Args:
            event_id: Event ID (as string)
            response: Optional response data if sent
            error: Optional error message if processing failed
            
        Returns:
            True if updated, False otherwise
        """
        await self._ensure_db()
        
        try:
            # Build update
            update_data: Dict[str, Any] = {
                "processed": True,
                "processed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            if response:
                update_data["response"] = response
                update_data["response_sent"] = True
            
            if error:
                update_data["error"] = error
            
            # Update document
            result = await self._collection.update_one(
                {"_id": ObjectId(event_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error marking event {event_id} as processed: {e}")
            return False
    
    async def find_by_user_and_message(
        self,
        user_id: str,
        message_id: Optional[str] = None
    ) -> Optional[WebhookEvent]:
        """
        Find webhook event by user_id and optionally message_id.
        
        Args:
            user_id: User ID
            message_id: Optional message ID
            
        Returns:
            WebhookEvent if found, None otherwise
        """
        await self._ensure_db()
        
        query: Dict[str, Any] = {"user_id": user_id}
        
        if message_id:
            query["message_id"] = message_id
        
        # Get most recent event
        cursor = self._collection.find(query).sort("created_at", -1).limit(1)
        docs = await cursor.to_list(length=1)
        
        if docs:
            return WebhookEvent(**docs[0])
        return None
