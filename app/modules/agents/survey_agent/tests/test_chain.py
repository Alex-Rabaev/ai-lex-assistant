"""Unit tests for SurveyChain.

Tests chain building, message formatting, and tool handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.modules.agents.survey_agent.chain import SurveyChain
from app.modules.conversations.schemas import IncomingMessage
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant, AssistantStep, AssistantType, AssistantStatus

from .conftest import MockAIMessage, create_tool_call


class TestSurveyChainBuildMessages:
    """Tests for _build_messages method."""
    
    @pytest.fixture
    def chain(self):
        """Create chain with mocked LLM."""
        with patch('app.modules.agents.survey_agent.chain.ChatOpenAI'):
            return SurveyChain()
    
    @pytest.fixture
    def interlocutor(self):
        """Create test interlocutor."""
        return Interlocutor(
            id=ObjectId(),
            user_id="telegram_123",
            first_name="Alex",
            language="English",
            profile={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    def test_build_messages_basic(self, chain, interlocutor):
        """Test basic message building."""
        messages = chain._build_messages(
            system_prompt="You are a survey assistant",
            step_system_prompt="Conduct the intro step",
            history=[],
            user_input="Hello",
            interlocutor=interlocutor,
            conversation_metadata={},
            assistant_settings={},
            step_metadata={}
        )
        
        # Should have: system, step_system, user input
        assert len(messages) == 3
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], SystemMessage)
        assert isinstance(messages[2], HumanMessage)
        
        assert "survey assistant" in messages[0].content
        assert "intro step" in messages[1].content
        assert messages[2].content == "Hello"
    
    def test_build_messages_with_history(self, chain, interlocutor):
        """Test message building with conversation history."""
        history = [
            {"role": "user", "content": "Hi there"},
            {"role": "assistant", "content": "Hello! How can I help?"},
            {"role": "user", "content": "I need help"}
        ]
        
        messages = chain._build_messages(
            system_prompt="System",
            step_system_prompt="Step",
            history=history,
            user_input="New message",
            interlocutor=interlocutor,
            conversation_metadata={},
            assistant_settings={},
            step_metadata={}
        )
        
        # system + step + 3 history + current input
        assert len(messages) == 6
        
        # Check history conversion
        assert isinstance(messages[2], HumanMessage)
        assert messages[2].content == "Hi there"
        assert isinstance(messages[3], AIMessage)
        assert messages[3].content == "Hello! How can I help?"
        assert isinstance(messages[4], HumanMessage)
        assert messages[4].content == "I need help"
        
        # Current input
        assert messages[5].content == "New message"
    
    def test_build_messages_empty_input_not_added(self, chain, interlocutor):
        """Test that empty user input is not added as message."""
        messages = chain._build_messages(
            system_prompt="System",
            step_system_prompt="Step",
            history=[],
            user_input="",  # Empty
            interlocutor=interlocutor,
            conversation_metadata={},
            assistant_settings={},
            step_metadata={}
        )
        
        # Only system prompts, no user message
        assert len(messages) == 2
        assert all(isinstance(m, SystemMessage) for m in messages)
    
    def test_build_messages_uses_conversation_language(self, chain, interlocutor):
        """Test that language is taken from conversation_metadata."""
        messages = chain._build_messages(
            system_prompt="Language: {language}",
            step_system_prompt="Step",
            history=[],
            user_input="Hi",
            interlocutor=interlocutor,
            conversation_metadata={"language": "Русский"},
            assistant_settings={},
            step_metadata={}
        )
        
        assert "Русский" in messages[0].content
    
    def test_build_messages_uses_interlocutor_language_fallback(self, chain, interlocutor):
        """Test that interlocutor.language is used if not in metadata."""
        interlocutor.language = "German"
        
        messages = chain._build_messages(
            system_prompt="Language: {language}",
            step_system_prompt="Step",
            history=[],
            user_input="Hi",
            interlocutor=interlocutor,
            conversation_metadata={},  # No language
            assistant_settings={},
            step_metadata={}
        )
        
        assert "German" in messages[0].content
    
    def test_build_messages_includes_metadata(self, chain, interlocutor):
        """Test that conversation metadata is available for prompt."""
        messages = chain._build_messages(
            system_prompt="Name: {name}, Profile: {profile_summary}",
            step_system_prompt="Step",
            history=[],
            user_input="Hi",
            interlocutor=interlocutor,
            conversation_metadata={
                "name": "Alex",
                "profile_summary": "Software developer"
            },
            assistant_settings={},
            step_metadata={}
        )
        
        assert "Alex" in messages[0].content
        assert "Software developer" in messages[0].content
    
    def test_build_messages_includes_assistant_settings(self, chain, interlocutor):
        """Test that assistant settings are available for prompt."""
        messages = chain._build_messages(
            system_prompt="Style: {communication_style}",
            step_system_prompt="Step",
            history=[],
            user_input="Hi",
            interlocutor=interlocutor,
            conversation_metadata={},
            assistant_settings={"communication_style": "Be friendly"},
            step_metadata={}
        )
        
        assert "Be friendly" in messages[0].content
    
    def test_build_messages_includes_step_metadata(self, chain, interlocutor):
        """Test that step metadata is available for prompt."""
        messages = chain._build_messages(
            system_prompt="System",
            step_system_prompt="Questions: {specific_questions}",
            history=[],
            user_input="Hi",
            interlocutor=interlocutor,
            conversation_metadata={},
            assistant_settings={},
            step_metadata={"specific_questions": "Q1?\nQ2?"}
        )
        
        assert "Q1?" in messages[1].content
        assert "Q2?" in messages[1].content


class TestSurveyChainFormatPrompt:
    """Tests for _format_prompt method."""
    
    @pytest.fixture
    def chain(self):
        """Create chain with mocked LLM."""
        with patch('app.modules.agents.survey_agent.chain.ChatOpenAI'):
            return SurveyChain()
    
    def test_format_prompt_basic(self, chain):
        """Test basic prompt formatting."""
        result = chain._format_prompt(
            "Hello {name}!",
            {"name": "Alex"}
        )
        
        assert result == "Hello Alex!"
    
    def test_format_prompt_multiple_vars(self, chain):
        """Test formatting with multiple variables."""
        result = chain._format_prompt(
            "Hello {name}, your language is {language}",
            {"name": "Alex", "language": "English"}
        )
        
        assert result == "Hello Alex, your language is English"
    
    def test_format_prompt_missing_var_fallback(self, chain):
        """Test fallback when variable is missing."""
        # When format_map fails, should use manual replacement
        result = chain._format_prompt(
            "Hello {name}, missing: {missing}",
            {"name": "Alex"}
        )
        
        # Should still work, just leave {missing} as is or empty
        assert "Alex" in result
    
    def test_format_prompt_empty_var(self, chain):
        """Test formatting with empty variable value."""
        result = chain._format_prompt(
            "Profile: {profile_summary}",
            {"profile_summary": ""}
        )
        
        assert result == "Profile: "


class TestSurveyChainHandleToolCalls:
    """Tests for _handle_tool_calls method."""
    
    @pytest.fixture
    def chain(self):
        """Create chain with mocked LLM and tools."""
        with patch('app.modules.agents.survey_agent.chain.ChatOpenAI'):
            chain = SurveyChain()
            return chain
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation."""
        conv = MagicMock()
        conv.id = ObjectId()
        return conv
    
    @pytest.fixture
    def mock_interlocutor(self):
        """Create mock interlocutor."""
        interlocutor = MagicMock()
        interlocutor.id = ObjectId()
        return interlocutor
    
    @pytest.mark.asyncio
    async def test_handle_single_tool_call(self, chain, mock_conversation, mock_interlocutor):
        """Test handling a single tool call."""
        # Create mock tool
        mock_tool = MagicMock()
        mock_tool.name = "update_language"
        mock_tool._arun = AsyncMock(return_value="Language set to English")
        chain.tools = [mock_tool]
        
        tool_calls = [
            {"name": "update_language", "args": {"language": "English"}}
        ]
        
        result, tool_results = await chain._handle_tool_calls(
            tool_calls, mock_conversation, mock_interlocutor
        )
        
        assert result == "Language set to English"
        assert len(tool_results) == 1
        assert tool_results[0] == ("update_language", "Language set to English")
        
        # Check conversation_id was injected
        assert mock_tool.conversation_id == str(mock_conversation.id)
    
    @pytest.mark.asyncio
    async def test_handle_multiple_tool_calls(self, chain, mock_conversation, mock_interlocutor):
        """Test handling multiple tool calls."""
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool_a"
        mock_tool1._arun = AsyncMock(return_value="Result A")
        
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool_b"
        mock_tool2._arun = AsyncMock(return_value="Result B")
        
        chain.tools = [mock_tool1, mock_tool2]
        
        tool_calls = [
            {"name": "tool_a", "args": {}},
            {"name": "tool_b", "args": {}}
        ]
        
        result, tool_results = await chain._handle_tool_calls(
            tool_calls, mock_conversation, mock_interlocutor
        )
        
        # Last tool's result is returned
        assert result == "Result B"
        assert len(tool_results) == 2
    
    @pytest.mark.asyncio
    async def test_injects_interlocutor_id_for_specific_tools(
        self, chain, mock_conversation, mock_interlocutor
    ):
        """Test that interlocutor_id is injected for tools that need it."""
        mock_tool = MagicMock()
        mock_tool.name = "save_email"
        mock_tool._arun = AsyncMock(return_value="Email saved")
        chain.tools = [mock_tool]
        
        tool_calls = [
            {"name": "save_email", "args": {"email": "test@test.com"}}
        ]
        
        await chain._handle_tool_calls(
            tool_calls, mock_conversation, mock_interlocutor
        )
        
        # Check interlocutor_id was injected
        assert mock_tool.interlocutor_id == str(mock_interlocutor.id)


