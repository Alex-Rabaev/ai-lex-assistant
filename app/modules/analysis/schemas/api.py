"""API request/response schemas for analysis endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateSnapshotRequest(BaseModel):
    """Request body for POST /analysis/snapshot."""
    force_recalculate: bool = Field(
        default=False,
        description="Force recalculation of all profiles"
    )
    include_partial: bool = Field(
        default=True,
        description="Include partial (incomplete) conversations"
    )
    include_mock: bool = Field(
        default=False,
        description="Include mock respondents (test snapshot). If False, only real conversations."
    )
    version_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="User-defined version name (e.g., 'Q1 2026')"
    )


class SnapshotResponse(BaseModel):
    """Response for snapshot endpoints."""
    id: str = Field(..., description="Execution ID")
    workflow_type: str = Field(default="analysis_snapshot")
    status: str = Field(..., description="Execution status")
    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = Field(default=None, description="Snapshot result")
    error_message: Optional[str] = Field(default=None)
    version_name: Optional[str] = Field(default=None)
    is_archived: bool = Field(default=False)
    include_mock: bool = Field(
        default=False,
        description="True if this snapshot was run with mock respondents (test snapshot)"
    )
    triggered_by: str = Field(..., description="User who triggered")
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class SnapshotListResponse(BaseModel):
    """Response for snapshot list endpoint."""
    snapshots: List[SnapshotResponse]
    total: int


class SnapshotCreatedResponse(BaseModel):
    """Response for POST snapshot (async start)."""
    execution_id: str = Field(..., description="Execution ID")
    status: str = Field(default="pending", description="Initial status")


class UpdateSnapshotRequest(BaseModel):
    """Request body for PATCH snapshot."""
    version_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Update version name"
    )
    is_archived: Optional[bool] = Field(
        default=None,
        description="Archive/unarchive snapshot"
    )


class ProfileResponse(BaseModel):
    """Response for analytic_meta endpoints."""
    conversation_id: str
    analytic_meta: Optional[Dict[str, Any]] = Field(default=None)
    is_mock: bool = Field(
        default=False,
        description="True if this profile is for a mock (test) respondent"
    )
    sufficient_data: bool = Field(
        default=True,
        description="False if data_completeness or analysis_confidence < 0.25"
    )


class ProfileListResponse(BaseModel):
    """Response for listing profiles by assistant."""
    profiles: List[ProfileResponse]
    total: int


class MockRespondentsRequest(BaseModel):
    """Request body for POST mock-respondents."""
    count: int = Field(default=10, ge=1, le=100, description="Number of mock respondents")
    language: str = Field(default="en", max_length=10, description="Language code for dialogues")
    include_abandoned: bool = Field(default=True, description="Include abandoned (incomplete) conversations")


class MockRespondentsResponse(BaseModel):
    """Response for POST mock-respondents."""
    created: int
    conversation_ids: List[str]


class MockRespondentsDeleteResponse(BaseModel):
    """Response for DELETE mock-respondents."""
    deleted: int = Field(..., description="Number of mock conversations deleted")
