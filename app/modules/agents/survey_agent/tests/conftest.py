"""Shared fixtures for survey agent tests."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional, List
from bson import ObjectId

from app.modules.conversations.schemas import IncomingMessage
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant, AssistantStep, AssistantType, AssistantStatus
from app.modules.agents.survey_agent.config import SurveyStepKey


# ============================================================================
# OBJECT ID HELPERS
# ============================================================================

def make_object_id() -> ObjectId:
    """Generate a new ObjectId."""
    return ObjectId()


# ============================================================================
# MODEL FACTORIES
# ============================================================================

@pytest.fixture
def assistant_id() -> str:
    """Fixed assistant ID for tests."""
    return str(ObjectId())


@pytest.fixture
def connection_id() -> str:
    """Fixed connection ID for tests."""
    return str(ObjectId())


@pytest.fixture
def conversation_id() -> str:
    """Fixed conversation ID for tests."""
    return str(ObjectId())


@pytest.fixture
def interlocutor_id() -> str:
    """Fixed interlocutor ID for tests."""
    return str(ObjectId())


@pytest.fixture
def user_id() -> str:
    """Fixed user ID for tests."""
    return "telegram_123456789"


@pytest.fixture
def mock_assistant(assistant_id: str) -> Assistant:
    """Create a mock assistant."""
    return Assistant(
        id=ObjectId(assistant_id),
        org_id="org_test",
        owner_user_id="user@test.com",
        name="Test Survey Bot",
        description="Test survey assistant",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        metadata={
            "communication_style": "Be friendly and professional",
            "self_introduction": "I am a helpful survey assistant"
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_interlocutor(interlocutor_id: str, user_id: str) -> Interlocutor:
    """Create a mock interlocutor."""
    return Interlocutor(
        id=ObjectId(interlocutor_id),
        user_id=user_id,
        first_name="Test",
        last_name="User",
        username="testuser",
        language=None,
        profile={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


def create_conversation(
    conversation_id: str,
    interlocutor_id: str,
    assistant_id: str,
    connection_id: str,
    state: Optional[str] = None,
    agent_metadata: Optional[Dict[str, Any]] = None
) -> Conversation:
    """Factory for creating conversation with specific state."""
    metadata = agent_metadata or {}
    if state:
        metadata["state"] = state
    
    return Conversation(
        id=ObjectId(conversation_id),
        interlocutor_id=ObjectId(interlocutor_id),
        assistant_id=ObjectId(assistant_id),
        connection_id=ObjectId(connection_id),
        state={"agent_metadata": metadata} if metadata else {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_conversation(
    conversation_id: str,
    interlocutor_id: str,
    assistant_id: str,
    connection_id: str
) -> Conversation:
    """Create a mock conversation with empty state (first message)."""
    return create_conversation(
        conversation_id, interlocutor_id, assistant_id, connection_id
    )


# ============================================================================
# ASSISTANT STEPS FIXTURES
# ============================================================================

def create_step(
    assistant_id: str,
    step_key: str,
    order_no: int,
    enabled: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> AssistantStep:
    """Factory for creating assistant step."""
    return AssistantStep(
        id=ObjectId(),
        assistant_id=ObjectId(assistant_id),
        step_key=step_key,
        order_no=order_no,
        enabled=enabled,
        metadata=metadata or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def mock_all_steps(assistant_id: str) -> List[AssistantStep]:
    """Create all survey steps (all enabled)."""
    return [
        create_step(assistant_id, SurveyStepKey.LANG.value, 1, True, {"default_language": "English"}),
        create_step(assistant_id, SurveyStepKey.INTRO.value, 2, True),
        create_step(assistant_id, SurveyStepKey.PROFILE.value, 3, True, {"profile_prompt": "Tell me about your business"}),
        create_step(assistant_id, SurveyStepKey.QUESTIONNAIRE.value, 4, True, {
            "intro_prompt": "I'll ask you a few questions",
            "specific_questions": "What is your budget?\nWhat is your timeline?",
            "survey_goal": "Understand customer needs"
        }),
        create_step(assistant_id, SurveyStepKey.ADDITIONAL_INFO.value, 5, True, {"info_to_collect": "email"}),
        create_step(assistant_id, SurveyStepKey.CLOSING.value, 6, True, {"closing_generation_prompt": "Generate a personalized closing"}),
    ]


@pytest.fixture
def mock_steps_lang_disabled(assistant_id: str) -> List[AssistantStep]:
    """Create steps with LANG disabled."""
    return [
        create_step(assistant_id, SurveyStepKey.LANG.value, 1, False, {"default_language": "English"}),
        create_step(assistant_id, SurveyStepKey.INTRO.value, 2, True),
        create_step(assistant_id, SurveyStepKey.PROFILE.value, 3, True),
        create_step(assistant_id, SurveyStepKey.QUESTIONNAIRE.value, 4, True, {
            "intro_prompt": "Survey questions",
            "specific_questions": "What is your budget?"
        }),
        create_step(assistant_id, SurveyStepKey.ADDITIONAL_INFO.value, 5, True),
        create_step(assistant_id, SurveyStepKey.CLOSING.value, 6, True),
    ]


# ============================================================================
# INCOMING MESSAGE FACTORY
# ============================================================================

def create_incoming_message(
    assistant_id: str,
    connection_id: str,
    user_id: str,
    text: str = "",
    message_type: str = "message"
) -> IncomingMessage:
    """Factory for creating incoming messages."""
    return IncomingMessage(
        assistant_id=assistant_id,
        connection_id=connection_id,
        user_id=user_id,
        type=message_type,
        text=text,
        message_id=str(ObjectId())
    )


@pytest.fixture
def message_factory(assistant_id: str, connection_id: str, user_id: str):
    """Factory fixture for creating messages."""
    def _create(text: str = "", message_type: str = "message") -> IncomingMessage:
        return create_incoming_message(assistant_id, connection_id, user_id, text, message_type)
    return _create


# ============================================================================
# LLM RESPONSE MOCKS
# ============================================================================

class MockAIMessage:
    """Mock AIMessage from LangChain."""
    
    def __init__(self, content: str = "", tool_calls: Optional[List[Dict]] = None):
        self.content = content
        self.tool_calls = tool_calls or []


def create_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a tool call dict."""
    return {
        "name": name,
        "args": args,
        "id": f"call_{ObjectId()}"
    }


