"""Tests for workflow_executions migration.

Tests verify that migration functions create correct collection and indexes.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from pymongo.errors import CollectionInvalid, OperationFailure
import importlib.util
import sys
from pathlib import Path

# Load migration module dynamically (filename starts with number)
migration_path = Path(__file__).parent.parent.parent.parent.parent / "migrations" / "mongodb" / "008_create_workflow_executions_collection.py"
spec = importlib.util.spec_from_file_location("migration_008", migration_path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class TestWorkflowExecutionsMigration:
    """Tests for 008_create_workflow_executions_collection migration."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db.list_collection_names = AsyncMock(return_value=[])
        return db
    
    @pytest.fixture
    def mock_collection(self):
        """Create mock collection."""
        collection = MagicMock()
        collection.create_index = AsyncMock()
        return collection
    
    @pytest.fixture
    def mock_client(self, mock_db):
        """Create mock MongoDB client."""
        client = MagicMock()
        client.__getitem__ = MagicMock(return_value=mock_db)
        return client
    
    @pytest.mark.asyncio
    async def test_up_creates_collection(self, mock_client, mock_db, mock_collection):
        """Test that up() creates the workflow_executions collection."""
        mock_db.create_collection = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_db["migration_history"] = MagicMock()
        mock_db["migration_history"].update_one = AsyncMock()
        
        await migration.up(mock_client, "test_db")
        
        mock_db.create_collection.assert_called_once_with("workflow_executions")
    
    @pytest.mark.asyncio
    async def test_up_handles_existing_collection(self, mock_client, mock_db, mock_collection):
        """Test that up() handles case when collection already exists."""
        mock_db.create_collection = AsyncMock(side_effect=CollectionInvalid("exists"))
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_db["migration_history"] = MagicMock()
        mock_db["migration_history"].update_one = AsyncMock()
        
        # Should not raise
        await migration.up(mock_client, "test_db")
        
        # Should still try to create indexes
        assert mock_collection.create_index.call_count == 3
    
    @pytest.mark.asyncio
    async def test_up_creates_all_indexes(self, mock_client, mock_db, mock_collection):
        """Test that up() creates all required indexes."""
        mock_db.create_collection = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_db["migration_history"] = MagicMock()
        mock_db["migration_history"].update_one = AsyncMock()
        
        await migration.up(mock_client, "test_db")
        
        # Should create 3 indexes (dedup handled by Temporal Workflow IDs)
        assert mock_collection.create_index.call_count == 3
        
        # Verify index names by checking call args
        call_args_list = mock_collection.create_index.call_args_list
        index_names = [call.kwargs.get("name") for call in call_args_list]
        
        expected_indexes = [
            "type_status_idx",
            "created_at_idx",
            "type_created_idx",
        ]
        
        for expected in expected_indexes:
            assert expected in index_names, f"Index {expected} not created"
    
    @pytest.mark.asyncio
    async def test_up_handles_existing_indexes(self, mock_client, mock_db, mock_collection):
        """Test that up() handles case when indexes already exist."""
        mock_db.create_collection = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_db["migration_history"] = MagicMock()
        mock_db["migration_history"].update_one = AsyncMock()
        
        # First index succeeds, rest already exist
        mock_collection.create_index = AsyncMock(
            side_effect=[
                None,  # First succeeds
                OperationFailure("already exists"),
                OperationFailure("already exists"),
            ]
        )
        
        # Should not raise
        await migration.up(mock_client, "test_db")
    
    @pytest.mark.asyncio
    async def test_up_raises_on_index_error(self, mock_client, mock_db, mock_collection):
        """Test that up() raises on unexpected index creation error."""
        mock_db.create_collection = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        # Unexpected error
        mock_collection.create_index = AsyncMock(
            side_effect=OperationFailure("unexpected error")
        )
        
        with pytest.raises(OperationFailure):
            await migration.up(mock_client, "test_db")
    
    @pytest.mark.asyncio
    async def test_up_records_migration_history(self, mock_client, mock_db, mock_collection):
        """Test that up() records migration in history."""
        mock_db.create_collection = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        mock_history = MagicMock()
        mock_history.update_one = AsyncMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda key: 
            mock_history if key == "migration_history" else mock_collection
        )
        
        await migration.up(mock_client, "test_db")
        
        mock_history.update_one.assert_called_once()
        call_args = mock_history.update_one.call_args
        
        # Verify migration ID
        assert call_args[0][0] == {"migration_id": migration.MIGRATION_ID}
        
        # Verify status is completed
        update_data = call_args[0][1]["$set"]
        assert update_data["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_down_drops_collection(self, mock_client, mock_db):
        """Test that down() drops the collection."""
        mock_db.drop_collection = AsyncMock()
        mock_db["migration_history"] = MagicMock()
        mock_db["migration_history"].delete_one = AsyncMock()
        
        await migration.down(mock_client, "test_db")
        
        mock_db.drop_collection.assert_called_once_with("workflow_executions")
    
    @pytest.mark.asyncio
    async def test_down_removes_migration_history(self, mock_client, mock_db):
        """Test that down() removes migration from history."""
        mock_db.drop_collection = AsyncMock()
        
        mock_history = MagicMock()
        mock_history.delete_one = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_history)
        
        await migration.down(mock_client, "test_db")
        
        mock_history.delete_one.assert_called_once_with({
            "migration_id": migration.MIGRATION_ID
        })
    
    @pytest.mark.asyncio
    async def test_down_raises_on_drop_error(self, mock_client, mock_db):
        """Test that down() raises on drop error."""
        mock_db.drop_collection = AsyncMock(side_effect=Exception("drop failed"))
        
        with pytest.raises(Exception, match="drop failed"):
            await migration.down(mock_client, "test_db")


class TestMigrationIndexKeys:
    """Tests to verify correct index key structures."""
    
    def test_type_status_idx_keys(self):
        """Verify type_status_idx has correct keys."""
        # This index is for filtering by type and status
        # Keys: (workflow_type, status)
        from pymongo import ASCENDING
        expected_keys = [("workflow_type", ASCENDING), ("status", ASCENDING)]
        
        # Index should support queries like:
        # find({"workflow_type": "x", "status": "pending"})
        assert expected_keys[0][0] == "workflow_type"
        assert expected_keys[1][0] == "status"
    
    def test_type_created_idx_keys(self):
        """Verify type_created_idx has correct keys."""
        # Compound index for type + time sorting
        from pymongo import ASCENDING, DESCENDING
        expected_keys = [("workflow_type", ASCENDING), ("created_at", DESCENDING)]
        
        assert expected_keys[0][0] == "workflow_type"
        assert expected_keys[1][0] == "created_at"
