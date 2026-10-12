"""Request and Response schemas for Assistants API."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.modules.assistants.models import (
    AssistantType, 
    AssistantStatus
)


# ============================================================================
# ASSISTANT SCHEMAS
# ============================================================================

class CreateAssistantRequest(BaseModel):
    """Request schema for creating a new assistant."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Assistant name")
    description: Optional[str] = Field(None, max_length=500, description="Assistant description")
    type: AssistantType = Field(..., description="Assistant type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (communication_style, self_introduction, etc.)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Customer Survey Bot",
                "description": "Collects customer feedback and preferences",
                "type": "survey",
                "metadata": {
                    "communication_style": "Engage in a respectful, friendly manner",
                    "self_introduction": "I am a professional AI assistant"
                }
            }
        }
    )


class UpdateAssistantRequest(BaseModel):
    """Request schema for updating an assistant."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated name")
    description: Optional[str] = Field(None, max_length=500, description="Updated description")
    type: Optional[AssistantType] = Field(None, description="Updated type")
    status: Optional[AssistantStatus] = Field(None, description="Updated status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Bot Name",
                "status": "active",
            }
        }
    )


class AssistantResponse(BaseModel):
    """Response schema for assistant data."""
    
    id: str = Field(..., description="Assistant ID")
    org_id: str = Field(..., description="Organization ID")
    owner_user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Assistant name")
    description: Optional[str] = Field(None, description="Description")
    type: AssistantType = Field(..., description="Assistant type")
    status: AssistantStatus = Field(..., description="Current status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "org_id": "org_123",
                "owner_user_id": "user_456",
                "name": "Customer Survey Bot",
                "description": "Collects customer feedback",
                "type": "survey",
                "status": "active",
                "metadata": {
                    "communication_style": "Friendly and professional",
                    "self_introduction": "I am your survey assistant"
                },
                "created_at": "2025-10-29T10:00:00",
                "updated_at": "2025-10-29T10:00:00"
            }
        }
    )


class AssistantListResponse(BaseModel):
    """Response schema for list of assistants with pagination."""
    
    items: List[AssistantResponse] = Field(..., description="List of assistants")
    total: int = Field(..., description="Total count")
    skip: int = Field(0, description="Items skipped")
    limit: int = Field(20, description="Items per page")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 42,
                "skip": 0,
                "limit": 20
            }
        }
    )


# ============================================================================
# UTILITY SCHEMAS
# ============================================================================

class CloneAssistantRequest(BaseModel):
    """Request schema for cloning an assistant."""

    new_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Name for the cloned assistant. Auto-generated as 'Copy of <name>' if not provided."
    )
    clone_steps: bool = Field(True, description="Whether to clone steps as well")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_name": "Customer Survey Bot (Copy)",
                "clone_steps": True
            }
        }
    )
