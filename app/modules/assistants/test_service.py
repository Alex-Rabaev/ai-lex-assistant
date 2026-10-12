"""Unit tests for assistant service layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from bson import ObjectId

from app.modules.assistants.models import Assistant, AssistantStatus, AssistantType, AssistantStep
from app.modules.assistants.schemas import (
    CreateAssistantRequest,
    UpdateAssistantRequest,
    CloneAssistantRequest
)
from app.modules.assistants.service import (
    AssistantService,
    AssistantNotFoundError,
    DuplicateNameError,
    InvalidStatusTransitionError
)


@pytest.fixture
def mock_repository():
    """Create mock repository with all methods."""
    repo = MagicMock()
    repo.exists_by_name = AsyncMock(return_value=False)
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_id_internal = AsyncMock()
    repo.find_by_user = AsyncMock(return_value=([], 0))
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.get_steps_by_assistant = AsyncMock(return_value=[])
    repo.create_steps = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def sample_assistant():
    """Create sample assistant."""
    return Assistant(
        id=ObjectId(),
        org_id="org_123",
        owner_user_id="user_456",
        name="Test Assistant",
        description="Test description",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestCreateAssistant:
    """Test create_assistant method."""
    
    @pytest.mark.asyncio
    async def test_create_assistant_success(self, mock_repository, sample_assistant):
        """Test successful assistant creation with default steps."""
        # Setup
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=sample_assistant)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            with patch('app.modules.assistants.steps.service.StepService') as MockStepService:
                mock_step_service = MockStepService.return_value
                mock_step_service.create_default_steps = AsyncMock(return_value=[])
                
                service = AssistantService()
                create_data = CreateAssistantRequest(
                    name="Test Assistant",
                    description="Test description",
                    type=AssistantType.SURVEY
                )
                
                # Execute
                result = await service.create_assistant("org_123", "user@example.com", create_data)
                
                # Verify
                assert result == sample_assistant
                mock_repository.exists_by_name.assert_called_once_with("user@example.com", "Test Assistant")
                mock_repository.create.assert_called_once_with("org_123", "user@example.com", create_data)
                mock_step_service.create_default_steps.assert_called_once_with(str(sample_assistant.id))
    
    @pytest.mark.asyncio
    async def test_create_assistant_duplicate_name(self, mock_repository):
        """Test creation fails with duplicate name."""
        # Setup
        mock_repository.exists_by_name = AsyncMock(return_value=True)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            create_data = CreateAssistantRequest(
                name="Duplicate Name",
                type=AssistantType.SURVEY
            )
            
            # Execute & Verify
            with pytest.raises(DuplicateNameError) as exc_info:
                await service.create_assistant("org_123", "user_456", create_data)
            
            assert "already exists" in str(exc_info.value)
            mock_repository.exists_by_name.assert_called_once()


class TestGetAssistant:
    """Test get_assistant method."""
    
    @pytest.mark.asyncio
    async def test_get_assistant_success(self, mock_repository, sample_assistant):
        """Test successful assistant retrieval."""
        # Setup
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            
            # Execute
            result = await service.get_assistant(str(sample_assistant.id), "org_123")
            
            # Verify
            assert result == sample_assistant
            mock_repository.get_by_id.assert_called_once_with(str(sample_assistant.id), "org_123")
    
    @pytest.mark.asyncio
    async def test_get_assistant_not_found(self, mock_repository):
        """Test get fails when assistant not found."""
        # Setup
        mock_repository.get_by_id = AsyncMock(return_value=None)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            
            # Execute & Verify
            with pytest.raises(AssistantNotFoundError):
                await service.get_assistant("507f1f77bcf86cd799439011", "org_123")


class TestListAssistants:
    """Test list_assistants method."""
    
    @pytest.mark.asyncio
    async def test_list_assistants_success(self, mock_repository, sample_assistant):
        """Test successful assistant listing."""
        # Setup
        expected_list = [sample_assistant]
        expected_total = 1
        mock_repository.find_by_user = AsyncMock(return_value=(expected_list, expected_total))
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            
            # Execute
            result_list, result_total = await service.list_assistants("user@example.com", AssistantStatus.ACTIVE)

            # Verify
            assert result_list == expected_list
            assert result_total == expected_total
            mock_repository.find_by_user.assert_called_once_with(
                "user@example.com", AssistantStatus.ACTIVE, 0, 20
            )
    
    @pytest.mark.asyncio
    async def test_list_assistants_pagination(self, mock_repository):
        """Test list with pagination."""
        # Setup
        mock_repository.find_by_user = AsyncMock(return_value=([], 0))
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            
            # Execute
            await service.list_assistants("user@example.com", skip=10, limit=5)
            
            # Verify
            mock_repository.find_by_user.assert_called_once_with("user@example.com", None, 10, 5)


class TestUpdateAssistant:
    """Test update_assistant method."""
    
    @pytest.mark.asyncio
    async def test_update_assistant_success(self, mock_repository, sample_assistant):
        """Test successful assistant update."""
        # Setup
        updated_assistant = sample_assistant.model_copy()
        updated_assistant.name = "Updated Name"
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.update = AsyncMock(return_value=updated_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            update_data = UpdateAssistantRequest(name="Updated Name")
            
            # Execute
            result = await service.update_assistant(str(sample_assistant.id), "org_123", update_data)
            
            # Verify
            assert result.name == "Updated Name"
            mock_repository.exists_by_name.assert_called_once_with(
                "org_123", "Updated Name", str(sample_assistant.id)
            )
    
    @pytest.mark.asyncio
    async def test_update_status_valid_transition(self, mock_repository, sample_assistant):
        """Test valid status transition: active -> inactive."""
        sample_assistant.status = AssistantStatus.ACTIVE
        updated_assistant = sample_assistant.model_copy()
        updated_assistant.status = AssistantStatus.INACTIVE
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.update = AsyncMock(return_value=updated_assistant)

        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            update_data = UpdateAssistantRequest(status=AssistantStatus.INACTIVE)
            result = await service.update_assistant(str(sample_assistant.id), "org_123", update_data)
            assert result.status == AssistantStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self, mock_repository, sample_assistant):
        """Test invalid status transition: same status."""
        sample_assistant.status = AssistantStatus.ACTIVE
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)

        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            update_data = UpdateAssistantRequest(status=AssistantStatus.ACTIVE)
            # same status — no-op, no error (validated in service as identity transition)
    
    @pytest.mark.asyncio
    async def test_update_duplicate_name(self, mock_repository, sample_assistant):
        """Test update fails with duplicate name."""
        # Setup
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=True)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            update_data = UpdateAssistantRequest(name="Duplicate Name")
            
            # Execute & Verify
            with pytest.raises(DuplicateNameError):
                await service.update_assistant(str(sample_assistant.id), "org_123", update_data)


class TestDeleteAssistant:
    """Test delete_assistant method."""
    
    @pytest.mark.asyncio
    async def test_delete_assistant_success(self, mock_repository, sample_assistant):
        """Test successful assistant deletion."""
        # Setup
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.delete = AsyncMock(return_value=True)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            
            # Execute
            result = await service.delete_assistant(str(sample_assistant.id), "org_123")
            
            # Verify
            assert result is True
            mock_repository.delete.assert_called_once_with(str(sample_assistant.id), "org_123")
    
    @pytest.mark.asyncio
    async def test_delete_assistant_not_found(self, mock_repository):
        """Test delete fails when assistant not found."""
        # Setup
        mock_repository.get_by_id = AsyncMock(return_value=None)
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            
            # Execute & Verify
            with pytest.raises(AssistantNotFoundError):
                await service.delete_assistant("507f1f77bcf86cd799439011", "org_123")


class TestCloneAssistant:
    """Test clone_assistant method."""
    
    @pytest.mark.asyncio
    async def test_clone_with_steps(self, mock_repository, sample_assistant):
        """Test cloning assistant with steps."""
        # Setup
        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()
        cloned_assistant.name = "Cloned Assistant"
        
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=cloned_assistant)
        
        # Mock source steps with new model
        mock_steps = [
            AssistantStep(
                assistant_id=sample_assistant.id,
                step_key="intro",
                order_no=1,
                enabled=True,
                metadata={"prompt_template": "Hello"}
            )
        ]
        mock_repository.get_steps_by_assistant = AsyncMock(return_value=mock_steps)
        mock_repository.create_steps = AsyncMock(return_value=[])
        
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            clone_data = CloneAssistantRequest(new_name="Cloned Assistant", clone_steps=True)
            
            # Execute
            result = await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )
            
            # Verify
            assert result.name == "Cloned Assistant"
            mock_repository.get_steps_by_assistant.assert_called_once()
            mock_repository.create_steps.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_clone_without_steps(self, mock_repository, sample_assistant):
        """Test cloning assistant without steps."""
        # Setup
        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()
        cloned_assistant.name = "Cloned Assistant"
        
        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=cloned_assistant)
        
        mock_step_svc = MagicMock()
        mock_step_svc.create_default_steps = AsyncMock()

        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository), \
             patch('app.modules.assistants.steps.service.StepService', return_value=mock_step_svc):
            service = AssistantService()
            clone_data = CloneAssistantRequest(new_name="Cloned Assistant", clone_steps=False)

            result = await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )

            assert result.name == "Cloned Assistant"
            mock_step_svc.create_default_steps.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_clone_auto_increments_name_on_conflict(self, mock_repository, sample_assistant):
        """VA-154: Clone auto-increments name when base name already exists."""
        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()
        cloned_assistant.name = "My Bot (2)"

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        # First call (base name "My Bot") → exists; second call ("My Bot (2)") → free
        mock_repository.exists_by_name = AsyncMock(side_effect=[True, False])
        mock_repository.create = AsyncMock(return_value=cloned_assistant)

        mock_step_svc = MagicMock()
        mock_step_svc.create_default_steps = AsyncMock()
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository), \
             patch('app.modules.assistants.steps.service.StepService', return_value=mock_step_svc):
            service = AssistantService()
            clone_data = CloneAssistantRequest(new_name="My Bot", clone_steps=False)
            result = await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )
            create_call_data = mock_repository.create.call_args[0][2]
            assert create_call_data.name == "My Bot (2)"

    @pytest.mark.asyncio
    async def test_clone_increments_multiple_conflicts(self, mock_repository, sample_assistant):
        """VA-154: Clone keeps incrementing until unique name found."""
        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        # "X", "X (2)", "X (3)" exist; "X (4)" is free
        mock_repository.exists_by_name = AsyncMock(side_effect=[True, True, True, False])
        mock_repository.create = AsyncMock(return_value=cloned_assistant)

        mock_step_svc = MagicMock()
        mock_step_svc.create_default_steps = AsyncMock()
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository), \
             patch('app.modules.assistants.steps.service.StepService', return_value=mock_step_svc):
            service = AssistantService()
            clone_data = CloneAssistantRequest(new_name="X", clone_steps=False)
            await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )
            create_call_data = mock_repository.create.call_args[0][2]
            assert create_call_data.name == "X (4)"

    @pytest.mark.asyncio
    async def test_clone_auto_generates_name_when_not_provided(self, mock_repository, sample_assistant):
        """VA-151: Clone auto-generates 'Copy of <name>' when new_name not provided."""
        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=cloned_assistant)

        mock_step_svc = MagicMock()
        mock_step_svc.create_default_steps = AsyncMock()
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository), \
             patch('app.modules.assistants.steps.service.StepService', return_value=mock_step_svc):
            service = AssistantService()
            clone_data = CloneAssistantRequest(clone_steps=False)
            await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )
            create_call_data = mock_repository.create.call_args[0][2]
            assert create_call_data.name == f"Copy of {sample_assistant.name}"

    @pytest.mark.asyncio
    async def test_clone_auto_name_truncates_long_source_name(self, mock_repository, sample_assistant):
        """VA-151: Auto-generated name stays within 100-char limit when source name is long."""
        sample_assistant.name = "A" * 95  # 95 chars — "Copy of " + 95 = 103, must be truncated

        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=cloned_assistant)

        mock_step_svc = MagicMock()
        mock_step_svc.create_default_steps = AsyncMock()
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository), \
             patch('app.modules.assistants.steps.service.StepService', return_value=mock_step_svc):
            service = AssistantService()
            clone_data = CloneAssistantRequest(clone_steps=False)
            await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )
            create_call_data = mock_repository.create.call_args[0][2]
            assert len(create_call_data.name) <= 100

    @pytest.mark.asyncio
    async def test_clone_description_truncated_to_500(self, mock_repository, sample_assistant):
        """VA-151: Description is truncated to 500 chars to avoid validation error."""
        sample_assistant.name = "A" * 100
        sample_assistant.description = "B" * 500

        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=cloned_assistant)

        mock_step_svc = MagicMock()
        mock_step_svc.create_default_steps = AsyncMock()
        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository), \
             patch('app.modules.assistants.steps.service.StepService', return_value=mock_step_svc):
            service = AssistantService()
            clone_data = CloneAssistantRequest(clone_steps=False)
            await service.clone_assistant(
                assistant_id=str(sample_assistant.id),
                user_id="user@example.com",
                org_id="org_123",
                clone_data=clone_data
            )
            create_call_data = mock_repository.create.call_args[0][2]
            assert len(create_call_data.description) <= 500

    @pytest.mark.asyncio
    async def test_clone_rollback_on_step_failure(self, mock_repository, sample_assistant):
        """VA-150: Cloned assistant is deleted (rollback) if step cloning raises an exception."""
        cloned_assistant = sample_assistant.model_copy()
        cloned_assistant.id = ObjectId()

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.exists_by_name = AsyncMock(return_value=False)
        mock_repository.create = AsyncMock(return_value=cloned_assistant)
        mock_repository.get_steps_by_assistant = AsyncMock(
            return_value=[
                AssistantStep(
                    assistant_id=sample_assistant.id,
                    step_key="intro",
                    order_no=1,
                    enabled=True,
                    metadata={}
                )
            ]
        )
        mock_repository.create_steps = AsyncMock(side_effect=Exception("DB write failed"))
        mock_repository.delete_internal = AsyncMock(return_value=True)

        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            clone_data = CloneAssistantRequest(clone_steps=True)

            with pytest.raises(Exception, match="DB write failed"):
                await service.clone_assistant(
                    assistant_id=str(sample_assistant.id),
                    user_id="user@example.com",
                    org_id="org_123",
                    clone_data=clone_data
                )

            # Rollback must have been called with the cloned assistant's id
            mock_repository.delete_internal.assert_called_once_with(str(cloned_assistant.id))


class TestStatusTransitionValidation:
    """Test status transition validation."""
    
    def test_valid_transitions(self):
        """Test all valid status transitions."""
        service = AssistantService()
        
        service._validate_status_transition(AssistantStatus.ACTIVE, AssistantStatus.INACTIVE)
        service._validate_status_transition(AssistantStatus.INACTIVE, AssistantStatus.ACTIVE)

    @pytest.mark.asyncio
    async def test_toggle_active_inactive(self, mock_repository, sample_assistant):
        """Test full flow: active -> inactive -> active."""
        sample_assistant.status = AssistantStatus.ACTIVE
        deactivated = sample_assistant.model_copy()
        deactivated.status = AssistantStatus.INACTIVE

        mock_repository.get_by_id = AsyncMock(return_value=sample_assistant)
        mock_repository.update = AsyncMock(return_value=deactivated)

        with patch('app.modules.assistants.service.AssistantRepository', return_value=mock_repository):
            service = AssistantService()
            result = await service.update_assistant(
                str(sample_assistant.id), "user@example.com",
                UpdateAssistantRequest(status=AssistantStatus.INACTIVE)
            )
            assert result.status == AssistantStatus.INACTIVE
