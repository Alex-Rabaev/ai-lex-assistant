"""Tests for webhook repository."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.webhooks.repository import WebhookRepository
from app.modules.webhooks.models import WebhookEvent, WebhookContent
from app.modules.webhooks.exceptions import DuplicateWebhookError


@pytest.fixture
def mock_db():
    """Create mock database."""
    db = MagicMock()
    collection = MagicMock()
    db.__getitem__.return_value = collection
    db["webhook_events"] = collection
    return db, collection


@pytest.fixture
def repository(mock_db):
    """Create repository with mock database."""
    db, collection = mock_db
    repo = WebhookRepository()
    repo._db = db
    repo._collection = collection
    return repo


class TestWebhookRepository:
    """Tests for WebhookRepository."""
    
    @pytest.mark.asyncio
    async def test_save_event_success(self, repository, mock_db):
        """Test successful saving of webhook event."""
        db, collection = mock_db
        
        # Setup mock
        inserted_id = ObjectId()
        collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=inserted_id))
        
        # Create event
        event = WebhookEvent(
            assistant_id=ObjectId(),
            connection_id=ObjectId(),
            channel="telegram",
            user_id="telegram_123",
            type="message",
            content=WebhookContent(text="Hello", raw={})
        )
        
        # Save event
        saved_event = await repository.save_event(event)
        
        # Assertions
        assert saved_event.id == inserted_id
        collection.insert_one.assert_called_once()
        
        # Check that the inserted data includes timestamps
        call_args = collection.insert_one.call_args[0][0]
        assert "created_at" in call_args
        assert "updated_at" in call_args
    
    @pytest.mark.asyncio
    async def test_save_event_duplicate(self, repository, mock_db):
        """Test handling of duplicate webhook event."""
        db, collection = mock_db
        
        # Setup mock to raise DuplicateKeyError
        collection.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("E11000 duplicate key error")
        )
        
        # Create event with update_id
        event = WebhookEvent(
            assistant_id=ObjectId(),
            connection_id=ObjectId(),
            channel="telegram",
            user_id="telegram_123",
            update_id=12345,
            type="message",
            content=WebhookContent(text="Hello", raw={})
        )
        
        # Try to save duplicate event
        with pytest.raises(DuplicateWebhookError):
            await repository.save_event(event)
    
    @pytest.mark.asyncio
    async def test_get_event_found(self, repository, mock_db):
        """Test getting event by ID when it exists."""
        db, collection = mock_db
        
        # Setup mock
        event_id = str(ObjectId())
        event_data = {
            "_id": ObjectId(event_id),
            "assistant_id": ObjectId(),
            "connection_id": ObjectId(),
            "channel": "telegram",
            "user_id": "telegram_123",
            "type": "message",
            "content": {"text": "Hello", "raw": {}},
            "processed": False,
            "response_sent": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        collection.find_one = AsyncMock(return_value=event_data)
        
        # Get event
        event = await repository.get_event(event_id)
        
        # Assertions
        assert event is not None
        assert str(event.id) == event_id
        assert event.user_id == "telegram_123"
        collection.find_one.assert_called_once_with({"_id": ObjectId(event_id)})
    
    @pytest.mark.asyncio
    async def test_get_event_not_found(self, repository, mock_db):
        """Test getting event by ID when it doesn't exist."""
        db, collection = mock_db
        
        # Setup mock
        collection.find_one = AsyncMock(return_value=None)
        
        # Get event
        event = await repository.get_event(str(ObjectId()))
        
        # Assertions
        assert event is None
    
    @pytest.mark.asyncio
    async def test_get_by_update_id(self, repository, mock_db):
        """Test getting event by Telegram update_id."""
        db, collection = mock_db
        
        # Setup mock
        update_id = 12345
        event_data = {
            "_id": ObjectId(),
            "assistant_id": ObjectId(),
            "connection_id": ObjectId(),
            "channel": "telegram",
            "user_id": "telegram_123",
            "update_id": update_id,
            "type": "message",
            "content": {"text": "Hello", "raw": {}},
            "processed": False,
            "response_sent": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        collection.find_one = AsyncMock(return_value=event_data)
        
        # Get event
        event = await repository.get_by_update_id(update_id)
        
        # Assertions
        assert event is not None
        assert event.update_id == update_id
        collection.find_one.assert_called_once_with({"update_id": update_id})
    
    
    @pytest.mark.asyncio
    async def test_mark_as_processed_success(self, repository, mock_db):
        """Test marking event as processed with response."""
        db, collection = mock_db
        
        # Setup mock
        event_id = str(ObjectId())
        collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        # Mark as processed with response
        response_data = {
            "text": "Response text",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "message_id": "resp_123"
        }
        result = await repository.mark_as_processed(event_id, response=response_data)
        
        # Assertions
        assert result is True
        collection.update_one.assert_called_once()
        
        # Check update data
        call_args = collection.update_one.call_args[0]
        update_data = call_args[1]["$set"]
        assert update_data["processed"] is True
        assert "processed_at" in update_data
        assert update_data["response"] == response_data
        assert update_data["response_sent"] is True
    
    @pytest.mark.asyncio
    async def test_mark_as_processed_with_error(self, repository, mock_db):
        """Test marking event as processed with error."""
        db, collection = mock_db
        
        # Setup mock
        event_id = str(ObjectId())
        collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        # Mark as processed with error
        error_msg = "Processing failed"
        result = await repository.mark_as_processed(event_id, error=error_msg)
        
        # Assertions
        assert result is True
        
        # Check update data
        call_args = collection.update_one.call_args[0]
        update_data = call_args[1]["$set"]
        assert update_data["processed"] is True
        assert update_data["error"] == error_msg
