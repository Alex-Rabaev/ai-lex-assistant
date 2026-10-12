"""Tests for WorkflowRepository."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.modules.workflows.repository import WorkflowRepository
from app.modules.workflows.models.execution import WorkflowExecution, WorkflowStatus


class TestWorkflowRepository:
    """Test WorkflowRepository CRUD operations."""
    
    @pytest.fixture
    def mock_collection(self):
        """Mock MongoDB collection."""
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_collection):
        """Create repository with mocked internals."""
        repo = WorkflowRepository()
        repo._db = MagicMock()
        repo._collection = mock_collection
        return repo
    
    @pytest.fixture
    def sample_execution(self):
        """Create sample WorkflowExecution."""
        return WorkflowExecution(
            workflow_type="analysis_snapshot",
            status=WorkflowStatus.PENDING,
            payload={"assistant_id": "abc123"},
            triggered_by="user123"
        )
    
    @pytest.fixture
    def sample_doc(self):
        """Create sample MongoDB document."""
        return {
            "_id": ObjectId(),
            "workflow_type": "analysis_snapshot",
            "status": "pending",
            "payload": {"assistant_id": "abc123"},
            "result": None,
            "error_message": None,
            "version_name": None,
            "is_archived": False,
            "triggered_by": "user123",
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    
    @pytest.mark.asyncio
    async def test_create(self, repository, sample_execution):
        """Test create workflow execution."""
        inserted_id = ObjectId()
        repository._collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )
        
        result = await repository.create(sample_execution)
        
        assert result is not None
        assert isinstance(result, WorkflowExecution)
        assert result.id == inserted_id
        assert result.workflow_type == "analysis_snapshot"
        repository._collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_one_found(self, repository, sample_doc):
        """Test find_one when document exists."""
        repository._collection.find_one = AsyncMock(return_value=sample_doc)
        
        result = await repository.find_one({"workflow_type": "analysis_snapshot"})
        
        assert result is not None
        assert isinstance(result, WorkflowExecution)
        assert result.workflow_type == "analysis_snapshot"
    
    @pytest.mark.asyncio
    async def test_find_one_not_found(self, repository):
        """Test find_one when document doesn't exist."""
        repository._collection.find_one = AsyncMock(return_value=None)
        
        result = await repository.find_one({"workflow_type": "nonexistent"})
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_many(self, repository, sample_doc):
        """Test find_many returns list of executions."""
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[sample_doc, sample_doc])
        repository._collection.find = MagicMock(return_value=mock_cursor)
        
        result = await repository.find_many({"workflow_type": "analysis_snapshot"})
        
        assert len(result) == 2
        assert all(isinstance(e, WorkflowExecution) for e in result)
    
    @pytest.mark.asyncio
    async def test_find_many_with_limit(self, repository, sample_doc):
        """Test find_many with limit."""
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[sample_doc])
        repository._collection.find = MagicMock(return_value=mock_cursor)
        
        result = await repository.find_many(
            {"workflow_type": "analysis_snapshot"},
            limit=1
        )
        
        assert len(result) == 1
        mock_cursor.limit.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repository, sample_doc):
        """Test get_by_id when execution exists."""
        repository._collection.find_one = AsyncMock(return_value=sample_doc)
        
        result = await repository.get_by_id(str(sample_doc["_id"]))
        
        assert result is not None
        assert isinstance(result, WorkflowExecution)
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """Test get_by_id when execution doesn't exist."""
        repository._collection.find_one = AsyncMock(return_value=None)
        
        result = await repository.get_by_id(str(ObjectId()))
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_status(self, repository, sample_doc):
        """Test update_status."""
        sample_doc["status"] = "processing"
        repository._collection.find_one_and_update = AsyncMock(return_value=sample_doc)
        
        result = await repository.update_status(
            str(sample_doc["_id"]),
            WorkflowStatus.PROCESSING
        )
        
        assert result is not None
        assert result.status == WorkflowStatus.PROCESSING
        repository._collection.find_one_and_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_status_with_timestamps(self, repository, sample_doc):
        """Test update_status with optional timestamps."""
        now = datetime.now(timezone.utc)
        sample_doc["status"] = "completed"
        sample_doc["started_at"] = now
        sample_doc["completed_at"] = now
        sample_doc["duration_ms"] = 5000
        repository._collection.find_one_and_update = AsyncMock(return_value=sample_doc)
        
        result = await repository.update_status(
            str(sample_doc["_id"]),
            WorkflowStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            duration_ms=5000
        )
        
        assert result is not None
        assert result.duration_ms == 5000
    
    @pytest.mark.asyncio
    async def test_update_status_not_found(self, repository):
        """Test update_status when execution not found."""
        repository._collection.find_one_and_update = AsyncMock(return_value=None)
        
        result = await repository.update_status(
            str(ObjectId()),
            WorkflowStatus.PROCESSING
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_result(self, repository, sample_doc):
        """Test update_result."""
        sample_doc["status"] = "completed"
        sample_doc["result"] = {"conversations_analyzed": 42}
        repository._collection.find_one_and_update = AsyncMock(return_value=sample_doc)
        
        result = await repository.update_result(
            str(sample_doc["_id"]),
            {"conversations_analyzed": 42}
        )
        
        assert result is not None
        assert result.status == WorkflowStatus.COMPLETED
        assert result.result == {"conversations_analyzed": 42}
    
    @pytest.mark.asyncio
    async def test_update_result_not_found(self, repository):
        """Test update_result when execution not found."""
        repository._collection.find_one_and_update = AsyncMock(return_value=None)
        
        result = await repository.update_result(
            str(ObjectId()),
            {"data": "test"}
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_error(self, repository, sample_doc):
        """Test update_error."""
        sample_doc["status"] = "failed"
        sample_doc["error_message"] = "Something went wrong"
        repository._collection.find_one_and_update = AsyncMock(return_value=sample_doc)
        
        result = await repository.update_error(
            str(sample_doc["_id"]),
            "Something went wrong"
        )
        
        assert result is not None
        assert result.status == WorkflowStatus.FAILED
        assert result.error_message == "Something went wrong"
    
    @pytest.mark.asyncio
    async def test_update_error_not_found(self, repository):
        """Test update_error when execution not found."""
        repository._collection.find_one_and_update = AsyncMock(return_value=None)
        
        result = await repository.update_error(
            str(ObjectId()),
            "Error message"
        )
        
        assert result is None
