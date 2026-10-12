"""Unit tests for steps service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone

from app.modules.assistants.steps.service import StepService
from app.modules.assistants.steps.schemas import UpdateStepRequest
from app.modules.assistants.models import AssistantStep
from app.modules.agents.survey_agent.config import SurveyStepKey


@pytest.fixture
def mock_step_repo():
    """Create mock step repository."""
    repo = MagicMock()
    repo.get_by_assistant = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    repo.create_many = AsyncMock()
    return repo


@pytest.fixture
def mock_assistant_repo():
    """Create mock assistant repository."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def sample_assistant():
    """Sample assistant for testing."""
    return MagicMock(
        id=ObjectId(),
        org_id="org_123",
        owner_user_id="user_456",
        name="Test Assistant"
    )


@pytest.fixture
def sample_step():
    """Sample step for testing with new model."""
    return AssistantStep(
        id=ObjectId(),
        assistant_id=ObjectId(),
        step_key="profile",
        order_no=3,
        enabled=True,
        metadata={"prompt_template": "Tell me about yourself"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestStepService:
    """Test cases for StepService."""
    
    @pytest.mark.asyncio
    async def test_get_assistant_steps(self, mock_step_repo, mock_assistant_repo, sample_assistant):
        """Test getting all steps for an assistant."""
        # Setup
        assistant_id = str(ObjectId())
        user_id = "user@example.com"
        
        mock_assistant_repo.get_by_id = AsyncMock(return_value=sample_assistant)
        
        sample_steps = [
            AssistantStep(
                id=ObjectId(),
                assistant_id=ObjectId(assistant_id),
                step_key="lang",
                order_no=1,
                enabled=True,
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        ]
        mock_step_repo.get_by_assistant = AsyncMock(return_value=sample_steps)
        
        # Create service
        step_service = StepService()
        step_service._step_repo = mock_step_repo
        step_service._assistant_repo = mock_assistant_repo
        
        # Execute
        steps = await step_service.get_assistant_steps(assistant_id, user_id)
        
        # Assert
        assert len(steps) == 1
        assert isinstance(steps[0], AssistantStep)
        assert steps[0].step_key == "lang"
        assert steps[0].order_no == 1
        mock_assistant_repo.get_by_id.assert_called_once_with(assistant_id, user_id)
        mock_step_repo.get_by_assistant.assert_called_once_with(assistant_id)
    
    @pytest.mark.asyncio
    async def test_get_assistant_steps_not_found(self, mock_step_repo, mock_assistant_repo):
        """Test getting steps for non-existent assistant."""
        # Setup
        assistant_id = str(ObjectId())
        user_id = "user@example.com"
        
        mock_assistant_repo.get_by_id = AsyncMock(return_value=None)
        
        # Create service
        step_service = StepService()
        step_service._step_repo = mock_step_repo
        step_service._assistant_repo = mock_assistant_repo
        
        # Execute & Assert
        with pytest.raises(ValueError, match=f"Assistant {assistant_id} not found"):
            await step_service.get_assistant_steps(assistant_id, user_id)
    
    @pytest.mark.asyncio
    async def test_update_step_metadata(self, mock_step_repo, mock_assistant_repo, sample_assistant, sample_step):
        """Test updating a step's metadata."""
        # Setup
        assistant_id = str(ObjectId())
        step_id = str(ObjectId())
        user_id = "user@example.com"
        
        update_data = UpdateStepRequest(
            metadata={"prompt_template": "New prompt template"}
        )
        
        mock_assistant_repo.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_step_repo.get_by_id = AsyncMock(return_value=sample_step)
        
        updated_step = AssistantStep(
            id=ObjectId(step_id),
            assistant_id=ObjectId(assistant_id),
            step_key="profile",
            order_no=3,
            enabled=True,
            metadata={"prompt_template": "New prompt template"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        mock_step_repo.update = AsyncMock(return_value=updated_step)
        
        # Create service
        step_service = StepService()
        step_service._step_repo = mock_step_repo
        step_service._assistant_repo = mock_assistant_repo
        
        # Execute
        result = await step_service.update_step(
            assistant_id, step_id, user_id, update_data
        )
        
        # Assert
        assert result is not None
        assert result.metadata["prompt_template"] == "New prompt template"
        mock_step_repo.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_step_enabled(self, mock_step_repo, mock_assistant_repo, sample_assistant, sample_step):
        """Test updating a step's enabled status."""
        # Setup
        assistant_id = str(ObjectId())
        step_id = str(ObjectId())
        user_id = "user@example.com"
        
        update_data = UpdateStepRequest(enabled=False)
        
        mock_assistant_repo.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_step_repo.get_by_id = AsyncMock(return_value=sample_step)
        
        updated_step = sample_step.model_copy()
        updated_step.enabled = False
        mock_step_repo.update = AsyncMock(return_value=updated_step)
        
        # Create service
        step_service = StepService()
        step_service._step_repo = mock_step_repo
        step_service._assistant_repo = mock_assistant_repo
        
        # Execute
        result = await step_service.update_step(
            assistant_id, step_id, user_id, update_data
        )
        
        # Assert
        assert result.enabled == False
    
    @pytest.mark.asyncio
    async def test_cannot_disable_mandatory_step(self, mock_step_repo, mock_assistant_repo, sample_assistant):
        """Test that mandatory steps cannot be disabled."""
        # Setup
        assistant_id = str(ObjectId())
        step_id = str(ObjectId())
        user_id = "user@example.com"
        
        # Create a mandatory step (questionnaire)
        mandatory_step = AssistantStep(
            id=ObjectId(step_id),
            assistant_id=ObjectId(assistant_id),
            step_key="questionnaire",  # This is a mandatory step
            order_no=4,
            enabled=True,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        update_data = UpdateStepRequest(enabled=False)
        
        mock_assistant_repo.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_step_repo.get_by_id = AsyncMock(return_value=mandatory_step)
        
        # Create service
        step_service = StepService()
        step_service._step_repo = mock_step_repo
        step_service._assistant_repo = mock_assistant_repo
        
        # Execute & Assert
        with pytest.raises(ValueError, match="mandatory and cannot be disabled"):
            await step_service.update_step(
                assistant_id, step_id, user_id, update_data
            )
    
    @pytest.mark.asyncio
    async def test_create_default_steps(self, mock_step_repo):
        """Test creating default steps for a new assistant."""
        # Setup
        assistant_id = str(ObjectId())
        
        inserted_ids = [ObjectId() for _ in range(6)]  # Now 6 steps
        mock_step_repo.create_many = AsyncMock(return_value=inserted_ids)
        
        # Create service
        step_service = StepService()
        step_service._step_repo = mock_step_repo
        step_service._assistant_repo = MagicMock()
        
        # Execute
        result = await step_service.create_default_steps(assistant_id)
        
        # Assert
        assert len(result) == 6
        mock_step_repo.create_many.assert_called_once()
        
        # Verify the inserted documents
        call_args = mock_step_repo.create_many.call_args[0][0]
        assert len(call_args) == 6
        
        # Check step keys
        step_keys = [step["step_key"] for step in call_args]
        assert step_keys == [
            SurveyStepKey.LANG.value,
            SurveyStepKey.INTRO.value,
            SurveyStepKey.PROFILE.value,
            SurveyStepKey.QUESTIONNAIRE.value,
            SurveyStepKey.ADDITIONAL_INFO.value,
            SurveyStepKey.CLOSING.value
        ]
        
        # Check order numbers
        order_numbers = [step["order_no"] for step in call_args]
        assert order_numbers == [1, 2, 3, 4, 5, 6]
        
        # Check enabled flags
        enabled_flags = [step["enabled"] for step in call_args]
        # LANG=True, INTRO=True, PROFILE=False, QUESTIONNAIRE=True, ADDITIONAL_INFO=False, CLOSING=True
        assert enabled_flags == [True, True, False, True, False, True]
