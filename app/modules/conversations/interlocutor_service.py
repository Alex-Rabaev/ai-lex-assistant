"""Service for Interlocutor admin operations."""

import logging
from typing import Dict, Any, Tuple
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.modules.conversations.schemas import (
    InterlocutorListQuery,
    InterlocutorListItem,
    InterlocutorListResponse,
    InterlocutorDetail,
    InterlocutorUpdate,
    ConversationInfo,
    MessageStats
)
from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.modules.conversations.repositories import (
    InterlocutorRepository,
    ConversationRepository,
    ConversationHistoryRepository
)

logger = logging.getLogger(__name__)


class InterlocutorService:
    """Service for interlocutor admin operations."""
    
    def __init__(self):
        """Initialize service with repositories."""
        self._assistant_service = AssistantService()
        self._interlocutor_repo = InterlocutorRepository()
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
    
    def _build_filter(self, query: InterlocutorListQuery) -> Dict[str, Any]:
        """Build MongoDB filter from query parameters."""
        match_filter = {}
        
        # Text search in interlocutor fields
        if query.q:
            import re
            regex = {"$regex": re.escape(query.q), "$options": "i"}
            match_filter["$or"] = [
                {"interlocutor.first_name": regex},
                {"interlocutor.last_name": regex},
                {"interlocutor.username": regex},
                {"interlocutor.profile.email": regex}
            ]
        
        # Stage filter
        if query.stage:
            match_filter["stage"] = {"$in": query.stage}
        
        # Language filter
        if query.language:
            match_filter["interlocutor.language"] = {"$in": query.language}
        
        # Email presence filter
        if query.has_email is not None:
            if query.has_email:
                match_filter["interlocutor.profile.email"] = {
                    "$exists": True, 
                    "$ne": None, 
                    "$ne": ""
                }
            else:
                match_filter["$or"] = [
                    {"interlocutor.profile.email": {"$exists": False}},
                    {"interlocutor.profile.email": None},
                    {"interlocutor.profile.email": ""}
                ]
        
        # Date range filter
        if query.date_from or query.date_to:
            date_filter = {}
            if query.date_from:
                date_filter["$gte"] = query.date_from
            if query.date_to:
                date_filter["$lte"] = query.date_to
            match_filter["interlocutor.created_at"] = date_filter
        
        return match_filter
    
    def _get_sort_field(self, sort: str) -> Tuple[str, int]:
        """Parse sort parameter into field and direction."""
        if sort.startswith("-"):
            return sort[1:], DESCENDING
        return sort, ASCENDING
    
    async def list_interlocutors(
        self,
        assistant_id: str,
        user_id: str,
        query: InterlocutorListQuery
    ) -> InterlocutorListResponse:
        """
        List interlocutors for assistant with filters.
        
        Uses aggregation pipeline to JOIN:
        - conversations (filter by assistant_id)
        - interlocutors (user data)
        - conversation_history (for last_message_at)
        
        Args:
            assistant_id: Assistant ID
            user_id: User email for access check
            query: Query parameters
            
        Returns:
            Paginated list of interlocutors
            
        Raises:
            ValueError: If no access to assistant
        """
        # Check access
        if not await self._check_assistant_access(assistant_id, user_id):
            raise ValueError(f"Assistant {assistant_id} not found or no access")
        
        # For complex aggregation, we use conversation repo's collection
        await self._conversation_repo._ensure_db()
        conversations_collection = self._conversation_repo._collection
        
        # Build aggregation pipeline
        sort_field, sort_direction = self._get_sort_field(query.sort)
        
        # Map sort fields to actual paths
        sort_field_map = {
            "created_at": "interlocutor.created_at",
            "first_name": "interlocutor.first_name",
            "last_name": "interlocutor.last_name",
            "language": "interlocutor.language",
            "last_message_at": "last_message_at",
            "stage": "stage"
        }
        actual_sort_field = sort_field_map.get(sort_field, f"interlocutor.{sort_field}")
        
        pipeline = [
            # Match conversations for this assistant
            {"$match": {"assistant_id": ObjectId(assistant_id)}},
            
            # Lookup interlocutor data
            {"$lookup": {
                "from": "interlocutors",
                "localField": "interlocutor_id",
                "foreignField": "_id",
                "as": "interlocutor"
            }},
            {"$unwind": "$interlocutor"},
            
            # Add computed fields
            {"$addFields": {
                "stage": "$state.agent_metadata.state",
                "email": "$interlocutor.profile.email"
            }},
            
            # Lookup last message
            {"$lookup": {
                "from": "conversation_history",
                "let": {"conv_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$conversation_id", "$$conv_id"]}}},
                    {"$sort": {"created_at": -1}},
                    {"$limit": 1},
                    {"$project": {"created_at": 1}}
                ],
                "as": "last_msg"
            }},
            
            # Add last_message_at field
            {"$addFields": {
                "last_message_at": {"$arrayElemAt": ["$last_msg.created_at", 0]}
            }},
        ]
        
        # Apply filters
        match_filter = self._build_filter(query)
        if match_filter:
            pipeline.append({"$match": match_filter})
        
        # Count total before pagination
        count_pipeline = pipeline + [{"$count": "total"}]
        count_result = await conversations_collection.aggregate(count_pipeline).to_list(1)
        total = count_result[0]["total"] if count_result else 0
        
        # Add sort and pagination
        pipeline.extend([
            {"$sort": {actual_sort_field: sort_direction}},
            {"$skip": query.skip},
            {"$limit": query.limit},
            
            # Project final shape
            {"$project": {
                "_id": 0,
                "id": {"$toString": "$interlocutor._id"},
                "conversation_id": {"$toString": "$_id"},
                "user_id": "$interlocutor.user_id",
                "first_name": "$interlocutor.first_name",
                "last_name": "$interlocutor.last_name",
                "username": "$interlocutor.username",
                "language": "$interlocutor.language",
                "email": "$email",
                "stage": "$stage",
                "created_at": "$interlocutor.created_at",
                "last_message_at": "$last_message_at"
            }}
        ])
        
        # Execute pipeline
        docs = await conversations_collection.aggregate(pipeline).to_list(None)
        
        # Convert to response items
        items = [InterlocutorListItem(**doc) for doc in docs]
        
        logger.info(
            f"Listed {len(items)}/{total} interlocutors for assistant {assistant_id}"
        )
        
        return InterlocutorListResponse(
            items=items,
            total=total,
            skip=query.skip,
            limit=query.limit,
            assistant_id=assistant_id
        )
    
    async def get_interlocutor(
        self,
        assistant_id: str,
        interlocutor_id: str,
        user_id: str
    ) -> InterlocutorDetail:
        """
        Get detailed interlocutor information.
        
        Args:
            assistant_id: Assistant ID
            interlocutor_id: Interlocutor ID
            user_id: User email for access check
            
        Returns:
            Detailed interlocutor info
            
        Raises:
            ValueError: If not found or no access
        """
        # Check access
        if not await self._check_assistant_access(assistant_id, user_id):
            raise ValueError(f"Assistant {assistant_id} not found or no access")
        
        # Get interlocutor
        interlocutor = await self._interlocutor_repo.get_by_id(interlocutor_id)
        
        if not interlocutor:
            raise ValueError(f"Interlocutor {interlocutor_id} not found")
        
        # Get conversation for this assistant
        conversation = await self._conversation_repo.get_by_interlocutor_and_assistant(
            interlocutor_id,
            assistant_id
        )
        
        if not conversation:
            raise ValueError(
                f"No conversation found for interlocutor {interlocutor_id} "
                f"with assistant {assistant_id}"
            )
        
        # Get message stats using history repository
        await self._history_repo._ensure_db()
        stats_pipeline = [
            {"$match": {"conversation_id": ObjectId(str(conversation.id))}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "first": {"$min": "$created_at"},
                "last": {"$max": "$created_at"}
            }}
        ]
        stats_result = await self._history_repo._collection.aggregate(
            stats_pipeline
        ).to_list(1)
        
        if stats_result:
            stats = MessageStats(
                total_messages=stats_result[0]["total"],
                first_message_at=stats_result[0]["first"],
                last_message_at=stats_result[0]["last"]
            )
        else:
            stats = MessageStats(total_messages=0)
        
        # Build conversation info
        conv_state = conversation.state or {}
        agent_metadata = conv_state.get("agent_metadata", {})
        conv_info = ConversationInfo(
            id=str(conversation.id),
            state=agent_metadata.get("state"),
            agent_metadata=agent_metadata,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
        return InterlocutorDetail(
            id=str(interlocutor.id),
            user_id=interlocutor.user_id,
            first_name=interlocutor.first_name,
            last_name=interlocutor.last_name,
            username=interlocutor.username,
            language=interlocutor.language,
            profile=interlocutor.profile or {},
            conversation=conv_info,
            stats=stats,
            created_at=interlocutor.created_at,
            updated_at=interlocutor.updated_at
        )
    
    async def update_interlocutor(
        self,
        assistant_id: str,
        interlocutor_id: str,
        user_id: str,
        data: InterlocutorUpdate
    ) -> InterlocutorDetail:
        """
        Update interlocutor data.
        
        Args:
            assistant_id: Assistant ID
            interlocutor_id: Interlocutor ID
            user_id: User email for access check
            data: Update data
            
        Returns:
            Updated interlocutor detail
            
        Raises:
            ValueError: If not found or no access
        """
        # Check access
        if not await self._check_assistant_access(assistant_id, user_id):
            raise ValueError(f"Assistant {assistant_id} not found or no access")
        
        # Get current interlocutor
        interlocutor = await self._interlocutor_repo.get_by_id(interlocutor_id)
        
        if not interlocutor:
            raise ValueError(f"Interlocutor {interlocutor_id} not found")
        
        # Check that conversation exists for this assistant
        conversation = await self._conversation_repo.get_by_interlocutor_and_assistant(
            interlocutor_id,
            assistant_id
        )
        
        if not conversation:
            raise ValueError(
                f"No conversation found for interlocutor {interlocutor_id} "
                f"with assistant {assistant_id}"
            )
        
        # Build update document
        update_doc = {}
        
        if data.first_name is not None:
            update_doc["first_name"] = data.first_name
        
        if data.last_name is not None:
            update_doc["last_name"] = data.last_name
        
        if data.language is not None:
            update_doc["language"] = data.language
        
        if data.profile is not None:
            # Merge with existing profile
            current_profile = interlocutor.profile or {}
            merged_profile = {**current_profile, **data.profile}
            update_doc["profile"] = merged_profile
        
        # Update via repository
        if update_doc:
            await self._interlocutor_repo.update(interlocutor_id, update_doc)
            logger.info(f"Updated interlocutor {interlocutor_id}: {list(update_doc.keys())}")
        
        # Return updated detail
        return await self.get_interlocutor(assistant_id, interlocutor_id, user_id)

