"""Conversation model - represents a dialogue between interlocutor and assistant."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import Field

from app.common.models.base import MongoBaseModel, PyObjectId


class Conversation(MongoBaseModel):
    """
    Conversation between an interlocutor and an assistant.
    
    Stores dialogue state which is updated by the agent.
    One interlocutor can have only one conversation with each assistant.
    """
    
    interlocutor_id: PyObjectId = Field(..., description="Reference to interlocutor")
    assistant_id: PyObjectId = Field(..., description="Reference to assistant")
    connection_id: PyObjectId = Field(..., description="Reference to connection (channel)")
    state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dialogue state (current step, collected data, summaries, etc.)"
    )
    analytic_meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Analytics metadata (respondent profile, scores, tags). Stored as dict, validated as AnalyticMeta."
    )
    is_mock: bool = Field(
        default=False,
        description="True if conversation was created for mock respondents (test snapshots)."
    )
    last_user_message_at: Optional[datetime] = Field(
        default=None,
        description="Denormalized time of the latest inbound user message (follow-up v4).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439012",
                "interlocutor_id": "507f1f77bcf86cd799439011",
                "assistant_id": "507f1f77bcf86cd799439013",
                "connection_id": "507f1f77bcf86cd799439014",
                "state": {
                    "current_step": "survey_question_2",
                    "collected_data": {"q1": "answer1"},
                    "summaries": []
                },
                "analytic_meta": None,
                "created_at": "2025-11-25T10:00:00Z",
                "updated_at": "2025-11-25T10:00:00Z"
            }
        }
    }
    
    def get_agent_metadata(self) -> Dict[str, Any]:
        """
        Get agent metadata from conversation state.
        
        Returns:
            Agent metadata dictionary
        """
        return self.state.get("agent_metadata", {})
    
    def get_current_stage(self) -> Optional[str]:
        """
        Get current stage/step from agent metadata.
        
        Returns:
            Current stage key or None if not set
        """
        return self.get_agent_metadata().get("state")

