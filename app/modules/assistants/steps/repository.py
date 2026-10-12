"""Repository layer for assistant steps data access."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
import logging

from app.modules.assistants.models import AssistantStep

logger = logging.getLogger(__name__)


class StepRepository:
    """Repository for assistant steps database operations."""
    
    def __init__(self):
        """Initialize repository without database dependency."""
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._collection: Optional[AsyncIOMotorCollection] = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["assistant_steps"]
    
    async def get_by_assistant(self, assistant_id: str) -> List[AssistantStep]:
        """
        Get all steps for an assistant, ordered by order_no.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            List of steps ordered by order_no
        """
        await self._ensure_db()
        
        cursor = self._collection.find({
            "assistant_id": ObjectId(assistant_id)
        }).sort("order_no", 1)
        
        docs = await cursor.to_list(length=100)
        return [AssistantStep(**doc) for doc in docs]
    
    async def get_by_id(
        self,
        step_id: str,
        assistant_id: str
    ) -> Optional[AssistantStep]:
        """
        Get a specific step by ID.
        
        Args:
            step_id: Step ID
            assistant_id: Assistant ID
            
        Returns:
            AssistantStep or None
        """
        await self._ensure_db()
        
        doc = await self._collection.find_one({
            "_id": ObjectId(step_id),
            "assistant_id": ObjectId(assistant_id)
        })
        
        if doc:
            return AssistantStep(**doc)
        return None
    
    async def update(
        self,
        step_id: str,
        assistant_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[AssistantStep]:
        """
        Update a step.
        
        Args:
            step_id: Step ID
            assistant_id: Assistant ID
            update_data: Fields to update
            
        Returns:
            Updated AssistantStep or None
        """
        await self._ensure_db()
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        result = await self._collection.find_one_and_update(
            {
                "_id": ObjectId(step_id),
                "assistant_id": ObjectId(assistant_id)
            },
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            logger.info(f"Updated step id={step_id} for assistant={assistant_id}")
            return AssistantStep(**result)
        
        return None
    
    async def create_many(
        self,
        steps: List[Dict[str, Any]]
    ) -> List[ObjectId]:
        """
        Create multiple steps.
        
        Args:
            steps: List of step documents
            
        Returns:
            List of inserted IDs
        """
        await self._ensure_db()
        
        if not steps:
            return []
        
        result = await self._collection.insert_many(steps)
        
        logger.info(f"Created {len(result.inserted_ids)} steps")
        
        return result.inserted_ids
    
    async def delete_by_assistant(self, assistant_id: str) -> int:
        """
        Delete all steps for an assistant.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            Number of deleted steps
        """
        await self._ensure_db()
        
        result = await self._collection.delete_many({
            "assistant_id": ObjectId(assistant_id)
        })
        
        return result.deleted_count

