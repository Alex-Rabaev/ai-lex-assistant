"""Repository layer for assistant data access."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
import logging

from app.modules.assistants.models import Assistant, AssistantStep, AssistantStatus, FollowUpConfig
from app.modules.assistants.schemas import CreateAssistantRequest, UpdateAssistantRequest

logger = logging.getLogger(__name__)


class AssistantRepository:
    """Repository for assistant database operations."""
    
    def __init__(self):
        """Initialize repository without database dependency."""
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._assistants_collection: Optional[AsyncIOMotorCollection] = None
        self._steps_collection: Optional[AsyncIOMotorCollection] = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._assistants_collection = self._db["assistants"]
            self._steps_collection = self._db["assistant_steps"]
    
    async def create(
        self,
        org_id: str,
        owner_user_id: str,
        data: CreateAssistantRequest
    ) -> Assistant:
        """Create new assistant in database.
        
        Args:
            org_id: Organization ID
            owner_user_id: User ID of the owner
            data: Assistant creation data
            
        Returns:
            Created assistant model
        """
        await self._ensure_db()
        
        doc = {
            "org_id": org_id,
            "owner_user_id": owner_user_id,
            "name": data.name.strip(),
            "description": data.description,
            "type": data.type.value,
            "status": AssistantStatus.ACTIVE.value,
            "metadata": data.metadata or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await self._assistants_collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        
        return Assistant(**doc)
    
    async def get_by_id(self, assistant_id: str, user_id: str) -> Optional[Assistant]:
        """Get assistant by ID with user ownership check.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            
        Returns:
            Assistant model or None if not found
        """
        await self._ensure_db()
        
        doc = await self._assistants_collection.find_one({
            "_id": ObjectId(assistant_id),
            "owner_user_id": user_id
        })
        
        return Assistant(**doc) if doc else None
    
    async def get_by_id_internal(self, assistant_id: str) -> Optional[Assistant]:
        """Get assistant by ID without access control (for internal use).
        
        This method is used by workers and internal services that don't have
        user context but need to access assistants.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            Assistant model or None if not found
        """
        await self._ensure_db()
        
        doc = await self._assistants_collection.find_one({
            "_id": ObjectId(assistant_id)
        })
        
        return Assistant(**doc) if doc else None
    
    async def find_enabled_follow_up_assistant_ids(self) -> List[str]:
        """Return IDs of active assistants with follow_up_config.enabled == true."""
        await self._ensure_db()
        cursor = self._assistants_collection.find(
            {
                "status": AssistantStatus.ACTIVE.value,
                "follow_up_config.enabled": True,
            },
            {"_id": 1},
        )
        docs = await cursor.to_list(length=None)
        return [str(doc["_id"]) for doc in docs]

    async def find_by_user(
        self,
        user_id: str,
        status: Optional[AssistantStatus] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Assistant], int]:
        """Find assistants by user with pagination.
        
        Args:
            user_id: User ID (email) - owner of assistants
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            Tuple of (assistants list, total count)
        """
        await self._ensure_db()
        
        query = {"owner_user_id": user_id}
        if status:
            query["status"] = status.value
        
        # Get total count
        total = await self._assistants_collection.count_documents(query)
        
        # Get paginated results
        cursor = self._assistants_collection.find(query)
        cursor = cursor.skip(skip).limit(limit)
        cursor = cursor.sort("created_at", -1)  # Newest first
        
        docs = await cursor.to_list(length=limit)
        assistants = [Assistant(**doc) for doc in docs]
        
        return assistants, total
    
    async def update(
        self,
        assistant_id: str,
        user_id: str,
        data: UpdateAssistantRequest
    ) -> Optional[Assistant]:
        """Update assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            data: Update data
            
        Returns:
            Updated assistant or None if not found
        """
        await self._ensure_db()
        
        update_doc = {"updated_at": datetime.now(timezone.utc)}
        
        if data.name is not None:
            update_doc["name"] = data.name.strip()
        if data.description is not None:
            update_doc["description"] = data.description
        if data.type is not None:
            update_doc["type"] = data.type.value
        if data.status is not None:
            update_doc["status"] = data.status.value
        if data.metadata is not None:
            update_doc["metadata"] = data.metadata
        
        result = await self._assistants_collection.find_one_and_update(
            {"_id": ObjectId(assistant_id), "owner_user_id": user_id},
            {"$set": update_doc},
            return_document=True
        )
        
        return Assistant(**result) if result else None
    
    async def update_metadata_field(
        self,
        assistant_id: str,
        field_key: str,
        field_value: Any
    ) -> Optional[Assistant]:
        """Update a single field within Assistant.metadata (internal use).
        
        Uses MongoDB dot notation to update only the specified key
        without overwriting the entire metadata dict.
        
        Args:
            assistant_id: Assistant ID
            field_key: Key within metadata (e.g., "analysis_config")
            field_value: Value to set
            
        Returns:
            Updated Assistant or None if not found
        """
        await self._ensure_db()
        
        result = await self._assistants_collection.find_one_and_update(
            {"_id": ObjectId(assistant_id)},
            {
                "$set": {
                    f"metadata.{field_key}": field_value,
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            return_document=True
        )
        
        return Assistant(**result) if result else None

    async def update_follow_up_config(
        self,
        assistant_id: str,
        user_id: str,
        config: FollowUpConfig
    ) -> Optional[Assistant]:
        """Update follow_up_config for an assistant.

        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            config: Follow-up configuration

        Returns:
            Updated Assistant or None if not found
        """
        await self._ensure_db()

        config_doc = config.model_dump()
        result = await self._assistants_collection.find_one_and_update(
            {"_id": ObjectId(assistant_id), "owner_user_id": user_id},
            {
                "$set": {
                    "follow_up_config": config_doc,
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            return_document=True
        )

        return Assistant(**result) if result else None
    
    async def delete(self, assistant_id: str, user_id: str) -> bool:
        """Delete assistant and its steps.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            
        Returns:
            True if deleted, False if not found
        """
        await self._ensure_db()
        
        # Delete assistant
        result = await self._assistants_collection.delete_one({
            "_id": ObjectId(assistant_id),
            "owner_user_id": user_id
        })
        
        if result.deleted_count == 0:
            return False
        
        # Delete associated steps
        await self._steps_collection.delete_many({
            "assistant_id": ObjectId(assistant_id)
        })
        
        return True
    
    async def exists_by_name(self, user_id: str, name: str, exclude_id: Optional[str] = None) -> bool:
        """Check if assistant with name exists for user.
        
        Args:
            user_id: User ID (email) - owner of assistants
            name: Assistant name to check
            exclude_id: Optional ID to exclude from check (for updates)
            
        Returns:
            True if exists, False otherwise
        """
        await self._ensure_db()
        
        query = {
            "owner_user_id": user_id,
            "name": name.strip()
        }
        
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}
        
        count = await self._assistants_collection.count_documents(query)
        return count > 0
    
    async def create_steps(self, assistant_id: ObjectId, steps: List[Dict[str, Any]]) -> List[AssistantStep]:
        """Create multiple steps for an assistant.
        
        Args:
            assistant_id: Assistant ID
            steps: List of step configurations
            
        Returns:
            List of created steps
        """
        await self._ensure_db()
        
        docs = []
        for step in steps:
            doc = {
                "assistant_id": assistant_id,
                "step_key": step["step_key"].value if hasattr(step["step_key"], "value") else step["step_key"],
                "order_no": step["order_no"],
                "enabled": step.get("enabled", True),
                "metadata": step.get("metadata", {}),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            docs.append(doc)
        
        if docs:
            result = await self._steps_collection.insert_many(docs)
            for doc, inserted_id in zip(docs, result.inserted_ids):
                doc["_id"] = inserted_id
        
        return [AssistantStep(**doc) for doc in docs]
    
    async def delete_internal(self, assistant_id: str) -> bool:
        """Delete assistant and its steps without user ownership check (for internal rollback).

        Args:
            assistant_id: Assistant ID

        Returns:
            True if deleted, False if not found
        """
        await self._ensure_db()

        result = await self._assistants_collection.delete_one({"_id": ObjectId(assistant_id)})
        if result.deleted_count == 0:
            return False

        await self._steps_collection.delete_many({"assistant_id": ObjectId(assistant_id)})
        return True

    async def get_steps_by_assistant(self, assistant_id: str) -> List[AssistantStep]:
        """Get all steps for an assistant.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            List of steps ordered by order_no
        """
        await self._ensure_db()
        
        cursor = self._steps_collection.find({
            "assistant_id": ObjectId(assistant_id)
        })
        cursor = cursor.sort("order_no", 1)
        
        docs = await cursor.to_list(length=None)
        return [AssistantStep(**doc) for doc in docs]
    
    async def get_step_by_order(self, assistant_id: str, order_no: int) -> Optional[AssistantStep]:
        """Get step by order_no.
        
        Args:
            assistant_id: Assistant ID
            order_no: Step order number
            
        Returns:
            AssistantStep or None if not found
        """
        await self._ensure_db()
        
        doc = await self._steps_collection.find_one({
            "assistant_id": ObjectId(assistant_id),
            "order_no": order_no
        })
        
        return AssistantStep(**doc) if doc else None