# LLM response factories for each step
def llm_response_lang(language: str = "English") -> MockAIMessage:
    """LLM response for LANG step - calls update_language tool."""
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("update_language", {"language": language})]
    )


def llm_response_intro(name: str = "Alex", next_step: str = "profile") -> MockAIMessage:
    """LLM response for INTRO step - calls save_name_and_transition tool."""
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("save_name_and_transition", {
            "name": name,
            "next_step_key": next_step
        })]
    )


def llm_response_profile(summary: str = "Software developer", next_step: str = "questionnaire") -> MockAIMessage:
    """LLM response for PROFILE step - calls save_profile tool."""
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("save_profile", {
            "profile_summary": summary,
            "next_step_key": next_step
        })]
    )


def llm_response_questionnaire(
    qa_pairs: Optional[List[Dict]] = None,
    next_step: str = "additional_info"
) -> MockAIMessage:
    """LLM response for QUESTIONNAIRE step - calls save_survey_answers tool (legacy)."""
    if qa_pairs is None:
        qa_pairs = [
            {"question": "What is your budget?", "answer": "$1000"},
            {"question": "What is your timeline?", "answer": "3 months"}
        ]
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("save_survey_answers", {
            "survey_data": qa_pairs,
            "next_step_key": next_step
        })]
    )


def llm_response_questionnaire_answer(answer: str = "Yes") -> MockAIMessage:
    """LLM response for QUESTIONNAIRE step - calls save_questionnaire_answer tool (incremental)."""
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("save_questionnaire_answer", {
            "answer": answer
        })]
    )


def llm_response_additional_info(
    info_type: str = "email",
    info_value: str = "alex@test.com",
    next_step: str = "closing"
) -> MockAIMessage:
    """LLM response for ADDITIONAL_INFO step - calls save_additional_info tool."""
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("save_additional_info", {
            "info_type": info_type,
            "info_value": info_value,
            "next_step_key": next_step
        })]
    )


def llm_response_closing(final_message: str = "Thank you for completing the survey!") -> MockAIMessage:
    """LLM response for CLOSING step - calls save_final_message tool."""
    return MockAIMessage(
        content="",
        tool_calls=[create_tool_call("save_final_message", {
            "final_message": final_message
        })]
    )


def llm_response_text_only(text: str) -> MockAIMessage:
    """LLM response with text only (no tool calls) - for intermediate messages."""
    return MockAIMessage(content=text, tool_calls=[])


# ============================================================================
# SERVICE MOCKS
# ============================================================================

@pytest.fixture
def mock_conversations_service():
    """Create mock ConversationsService."""
    service = MagicMock()
    service.update_agent_metadata = AsyncMock()
    service.save_message = AsyncMock()
    service.get_history = AsyncMock(return_value=[])
    service.get_conversation = AsyncMock()
    service.reset_conversation = AsyncMock()
    service.update_interlocutor_language = AsyncMock()
    service.update_interlocutor_name = AsyncMock()
    service.update_interlocutor_profile = AsyncMock()
    service.update_interlocutor_email = AsyncMock()
    return service


@pytest.fixture
def mock_assistant_service():
    """Create mock AssistantService."""
    service = MagicMock()
    service.get_steps_internal = AsyncMock()
    service.get_step_by_order = AsyncMock()
    service.get_current_step = AsyncMock()
    service.get_assistant_internal = AsyncMock()
    return service


@pytest.fixture
def mock_prompt_loader():
    """Create mock PromptLoader."""
    loader = MagicMock()
    loader.load_system_prompt = AsyncMock(return_value="You are a helpful survey assistant.")
    loader.load_step_system_prompt = AsyncMock(return_value="Conduct the {step_key} step.")
    return loader


# ============================================================================
# CONVERSATION STATE TRACKER
# ============================================================================

class ConversationStateTracker:
    """
    Helper class to track conversation state changes during tests.
    
    Simulates how conversation.state changes when tools update agent_metadata.
    """
    
    def __init__(self, initial_state: Optional[str] = None):
        self.agent_metadata: Dict[str, Any] = {}
        if initial_state:
            self.agent_metadata["state"] = initial_state
    
    def update(self, metadata: Dict[str, Any]) -> None:
        """Merge new metadata."""
        self.agent_metadata.update(metadata)
    
    def get_state(self) -> Optional[str]:
        """Get current state."""
        return self.agent_metadata.get("state")
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get full metadata."""
        return self.agent_metadata.copy()
    
    def to_conversation_state(self) -> Dict[str, Any]:
        """Convert to conversation.state format."""
        return {"agent_metadata": self.agent_metadata}


@pytest.fixture
def state_tracker():
    """Create a fresh state tracker."""
    return ConversationStateTracker()

