"""Unit tests for WorkflowService."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from temporalio.exceptions import WorkflowAlreadyStartedError

from app.modules.workflows.service import WorkflowService
from app.modules.workflows.models.execution import WorkflowExecution, WorkflowStatus
from app.modules.workflows.models.params import SnapshotInput


class TestWorkflowServiceStartWorkflow:
    """Tests for WorkflowService.start_workflow method."""
    
    @pytest.fixture
    def mock_repository(self):
        repo = MagicMock()
        repo.create = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_temporal_client(self):
        manager = MagicMock()
        client = MagicMock()
        client.start_workflow = AsyncMock()
        manager.get_client = AsyncMock(return_value=client)
        return manager, client
    
    @pytest.fixture
    def service(self, mock_repository, mock_temporal_client):
        manager, _ = mock_temporal_client
        return WorkflowService(
            repository=mock_repository,
            temporal_client=manager
        )
    
    @pytest.fixture
    def sample_input(self):
        return SnapshotInput(
            assistant_id="asst_123",
            execution_id="exec_456"
        )
    
    @pytest.mark.asyncio
    async def test_start_workflow_creates_execution(
        self, service, mock_repository, mock_temporal_client, sample_input
    ):
        """Test that start_workflow creates execution in MongoDB."""
        _, client = mock_temporal_client
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=ObjectId(),
                workflow_type="analysis_snapshot",
                status=WorkflowStatus.PENDING,
                payload={"assistant_id": "asst_123"},
                triggered_by="user_456"
            )
        )
        
        await service.start_workflow(
            workflow_name="SnapshotWorkflow",
            workflow_id="snapshot-asst_123-exec_456",
            workflow_type="analysis_snapshot",
            input_data=sample_input,
            task_queue="analysis-workflows",
            user_id="user_456",
            payload={"assistant_id": "asst_123"}
        )
        
        mock_repository.create.assert_called_once()
        call_arg = mock_repository.create.call_args[0][0]
        assert call_arg.workflow_type == "analysis_snapshot"
        assert call_arg.triggered_by == "user_456"
    
    @pytest.mark.asyncio
    async def test_start_workflow_starts_temporal(
        self, service, mock_repository, mock_temporal_client, sample_input
    ):
        """Test that start_workflow starts Temporal workflow."""
        _, client = mock_temporal_client
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=ObjectId(),
                workflow_type="analysis_snapshot",
                status=WorkflowStatus.PENDING,
                payload={},
                triggered_by="user_456"
            )
        )
        
        await service.start_workflow(
            workflow_name="SnapshotWorkflow",
            workflow_id="snapshot-asst_123-exec_456",
            workflow_type="analysis_snapshot",
            input_data=sample_input,
            task_queue="analysis-workflows",
            user_id="user_456"
        )
        
        client.start_workflow.assert_called_once()
        call_args = client.start_workflow.call_args
        assert call_args[0][0] == "SnapshotWorkflow"
        assert call_args[0][1] == sample_input
        assert call_args[1]["id"] == "snapshot-asst_123-exec_456"
        assert call_args[1]["task_queue"] == "analysis-workflows"
    
    @pytest.mark.asyncio
    async def test_start_workflow_returns_execution_id(
        self, service, mock_repository, mock_temporal_client, sample_input
    ):
        """Test that start_workflow returns execution_id."""
        _, client = mock_temporal_client
        execution_id = ObjectId()
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=execution_id,
                workflow_type="analysis_snapshot",
                status=WorkflowStatus.PENDING,
                payload={},
                triggered_by="user_456"
            )
        )
        
        result = await service.start_workflow(
            workflow_name="SnapshotWorkflow",
            workflow_id="snapshot-asst_123",
            workflow_type="analysis_snapshot",
            input_data=sample_input,
            task_queue="analysis-workflows",
            user_id="user_456"
        )
        
        assert result == str(execution_id)
    
    @pytest.mark.asyncio
    async def test_start_workflow_handles_already_started(
        self, service, mock_repository, mock_temporal_client, sample_input
    ):
        """Test that WorkflowAlreadyStartedError is handled gracefully."""
        _, client = mock_temporal_client
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=ObjectId(),
                workflow_type="analysis_snapshot",
                status=WorkflowStatus.PENDING,
                payload={},
                triggered_by="user_456"
            )
        )
        client.start_workflow = AsyncMock(
            side_effect=WorkflowAlreadyStartedError(
                "snapshot-asst_123", "SnapshotWorkflow"
            )
        )
        
        # Should not raise
        result = await service.start_workflow(
            workflow_name="SnapshotWorkflow",
            workflow_id="snapshot-asst_123",
            workflow_type="analysis_snapshot",
            input_data=sample_input,
            task_queue="analysis-workflows",
            user_id="user_456"
        )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_start_workflow_handles_temporal_failure(
        self, service, mock_repository, mock_temporal_client, sample_input
    ):
        """Test that Temporal failure updates execution as failed."""
        _, client = mock_temporal_client
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=ObjectId(),
                workflow_type="analysis_snapshot",
                status=WorkflowStatus.PENDING,
                payload={},
                triggered_by="user_456"
            )
        )
        mock_repository.update_error = AsyncMock()
        client.start_workflow = AsyncMock(
            side_effect=RuntimeError("Temporal down")
        )
        
        with pytest.raises(RuntimeError):
            await service.start_workflow(
                workflow_name="SnapshotWorkflow",
                workflow_id="snapshot-asst_123",
                workflow_type="analysis_snapshot",
                input_data=sample_input,
                task_queue="analysis-workflows",
                user_id="user_456"
            )
        
        mock_repository.update_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_workflow_passes_version_name(
        self, service, mock_repository, mock_temporal_client, sample_input
    ):
        """Test that version_name is stored in execution."""
        _, client = mock_temporal_client
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=ObjectId(),
                workflow_type="analysis_snapshot",
                status=WorkflowStatus.PENDING,
                payload={},
                triggered_by="user_456",
                version_name="Q1 2026"
            )
        )
        
        await service.start_workflow(
            workflow_name="SnapshotWorkflow",
            workflow_id="snapshot-asst_123",
            workflow_type="analysis_snapshot",
            input_data=sample_input,
            task_queue="analysis-workflows",
            user_id="user_456",
            version_name="Q1 2026"
        )
        
        call_arg = mock_repository.create.call_args[0][0]
        assert call_arg.version_name == "Q1 2026"
    
    @pytest.mark.asyncio
    async def test_start_workflow_is_generic(
        self, service, mock_repository, mock_temporal_client
    ):
        """Test that start_workflow works with any workflow type."""
        _, client = mock_temporal_client
        mock_repository.create = AsyncMock(
            return_value=WorkflowExecution(
                id=ObjectId(),
                workflow_type="export_report",
                status=WorkflowStatus.PENDING,
                payload={},
                triggered_by="user_123"
            )
        )
        
        await service.start_workflow(
            workflow_name="ExportReportWorkflow",
            workflow_id="export-report-123",
            workflow_type="export_report",
            input_data={"report_id": "r123"},
            task_queue="export-workflows",
            user_id="user_123"
        )
        
        call_args = client.start_workflow.call_args
        assert call_args[0][0] == "ExportReportWorkflow"
        assert call_args[1]["task_queue"] == "export-workflows"


class TestWorkflowServiceGetWorkflowProgress:
    """Tests for WorkflowService.get_workflow_progress method."""
    
    @pytest.fixture
    def mock_temporal_client(self):
        manager = MagicMock()
        client = MagicMock()
        manager.get_client = AsyncMock(return_value=client)
        return manager, client
    
    @pytest.fixture
    def service(self, mock_temporal_client):
        manager, _ = mock_temporal_client
        return WorkflowService(temporal_client=manager)
    
    @pytest.mark.asyncio
    async def test_get_progress_success(self, service, mock_temporal_client):
        _, client = mock_temporal_client
        handle = MagicMock()
        handle.query = AsyncMock(
            return_value={"step": "profiles", "processed": 5, "total": 10}
        )
        client.get_workflow_handle = MagicMock(return_value=handle)
        
        result = await service.get_workflow_progress("snapshot-asst-123")
        
        assert result == {"step": "profiles", "processed": 5, "total": 10}
    
    @pytest.mark.asyncio
    async def test_get_progress_handles_error(self, service, mock_temporal_client):
        _, client = mock_temporal_client
        handle = MagicMock()
        handle.query = AsyncMock(side_effect=Exception("not found"))
        client.get_workflow_handle = MagicMock(return_value=handle)
        
        result = await service.get_workflow_progress("bad-id")
        assert "error" in result


class TestWorkflowServiceGetExecution:
    """Tests for WorkflowService.get_execution method."""
    
    @pytest.fixture
    def mock_repository(self):
        repo = MagicMock()
        repo.get_by_id = AsyncMock()
        return repo
    
    @pytest.fixture
    def service(self, mock_repository):
        return WorkflowService(repository=mock_repository)
    
    @pytest.mark.asyncio
    async def test_get_execution_found(self, service, mock_repository):
        execution_id = ObjectId()
        expected = WorkflowExecution(
            id=execution_id,
            workflow_type="analysis_snapshot",
            status=WorkflowStatus.COMPLETED,
            payload={},
            triggered_by="user_123"
        )
        mock_repository.get_by_id = AsyncMock(return_value=expected)
        
        result = await service.get_execution(str(execution_id))
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, service, mock_repository):
        mock_repository.get_by_id = AsyncMock(return_value=None)
        result = await service.get_execution("nonexistent")
        assert result is None


class TestWorkflowServiceGetExecutions:
    """Tests for WorkflowService.get_executions method."""
    
    @pytest.fixture
    def mock_repository(self):
        repo = MagicMock()
        repo.find_many = AsyncMock(return_value=[])
        return repo
    
    @pytest.fixture
    def service(self, mock_repository):
        return WorkflowService(repository=mock_repository)
    
    @pytest.mark.asyncio
    async def test_get_executions_by_type(self, service, mock_repository):
        await service.get_executions(workflow_type="analysis_snapshot")
        call_kwargs = mock_repository.find_many.call_args[1]
        assert call_kwargs["filter"]["workflow_type"] == "analysis_snapshot"
    
    @pytest.mark.asyncio
    async def test_get_executions_with_status_filter(self, service, mock_repository):
        await service.get_executions(
            workflow_type="analysis_snapshot",
            filters={"status": WorkflowStatus.COMPLETED}
        )
        call_kwargs = mock_repository.find_many.call_args[1]
        assert call_kwargs["filter"]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_get_executions_with_payload_filter(self, service, mock_repository):
        await service.get_executions(
            workflow_type="analysis_snapshot",
            filters={"payload": {"assistant_id": "asst_123"}}
        )
        call_kwargs = mock_repository.find_many.call_args[1]
        assert call_kwargs["filter"]["payload.assistant_id"] == "asst_123"
    
    @pytest.mark.asyncio
    async def test_get_executions_default_sort(self, service, mock_repository):
        await service.get_executions(workflow_type="analysis_snapshot")
        call_kwargs = mock_repository.find_many.call_args[1]
        assert call_kwargs["sort_by"] == "created_at"
        assert call_kwargs["sort_order"] == -1


class TestWorkflowServiceUpdateStatus:
    """Tests for update/complete/fail methods."""
    
    @pytest.fixture
    def mock_repository(self):
        repo = MagicMock()
        repo.update_status = AsyncMock()
        repo.update_result = AsyncMock()
        repo.update_error = AsyncMock()
        return repo
    
    @pytest.fixture
    def service(self, mock_repository):
        return WorkflowService(repository=mock_repository)
    
    @pytest.mark.asyncio
    async def test_update_status_success(self, service, mock_repository):
        execution_id = ObjectId()
        updated = WorkflowExecution(
            id=execution_id, workflow_type="analysis_snapshot",
            status=WorkflowStatus.PROCESSING, payload={}, triggered_by="u"
        )
        mock_repository.update_status = AsyncMock(return_value=updated)
        result = await service.update_execution_status(str(execution_id), WorkflowStatus.PROCESSING)
        assert result.status == WorkflowStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_update_status_not_found(self, service, mock_repository):
        mock_repository.update_status = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await service.update_execution_status("x", WorkflowStatus.COMPLETED)
    
    @pytest.mark.asyncio
    async def test_complete_execution_success(self, service, mock_repository):
        execution_id = ObjectId()
        updated = WorkflowExecution(
            id=execution_id, workflow_type="analysis_snapshot",
            status=WorkflowStatus.COMPLETED, payload={}, triggered_by="u"
        )
        mock_repository.update_result = AsyncMock(return_value=updated)
        result = await service.complete_execution(str(execution_id), {"k": "v"}, 500)
        assert result == updated
    
    @pytest.mark.asyncio
    async def test_complete_execution_not_found(self, service, mock_repository):
        mock_repository.update_result = AsyncMock(return_value=None)
        result = await service.complete_execution("x", {}, 100)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_fail_execution_success(self, service, mock_repository):
        execution_id = ObjectId()
        updated = WorkflowExecution(
            id=execution_id, workflow_type="analysis_snapshot",
            status=WorkflowStatus.FAILED, payload={}, triggered_by="u"
        )
        mock_repository.update_error = AsyncMock(return_value=updated)
        result = await service.fail_execution(str(execution_id), "err")
        assert result == updated
    
    @pytest.mark.asyncio
    async def test_fail_execution_not_found(self, service, mock_repository):
        mock_repository.update_error = AsyncMock(return_value=None)
        result = await service.fail_execution("x", "err")
        assert result is None


class TestWorkflowServiceDefaults:
    """Tests for default instances."""
    
    def test_creates_default_repository(self):
        service = WorkflowService()
        from app.modules.workflows.repository import WorkflowRepository
        assert isinstance(service.repository, WorkflowRepository)
    
    def test_creates_default_temporal_client(self):
        service = WorkflowService()
        from app.modules.workflows.temporal_client import TemporalClientManager
        assert isinstance(service.temporal_client, TemporalClientManager)
