"""Schemas for assistant steps API endpoints."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ParseQuestionsRequest(BaseModel):
    """Request to parse free-form text into a list of individual questions."""
    
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Free-form text containing questions to parse"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "1. What is your budget? 2. What is your timeline? 3. What features are most important?"
            }
        }
    }


class ParseQuestionsResponse(BaseModel):
    """Response with parsed list of questions."""
    
    questions: List[str] = Field(
        ...,
        description="List of individual questions extracted from the text"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "questions": [
                    "What is your budget?",
                    "What is your timeline?",
                    "What features are most important?"
                ]
            }
        }
    }


class UpdateStepRequest(BaseModel):
    """Request to update an assistant step."""
    
    enabled: Optional[bool] = Field(
        None,
        description="Whether this step is enabled"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Step configuration and prompts (prompt_template, etc.)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "enabled": True,
                "metadata": {
                    "prompt_template": "Custom instructions for this step..."
                }
            }
        }
    }


class StepResponse(BaseModel):
    """Response model for assistant step."""
    
    id: str = Field(..., description="Step ID")
    assistant_id: str = Field(..., description="Parent assistant ID")
    step_key: str = Field(..., description="Step key identifier")
    order_no: int = Field(..., description="Order in the flow")
    enabled: bool = Field(..., description="Whether step is enabled")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Step configuration")
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "507f1f77bcf86cd799439012",
                "assistant_id": "507f1f77bcf86cd799439011",
                "step_key": "questionnaire",
                "order_no": 4,
                "enabled": True,
                "metadata": {
                    "intro_prompt": "Custom intro...",
                    "specific_questions": "Q1?\nQ2?"
                },
                "created_at": "2025-10-29T10:00:00",
                "updated_at": "2025-10-29T10:00:00"
            }
        }
    }
    
    @classmethod
    def from_model(cls, step) -> "StepResponse":
        """Convert AssistantStep model to response."""
        return cls(
            id=str(step.id),
            assistant_id=str(step.assistant_id),
            step_key=step.step_key,
            order_no=step.order_no,
            enabled=step.enabled,
            metadata=step.metadata or {},
            created_at=step.created_at,
            updated_at=step.updated_at
        )


class StepListResponse(BaseModel):
    """Response for list of assistant steps."""
    
    steps: List[StepResponse]
    total: int
    assistant_id: str
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "steps": [
                    {
                        "id": "507f1f77bcf86cd799439012",
                        "assistant_id": "507f1f77bcf86cd799439011",
                        "step_key": "lang",
                        "order_no": 1,
                        "enabled": True,
                        "metadata": {},
                        "created_at": "2025-10-29T10:00:00",
                        "updated_at": "2025-10-29T10:00:00"
                    }
                ],
                "total": 6,
                "assistant_id": "507f1f77bcf86cd799439011"
            }
        }
    }
