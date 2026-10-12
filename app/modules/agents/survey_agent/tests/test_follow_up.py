"""Tests for SurveyAgent follow-up methods (generate_reminder, list_follow_up_candidate_conversation_ids)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.modules.agents.survey_agent.agent import SurveyAgent, _FOLLOW_UP_EXCLUDED_STATES
from app.modules.agents.survey_agent.state import SurveyAgentState
from app.modules.agents.survey_agent.tests.conftest import create_conversation
from app.modules.assistants.models import Assistant, AssistantStatus, AssistantType
from app.modules.conversations.models.interlocutor import Interlocutor


def _ids():
    return str(ObjectId()), str(ObjectId()), str(ObjectId()), str(ObjectId())


def _interlocutor(iid):
    return Interlocutor(
        id=ObjectId(iid), user_id="telegram_1", first_name="Alex",
        language="Русский", opted_out=False, blocked=False,
    )


def _assistant(aid):
    return Assistant(
        id=ObjectId(aid), org_id="o", owner_user_id="u", name="Bot",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
    )


class TestGenerateReminder:
    @pytest.mark.asyncio
    async def test_completed_state_returns_none(self):
        cid, iid, aid, conn_id = _ids()
        conv = create_conversation(cid, iid, aid, conn_id, state=SurveyAgentState.COMPLETED.value)
        agent = SurveyAgent.__new__(SurveyAgent)

        result = await agent.generate_reminder(conv, _interlocutor(iid), _assistant(aid))

        assert result is None

    @pytest.mark.asyncio
    async def test_closing_state_returns_none(self):
        cid, iid, aid, conn_id = _ids()
        conv = create_conversation(cid, iid, aid, conn_id, state=SurveyAgentState.CLOSING.value)
        agent = SurveyAgent.__new__(SurveyAgent)

        result = await agent.generate_reminder(conv, _interlocutor(iid), _assistant(aid))

        assert result is None

    @pytest.mark.asyncio
    @patch("app.modules.agents.survey_agent.agent.ChatOpenAI")
    @patch("app.modules.agents.survey_agent.agent.PromptLoader")
    async def test_active_state_calls_llm(self, mock_loader_cls, mock_llm_cls):
        cid, iid, aid, conn_id = _ids()
        conv = create_conversation(
            cid, iid, aid, conn_id,
            agent_metadata={"state": "questionnaire", "language": "English"},
        )
        loader = MagicMock()
        loader.load_reminder_prompt = AsyncMock(
            return_value=("Remind {name} in {language}", "gpt-4.1-mini")
        )
        mock_loader_cls.return_value = loader

        llm_instance = MagicMock()
        llm_response = MagicMock()
        llm_response.content = "Hey Alex, please continue!"
        llm_instance.ainvoke = AsyncMock(return_value=llm_response)
        mock_llm_cls.return_value = llm_instance

        agent = SurveyAgent.__new__(SurveyAgent)
        agent._conversations_service = MagicMock()
        agent._conversations_service.get_history = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ])
        result = await agent.generate_reminder(conv, _interlocutor(iid), _assistant(aid))

        assert result == "Hey Alex, please continue!"
        llm_instance.ainvoke.assert_awaited_once()
        loader.load_reminder_prompt.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.modules.agents.survey_agent.agent.ChatOpenAI")
    @patch("app.modules.agents.survey_agent.agent.PromptLoader")
    async def test_model_from_langsmith_metadata(self, mock_loader_cls, mock_llm_cls):
        cid, iid, aid, conn_id = _ids()
        conv = create_conversation(cid, iid, aid, conn_id, state="intro")
        loader = MagicMock()
        loader.load_reminder_prompt = AsyncMock(
            return_value=("template", "gpt-4o")
        )
        mock_loader_cls.return_value = loader

        llm_instance = MagicMock()
        llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="Hi"))
        mock_llm_cls.return_value = llm_instance

        agent = SurveyAgent.__new__(SurveyAgent)
        agent._conversations_service = MagicMock()
        agent._conversations_service.get_history = AsyncMock(return_value=[])
        await agent.generate_reminder(conv, _interlocutor(iid), _assistant(aid))

        mock_llm_cls.assert_called_once()
        assert mock_llm_cls.call_args.kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    @patch("app.modules.agents.survey_agent.agent.ChatOpenAI")
    @patch("app.modules.agents.survey_agent.agent.PromptLoader")
    async def test_llm_empty_response_returns_none(self, mock_loader_cls, mock_llm_cls):
        cid, iid, aid, conn_id = _ids()
        conv = create_conversation(cid, iid, aid, conn_id, state="intro")
        loader = MagicMock()
        loader.load_reminder_prompt = AsyncMock(return_value=("template", "gpt-4.1-mini"))
        mock_loader_cls.return_value = loader

        llm_instance = MagicMock()
        llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content=""))
        mock_llm_cls.return_value = llm_instance

        agent = SurveyAgent.__new__(SurveyAgent)
        agent._conversations_service = MagicMock()
        agent._conversations_service.get_history = AsyncMock(return_value=[])
        result = await agent.generate_reminder(conv, _interlocutor(iid), _assistant(aid))

        assert result is None


class TestListFollowUpCandidates:
    @pytest.mark.asyncio
    async def test_delegates_to_conversations_service(self):
        aid = str(ObjectId())
        expected = [str(ObjectId()), str(ObjectId())]
        agent = SurveyAgent.__new__(SurveyAgent)
        agent._conversations_service = MagicMock()
        agent._conversations_service.find_follow_up_candidates = AsyncMock(return_value=expected)

        result = await agent.list_follow_up_candidate_conversation_ids(aid)

        assert result == expected
        agent._conversations_service.find_follow_up_candidates.assert_awaited_once_with(
            aid,
            extra_filter={"state.agent_metadata.state": {"$nin": _FOLLOW_UP_EXCLUDED_STATES}},
        )

    @pytest.mark.asyncio
    async def test_excluded_states_match_completed_and_closing(self):
        assert set(_FOLLOW_UP_EXCLUDED_STATES) == {
            SurveyAgentState.COMPLETED.value,
            SurveyAgentState.CLOSING.value,
        }