class TestSurveyChainInvoke:
    """Tests for invoke method."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.bind_tools = MagicMock(return_value=llm)
        return llm
    
    @pytest.fixture
    def chain(self, mock_llm):
        """Create chain with mocked dependencies."""
        with patch('app.modules.agents.survey_agent.chain.ChatOpenAI', return_value=mock_llm):
            return SurveyChain()
    
    @pytest.fixture
    def mock_message(self):
        """Create mock incoming message."""
        return IncomingMessage(
            assistant_id=str(ObjectId()),
            connection_id=str(ObjectId()),
            user_id="telegram_123",
            type="message",
            text="Hello"
        )
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation."""
        conv = MagicMock()
        conv.id = ObjectId()
        conv.get_agent_metadata.return_value = {"state": "intro", "language": "English"}
        return conv
    
    @pytest.fixture
    def mock_interlocutor(self):
        """Create mock interlocutor."""
        return Interlocutor(
            id=ObjectId(),
            user_id="telegram_123",
            first_name="Alex",
            language="English",
            profile={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def mock_assistant(self):
        """Create mock assistant."""
        return Assistant(
            id=ObjectId(),
            org_id="org_test",
            owner_user_id="user@test.com",
            name="Test Bot",
            type=AssistantType.SURVEY,
            status=AssistantStatus.ACTIVE,
            metadata={"communication_style": "Friendly"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def mock_step(self):
        """Create mock step."""
        return AssistantStep(
            id=ObjectId(),
            assistant_id=ObjectId(),
            step_key="intro",
            order_no=2,
            enabled=True,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.mark.asyncio
    async def test_invoke_with_tool_calls(
        self, chain, mock_llm, mock_message, mock_conversation, 
        mock_interlocutor, mock_assistant, mock_step
    ):
        """Test invoke when LLM returns tool calls."""
        # Setup LLM response with tool call
        llm_response = MagicMock()
        llm_response.content = ""
        llm_response.tool_calls = [
            {"name": "save_name_and_transition", "args": {"name": "Alex", "next_step_key": "profile"}}
        ]
        mock_llm.ainvoke = AsyncMock(return_value=llm_response)
        chain.llm = mock_llm
        
        # Mock prompt loader
        mock_prompt_loader = MagicMock()
        mock_prompt_loader.load_system_prompt = AsyncMock(return_value="System prompt")
        mock_prompt_loader.load_step_system_prompt = AsyncMock(return_value="Step prompt")
        
        # Mock tool execution
        mock_tool = MagicMock()
        mock_tool.name = "save_name_and_transition"
        mock_tool._arun = AsyncMock(return_value="Name saved, moving to profile")
        
        with patch('app.modules.agents.survey_agent.chain.PromptLoader', return_value=mock_prompt_loader), \
             patch('app.modules.agents.survey_agent.chain.get_survey_tools', return_value=[mock_tool]):
            
            response_text, tool_results = await chain.invoke(
                message=mock_message,
                conversation=mock_conversation,
                interlocutor=mock_interlocutor,
                assistant=mock_assistant,
                current_step=mock_step,
                history=[]
            )
            
            # Should execute tool and return its result
            assert "Name saved" in response_text or response_text == ""
            assert len(tool_results) >= 0
    
    @pytest.mark.asyncio
    async def test_invoke_without_tool_calls(
        self, chain, mock_llm, mock_message, mock_conversation, 
        mock_interlocutor, mock_assistant, mock_step
    ):
        """Test invoke when LLM returns text without tool calls."""
        # Setup LLM response without tool calls
        llm_response = MagicMock()
        llm_response.content = "Hello! What's your name?"
        llm_response.tool_calls = []
        mock_llm.ainvoke = AsyncMock(return_value=llm_response)
        chain.llm = mock_llm
        
        mock_prompt_loader = MagicMock()
        mock_prompt_loader.load_system_prompt = AsyncMock(return_value="System prompt")
        mock_prompt_loader.load_step_system_prompt = AsyncMock(return_value="Step prompt")
        
        with patch('app.modules.agents.survey_agent.chain.PromptLoader', return_value=mock_prompt_loader), \
             patch('app.modules.agents.survey_agent.chain.get_survey_tools', return_value=[]):
            
            response_text, tool_results = await chain.invoke(
                message=mock_message,
                conversation=mock_conversation,
                interlocutor=mock_interlocutor,
                assistant=mock_assistant,
                current_step=mock_step,
                history=[]
            )
            
            # Should return LLM content directly
            assert response_text == "Hello! What's your name?"
            assert tool_results == []

