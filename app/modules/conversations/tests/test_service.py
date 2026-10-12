"""Unit tests for ConversationsService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone

from app.modules.conversations.service import ConversationsService
from app.modules.conversations.schemas import IncomingMessage, ProcessingResult, AgentResponse
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models import ConversationMessage
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.conversations.exceptions import ProcessingError
from app.modules.assistants.models import Assistant, AssistantType, AssistantStatus


class TestConversationsServiceTypingIndicator:
    """Test suite for typing indicator functionality in ConversationsService."""
    
    @pytest.fixture
    def mock_publisher(self):
        """Create mock publisher."""
        publisher = MagicMock()
        publisher.publish_typing_indicator = AsyncMock()
        publisher.publish_outgoing_message = AsyncMock()
        return publisher
    
    @pytest.fixture
    def service(self, mock_publisher):
        """Create ConversationsService instance with mocked dependencies."""
        service = ConversationsService(publisher=mock_publisher)
        service._assistant_service = MagicMock()
        service._webhook_service = MagicMock()
        return service
    
    @pytest.fixture
    def mock_assistant(self):
        """Create mock assistant."""
        assistant = MagicMock(spec=Assistant)
        assistant.id = ObjectId()
        assistant.name = "Test Assistant"
        assistant.type = AssistantType.SURVEY
        assistant.status = AssistantStatus.ACTIVE
        return assistant
    
    @pytest.fixture
    def mock_interlocutor(self):
        """Create mock interlocutor."""
        interlocutor = MagicMock(spec=Interlocutor)
        interlocutor.id = ObjectId()
        interlocutor.user_id = "telegram_284639219"
        return interlocutor
    
    @pytest.fixture
    def mock_conversation(self, mock_interlocutor, mock_assistant):
        """Create mock conversation."""
        conversation = MagicMock(spec=Conversation)
        conversation.id = ObjectId()
        conversation.interlocutor_id = mock_interlocutor.id
        conversation.assistant_id = mock_assistant.id
        conversation.state = {}
        return conversation
    
    @pytest.fixture
    def incoming_message(self, mock_assistant):
        """Create incoming message for testing."""
        return IncomingMessage(
            assistant_id=str(mock_assistant.id),
            connection_id=str(ObjectId()),
            user_id="telegram_284639219",
            type="message",
            text="Hello!"
        )
    
    @pytest.mark.asyncio
    async def test_process_message_sends_typing_indicator(
        self,
        service,
        mock_publisher,
        mock_assistant,
        mock_interlocutor,
        mock_conversation,
        incoming_message
    ):
        """Test that typing indicator is sent before agent processes message."""
        # Setup mocks
        service._assistant_service.get_assistant_internal = AsyncMock(
            return_value=mock_assistant
        )
        service._webhook_service.get_user_info_from_event = AsyncMock(
            return_value={}
        )
        
        with patch(
            "app.modules.conversations.service.InterlocutorRepository"
        ) as mock_interlocutor_repo_class, \
        patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_conversation_repo_class, \
        patch(
            "app.modules.conversations.service.AgentFactory"
        ) as mock_agent_factory:
            
            # Setup repository mocks
            mock_interlocutor_repo = MagicMock()
            mock_interlocutor_repo.get_or_create = AsyncMock(
                return_value=mock_interlocutor
            )
            mock_interlocutor_repo_class.return_value = mock_interlocutor_repo
            
            mock_conversation_repo = MagicMock()
            mock_conversation_repo.get_or_create = AsyncMock(
                return_value=mock_conversation
            )
            mock_conversation_repo_class.return_value = mock_conversation_repo
            
            # Setup agent mock
            mock_agent = MagicMock()
            mock_agent.process_message = AsyncMock(
                return_value=AgentResponse(response_text="Hello back!")
            )
            mock_agent_factory.get_agent.return_value = mock_agent
            
            # Process message
            result = await service.process_incoming_message(incoming_message)
            
            # Verify typing indicator was published
            mock_publisher.publish_typing_indicator.assert_called_once_with(
                assistant_id=incoming_message.assistant_id,
                connection_id=incoming_message.connection_id,
                user_id=incoming_message.user_id,
                trace_id=incoming_message.trace_id
            )
            
            # Verify agent was called AFTER typing indicator
            mock_agent.process_message.assert_called_once()
            
            # Verify response was published
            mock_publisher.publish_outgoing_message.assert_called_once()
            
            assert result.success is True
            assert result.response_generated is True
    
    @pytest.mark.asyncio
    async def test_typing_indicator_failure_does_not_block_processing(
        self,
        service,
        mock_publisher,
        mock_assistant,
        mock_interlocutor,
        mock_conversation,
        incoming_message
    ):
        """Test that typing indicator failure doesn't block message processing."""
        # Setup typing indicator to fail
        mock_publisher.publish_typing_indicator = AsyncMock(
            side_effect=Exception("RabbitMQ error")
        )
        
        # Setup mocks
        service._assistant_service.get_assistant_internal = AsyncMock(
            return_value=mock_assistant
        )
        service._webhook_service.get_user_info_from_event = AsyncMock(
            return_value={}
        )
        
        with patch(
            "app.modules.conversations.service.InterlocutorRepository"
        ) as mock_interlocutor_repo_class, \
        patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_conversation_repo_class, \
        patch(
            "app.modules.conversations.service.AgentFactory"
        ) as mock_agent_factory:
            
            # Setup repository mocks
            mock_interlocutor_repo = MagicMock()
            mock_interlocutor_repo.get_or_create = AsyncMock(
                return_value=mock_interlocutor
            )
            mock_interlocutor_repo_class.return_value = mock_interlocutor_repo
            
            mock_conversation_repo = MagicMock()
            mock_conversation_repo.get_or_create = AsyncMock(
                return_value=mock_conversation
            )
            mock_conversation_repo_class.return_value = mock_conversation_repo
            
            # Setup agent mock
            mock_agent = MagicMock()
            mock_agent.process_message = AsyncMock(
                return_value=AgentResponse(response_text="Response!")
            )
            mock_agent_factory.get_agent.return_value = mock_agent
            
            # Process message - should succeed despite typing indicator failure
            result = await service.process_incoming_message(incoming_message)
            
            # Verify typing indicator was attempted
            mock_publisher.publish_typing_indicator.assert_called_once()
            
            # Verify agent was still called
            mock_agent.process_message.assert_called_once()
            
            # Verify response was still published
            mock_publisher.publish_outgoing_message.assert_called_once()
            
            # Processing should succeed
            assert result.success is True
            assert result.response_generated is True
    
    @pytest.mark.asyncio
    async def test_typing_indicator_called_with_trace_id(
        self,
        service,
        mock_publisher,
        mock_assistant,
        mock_interlocutor,
        mock_conversation
    ):
        """Test that typing indicator includes trace_id when provided."""
        incoming_message = IncomingMessage(
            assistant_id=str(mock_assistant.id),
            connection_id=str(ObjectId()),
            user_id="telegram_284639219",
            type="message",
            text="Hello!",
            trace_id="trace_abc123"
        )
        
        # Setup mocks
        service._assistant_service.get_assistant_internal = AsyncMock(
            return_value=mock_assistant
        )
        service._webhook_service.get_user_info_from_event = AsyncMock(
            return_value={}
        )
        
        with patch(
            "app.modules.conversations.service.InterlocutorRepository"
        ) as mock_interlocutor_repo_class, \
        patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_conversation_repo_class, \
        patch(
            "app.modules.conversations.service.AgentFactory"
        ) as mock_agent_factory:
            
            # Setup repository mocks
            mock_interlocutor_repo = MagicMock()
            mock_interlocutor_repo.get_or_create = AsyncMock(
                return_value=mock_interlocutor
            )
            mock_interlocutor_repo_class.return_value = mock_interlocutor_repo
            
            mock_conversation_repo = MagicMock()
            mock_conversation_repo.get_or_create = AsyncMock(
                return_value=mock_conversation
            )
            mock_conversation_repo_class.return_value = mock_conversation_repo
            
            # Setup agent mock
            mock_agent = MagicMock()
            mock_agent.process_message = AsyncMock(
                return_value=AgentResponse(response_text="Response!")
            )
            mock_agent_factory.get_agent.return_value = mock_agent
            
            # Process message
            await service.process_incoming_message(incoming_message)
            
            # Verify trace_id was passed to typing indicator
            call_args = mock_publisher.publish_typing_indicator.call_args
            assert call_args[1]["trace_id"] == "trace_abc123"


