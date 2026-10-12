"""Tests for agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.modules.conversations.agents.test_agent import TestAgent
from app.modules.conversations.agents.factory import AgentFactory
from app.modules.conversations.schemas import IncomingMessage, AgentResponse
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant, AssistantType


class TestTestAgent:
    """Test TestAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create TestAgent instance."""
        return TestAgent()
    
    @pytest.fixture
    def mock_message(self):
        """Mock incoming message."""
        return IncomingMessage(
            assistant_id=str(ObjectId()),
            connection_id=str(ObjectId()),
            user_id="telegram_123",
            type="message",
            text="Hello bot",
            message_id="123"
        )
    
    @pytest.fixture
    def mock_conversation(self):
        """Mock conversation."""
        # Create a full mock instead of Pydantic model
        conv = MagicMock()
        conv.id = ObjectId()
        conv.interlocutor_id = ObjectId()
        conv.assistant_id = ObjectId()
        conv.connection_id = ObjectId()
        conv.state = {"message_count": 0}
        conv.update_state = AsyncMock()
        return conv
    
    @pytest.fixture
    def mock_interlocutor(self):
        """Mock interlocutor."""
        return Interlocutor(
            user_id="telegram_123",
            first_name="John",
            last_name="Doe"
        )
    
    @pytest.fixture
    def mock_assistant(self):
        """Mock assistant."""
        return Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Test Assistant",
            type=AssistantType.SURVEY
        )
    
    @pytest.mark.asyncio
    async def test_process_message(
        self,
        agent,
        mock_message,
        mock_conversation,
        mock_interlocutor,
        mock_assistant,
        monkeypatch
    ):
        """Test process_message generates response and updates state."""
        # Mock get_database
        mock_db = MagicMock()
        monkeypatch.setattr(
            "app.modules.conversations.agents.test_agent.get_database",
            AsyncMock(return_value=mock_db)
        )
        
        # Act
        result = await agent.process_message(
            mock_message,
            mock_conversation,
            mock_interlocutor,
            mock_assistant
        )
        
        # Assert
        assert isinstance(result, AgentResponse)
        assert result.response_text is not None
        assert "John" in result.response_text
        assert "Hello bot" in result.response_text
        
        # Check that state was updated
        mock_conversation.update_state.assert_called_once()
        call_args = mock_conversation.update_state.call_args[0]
        new_state = call_args[0]
        assert new_state["message_count"] == 1
        assert new_state["last_message"] == "Hello bot"


class TestTestAgentFollowUpDefaults:
    """TestAgent follow-up methods return safe defaults (no candidates, no reminder)."""

    @pytest.mark.asyncio
    async def test_generate_reminder_returns_none(self):
        agent = TestAgent()
        result = await agent.generate_reminder(MagicMock(), MagicMock(), MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_candidates_returns_empty(self):
        agent = TestAgent()
        result = await agent.list_follow_up_candidate_conversation_ids(str(ObjectId()))
        assert result == []



class TestAgentFactory:
    """Test AgentFactory."""
    
    def test_get_agent_survey(self):
        """Test get_agent for SURVEY type."""
        agent = AgentFactory.get_agent(AssistantType.SURVEY)
        
        assert agent is not None
        # Now returns SurveyAgent instead of TestAgent
        from app.modules.agents.survey_agent.agent import SurveyAgent
        assert isinstance(agent, SurveyAgent)
    
    def test_get_agent_faq(self):
        """Test get_agent for FAQ type."""
        agent = AgentFactory.get_agent(AssistantType.FAQ)
        assert isinstance(agent, TestAgent)
    
    def test_get_agent_support(self):
        """Test get_agent for SUPPORT type."""
        agent = AgentFactory.get_agent(AssistantType.SUPPORT)
        assert isinstance(agent, TestAgent)

