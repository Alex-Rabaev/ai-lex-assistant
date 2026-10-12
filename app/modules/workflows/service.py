"""Service layer for workflow execution management.

Provides GENERIC business logic for launching and querying workflows.
Uses WorkflowRepository for MongoDB persistence and
TemporalClientManager for workflow orchestration.

This service does NOT contain workflow-specific logic.
Concrete workflow launch methods live in domain services
(e.g., AnalysisService.create_snapshot).
"""

import logging
from typing import Any, Dict, List, Optional

from temporalio.exceptions import WorkflowAlreadyStartedError

from app.modules.workflows.models.execution import WorkflowExecution, WorkflowStatus
from app.modules.workflows.repository import WorkflowRepository
from app.modules.workflows.temporal_client import TemporalClientManager

logger = logging.getLogger(__name__)


class WorkflowService:
    """Generic service for workflow execution management.
    
    Provides methods to:
    - Start any workflow via Temporal Client
    - Retrieve execution state from MongoDB
    - Query workflow progress from Temporal
    - Update execution status
    
    Does NOT contain workflow-specific logic (e.g., snapshot, profile).
    Domain services use this service to launch their workflows.
    """
    
    def __init__(
        self,
        repository: Optional[WorkflowRepository] = None,
        temporal_client: Optional[TemporalClientManager] = None
    ):
        """Initialize service.
        
        Args:
            repository: Optional WorkflowRepository instance
            temporal_client: Optional TemporalClientManager instance
        """
        self.repository = repository or WorkflowRepository()
        self.temporal_client = temporal_client or TemporalClientManager()
    
    async def start_workflow(
        self,
        workflow_name: str,
        workflow_id: str,
        workflow_type: str,
        input_data: Any,
        task_queue: str,
        user_id: str,
        payload: Optional[Dict[str, Any]] = None,
        version_name: Optional[str] = None
    ) -> str:
        """Start a workflow via Temporal.
        
        Creates a WorkflowExecution record in MongoDB, then starts
        the Temporal Workflow. Deduplication is handled natively
        by Temporal via unique Workflow IDs.
        
        Args:
            workflow_name: Temporal Workflow name (e.g., "SnapshotWorkflow")
            workflow_id: Unique Temporal Workflow ID
            workflow_type: Type for MongoDB record (e.g., "analysis_snapshot")
            input_data: Workflow input (dataclass)
            task_queue: Temporal Task Queue name
            user_id: ID of user triggering the workflow
            payload: Optional payload dict for MongoDB record
            version_name: Optional user-defined version name
            
        Returns:
            execution_id (str)
            
        Raises:
            RuntimeError: If Temporal connection fails
        """
        # Create execution record in MongoDB
        execution = WorkflowExecution(
            workflow_type=workflow_type,
            status=WorkflowStatus.PENDING,
            payload=payload or {},
            triggered_by=user_id,
            version_name=version_name
        )
        
        created = await self.repository.create(execution)
        execution_id = str(created.id)
        
        # Inject execution_id into input_data if it has the attribute
        if hasattr(input_data, 'execution_id'):
            input_data.execution_id = execution_id
        
        # Start Temporal Workflow
        try:
            client = await self.temporal_client.get_client()
            
            await client.start_workflow(
                workflow_name,
                input_data,
                id=workflow_id,
                task_queue=task_queue,
            )
            
            logger.info(
                f"Started workflow: "
                f"name={workflow_name}, "
                f"workflow_id={workflow_id}, "
                f"execution_id={execution_id}"
            )
            
        except WorkflowAlreadyStartedError:
            # Workflow already running — not an error
            logger.info(
                f"Workflow already running: workflow_id={workflow_id}"
            )
            
        except Exception as e:
            await self.repository.update_error(
                execution_id,
                f"Failed to start Temporal workflow: {e}"
            )
            logger.error(
                f"Failed to start workflow: "
                f"execution_id={execution_id}, error={e}"
            )
            raise
        
        return execution_id
    
    async def get_execution(
        self,
        execution_id: str
    ) -> Optional[WorkflowExecution]:
        """Retrieve a workflow execution by ID from MongoDB.
        
        Args:
            execution_id: ID of the execution to retrieve
            
        Returns:
            WorkflowExecution if found, None otherwise
        """
        execution = await self.repository.get_by_id(execution_id)
        
        if execution:
            logger.debug(f"Retrieved workflow execution: id={execution_id}")
        else:
            logger.debug(f"Workflow execution not found: id={execution_id}")
        
        return execution
    
    async def get_executions(
        self,
        workflow_type: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[WorkflowExecution]:
        """Retrieve workflow executions with filtering from MongoDB.
        
        Args:
            workflow_type: Type of workflow to filter by
            filters: Additional filters (status, triggered_by, etc.)
            
        Returns:
            List of matching WorkflowExecution records
        """
        query: Dict[str, Any] = {"workflow_type": workflow_type}
        
        if filters:
            if "status" in filters:
                status = filters["status"]
                if isinstance(status, WorkflowStatus):
                    query["status"] = status.value
                else:
                    query["status"] = status
            
            if "triggered_by" in filters:
                query["triggered_by"] = filters["triggered_by"]
            
            if "payload" in filters and isinstance(filters["payload"], dict):
                for key, value in filters["payload"].items():
                    query[f"payload.{key}"] = value
        
        limit = filters.get("limit", 100) if filters else 100
        
        executions = await self.repository.find_many(
            filter=query,
            limit=limit,
            sort_by="created_at",
            sort_order=-1
        )
        
        logger.debug(
            f"Retrieved {len(executions)} workflow executions: "
            f"type={workflow_type}"
        )
        
        return executions
    
    async def get_workflow_progress(
        self,
        workflow_id: str
    ) -> dict:
        """Query Temporal Workflow for current progress.
        
        Uses Temporal's @workflow.query to read workflow state
        without modifying it.
        
        Args:
            workflow_id: Temporal Workflow ID
            
        Returns:
            Progress dict from workflow query
        """
        try:
            client = await self.temporal_client.get_client()
            handle = client.get_workflow_handle(workflow_id)
            progress = await handle.query("get_progress")
            return progress
        except Exception as e:
            logger.error(
                f"Failed to query workflow progress: "
                f"workflow_id={workflow_id}, error={e}"
            )
            return {"error": str(e)}
    
    async def update_execution_status(
        self,
        execution_id: str,
        status: WorkflowStatus
    ) -> WorkflowExecution:
        """Update the status of a workflow execution.
        
        Args:
            execution_id: ID of the execution to update
            status: New status value
            
        Returns:
            Updated WorkflowExecution
            
        Raises:
            ValueError: If execution not found
        """
        execution = await self.repository.update_status(execution_id, status)
        
        if not execution:
            raise ValueError(f"Workflow execution not found: {execution_id}")
        
        logger.info(
            f"Updated workflow execution status: "
            f"id={execution_id}, status={status.value}"
        )
        
        return execution
    
    async def complete_execution(
        self,
        execution_id: str,
        result: Dict[str, Any],
        duration_ms: int
    ) -> Optional[WorkflowExecution]:
        """Mark execution as completed with result.
        
        Args:
            execution_id: ID of the execution
            result: Workflow output data
            duration_ms: Execution duration in milliseconds
            
        Returns:
            Updated WorkflowExecution or None if not found
        """
        execution = await self.repository.update_result(
            execution_id, result, duration_ms
        )
        
        if execution:
            logger.info(
                f"Workflow execution completed: "
                f"id={execution_id}, duration_ms={duration_ms}"
            )
        else:
            logger.error(f"Failed to complete execution: id={execution_id}")
        
        return execution
    
    async def fail_execution(
        self,
        execution_id: str,
        error_message: str
    ) -> Optional[WorkflowExecution]:
        """Mark execution as failed with error message.
        
        Args:
            execution_id: ID of the execution
            error_message: Error description
            
        Returns:
            Updated WorkflowExecution or None if not found
        """
        execution = await self.repository.update_error(
            execution_id, error_message
        )
        
        if execution:
            logger.info(
                f"Workflow execution failed: "
                f"id={execution_id}, error={error_message}"
            )
        else:
            logger.error(f"Failed to update execution error: id={execution_id}")
        
        return execution
