"""Tests for connection repository."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, MagicMock
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)


class TestConnectionRepository:
    """Test ConnectionRepository methods."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        collection = MagicMock()
        db.__getitem__ = MagicMock(return_value=collection)
        db["connections"] = collection
        return db
    
    @pytest.fixture
    def repository(self, mock_db):
        """Create repository instance with mock DB."""
        repo = ConnectionRepository()
        repo._db = mock_db
        repo._collection = mock_db["connections"]
        return repo
    
    @pytest.fixture
    def sample_settings(self):
        """Create sample connection settings."""
        return ConnectionSettings(
            bot_token="encrypted_token_123",
            bot_username="@test_bot",
            bot_id=123456789,
            bot_first_name="Test Bot",
            webhook_url="https://example.com/webhook"
        )
    
    # ===== Test create =====
    
    @pytest.mark.asyncio
    async def test_create_success(self, repository, sample_settings):
        """Test successful connection creation."""
        assistant_id = "507f1f77bcf86cd799439011"
        
        # Mock insert_one
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId()
        repository._collection.insert_one = AsyncMock(return_value=mock_result)
        
        # Create connection
        connection = await repository.create(
            assistant_id,
            ConnectionChannel.TELEGRAM,
            sample_settings
        )
        
        assert connection is not None
        assert str(connection.assistant_id) == assistant_id
        assert connection.channel == ConnectionChannel.TELEGRAM
        assert connection.status == ConnectionStatus.PENDING
        assert connection.settings.bot_token == "encrypted_token_123"
        
        # Verify insert_one was called
        repository._collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_duplicate_error(self, repository, sample_settings):
        """Test creation with duplicate key error."""
        assistant_id = "507f1f77bcf86cd799439011"
        
        # Mock insert_one to raise DuplicateKeyError
        repository._collection.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("Duplicate key error")
        )
        
        with pytest.raises(DuplicateKeyError, match="Connection already exists"):
            await repository.create(
                assistant_id,
                ConnectionChannel.TELEGRAM,
                sample_settings
            )
    
    # ===== Test get_by_id =====
    
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repository, sample_settings):
        """Test getting connection by ID when it exists."""
        connection_id = "507f1f77bcf86cd799439012"
        
        mock_doc = {
            "_id": ObjectId(connection_id),
            "assistant_id": ObjectId("507f1f77bcf86cd799439011"),
            "channel": "telegram",
            "status": "connected",
            "settings": sample_settings.model_dump(),
            "last_error": None,
            "last_checked_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        repository._collection.find_one = AsyncMock(return_value=mock_doc)
        
        connection = await repository.get_by_id(connection_id)
        
        assert connection is not None
        assert str(connection.id) == connection_id
        assert connection.channel == ConnectionChannel.TELEGRAM
        assert connection.status == ConnectionStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """Test getting connection by ID when it doesn't exist."""
        repository._collection.find_one = AsyncMock(return_value=None)
        
        connection = await repository.get_by_id("507f1f77bcf86cd799439012")
        
        assert connection is None
    
    # ===== Test find_by_assistant =====
    
    @pytest.mark.asyncio
    async def test_find_by_assistant(self, repository, sample_settings):
        """Test finding connections by assistant ID."""
        assistant_id = "507f1f77bcf86cd799439011"
        
        mock_docs = [
            {
                "_id": ObjectId(),
                "assistant_id": ObjectId(assistant_id),
                "channel": "telegram",
                "status": "connected",
                "settings": sample_settings.model_dump(),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(),
                "assistant_id": ObjectId(assistant_id),
                "channel": "whatsapp",
                "status": "pending",
                "settings": sample_settings.model_dump(),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]
        
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_docs)
        repository._collection.find = Mock(return_value=mock_cursor)
        
        connections = await repository.find_by_assistant(assistant_id)
        
        assert len(connections) == 2
        assert connections[0].channel == ConnectionChannel.TELEGRAM
        assert connections[1].channel == ConnectionChannel.WHATSAPP
    
    @pytest.mark.asyncio
    async def test_find_by_assistant_with_status_filter(self, repository):
        """Test finding connections with status filter."""
        assistant_id = "507f1f77bcf86cd799439011"
        
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        repository._collection.find = Mock(return_value=mock_cursor)
        
        await repository.find_by_assistant(assistant_id, ConnectionStatus.CONNECTED)
        
        # Verify find was called with status filter
        repository._collection.find.assert_called_once_with({
            "assistant_id": ObjectId(assistant_id),
            "status": "connected"
        })
    
    # ===== Test update =====
    
    @pytest.mark.asyncio
    async def test_update_success(self, repository, sample_settings):
        """Test successful connection update."""
        connection_id = "507f1f77bcf86cd799439012"
        
        mock_doc = {
            "_id": ObjectId(connection_id),
            "assistant_id": ObjectId("507f1f77bcf86cd799439011"),
            "channel": "telegram",
            "status": "connected",
            "settings": sample_settings.model_dump(),
            "last_error": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        repository._collection.find_one_and_update = AsyncMock(return_value=mock_doc)
        
        connection = await repository.update(
            connection_id,
            {"status": ConnectionStatus.CONNECTED}
        )
        
        assert connection is not None
        assert connection.status == ConnectionStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_update_not_found(self, repository):
        """Test update when connection not found."""
        repository._collection.find_one_and_update = AsyncMock(return_value=None)
        
        connection = await repository.update(
            "507f1f77bcf86cd799439012",
            {"status": ConnectionStatus.ERROR}
        )
        
        assert connection is None
    
    # ===== Test delete =====
    
    @pytest.mark.asyncio
    async def test_delete_success(self, repository):
        """Test successful connection deletion."""
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        repository._collection.delete_one = AsyncMock(return_value=mock_result)
        
        result = await repository.delete("507f1f77bcf86cd799439012")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, repository):
        """Test deletion when connection not found."""
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        repository._collection.delete_one = AsyncMock(return_value=mock_result)
        
        result = await repository.delete("507f1f77bcf86cd799439012")
        
        assert result is False
    
    # ===== Test exists_by_assistant_and_channel =====
    
    @pytest.mark.asyncio
    async def test_exists_by_assistant_and_channel_true(self, repository):
        """Test checking existence when connection exists."""
        repository._collection.count_documents = AsyncMock(return_value=1)
        
        exists = await repository.exists_by_assistant_and_channel(
            "507f1f77bcf86cd799439011",
            ConnectionChannel.TELEGRAM
        )
        
        assert exists is True
    
    @pytest.mark.asyncio
    async def test_exists_by_assistant_and_channel_false(self, repository):
        """Test checking existence when connection doesn't exist."""
        repository._collection.count_documents = AsyncMock(return_value=0)
        
        exists = await repository.exists_by_assistant_and_channel(
            "507f1f77bcf86cd799439011",
            ConnectionChannel.WHATSAPP
        )
        
        assert exists is False
    
    # ===== Test update_status =====
    
    @pytest.mark.asyncio
    async def test_update_status_with_error(self, repository, sample_settings):
        """Test updating status with error message."""
        connection_id = "507f1f77bcf86cd799439012"
        
        mock_doc = {
            "_id": ObjectId(connection_id),
            "assistant_id": ObjectId("507f1f77bcf86cd799439011"),
            "channel": "telegram",
            "status": "error",
            "settings": sample_settings.model_dump(),
            "last_error": "Invalid token",
            "last_checked_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        repository._collection.find_one_and_update = AsyncMock(return_value=mock_doc)
        
        connection = await repository.update_status(
            connection_id,
            ConnectionStatus.ERROR,
            "Invalid token"
        )
        
        assert connection is not None
        assert connection.status == ConnectionStatus.ERROR
        assert connection.last_error == "Invalid token"
        assert connection.last_checked_at is not None
    
    @pytest.mark.asyncio
    async def test_update_status_clear_error(self, repository, sample_settings):
        """Test that error is cleared when status becomes connected."""
        connection_id = "507f1f77bcf86cd799439012"
        
        mock_doc = {
            "_id": ObjectId(connection_id),
            "assistant_id": ObjectId("507f1f77bcf86cd799439011"),
            "channel": "telegram",
            "status": "connected",
            "settings": sample_settings.model_dump(),
            "last_error": None,
            "last_checked_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        repository._collection.find_one_and_update = AsyncMock(return_value=mock_doc)
        
        connection = await repository.update_status(
            connection_id,
            ConnectionStatus.CONNECTED
        )
        
        assert connection is not None
        assert connection.status == ConnectionStatus.CONNECTED
        assert connection.last_error is None
    
    # ===== Test get_by_assistant_and_channel =====
    
    @pytest.mark.asyncio
    async def test_get_by_assistant_and_channel_found(self, repository, sample_settings):
        """Test getting connection by assistant and channel."""
        assistant_id = "507f1f77bcf86cd799439011"
        
        mock_doc = {
            "_id": ObjectId(),
            "assistant_id": ObjectId(assistant_id),
            "channel": "telegram",
            "status": "connected",
            "settings": sample_settings.model_dump(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        repository._collection.find_one = AsyncMock(return_value=mock_doc)
        
        connection = await repository.get_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.TELEGRAM
        )
        
        assert connection is not None
        assert str(connection.assistant_id) == assistant_id
        assert connection.channel == ConnectionChannel.TELEGRAM
    
    @pytest.mark.asyncio
    async def test_get_by_assistant_and_channel_not_found(self, repository):
        """Test getting connection when it doesn't exist."""
        repository._collection.find_one = AsyncMock(return_value=None)
        
        connection = await repository.get_by_assistant_and_channel(
            "507f1f77bcf86cd799439011",
            ConnectionChannel.WHATSAPP
        )
        
        assert connection is None