class TestConversationsServiceAnalytics:
    """Test suite for analytics methods in ConversationsService."""
    
    @pytest.fixture
    def service(self):
        """Create ConversationsService instance."""
        return ConversationsService()
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation."""
        return Conversation(
            id=ObjectId(),
            interlocutor_id=ObjectId(),
            assistant_id=ObjectId(),
            connection_id=ObjectId(),
            state={"agent_metadata": {"state": "intro"}},
            analytic_meta=None
        )
    
    @pytest.fixture
    def mock_conversation_message(self):
        """Create mock conversation message."""
        return ConversationMessage(
            id=ObjectId(),
            conversation_id=ObjectId(),
            assistant_id=ObjectId(),
            interlocutor_id=ObjectId(),
            role="user",
            content="Hello!",
            state="intro",
            created_at=datetime.now(timezone.utc)
        )
    
    @pytest.mark.asyncio
    async def test_get_conversations_by_assistant_success(
        self,
        service,
        mock_conversation
    ):
        """Test get_conversations_by_assistant returns conversations."""
        assistant_id = str(ObjectId())
        
        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_by_assistant = AsyncMock(return_value=[mock_conversation])
            mock_repo_class.return_value = mock_repo
            
            # Act
            result = await service.get_conversations_by_assistant(assistant_id)
            
            # Assert
            assert len(result) == 1
            assert result[0] == mock_conversation
            mock_repo.get_by_assistant.assert_called_once_with(
                assistant_id=assistant_id,
                stage=None,
                include_mock=None
            )
    
    @pytest.mark.asyncio
    async def test_get_conversations_by_assistant_with_stage(
        self,
        service,
        mock_conversation
    ):
        """Test get_conversations_by_assistant with stage filter."""
        assistant_id = str(ObjectId())
        stage = "survey"
        
        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_by_assistant = AsyncMock(return_value=[mock_conversation])
            mock_repo_class.return_value = mock_repo
            
            # Act
            result = await service.get_conversations_by_assistant(
                assistant_id,
                stage=stage
            )
            
            # Assert
            mock_repo.get_by_assistant.assert_called_once_with(
                assistant_id=assistant_id,
                stage=stage,
                include_mock=None
            )
    
    @pytest.mark.asyncio
    async def test_get_conversations_by_assistant_error(self, service):
        """Test get_conversations_by_assistant raises ProcessingError on failure."""
        assistant_id = str(ObjectId())
        
        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_by_assistant = AsyncMock(
                side_effect=Exception("DB error")
            )
            mock_repo_class.return_value = mock_repo
            
            # Act & Assert
            with pytest.raises(ProcessingError) as exc_info:
                await service.get_conversations_by_assistant(assistant_id)
            
            assert "Failed to get conversations" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_full_history_success(
        self,
        service,
        mock_conversation_message
    ):
        """Test get_full_history returns message history."""
        conversation_id = str(ObjectId())
        
        with patch(
            "app.modules.conversations.service.ConversationHistoryRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_full_history = AsyncMock(
                return_value=[mock_conversation_message]
            )
            mock_repo_class.return_value = mock_repo
            
            # Act
            result = await service.get_full_history(conversation_id, limit=100)
            
            # Assert
            assert len(result) == 1
            assert result[0] == mock_conversation_message
            mock_repo.get_full_history.assert_called_once_with(
                conversation_id=conversation_id,
                limit=100
            )
    
    @pytest.mark.asyncio
    async def test_get_full_history_default_limit(self, service):
        """Test get_full_history uses default limit of 500."""
        conversation_id = str(ObjectId())
        
        with patch(
            "app.modules.conversations.service.ConversationHistoryRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_full_history = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo
            
            # Act
            await service.get_full_history(conversation_id)
            
            # Assert - default limit is 500
            mock_repo.get_full_history.assert_called_once_with(
                conversation_id=conversation_id,
                limit=500
            )
    
    @pytest.mark.asyncio
    async def test_get_full_history_error(self, service):
        """Test get_full_history raises ProcessingError on failure."""
        conversation_id = str(ObjectId())
        
        with patch(
            "app.modules.conversations.service.ConversationHistoryRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_full_history = AsyncMock(
                side_effect=Exception("DB error")
            )
            mock_repo_class.return_value = mock_repo
            
            # Act & Assert
            with pytest.raises(ProcessingError) as exc_info:
                await service.get_full_history(conversation_id)
            
            assert "Failed to get full history" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_analytic_meta_success(
        self,
        service,
        mock_conversation
    ):
        """Test update_analytic_meta updates and returns conversation."""
        conversation_id = str(ObjectId())
        analytic_meta = {
            "overall_score": 4.5,
            "category_scores": [],
            "survey_status": "completed",
            "final_stage": "survey_complete",
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
        
        mock_conversation.analytic_meta = analytic_meta
        
        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.update_analytic_meta = AsyncMock(return_value=mock_conversation)
            mock_repo_class.return_value = mock_repo
            
            # Act
            result = await service.update_analytic_meta(
                conversation_id,
                analytic_meta
            )
            
            # Assert
            assert result == mock_conversation
            mock_repo.update_analytic_meta.assert_called_once_with(
                conversation_id=conversation_id,
                analytic_meta=analytic_meta
            )
    
    @pytest.mark.asyncio
    async def test_update_analytic_meta_not_found(self, service):
        """Test update_analytic_meta raises error when conversation not found."""
        conversation_id = str(ObjectId())
        analytic_meta = {"overall_score": 4.5}
        
        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.update_analytic_meta = AsyncMock(return_value=None)
            mock_repo_class.return_value = mock_repo
            
            # Act & Assert
            with pytest.raises(ProcessingError) as exc_info:
                await service.update_analytic_meta(conversation_id, analytic_meta)
            
            assert "Conversation not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_analytic_meta_error(self, service):
        """Test update_analytic_meta raises ProcessingError on failure."""
        conversation_id = str(ObjectId())
        analytic_meta = {"overall_score": 4.5}
        
        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.update_analytic_meta = AsyncMock(
                side_effect=Exception("DB error")
            )
            mock_repo_class.return_value = mock_repo
            
            # Act & Assert
            with pytest.raises(ProcessingError) as exc_info:
                await service.update_analytic_meta(conversation_id, analytic_meta)
            
            assert "Failed to update analytic_meta" in str(exc_info.value)


class TestConversationsServiceCreateMockConversation:
    """Tests for ConversationsService.create_mock_conversation."""

    @pytest.fixture
    def service(self):
        return ConversationsService()

    @pytest.mark.asyncio
    async def test_create_mock_conversation_returns_conversation_id(self, service):
        """create_mock_conversation creates a real Interlocutor and a Conversation, returns conv id."""
        conv_id = ObjectId()
        interlocutor_id = ObjectId()
        mock_conversation = MagicMock(spec=Conversation)
        mock_conversation.id = conv_id
        mock_interlocutor = MagicMock()
        mock_interlocutor.id = interlocutor_id
        save_message_mock = AsyncMock()

        with patch(
            "app.modules.conversations.service.ConversationRepository"
        ) as mock_conv_repo_class, patch(
            "app.modules.conversations.service.InterlocutorRepository"
        ) as mock_ilr_class:
            mock_conv_repo = MagicMock()
            mock_conv_repo.create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.update_state = AsyncMock(return_value=True)
            mock_conv_repo_class.return_value = mock_conv_repo

            mock_ilr = MagicMock()
            mock_ilr.create_mock = AsyncMock(return_value=mock_interlocutor)
            mock_ilr_class.return_value = mock_ilr

            with patch.object(service, "save_message", save_message_mock):
                result = await service.create_mock_conversation(
                    assistant_id=str(ObjectId()),
                    connection_id=str(ObjectId()),
                    stage="completed",
                    messages=[
                        ("user", "Hi", "intro"),
                        ("assistant", "Hello", "intro"),
                    ],
                    mock_name="Alex",
                    respondent_index=1,
                )
        assert result == str(conv_id)
        mock_ilr.create_mock.assert_called_once()
        mock_conv_repo.create.assert_called_once()
        call_kwargs = mock_conv_repo.create.call_args[1]
        assert call_kwargs.get("is_mock") is True
        mock_conv_repo.update_state.assert_called_once_with(
            str(conv_id), {"agent_metadata": {"state": "completed"}}
        )
        assert save_message_mock.await_count == 2

    @pytest.mark.asyncio
    async def test_create_mock_conversation_raises_on_create_failure(self, service):
        """create_mock_conversation raises ProcessingError when interlocutor create fails."""
        with patch(
            "app.modules.conversations.service.InterlocutorRepository"
        ) as mock_ilr_class:
            mock_ilr = MagicMock()
            mock_ilr.create_mock = AsyncMock(side_effect=Exception("DB error"))
            mock_ilr_class.return_value = mock_ilr

            with pytest.raises(ProcessingError) as exc_info:
                await service.create_mock_conversation(
                    assistant_id=str(ObjectId()),
                    connection_id=str(ObjectId()),
                    stage="questionnaire",
                    messages=[("user", "Hi", "intro")],
                    mock_name="Morgan",
                    respondent_index=1,
                )
            assert "Failed to create mock conversation" in str(exc_info.value)

