"""Unit tests for steps schemas."""

import pytest
from datetime import datetime, timezone
from bson import ObjectId

from app.modules.assistants.steps.schemas import (
    UpdateStepRequest,
    StepResponse,
    StepListResponse
)
from app.modules.assistants.models import AssistantStep


class TestUpdateStepRequest:
    """Test cases for UpdateStepRequest schema."""
    
    def test_valid_update_request_with_enabled(self):
        """Test creating a valid update request with enabled flag."""
        data = {
            "enabled": True,
            "metadata": {"prompt_template": "Test prompt"}
        }
        
        request = UpdateStepRequest(**data)
        
        assert request.enabled == True
        assert request.metadata["prompt_template"] == "Test prompt"
    
    def test_valid_update_request_metadata_only(self):
        """Test creating update request with only metadata."""
        data = {
            "metadata": {
                "intro_prompt": "Please tell me about your needs",
                "specific_questions": "Q1?\nQ2?"
            }
        }
        
        request = UpdateStepRequest(**data)
        
        assert request.enabled is None
        assert request.metadata["intro_prompt"] == "Please tell me about your needs"
        assert "Q1?" in request.metadata["specific_questions"]
    
    def test_valid_update_request_enabled_only(self):
        """Test creating update request with only enabled flag."""
        request = UpdateStepRequest(enabled=False)
        
        assert request.enabled == False
        assert request.metadata is None


class TestStepResponse:
    """Test cases for StepResponse schema."""
    
    def test_from_model_conversion(self):
        """Test converting AssistantStep model to response."""
        # Create a sample step with new model
        step = AssistantStep(
            id=ObjectId(),
            assistant_id=ObjectId(),
            step_key="profile",
            order_no=3,
            enabled=True,
            metadata={"prompt_template": "Tell me about yourself", "custom": "data"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Convert to response
        response = StepResponse.from_model(step)
        
        # Assert
        assert response.id == str(step.id)
        assert response.assistant_id == str(step.assistant_id)
        assert response.step_key == "profile"
        assert response.order_no == 3
        assert response.enabled == True
        assert response.metadata["custom"] == "data"
        assert isinstance(response.created_at, datetime)
        assert isinstance(response.updated_at, datetime)
    
    def test_response_serialization(self):
        """Test that response can be serialized to dict/JSON."""
        step = AssistantStep(
            id=ObjectId(),
            assistant_id=ObjectId(),
            step_key="lang",
            order_no=1,
            enabled=True,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        response = StepResponse.from_model(step)
        response_dict = response.model_dump()
        
        assert isinstance(response_dict, dict)
        assert "id" in response_dict
        assert "assistant_id" in response_dict
        assert response_dict["step_key"] == "lang"
        assert response_dict["order_no"] == 1
        assert response_dict["enabled"] == True


class TestStepListResponse:
    """Test cases for StepListResponse schema."""
    
    def test_list_response_creation(self):
        """Test creating a step list response."""
        # Create sample steps
        steps = []
        step_keys = ["lang", "intro", "profile"]
        for i in range(3):
            step = AssistantStep(
                id=ObjectId(),
                assistant_id=ObjectId(),
                step_key=step_keys[i],
                order_no=i + 1,
                enabled=True,
                metadata={"prompt_template": f"Question {i}"},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            steps.append(StepResponse.from_model(step))
        
        # Create list response
        list_response = StepListResponse(
            steps=steps,
            total=3,
            assistant_id=str(ObjectId())
        )
        
        # Assert
        assert len(list_response.steps) == 3
        assert list_response.total == 3
        assert isinstance(list_response.assistant_id, str)
        assert list_response.steps[0].order_no == 1
        assert list_response.steps[2].metadata["prompt_template"] == "Question 2"
