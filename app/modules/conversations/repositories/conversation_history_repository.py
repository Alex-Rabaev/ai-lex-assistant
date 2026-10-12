"""Repository for managing conversation history."""

import logging
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.modules.conversations.models import ConversationMessage

logger = logging.getLogger(__name__)


class ConversationHistoryRepository:
    """Repository for conversation history operations."""
    
    def __init__(self):
        """Initialize repository."""
        self._db = None
        self._collection = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["conversation_history"]
    
    async def save_message(
        self,
        conversation_id: str,
        assistant_id: str,
        interlocutor_id: str,
        role: str,
        content: str,
        state: Optional[str] = None,
        message_type: Literal["text", "voice", "audio"] = "text",
        audio_duration_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationMessage:
        """
        Save message to conversation history.

        For user messages also updates ``last_user_message_at`` and
        ``updated_at`` on the parent conversation document (separate
        collection, so two DB calls, but always kept in sync).

        Args:
            conversation_id: Conversation ID
            assistant_id: Assistant ID
            interlocutor_id: Interlocutor ID
            role: Message role (user/assistant)
            content: Message text (or transcript for voice messages)
            state: Current step key
            message_type: Type of message ('text', 'voice', or 'audio')
            audio_duration_seconds: Duration of audio message (None for text)
            metadata: Optional metadata (e.g. follow_up, follow_up_attempt)

        Returns:
            Created ConversationMessage
        """
        await self._ensure_db()
        now = datetime.now(timezone.utc)
        message_data = {
            "conversation_id": ObjectId(conversation_id),
            "assistant_id": ObjectId(assistant_id),
            "interlocutor_id": ObjectId(interlocutor_id),
            "role": role,
            "content": content,
            "state": state,
            "message_type": message_type,
            "audio_duration_seconds": audio_duration_seconds,
            "created_at": now,
        }
        if metadata is not None:
            message_data["metadata"] = metadata
        
        result = await self._collection.insert_one(message_data)
        message_data["_id"] = result.inserted_id
        
        logger.debug(
            f"Saved {role} message: "
            f"conversation={conversation_id}, "
            f"state={state}, "
            f"message_type={message_type}"
        )
        
        return ConversationMessage(**message_data)
    
    async def get_full_history(
        self,
        conversation_id: str,
        limit: int
    ) -> List[ConversationMessage]:
        """
        Get conversation history.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return
            
        Returns:
            List of messages sorted by created_at (oldest first)
        """
        await self._ensure_db()
        cursor = self._collection.find({
            "conversation_id": ObjectId(conversation_id)
        }).sort("created_at", 1).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        
        return [ConversationMessage(**doc) for doc in docs]
    
    async def get_formatted_history(
        self,
        conversation_id: str,
        state: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get conversation history formatted for agent (only necessary fields).
        
        This method is optimized for agent use:
        - Queries DB with state filter if provided
        - Returns only needed fields (role, content, state, created_at)
        - Returns list of dicts (not models) ready for agent consumption
        
        Args:
            conversation_id: Conversation ID
            state: Optional state filter (step key)
            limit: Optional maximum number of messages to return (None = no limit)
            
        Returns:
            List of dicts with keys: role, content, state, created_at
        """
        await self._ensure_db()
        
        # Build query
        query = {"conversation_id": ObjectId(conversation_id)}
        if state:
            query["state"] = state
        
        # Query with projection (only needed fields, exclude _id)
        cursor = self._collection.find(
            query,
            {"_id": 0, "role": 1, "content": 1, "state": 1, "created_at": 1}
        ).sort("created_at", 1)
        
        if limit:
            cursor = cursor.limit(limit)
        
        docs = await cursor.to_list(length=limit if limit else None)
        
        return docs
    
    async def delete_all_by_conversation(
        self,
        conversation_id: str
    ) -> int:
        """
        Delete all messages for conversation (for /reset command).

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of deleted messages
        """
        await self._ensure_db()
        result = await self._collection.delete_many({
            "conversation_id": ObjectId(conversation_id)
        })

        logger.info(
            f"Deleted {result.deleted_count} messages "
            f"for conversation {conversation_id}"
        )

        return result.deleted_count

    async def delete_by_conversation_ids(self, conversation_ids: List[str]) -> int:
        """
        Delete all messages for the given conversation IDs.

        Args:
            conversation_ids: List of conversation IDs

        Returns:
            Total number of deleted messages
        """
        if not conversation_ids:
            return 0
        await self._ensure_db()
        ids = [ObjectId(cid) for cid in conversation_ids if cid]
        if not ids:
            return 0
        result = await self._collection.delete_many({"conversation_id": {"$in": ids}})
        logger.info(f"Deleted {result.deleted_count} messages for {len(ids)} conversations")
        return result.deleted_count

