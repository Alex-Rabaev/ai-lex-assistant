"""Service for Message admin operations."""

import logging
from typing import Tuple
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.modules.conversations.schemas import (
    MessageListQuery,
    MessageItem,
    MessageListResponse
)
from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.modules.conversations.repositories import (
    ConversationRepository,
    ConversationHistoryRepository
)

logger = logging.getLogger(__name__)


class MessageService:
    """Service for message admin operations."""
    
    def __init__(self):
        """Initialize service with repositories."""
        self._assistant_service = AssistantService()
        self._conversation_repo = ConversationRepository()
        self._history_repo = ConversationHistoryRepository()
    
    async def _check_assistant_access(
        self,
        assistant_id: str,
        user_id: str
    ) -> bool:
        """
        Check if user has access to assistant using AssistantService.
        
        Args:
            assistant_id: Assistant ID
            user_id: User email from JWT
            
        Returns:
            True if user has access
        """
        try:
            await self._assistant_service.get_assistant(assistant_id, user_id)
            return True
        except AssistantNotFoundError:
            return False
    
    def _get_sort_direction(self, sort: str) -> Tuple[str, int]:
        """Parse sort parameter into field and direction."""
        if sort.startswith("-"):
            return sort[1:], DESCENDING
        return sort, ASCENDING
    
    async def list_messages(
        self,
        assistant_id: str,
        interlocutor_id: str,
        user_id: str,
        query: MessageListQuery
    ) -> MessageListResponse:
        """
        List messages for interlocutor-assistant conversation.
        
        Args:
            assistant_id: Assistant ID
            interlocutor_id: Interlocutor ID
            user_id: User email for access check
            query: Query parameters
            
        Returns:
            Paginated list of messages
            
        Raises:
            ValueError: If no access or conversation not found
        """
        # Check access
        if not await self._check_assistant_access(assistant_id, user_id):
            raise ValueError(f"Assistant {assistant_id} not found or no access")
        
        # Get conversation
        conversation = await self._conversation_repo.get_by_interlocutor_and_assistant(
            interlocutor_id,
            assistant_id
        )
        
        if not conversation:
            raise ValueError(
                f"No conversation found for interlocutor {interlocutor_id} "
                f"with assistant {assistant_id}"
            )
        
        conversation_id = str(conversation.id)
        
        # For complex queries with filters, we need direct collection access
        await self._history_repo._ensure_db()
        history_collection = self._history_repo._collection
        
        # Build filter
        match_filter = {"conversation_id": ObjectId(conversation_id)}
        
        if query.state:
            match_filter["state"] = {"$in": query.state}
        
        if query.role:
            match_filter["role"] = {"$in": query.role}
        
        if query.date_from or query.date_to:
            date_filter = {}
            if query.date_from:
                date_filter["$gte"] = query.date_from
            if query.date_to:
                date_filter["$lte"] = query.date_to
            match_filter["created_at"] = date_filter
        
        # Get total count
        total = await history_collection.count_documents(match_filter)
        
        # Get sort direction
        sort_field, sort_direction = self._get_sort_direction(query.sort)
        
        # Query messages (include audio metadata fields)
        cursor = history_collection.find(
            match_filter,
            {
                "_id": 1,
                "role": 1,
                "content": 1,
                "state": 1,
                "created_at": 1,
                "message_type": 1,
                "audio_duration_seconds": 1
            }
        ).sort(
            sort_field, sort_direction
        ).skip(
            query.skip
        ).limit(
            query.limit
        )
        
        docs = await cursor.to_list(None)
        
        # Convert to response items (include audio metadata)
        items = [
            MessageItem(
                id=str(doc["_id"]),
                role=doc["role"],
                content=doc["content"],
                state=doc.get("state"),
                created_at=doc["created_at"],
                message_type=doc.get("message_type", "text"),
                audio_duration_seconds=doc.get("audio_duration_seconds")
            )
            for doc in docs
        ]
        
        logger.info(
            f"Listed {len(items)}/{total} messages for conversation "
            f"(interlocutor={interlocutor_id}, assistant={assistant_id})"
        )
        
        return MessageListResponse(
            items=items,
            total=total,
            skip=query.skip,
            limit=query.limit,
            conversation_id=conversation_id,
            interlocutor_id=interlocutor_id,
            assistant_id=assistant_id
        )

