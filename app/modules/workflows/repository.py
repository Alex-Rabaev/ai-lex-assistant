"""Repository for workflow execution CRUD operations.

Single repository for ALL workflow types.
Uses MongoDB collection 'workflow_executions'.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import DESCENDING, ReturnDocument

from app.modules.workflows.models.execution import WorkflowExecution, WorkflowStatus

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """Repository for workflow execution database operations.
    
    Handles CRUD operations for WorkflowExecution documents.
    Single repository for all workflow types (not per-type).
    """
    
    def __init__(self):
        """Initialize repository."""
        self._db = None
        self._collection = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["workflow_executions"]
    
    async def create(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Create a new workflow execution record.
        
        Args:
            execution: WorkflowExecution to create
            
        Returns:
            Created WorkflowExecution with generated ID
        """
        await self._ensure_db()
        
        data = execution.model_dump(by_alias=True, exclude={"id"})
        data["created_at"] = datetime.now(timezone.utc)
        data["updated_at"] = datetime.now(timezone.utc)
        
        result = await self._collection.insert_one(data)
        data["_id"] = result.inserted_id
        
        logger.info(
            f"Created workflow execution: "
            f"type={execution.workflow_type}, "
            f"id={result.inserted_id}"
        )
        
        return WorkflowExecution(**data)
    
    async def find_one(self, filter: Dict[str, Any]) -> Optional[WorkflowExecution]:
        """Find a single workflow execution by filter.
        
        Args:
            filter: MongoDB filter dict
            
        Returns:
            WorkflowExecution if found, None otherwise
        """
        await self._ensure_db()
        
        doc = await self._collection.find_one(filter)
        if doc:
            return WorkflowExecution(**doc)
        return None
    
    async def find_many(
        self,
        filter: Dict[str, Any],
        limit: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: int = DESCENDING
    ) -> List[WorkflowExecution]:
        """Find multiple workflow executions by filter.
        
        Args:
            filter: MongoDB filter dict
            limit: Maximum number of results (None = no limit)
            sort_by: Field to sort by (default: created_at)
            sort_order: Sort order (default: DESCENDING)
            
        Returns:
            List of WorkflowExecution objects
        """
        await self._ensure_db()
        
        cursor = self._collection.find(filter).sort(sort_by, sort_order)
        if limit:
            cursor = cursor.limit(limit)
        
        docs = await cursor.to_list(length=limit)
        return [WorkflowExecution(**doc) for doc in docs]
    
    async def get_by_id(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            WorkflowExecution if found, None otherwise
        """
        await self._ensure_db()
        
        try:
            doc = await self._collection.find_one({"_id": ObjectId(execution_id)})
            if doc:
                return WorkflowExecution(**doc)
            return None
        except Exception as e:
            logger.error(f"Error getting execution {execution_id}: {e}")
            return None
    
    async def update_status(
        self,
        execution_id: str,
        status: WorkflowStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None
    ) -> Optional[WorkflowExecution]:
        """Update execution status.
        
        Args:
            execution_id: Execution ID
            status: New status
            started_at: When processing started (optional)
            completed_at: When processing completed (optional)
            duration_ms: Execution duration in ms (optional)
            
        Returns:
            Updated WorkflowExecution or None if not found
        """
        await self._ensure_db()
        
        update_data: Dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc)
        }
        
        if started_at:
            update_data["started_at"] = started_at
        if completed_at:
            update_data["completed_at"] = completed_at
        if duration_ms is not None:
            update_data["duration_ms"] = duration_ms
        
        try:
            result = await self._collection.find_one_and_update(
                {"_id": ObjectId(execution_id)},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER
            )
            
            if result:
                logger.info(f"Updated execution {execution_id} status to {status.value}")
                return WorkflowExecution(**result)
            
            logger.warning(f"Execution not found: {execution_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            return None
    
    async def update_result(
        self,
        execution_id: str,
        result: Dict[str, Any],
        duration_ms: Optional[int] = None
    ) -> Optional[WorkflowExecution]:
        """Update execution result.
        
        Args:
            execution_id: Execution ID
            result: Result data dict
            duration_ms: Optional execution duration in milliseconds
            
        Returns:
            Updated WorkflowExecution or None if not found
        """
        await self._ensure_db()
        
        update_data = {
            "result": result,
            "status": WorkflowStatus.COMPLETED.value,
            "completed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        if duration_ms is not None:
            update_data["duration_ms"] = duration_ms
        
        try:
            doc = await self._collection.find_one_and_update(
                {"_id": ObjectId(execution_id)},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER
            )
            
            if doc:
                logger.info(f"Updated execution {execution_id} with result")
                return WorkflowExecution(**doc)
            
            logger.warning(f"Execution not found: {execution_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error updating result: {e}")
            return None
    
    async def update_error(
        self,
        execution_id: str,
        error: str
    ) -> Optional[WorkflowExecution]:
        """Update execution with error.
        
        Args:
            execution_id: Execution ID
            error: Error message
            
        Returns:
            Updated WorkflowExecution or None if not found
        """
        await self._ensure_db()
        
        try:
            doc = await self._collection.find_one_and_update(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "error_message": error,
                        "status": WorkflowStatus.FAILED.value,
                        "completed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                return_document=ReturnDocument.AFTER
            )
            
            if doc:
                logger.info(f"Updated execution {execution_id} with error: {error[:50]}...")
                return WorkflowExecution(**doc)
            
            logger.warning(f"Execution not found: {execution_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error updating error: {e}")
            return None
