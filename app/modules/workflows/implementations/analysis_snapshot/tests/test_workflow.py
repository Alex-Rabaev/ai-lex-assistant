"""Unit tests for SnapshotWorkflow."""

import pytest

from app.modules.workflows.implementations.analysis_snapshot.workflow import (
    SnapshotWorkflow,
)
from app.modules.workflows.implementations.analysis_snapshot.activities import (
    load_assistant,
    load_conversations,
    compute_statistics,
    generate_profile,
    generate_conclusions,
    save_snapshot,
    notify_websocket,
)
from app.modules.workflows.models.params import SnapshotInput


class TestSnapshotWorkflowStructure:
    """Tests for SnapshotWorkflow class structure."""
    
    def test_workflow_has_run_method(self):
        """Test that SnapshotWorkflow has run method."""
        workflow = SnapshotWorkflow()
        assert hasattr(workflow, "run")
        assert callable(workflow.run)
    
    def test_workflow_has_get_progress_query(self):
        """Test that SnapshotWorkflow has get_progress query."""
        workflow = SnapshotWorkflow()
        assert hasattr(workflow, "get_progress")
        assert callable(workflow.get_progress)
    
    def test_initial_progress(self):
        """Test initial progress state."""
        workflow = SnapshotWorkflow()
        progress = workflow.get_progress()
        
        assert progress["step"] == "init"
        assert progress["processed"] == 0
        assert progress["total"] == 0
        assert progress["status"] == "pending"
    
    def test_snapshot_input_dataclass(self):
        """Test SnapshotInput can be created."""
        input_data = SnapshotInput(
            assistant_id="asst_123",
            execution_id="exec_456",
            force_recalculate=True,
            include_partial=False
        )
        
        assert input_data.assistant_id == "asst_123"
        assert input_data.execution_id == "exec_456"
        assert input_data.force_recalculate is True
        assert input_data.include_partial is False
    
    def test_snapshot_input_defaults(self):
        """Test SnapshotInput default values."""
        input_data = SnapshotInput(
            assistant_id="asst_123",
            execution_id="exec_456"
        )
        
        assert input_data.force_recalculate is False
        assert input_data.include_partial is True


class TestActivitiesExist:
    """Tests that all Activity functions are defined."""
    
    def test_load_assistant_exists(self):
        assert callable(load_assistant)
    
    def test_load_conversations_exists(self):
        assert callable(load_conversations)
    
    def test_compute_statistics_exists(self):
        assert callable(compute_statistics)
    
    def test_generate_profile_exists(self):
        assert callable(generate_profile)
    
    def test_generate_conclusions_exists(self):
        assert callable(generate_conclusions)
    
    def test_save_snapshot_exists(self):
        assert callable(save_snapshot)
    
    def test_notify_websocket_exists(self):
        assert callable(notify_websocket)


class TestWorkerRegistration:
    """Tests that worker correctly registers workflow and activities."""
    
    def test_get_workflow_classes_includes_snapshot(self):
        from app.modules.workflows.temporal_worker import get_workflow_classes
        workflows = get_workflow_classes()
        assert SnapshotWorkflow in workflows
    
    def test_get_activity_functions_includes_all(self):
        from app.modules.workflows.temporal_worker import get_activity_functions
        activities = get_activity_functions()
        
        assert load_assistant in activities
        assert load_conversations in activities
        assert compute_statistics in activities
        assert generate_profile in activities
        assert generate_conclusions in activities
        assert save_snapshot in activities
        assert notify_websocket in activities
    
