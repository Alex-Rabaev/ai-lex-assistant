"""Repository layer for webchat messages database operations."""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.modules.connections.vendors.webchat.models import WebchatMessage

logger = logging.getLogger(__name__)


class WebchatMessageRepository:
    """Repository for webchat messages database operations."""
    
    COLLECTION_NAME = "webchat_messages"
    
    def __init__(self):
        """Initialize repository without database dependency."""
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._collection: Optional[AsyncIOMotorCollection] = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db[self.COLLECTION_NAME]
    
    async def create(
        self,
        conversation_id: str,
        assistant_id: str,
        user_id: str,
        role: str,
        content: str
    ) -> WebchatMessage:
        """
        Create new webchat message.
        
        Args:
            conversation_id: Conversation ID
            assistant_id: Assistant ID
            user_id: User ID from frontend
            role: Message role (user/assistant)
            content: Message content
            
        Returns:
            Created WebchatMessage
        """
        await self._ensure_db()
        
        now = datetime.now(timezone.utc)
        doc = {
            "conversation_id": ObjectId(conversation_id),
            "assistant_id": ObjectId(assistant_id),
            "user_id": user_id,
            "role": role,
            "content": content,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now
        }
        
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        
        logger.debug(f"Created webchat message {result.inserted_id} for conversation {conversation_id}")
        return WebchatMessage(**doc)
    
    async def get_by_id(self, message_id: str) -> Optional[WebchatMessage]:
        """
        Get message by ID.
        
        Args:
            message_id: Message ID
            
        Returns:
            WebchatMessage or None if not found
        """
        await self._ensure_db()
        
        try:
            doc = await self._collection.find_one({
                "_id": ObjectId(message_id)
            })
            
            if doc:
                return WebchatMessage(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Error getting webchat message {message_id}: {e}")
            return None
    
    async def get_messages(
        self,
        assistant_id: str,
        user_id: str,
        limit: int = 50,
        skip: int = 0,
        include_deleted: bool = False
    ) -> List[WebchatMessage]:
        """
        Get messages for a user and assistant.

        Returns the last (most recent) N messages in chronological order (oldest first).
        Sort by created_at DESC, take skip+limit from the "new" end, then return
        the last `limit` in reversed order so the client gets oldest ... newest.

        Args:
            assistant_id: Assistant ID
            user_id: User ID
            limit: Maximum messages to return
            skip: Number of most-recent messages to skip (for pagination: skip=0 gives last N)
            include_deleted: Whether to include soft-deleted messages

        Returns:
            List of WebchatMessage ordered by created_at ascending (oldest first)
        """
        await self._ensure_db()

        query = {
            "assistant_id": ObjectId(assistant_id),
            "user_id": user_id
        }

        if not include_deleted:
            query["is_deleted"] = False

        # Fetch from the end: sort DESC, skip the most recent `skip`, take `limit`, then reverse
        cursor = (
            self._collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        # Chronological order for the client (oldest first)
        docs = list(reversed(docs))
        return [WebchatMessage(**doc) for doc in docs]
    
    async def get_messages_by_conversation(
        self,
        conversation_id: str,
        limit: int = 50,
        include_deleted: bool = False
    ) -> List[WebchatMessage]:
        """
        Get messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum messages to return
            include_deleted: Whether to include soft-deleted messages
            
        Returns:
            List of WebchatMessage ordered by created_at
        """
        await self._ensure_db()
        
        query = {"conversation_id": ObjectId(conversation_id)}
        
        if not include_deleted:
            query["is_deleted"] = False
        
        cursor = self._collection.find(query).sort("created_at", 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        return [WebchatMessage(**doc) for doc in docs]
    
    async def count_messages(
        self,
        assistant_id: str,
        user_id: str,
        include_deleted: bool = False
    ) -> int:
        """
        Count messages for a user and assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID
            include_deleted: Whether to include soft-deleted messages
            
        Returns:
            Number of messages
        """
        await self._ensure_db()
        
        query = {
            "assistant_id": ObjectId(assistant_id),
            "user_id": user_id
        }
        
        if not include_deleted:
            query["is_deleted"] = False
        
        return await self._collection.count_documents(query)
    
    async def update_content(
        self,
        message_id: str,
        content: str
    ) -> Optional[WebchatMessage]:
        """
        Update message content.
        
        Args:
            message_id: Message ID
            content: New content
            
        Returns:
            Updated WebchatMessage or None if not found
        """
        await self._ensure_db()
        
        result = await self._collection.find_one_and_update(
            {"_id": ObjectId(message_id)},
            {
                "$set": {
                    "content": content,
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            return_document=True
        )
        
        if result:
            logger.debug(f"Updated webchat message {message_id}")
            return WebchatMessage(**result)
        
        return None
    
    async def soft_delete(self, message_id: str) -> bool:
        """
        Soft delete a message (set is_deleted=True).
        
        Args:
            message_id: Message ID
            
        Returns:
            True if deleted, False if not found
        """
        await self._ensure_db()
        
        result = await self._collection.update_one(
            {"_id": ObjectId(message_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            logger.debug(f"Soft deleted webchat message {message_id}")
            return True
        
        return False
    
    async def hard_delete(self, message_id: str) -> bool:
        """
        Hard delete a message (remove from database).
        
        Args:
            message_id: Message ID
            
        Returns:
            True if deleted, False if not found
        """
        await self._ensure_db()
        
        result = await self._collection.delete_one({
            "_id": ObjectId(message_id)
        })
        
        if result.deleted_count > 0:
            logger.debug(f"Hard deleted webchat message {message_id}")
            return True
        
        return False
    
    async def delete_by_conversation(self, conversation_id: str) -> int:
        """
        Delete all messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Number of deleted messages
        """
        await self._ensure_db()
        
        result = await self._collection.delete_many({
            "conversation_id": ObjectId(conversation_id)
        })
        
        logger.debug(f"Deleted {result.deleted_count} webchat messages for conversation {conversation_id}")
        return result.deleted_count
    
    async def update_user_id(
        self,
        old_user_id: str,
        new_user_id: str,
        assistant_id: Optional[str] = None
    ) -> int:
        """
        Update user_id for all messages from old to new.
        
        Used for claiming anonymous sessions after user logs in.
        
        Args:
            old_user_id: Old user ID (anonymous ID)
            new_user_id: New user ID (authenticated email)
            assistant_id: Optional assistant ID to limit scope
            
        Returns:
            Number of messages updated
        """
        await self._ensure_db()
        
        query = {"user_id": old_user_id}
        
        if assistant_id:
            query["assistant_id"] = ObjectId(assistant_id)
        
        result = await self._collection.update_many(
            query,
            {
                "$set": {
                    "user_id": new_user_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(
            f"Updated user_id for {result.modified_count} webchat messages: "
            f"{old_user_id} → {new_user_id}"
        )
        
        return result.modified_count

