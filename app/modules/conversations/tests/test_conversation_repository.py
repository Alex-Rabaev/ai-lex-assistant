"""Tests for ConversationRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.modules.conversations.repositories.conversation_repository import ConversationRepository
from app.modules.conversations.models.conversation import Conversation


class TestConversationRepository:
    """Test ConversationRepository."""
    
    @pytest.fixture
    def mock_collection(self):
        """Mock collection."""
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_collection):
        """Create repository with mocked internals."""
        repo = ConversationRepository()
        repo._db = MagicMock()
        repo._collection = mock_collection
        return repo
    
    @pytest.mark.asyncio
    async def test_get_by_interlocutor_and_assistant_found(self, repository):
        """Test get_by_interlocutor_and_assistant when conversation exists."""
        # Arrange
        interlocutor_id = str(ObjectId())
        assistant_id = str(ObjectId())
        mock_doc = {
            "_id": ObjectId(),
            "interlocutor_id": ObjectId(interlocutor_id),
            "assistant_id": ObjectId(assistant_id),
            "connection_id": ObjectId(),
            "state": {}
        }
        repository._collection.find_one = AsyncMock(return_value=mock_doc)
        
        # Act
        result = await repository.get_by_interlocutor_and_assistant(
            interlocutor_id,
            assistant_id
        )
        
        # Assert
        assert result is not None
        assert isinstance(result, Conversation)
    
    @pytest.mark.asyncio
    async def test_create(self, repository):
        """Test create conversation."""
        # Arrange
        interlocutor_id = str(ObjectId())
        assistant_id = str(ObjectId())
        connection_id = str(ObjectId())
        inserted_id = ObjectId()
        
        repository._collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )
        
        # Act
        result = await repository.create(
            interlocutor_id=interlocutor_id,
            assistant_id=assistant_id,
            connection_id=connection_id
        )
        
        # Assert
        assert result is not None
        assert isinstance(result, Conversation)
        assert result.id == inserted_id
        assert result.state == {}  # Empty state initially
    
    @pytest.mark.asyncio
    async def test_update_state(self, repository):
        """Test update_state."""
        # Arrange
        conversation_id = str(ObjectId())
        new_state = {"step": "question_2", "data": {"q1": "answer1"}}
        
        repository._collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        # Act
        result = await repository.update_state(conversation_id, new_state)
        
        # Assert
        assert result is True
        repository._collection.update_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_assistant_returns_conversations(self, repository):
        """Test get_by_assistant returns list of conversations."""
        # Arrange
        assistant_id = str(ObjectId())
        mock_docs = [
            {
                "_id": ObjectId(),
                "interlocutor_id": ObjectId(),
                "assistant_id": ObjectId(assistant_id),
                "connection_id": ObjectId(),
                "state": {"agent_metadata": {"state": "intro"}}
            },
            {
                "_id": ObjectId(),
                "interlocutor_id": ObjectId(),
                "assistant_id": ObjectId(assistant_id),
                "connection_id": ObjectId(),
                "state": {"agent_metadata": {"state": "survey"}}
            }
        ]
        
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=mock_docs)
        repository._collection.find = MagicMock(return_value=mock_cursor)
        
        # Act
        result = await repository.get_by_assistant(assistant_id)
        
        # Assert
        assert len(result) == 2
        assert all(isinstance(c, Conversation) for c in result)
        repository._collection.find.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_assistant_with_stage_filter(self, repository):
        """Test get_by_assistant filters by stage."""
        # Arrange
        assistant_id = str(ObjectId())
        stage = "survey"
        mock_docs = [
            {
                "_id": ObjectId(),
                "interlocutor_id": ObjectId(),
                "assistant_id": ObjectId(assistant_id),
                "connection_id": ObjectId(),
                "state": {"agent_metadata": {"state": "survey"}}
            }
        ]
        
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=mock_docs)
        repository._collection.find = MagicMock(return_value=mock_cursor)
        
        # Act
        result = await repository.get_by_assistant(assistant_id, stage=stage)
        
        # Assert
        assert len(result) == 1
        # Verify filter includes stage
        call_args = repository._collection.find.call_args[0][0]
        assert "state.agent_metadata.state" in call_args
        assert call_args["state.agent_metadata.state"] == stage
    
    @pytest.mark.asyncio
    async def test_get_by_assistant_empty_result(self, repository):
        """Test get_by_assistant returns empty list when no conversations."""
        # Arrange
        assistant_id = str(ObjectId())
        
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])
        repository._collection.find = MagicMock(return_value=mock_cursor)
        
        # Act
        result = await repository.get_by_assistant(assistant_id)
        
        # Assert
        assert result == []
    
    @pytest.mark.asyncio
    async def test_update_analytic_meta_success(self, repository):
        """Test update_analytic_meta updates and returns conversation."""
        # Arrange
        conversation_id = str(ObjectId())
        analytic_meta = {
            "overall_score": 4.5,
            "category_scores": [],
            "survey_status": "completed",
            "final_stage": "survey_complete",
            "analyzed_at": "2026-02-01T10:00:00Z"
        }
        
        updated_doc = {
            "_id": ObjectId(conversation_id),
            "interlocutor_id": ObjectId(),
            "assistant_id": ObjectId(),
            "connection_id": ObjectId(),
            "state": {},
            "analytic_meta": analytic_meta
        }
        
        repository._collection.find_one_and_update = AsyncMock(return_value=updated_doc)
        
        # Act
        result = await repository.update_analytic_meta(conversation_id, analytic_meta)
        
        # Assert
        assert result is not None
        assert isinstance(result, Conversation)
        assert result.analytic_meta == analytic_meta
        repository._collection.find_one_and_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_analytic_meta_not_found(self, repository):
        """Test update_analytic_meta returns None when conversation not found."""
        # Arrange
        conversation_id = str(ObjectId())
        analytic_meta = {"overall_score": 4.5}
        
        repository._collection.find_one_and_update = AsyncMock(return_value=None)
        
        # Act
        result = await repository.update_analytic_meta(conversation_id, analytic_meta)
        
        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_find_follow_up_candidates_with_extra_filter(self, repository):
        assistant_id = str(ObjectId())
        id1, id2 = ObjectId(), ObjectId()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"_id": id1}, {"_id": id2}])
        repository._collection.find = MagicMock(return_value=mock_cursor)

        extra = {"state.agent_metadata.state": {"$nin": ["completed", "closing"]}}
        result = await repository.find_follow_up_candidates(
            assistant_id, extra_filter=extra
        )

        assert result == [str(id1), str(id2)]
        query = repository._collection.find.call_args[0][0]
        assert query["assistant_id"] == ObjectId(assistant_id)
        assert query["is_mock"] == {"$ne": True}
        assert query["state.agent_metadata.state"] == {"$nin": ["completed", "closing"]}

    @pytest.mark.asyncio
    async def test_find_follow_up_candidates_no_extra_filter(self, repository):
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        repository._collection.find = MagicMock(return_value=mock_cursor)

        result = await repository.find_follow_up_candidates(str(ObjectId()))

        assert result == []
        query = repository._collection.find.call_args[0][0]
        assert "state.agent_metadata.state" not in query

