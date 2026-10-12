"""Unit tests for Temporal Worker."""

import pytest
import signal
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.workflows.temporal_worker import (
    get_workflow_classes,
    get_activity_functions,
    run_worker,
)


class TestWorkerRegistration:
    """Tests for workflow and activity registration."""
    
    def test_get_workflow_classes_returns_list(self):
        """Test that get_workflow_classes returns a list."""
        result = get_workflow_classes()
        assert isinstance(result, list)
    
    def test_get_activity_functions_returns_list(self):
        """Test that get_activity_functions returns a list."""
        result = get_activity_functions()
        assert isinstance(result, list)
    
    def test_config_defaults(self):
        """Test that config has correct default values."""
        from app.config import config
        assert config.TEMPORAL_TASK_QUEUE == "analysis-workflows"
        assert config.TEMPORAL_MAX_CONCURRENT_ACTIVITIES == 5
        assert config.TEMPORAL_MAX_CONCURRENT_WORKFLOWS == 10


class TestRunWorker:
    """Tests for run_worker function."""
    
    @pytest.mark.asyncio
    async def test_run_worker_connects_to_temporal(self):
        """Test that run_worker connects to Temporal Service."""
        mock_client = MagicMock()
        mock_worker = MagicMock()
        
        # Mock Worker as async context manager
        mock_worker.__aenter__ = AsyncMock()
        mock_worker.__aexit__ = AsyncMock()
        
        with patch(
            "app.modules.workflows.temporal_worker.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ) as mock_connect, \
        patch(
            "app.modules.workflows.temporal_worker.Worker",
            return_value=mock_worker
        ), \
        patch(
            "app.modules.workflows.temporal_worker.asyncio.Event"
        ) as mock_event_cls:
            # Make shutdown_event.wait() return immediately
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            mock_event.set = MagicMock()
            mock_event_cls.return_value = mock_event
            
            await run_worker(
                temporal_host="localhost:7233",
                temporal_namespace="test-ns"
            )
            
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["target_host"] == "localhost:7233"
            assert call_kwargs["namespace"] == "test-ns"
    
    @pytest.mark.asyncio
    async def test_run_worker_creates_worker_with_correct_params(self):
        """Test that Worker is created with correct configuration."""
        mock_client = MagicMock()
        mock_worker = MagicMock()
        mock_worker.__aenter__ = AsyncMock()
        mock_worker.__aexit__ = AsyncMock()
        
        with patch(
            "app.modules.workflows.temporal_worker.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ), \
        patch(
            "app.modules.workflows.temporal_worker.Worker",
            return_value=mock_worker
        ) as mock_worker_cls, \
        patch(
            "app.modules.workflows.temporal_worker.asyncio.Event"
        ) as mock_event_cls:
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            mock_event_cls.return_value = mock_event
            
            await run_worker(
                temporal_host="localhost:7233",
                temporal_namespace="default",
                task_queue="test-queue",
                max_concurrent_activities=3,
                max_concurrent_workflows=5
            )
            
            mock_worker_cls.assert_called_once()
            call_kwargs = mock_worker_cls.call_args
            
            assert call_kwargs[0][0] == mock_client
            assert call_kwargs[1]["task_queue"] == "test-queue"
            assert call_kwargs[1]["max_concurrent_activities"] == 3
            assert call_kwargs[1]["max_concurrent_workflow_tasks"] == 5
    
    @pytest.mark.asyncio
    async def test_run_worker_uses_config_defaults(self):
        """Test that run_worker uses config values by default."""
        mock_client = MagicMock()
        mock_worker = MagicMock()
        mock_worker.__aenter__ = AsyncMock()
        mock_worker.__aexit__ = AsyncMock()
        
        with patch(
            "app.modules.workflows.temporal_worker.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ), \
        patch(
            "app.modules.workflows.temporal_worker.Worker",
            return_value=mock_worker
        ) as mock_worker_cls, \
        patch(
            "app.modules.workflows.temporal_worker.asyncio.Event"
        ) as mock_event_cls:
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            mock_event_cls.return_value = mock_event
            
            await run_worker(
                temporal_host="localhost:7233",
                temporal_namespace="default"
            )
            
            from app.config import config
            call_kwargs = mock_worker_cls.call_args
            assert call_kwargs[1]["task_queue"] == config.TEMPORAL_TASK_QUEUE
            assert call_kwargs[1]["max_concurrent_activities"] == config.TEMPORAL_MAX_CONCURRENT_ACTIVITIES
            assert call_kwargs[1]["max_concurrent_workflow_tasks"] == config.TEMPORAL_MAX_CONCURRENT_WORKFLOWS
    
    @pytest.mark.asyncio
    async def test_run_worker_registers_workflows_and_activities(self):
        """Test that Worker receives registered workflows and activities."""
        mock_client = MagicMock()
        mock_worker = MagicMock()
        mock_worker.__aenter__ = AsyncMock()
        mock_worker.__aexit__ = AsyncMock()
        
        with patch(
            "app.modules.workflows.temporal_worker.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ), \
        patch(
            "app.modules.workflows.temporal_worker.Worker",
            return_value=mock_worker
        ) as mock_worker_cls, \
        patch(
            "app.modules.workflows.temporal_worker.get_workflow_classes",
            return_value=["MockWorkflow"]
        ), \
        patch(
            "app.modules.workflows.temporal_worker.get_activity_functions",
            return_value=["mock_activity"]
        ), \
        patch(
            "app.modules.workflows.temporal_worker.asyncio.Event"
        ) as mock_event_cls:
            mock_event = MagicMock()
            mock_event.wait = AsyncMock()
            mock_event_cls.return_value = mock_event
            
            await run_worker(
                temporal_host="localhost:7233",
                temporal_namespace="default"
            )
            
            call_kwargs = mock_worker_cls.call_args
            assert call_kwargs[1]["workflows"] == ["MockWorkflow"]
            assert call_kwargs[1]["activities"] == ["mock_activity"]
