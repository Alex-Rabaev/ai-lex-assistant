"""Tests for InterlocutorRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.modules.conversations.repositories.interlocutor_repository import InterlocutorRepository
from app.modules.conversations.models.interlocutor import Interlocutor


class TestInterlocutorRepository:
    """Test InterlocutorRepository."""
    
    @pytest.fixture
    def mock_collection(self):
        """Mock collection."""
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_collection):
        """Create repository with mocked internals."""
        repo = InterlocutorRepository()
        repo._db = MagicMock()
        repo._collection = mock_collection
        return repo
    
    @pytest.mark.asyncio
    async def test_get_by_user_id_found(self, repository):
        """Test get_by_user_id when interlocutor exists."""
        # Arrange
        user_id = "telegram_123"
        mock_doc = {
            "_id": ObjectId(),
            "user_id": user_id,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "language_code": "en",
            "profile": {}
        }
        repository._collection.find_one = AsyncMock(return_value=mock_doc)
        
        # Act
        result = await repository.get_by_user_id(user_id)
        
        # Assert
        assert result is not None
        assert isinstance(result, Interlocutor)
        assert result.user_id == user_id
        assert result.first_name == "John"
    
    @pytest.mark.asyncio
    async def test_get_by_user_id_not_found(self, repository):
        """Test get_by_user_id when interlocutor doesn't exist."""
        # Arrange
        repository._collection.find_one = AsyncMock(return_value=None)
        
        # Act
        result = await repository.get_by_user_id("telegram_999")
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create(self, repository):
        """Test create interlocutor."""
        # Arrange
        user_id = "telegram_123"
        inserted_id = ObjectId()
        repository._collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )
        
        # Act
        result = await repository.create(
            user_id=user_id,
            first_name="John",
            last_name="Doe"
        )
        
        # Assert
        assert result is not None
        assert isinstance(result, Interlocutor)
        assert result.user_id == user_id
        assert result.first_name == "John"
        assert result.id == inserted_id
    
    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, repository):
        """Test get_or_create when interlocutor exists."""
        # Arrange
        user_id = "telegram_123"
        existing_doc = {
            "_id": ObjectId(),
            "user_id": user_id,
            "first_name": "John",
            "profile": {}
        }
        repository._collection.find_one = AsyncMock(return_value=existing_doc)
        
        # Act
        result = await repository.get_or_create(user_id)
        
        # Assert
        assert result is not None
        assert result.user_id == user_id
    
    @pytest.mark.asyncio
    async def test_get_or_create_new(self, repository):
        """Test get_or_create when interlocutor doesn't exist."""
        # Arrange
        user_id = "telegram_123"
        repository._collection.find_one = AsyncMock(return_value=None)
        repository._collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        
        user_info = {
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe"
        }
        
        # Act
        result = await repository.get_or_create(user_id, user_info)
        
        # Assert
        assert result is not None
        assert result.user_id == user_id
        assert result.first_name == "John"
        # Should call insert_one
        repository._collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_opted_out(self, repository):
        """Test update_opted_out sets flag."""
        interlocutor_id = str(ObjectId())
        repository._collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        result = await repository.update_opted_out(interlocutor_id, opted_out=True)

        assert result is True
        repository._collection.update_one.assert_called_once()
        call_args = repository._collection.update_one.call_args
        assert call_args[0][0] == {"_id": ObjectId(interlocutor_id)}
        assert call_args[0][1]["$set"]["opted_out"] is True

    @pytest.mark.asyncio
    async def test_update_blocked(self, repository):
        """Test update_blocked sets flag."""
        interlocutor_id = str(ObjectId())
        repository._collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        result = await repository.update_blocked(interlocutor_id, blocked=True)

        assert result is True
        repository._collection.update_one.assert_called_once()
        call_args = repository._collection.update_one.call_args
        assert call_args[0][1]["$set"]["blocked"] is True

