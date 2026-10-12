"""Repository for managing conversations."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.modules.conversations.models.conversation import Conversation

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation database operations."""
    
    def __init__(self):
        """Initialize repository."""
        self._db = None
        self._collection = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["conversations"]
    
    async def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation if found, None otherwise
        """
        await self._ensure_db()
        try:
            doc = await self._collection.find_one({"_id": ObjectId(conversation_id)})
            
            if doc:
                return Conversation(**doc)
            return None
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            return None
    
    async def get_by_interlocutor_and_assistant(
        self,
        interlocutor_id: str,
        assistant_id: str
    ) -> Optional[Conversation]:
        """
        Get conversation by interlocutor and assistant.
        
        Args:
            interlocutor_id: Interlocutor ID
            assistant_id: Assistant ID
            
        Returns:
            Conversation if found, None otherwise
        """
        await self._ensure_db()
        doc = await self._collection.find_one({
            "interlocutor_id": ObjectId(interlocutor_id),
            "assistant_id": ObjectId(assistant_id)
        })
        
        if doc:
            return Conversation(**doc)
        return None
    
    async def create(
        self,
        interlocutor_id: str,
        assistant_id: str,
        connection_id: str,
        is_mock: bool = False
    ) -> Conversation:
        """
        Create new conversation.

        Args:
            interlocutor_id: Interlocutor ID
            assistant_id: Assistant ID
            connection_id: Connection ID
            is_mock: True if created for mock respondents (test data)

        Returns:
            Created Conversation
        """
        await self._ensure_db()
        now = datetime.now(timezone.utc)

        conversation_data = {
            "interlocutor_id": ObjectId(interlocutor_id),
            "assistant_id": ObjectId(assistant_id),
            "connection_id": ObjectId(connection_id),
            "state": {},  # Empty state initially
            "is_mock": is_mock,
            "created_at": now,
            "updated_at": now
        }
        
        result = await self._collection.insert_one(conversation_data)
        conversation_data["_id"] = result.inserted_id
        
        logger.info(
            f"Created conversation: "
            f"interlocutor={interlocutor_id}, "
            f"assistant={assistant_id}, "
            f"id={result.inserted_id}"
        )
        
        return Conversation(**conversation_data)
    
    async def get_or_create(
        self,
        interlocutor_id: str,
        assistant_id: str,
        connection_id: str
    ) -> Conversation:
        """
        Get existing conversation or create new one.
        
        Args:
            interlocutor_id: Interlocutor ID
            assistant_id: Assistant ID
            connection_id: Connection ID
            
        Returns:
            Conversation (existing or newly created)
        """
        await self._ensure_db()
        # Try to get existing
        conversation = await self.get_by_interlocutor_and_assistant(
            interlocutor_id,
            assistant_id
        )
        
        if conversation:
            logger.debug(
                f"Found existing conversation: "
                f"interlocutor={interlocutor_id}, "
                f"assistant={assistant_id}"
            )
            return conversation
        
        # Create new
        conversation = await self.create(
            interlocutor_id=interlocutor_id,
            assistant_id=assistant_id,
            connection_id=connection_id
        )
        
        return conversation
    
    async def update_last_user_message_at(
        self,
        conversation_id: str,
        at: datetime,
    ) -> bool:
        """Set last_user_message_at (latest inbound user message)."""
        await self._ensure_db()
        try:
            result = await self._collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {
                        "last_user_message_at": at,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error("Error updating last_user_message_at: %s", e)
            return False

    async def update_state(
        self,
        conversation_id: str,
        new_state: Dict[str, Any]
    ) -> bool:
        """
        Update conversation state.
        
        Args:
            conversation_id: Conversation ID
            new_state: New state dictionary
            
        Returns:
            True if updated, False otherwise
        """
        await self._ensure_db()
        try:
            result = await self._collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {
                        "state": new_state,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating conversation state: {e}")
            return False
    
    async def get_by_assistant(
        self,
        assistant_id: str,
        stage: Optional[str] = None,
        include_mock: Optional[bool] = None
    ) -> List[Conversation]:
        """
        Get all conversations for a given assistant.

        Args:
            assistant_id: Assistant ID
            stage: Optional stage filter (filters by state.agent_metadata.state)
            include_mock: If False, return only real conversations (is_mock != True).
                If True or None, return all (no filter by is_mock).

        Returns:
            List of conversations for the assistant
        """
        await self._ensure_db()

        query: Dict[str, Any] = {"assistant_id": ObjectId(assistant_id)}

        if stage:
            query["state.agent_metadata.state"] = stage
        if include_mock is False:
            query["is_mock"] = {"$ne": True}

        cursor = self._collection.find(query).sort("created_at", -1)
        docs = await cursor.to_list(length=None)

        return [Conversation(**doc) for doc in docs]
    
    async def update_analytic_meta(
        self,
        conversation_id: str,
        analytic_meta: Dict[str, Any]
    ) -> Optional[Conversation]:
        """
        Update analytic_meta field of a conversation.
        
        Args:
            conversation_id: Conversation ID
            analytic_meta: Analytics metadata dictionary (validated as AnalyticMeta)
            
        Returns:
            Updated Conversation or None if not found
        """
        await self._ensure_db()
        try:
            result = await self._collection.find_one_and_update(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {
                        "analytic_meta": analytic_meta,
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                return_document=ReturnDocument.AFTER
            )
            
            if result:
                logger.info(f"Updated analytic_meta for conversation {conversation_id}")
                return Conversation(**result)
            
            logger.warning(f"Conversation not found: {conversation_id}")
            return None

        except Exception as e:
            logger.error(f"Error updating analytic_meta: {e}")
            return None

    async def get_mock_conversation_ids_by_assistant(self, assistant_id: str) -> List[str]:
        """
        Get IDs of all mock conversations for an assistant.

        Args:
            assistant_id: Assistant ID

        Returns:
            List of conversation IDs (is_mock=True)
        """
        await self._ensure_db()
        cursor = self._collection.find(
            {"assistant_id": ObjectId(assistant_id), "is_mock": True},
            {"_id": 1}
        )
        docs = await cursor.to_list(length=None)
        return [str(doc["_id"]) for doc in docs]

    async def delete_by_id(self, conversation_id: str) -> bool:
        """Delete a single conversation by ID."""
        await self._ensure_db()
        result = await self._collection.delete_one({"_id": ObjectId(conversation_id)})
        if result.deleted_count > 0:
            logger.info(f"Deleted conversation {conversation_id}")
            return True
        return False

    async def find_follow_up_candidates(
        self,
        assistant_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Return conversation IDs eligible for follow-up.

        Always excludes mock conversations. ``extra_filter`` is merged into
        the query so the caller (agent) can add any MongoDB predicates it
        needs without the repository knowing about agent_metadata internals.
        """
        await self._ensure_db()
        query: Dict[str, Any] = {
            "assistant_id": ObjectId(assistant_id),
            "is_mock": {"$ne": True},
        }
        if extra_filter:
            query.update(extra_filter)
        cursor = self._collection.find(query, {"_id": 1})
        docs = await cursor.to_list(length=None)
        return [str(doc["_id"]) for doc in docs]

    async def delete_many_by_ids(self, conversation_ids: List[str]) -> int:
        """
        Delete conversations by IDs.

        Args:
            conversation_ids: List of conversation IDs

        Returns:
            Number of deleted conversations
        """
        if not conversation_ids:
            return 0
        await self._ensure_db()
        ids = [ObjectId(cid) for cid in conversation_ids if cid]
        if not ids:
            return 0
        result = await self._collection.delete_many({"_id": {"$in": ids}})
        logger.info(f"Deleted {result.deleted_count} mock conversations")
        return result.deleted_count

