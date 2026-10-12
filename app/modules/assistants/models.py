"""Assistant and AssistantStep models."""

from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.common.models.base import MongoBaseModel, PyObjectId


class FollowUpConfig(BaseModel):
    """Follow-up reminder configuration for an assistant.

    When enabled, sends AI-generated reminders to respondents
    who have abandoned a survey after idle_threshold_hours.
    """
    enabled: bool = Field(True, description="Whether follow-ups are enabled")
    idle_threshold_hours: int = Field(23, ge=1, le=168, description="Hours of inactivity before reminder (1-168)")
    max_attempts: int = Field(1, ge=1, le=10, description="Max reminder attempts per conversation (1-10)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "idle_threshold_hours": 23,
                "max_attempts": 1
            }
        }
    )


class AssistantType(str, Enum):
    """Types of assistants."""
    SURVEY = "survey"
    FAQ = "faq"
    SUPPORT = "support"


class AssistantStatus(str, Enum):
    """Assistant statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Assistant(MongoBaseModel):
    """Assistant model - main entity.
    
    For Survey type assistants, metadata may contain:
    - communication_style: str
    - self_introduction: str
    """
    
    org_id: str = Field(..., description="Organization ID")
    owner_user_id: str = Field(..., description="User who created the assistant")
    name: str = Field(..., min_length=1, max_length=100, description="Assistant name")
    description: Optional[str] = Field(None, max_length=500)
    type: AssistantType = Field(AssistantType.SURVEY, description="Type of assistant")
    status: AssistantStatus = Field(AssistantStatus.ACTIVE, description="Current status")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    follow_up_config: Optional[FollowUpConfig] = Field(
        None,
        description="Follow-up reminder configuration (enabled by default when None)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "org_id": "org_123",
                "owner_user_id": "user_456",
                "name": "Customer Survey Bot",
                "description": "Collects customer feedback",
                "type": "survey",
                "status": "active",
                "metadata": {
                    "communication_style": "Engage in a respectful, friendly manner",
                    "self_introduction": "I am a professional AI assistant"
                },
                "created_at": "2025-10-29T10:00:00",
                "updated_at": "2025-10-29T10:00:00"
            }
        }
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate assistant name."""
        if not v or not v.strip():
            raise ValueError("Assistant name cannot be empty")
        return v.strip()


class AssistantStep(MongoBaseModel):
    """Assistant step model - defines dialogue flow.
    
    Simplified model: step configuration and prompts are stored in metadata.
    Agent-specific logic (validation, configs) is handled by the agent service.
    
    For Survey type metadata fields:
    - default_language: (lang step) language when step is disabled
    - intro_prompt, specific_questions (text), survey_goal: (questionnaire step)
    - info_to_collect: (additional_info step)
    - closing_generation_prompt: (closing step)
    """
    
    assistant_id: PyObjectId = Field(..., description="Reference to parent assistant")
    step_key: str = Field(..., description="Unique step identifier (e.g., 'lang', 'intro')")
    order_no: int = Field(..., ge=1, le=100, description="Order in the flow")
    enabled: bool = Field(True, description="Whether this step is enabled")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Step configuration and prompts")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439012",
                "assistant_id": "507f1f77bcf86cd799439011",
                "step_key": "questionnaire",
                "order_no": 4,
                "enabled": True,
                "metadata": {
                    "intro_prompt": "This survey will help us find the best option for you.",
                    "specific_questions": "What is your budget?\nWhat is your timeline?",
                    "survey_goal": "Understand customer needs"
                },
                "created_at": "2025-10-29T10:00:00",
                "updated_at": "2025-10-29T10:00:00"
            }
        }
    )
    
    @field_validator('step_key')
    @classmethod
    def validate_step_key(cls, v):
        """Validate step key format."""
        if not v or not v.strip():
            raise ValueError("Step key cannot be empty")
        # Only allow alphanumeric and underscore
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Step key must be alphanumeric with underscores only")
        return v.lower()
