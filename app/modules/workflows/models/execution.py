"""Workflow execution model for tracking workflow state in MongoDB.

WorkflowExecution is the central model for tracking all workflow executions.
Results are stored in the `result` field, not in separate collections.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from app.common.models.base import MongoBaseModel


class WorkflowStatus(str, Enum):
    """Status of workflow execution."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowExecution(MongoBaseModel):
    """Workflow execution record stored in MongoDB.
    
    This is a unified model for ALL workflow types.
    Results (snapshot, profile, etc.) are stored in the `result` field,
    not in separate collections.
    
    Collection: workflow_executions
    """
    
    # Workflow identification
    workflow_type: str = Field(
        ...,
        description="Workflow type identifier (e.g., 'analysis_snapshot', 'analytic_meta')"
    )
    status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING,
        description="Current execution status"
    )
    
    # Input/Output data
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input data specific to workflow type (e.g., assistant_id, include_partial)"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Output data - stores AnalysisSnapshotResult or other schema as dict"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is FAILED"
    )
    
    # Versioning (for snapshots)
    version_name: Optional[str] = Field(
        default=None,
        description="User-defined version name for the execution"
    )
    is_archived: bool = Field(
        default=False,
        description="Whether this execution is archived by user"
    )
    
    # Audit fields
    triggered_by: str = Field(
        ...,
        description="User ID who triggered the workflow"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when processing started"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when processing completed"
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Total execution duration in milliseconds"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "_id": "675a1234567890abcdef1234",
                "workflow_type": "analysis_snapshot",
                "status": "completed",
                "payload": {
                    "assistant_id": "672d1234567890abcdef5678",
                    "include_partial": True
                },
                "result": {
                    "statistics": {"total_respondents": 42},
                    "conclusions": {"summary": "Analysis complete"}
                },
                "error_message": None,
                "version_name": "Q1 2026 Analysis",
                "is_archived": False,
                "triggered_by": "user_abc123",
                "started_at": "2026-02-01T10:00:00Z",
                "completed_at": "2026-02-01T10:05:00Z",
                "duration_ms": 300000,
                "created_at": "2026-02-01T10:00:00Z",
                "updated_at": "2026-02-01T10:05:00Z"
            }
        }
    }
