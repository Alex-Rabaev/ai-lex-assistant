"""Tests for FollowUpService (v4 checks)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.modules.assistants.models import Assistant, AssistantStatus, AssistantType, FollowUpConfig
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionSettings,
    ConnectionStatus,
)
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.follow_ups import service as fu_service


@pytest.fixture
def service():
    with patch.object(fu_service, "FollowUpRepository"):
        svc = fu_service.FollowUpService()
        svc._follow_up_repo = MagicMock()
        svc._assistant_service = MagicMock()
        svc._connection_service = MagicMock()
        svc._conversations_service = MagicMock()
        svc._conversations_service.get_conversation_internal = AsyncMock()
        svc._conversations_service.generate_follow_up_reminder = AsyncMock(return_value=None)
        svc._conversations_service.get_interlocutor_by_id = AsyncMock()
        svc._publisher = MagicMock()
        svc._publisher.publish_outgoing_message = AsyncMock()
        return svc


def _conversation(
    *,
    conv_id: str,
    last_user_message_at=None,
    state: str = "questionnaire",
    assistant_id=None,
    interlocutor_id=None,
    connection_id=None,
):
    aid = assistant_id or ObjectId()
    iid = interlocutor_id or ObjectId()
    cid_conn = connection_id or ObjectId()
    now = datetime.now(timezone.utc)
    return Conversation(
        id=ObjectId(conv_id),
        interlocutor_id=iid,
        assistant_id=aid,
        connection_id=cid_conn,
        state={"agent_metadata": {"state": state}},
        created_at=now - timedelta(days=1),
        updated_at=now,
        last_user_message_at=last_user_message_at,
    )


@pytest.mark.asyncio
async def test_manual_conversation_not_found(service):
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=None)

    r = await service.send_reminder(str(ObjectId()))

    assert r.sent is False
    assert r.reason == fu_service.REASON_CONVERSATION_NOT_FOUND


@pytest.mark.asyncio
async def test_manual_completed_survey_agent_returns_none(service):
    """Completed conversations: agent's generate_reminder returns None → llm_error."""
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, state="completed", last_user_message_at=now - timedelta(hours=2))
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(enabled=True, idle_threshold_hours=1, max_attempts=3),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False)
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    conn = Connection(
        id=conv.connection_id, assistant_id=conv.assistant_id,
        channel=ConnectionChannel.TELEGRAM, status=ConnectionStatus.CONNECTED, settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)
    service._conversations_service.generate_follow_up_reminder = AsyncMock(return_value=None)

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_LLM_ERROR


@pytest.mark.asyncio
async def test_idle_not_met(service):
    """Auto mode rejects when idle threshold not met; manual mode would pass this check."""
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, last_user_message_at=now - timedelta(hours=1))
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=24, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)

    r = await service.send_reminder(conv_id, auto=True)

    assert r.sent is False
    assert r.reason == fu_service.REASON_AGENT_DECLINED


@pytest.mark.asyncio
async def test_auto_max_attempts(service):
    """Auto mode rejects when max_attempts reached."""
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(days=7),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=2
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)
    service._follow_up_repo.count_since = AsyncMock(return_value=2)

    r = await service.send_reminder(conv_id, auto=True)

    assert r.sent is False
    assert r.reason == fu_service.REASON_MAX_ATTEMPTS_REACHED


@pytest.mark.asyncio
async def test_interval_not_met(service):
    """Auto mode rejects when interval between reminders not met."""
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(days=7),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=48, max_attempts=5
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)
    service._follow_up_repo.count_since = AsyncMock(return_value=1)
    service._follow_up_repo.last_sent_at_since = AsyncMock(
        return_value=now - timedelta(hours=1)
    )

    r = await service.send_reminder(conv_id, auto=True)

    assert r.sent is False
    assert r.reason == fu_service.REASON_AGENT_DECLINED


@pytest.mark.asyncio
async def test_manual_bypasses_limits(service):
    """Manual send_reminder (auto=False) ignores idle, max_attempts, interval."""
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, last_user_message_at=now - timedelta(minutes=5))
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=False, idle_threshold_hours=24, max_attempts=1
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)
    conn = Connection(
        id=conv.connection_id, assistant_id=conv.assistant_id,
        channel=ConnectionChannel.TELEGRAM, status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)
    service._conversations_service.generate_follow_up_reminder = AsyncMock(return_value="Hey!")
    service._follow_up_repo.append_log_entry = AsyncMock()

    r = await service.send_reminder(conv_id)

    assert r.sent is True
    service._follow_up_repo.count_since.assert_not_called()


@pytest.mark.asyncio
async def test_manual_opted_out(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(days=7),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id,
        user_id="u1",
        opted_out=True,
        blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_OPTED_OUT
    service._assistant_service.get_assistant_internal.assert_not_called()


@pytest.mark.asyncio
async def test_no_user_messages_skipped(service):
    """When last_user_message_at is None the conversation has no user messages yet."""
    conv_id = str(ObjectId())
    conv = _conversation(conv_id=conv_id, last_user_message_at=None)
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(enabled=True, idle_threshold_hours=1, max_attempts=3),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_AGENT_DECLINED
    service._assistant_service.get_assistant_internal.assert_not_called()


@pytest.mark.asyncio
async def test_manual_whatsapp_window_passed(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(hours=30),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id,
        user_id="u1",
        opted_out=False,
        blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )
    conn = Connection(
        id=conv.connection_id,
        assistant_id=conv.assistant_id,
        channel=ConnectionChannel.WHATSAPP,
        status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_WHATSAPP_24H_PASSED
    service._assistant_service.get_assistant_internal.assert_not_called()


@pytest.mark.asyncio
async def test_manual_webchat_delivers_via_outbound(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(days=1),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id,
        user_id="webchat_abc",
        opted_out=False,
        blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )
    conn = Connection(
        id=conv.connection_id,
        assistant_id=conv.assistant_id,
        channel=ConnectionChannel.WEBCHAT,
        status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)

    service._conversations_service.generate_follow_up_reminder = AsyncMock(
        return_value="Come back!"
    )
    service._follow_up_repo.append_log_entry = AsyncMock()

    r = await service.send_reminder(conv_id)

    assert r.sent is True
    service._publisher.publish_outgoing_message.assert_awaited_once()
    call_kw = service._publisher.publish_outgoing_message.await_args.kwargs
    assert call_kw["conversation_id"] == conv_id


def _setup_passing_checks(service, conv, assistant, interlocutor, channel):
    """Wire mocks so all v4 checks pass, reaching the agent/publish stage."""
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )
    conn = Connection(
        id=conv.connection_id,
        assistant_id=conv.assistant_id,
        channel=channel,
        status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)


@pytest.mark.asyncio
async def test_manual_blocked_interlocutor(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, last_user_message_at=now - timedelta(days=7))
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(enabled=True, idle_threshold_hours=1, max_attempts=3),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=True,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_BLOCKED
    service._assistant_service.get_assistant_internal.assert_not_called()


@pytest.mark.asyncio
async def test_manual_agent_exception_returns_llm_error(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, last_user_message_at=now - timedelta(hours=1))
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(enabled=True, idle_threshold_hours=1, max_attempts=3),
    )
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="telegram_1", opted_out=False, blocked=False,
    )
    _setup_passing_checks(service, conv, assistant, interlocutor, ConnectionChannel.TELEGRAM)

    service._conversations_service.generate_follow_up_reminder = AsyncMock(
        side_effect=RuntimeError("LLM timeout")
    )

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_LLM_ERROR
    service._publisher.publish_outgoing_message.assert_not_called()


@pytest.mark.asyncio
async def test_manual_agent_empty_string_returns_llm_error(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, last_user_message_at=now - timedelta(hours=1))
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(enabled=True, idle_threshold_hours=1, max_attempts=3),
    )
    interlocutor = Interlocutor(
        id=conv.interlocutor_id, user_id="telegram_1", opted_out=False, blocked=False,
    )
    _setup_passing_checks(service, conv, assistant, interlocutor, ConnectionChannel.TELEGRAM)

    service._conversations_service.generate_follow_up_reminder = AsyncMock(return_value="   ")

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_LLM_ERROR
    service._publisher.publish_outgoing_message.assert_not_called()


@pytest.mark.asyncio
async def test_manual_closing_agent_returns_none(service):
    """Closing conversations: agent's generate_reminder returns None → llm_error."""
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(conv_id=conv_id, state="closing", last_user_message_at=now - timedelta(hours=2))
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id, org_id="o", owner_user_id="u", name="A",
        type=AssistantType.SURVEY, status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(enabled=True, idle_threshold_hours=1, max_attempts=3),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    interlocutor = Interlocutor(id=conv.interlocutor_id, user_id="u1", opted_out=False, blocked=False)
    service._conversations_service.get_interlocutor_by_id = AsyncMock(return_value=interlocutor)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    conn = Connection(
        id=conv.connection_id, assistant_id=conv.assistant_id,
        channel=ConnectionChannel.TELEGRAM, status=ConnectionStatus.CONNECTED, settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)
    service._conversations_service.generate_follow_up_reminder = AsyncMock(return_value=None)

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_LLM_ERROR


@pytest.mark.asyncio
async def test_telegram_agent_returns_none_llm_error(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(hours=1),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id,
        user_id="telegram_123",
        opted_out=False,
        blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )
    conn = Connection(
        id=conv.connection_id,
        assistant_id=conv.assistant_id,
        channel=ConnectionChannel.TELEGRAM,
        status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_LLM_ERROR
    service._publisher.publish_outgoing_message.assert_not_called()
    service._follow_up_repo.append_log_entry.assert_not_called()


@pytest.mark.asyncio
async def test_manual_telegram_publishes_and_appends_log(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(hours=1),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id,
        user_id="telegram_123",
        opted_out=False,
        blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )
    conn = Connection(
        id=conv.connection_id,
        assistant_id=conv.assistant_id,
        channel=ConnectionChannel.TELEGRAM,
        status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)

    service._conversations_service.generate_follow_up_reminder = AsyncMock(
        return_value="  Reminder text  "
    )
    service._follow_up_repo.append_log_entry = AsyncMock()

    r = await service.send_reminder(conv_id)

    assert r.sent is True
    assert r.reason is None
    service._publisher.publish_outgoing_message.assert_awaited_once()
    call_kw = service._publisher.publish_outgoing_message.await_args.kwargs
    assert call_kw["assistant_id"] == str(conv.assistant_id)
    assert call_kw["connection_id"] == str(conv.connection_id)
    assert call_kw["user_id"] == "telegram_123"
    assert call_kw["response_text"] == "Reminder text"
    assert call_kw["conversation_id"] == conv_id
    service._follow_up_repo.append_log_entry.assert_awaited_once_with(
        conversation_id=conv_id,
        assistant_id=str(conv.assistant_id),
        interlocutor_id=str(conv.interlocutor_id),
    )


@pytest.mark.asyncio
async def test_manual_publish_failure_no_log_append(service):
    conv_id = str(ObjectId())
    now = datetime.now(timezone.utc)
    conv = _conversation(
        conv_id=conv_id,
        last_user_message_at=now - timedelta(hours=1),
    )
    service._conversations_service.get_conversation_internal = AsyncMock(return_value=conv)
    assistant = Assistant(
        id=conv.assistant_id,
        org_id="o",
        owner_user_id="u",
        name="A",
        type=AssistantType.SURVEY,
        status=AssistantStatus.ACTIVE,
        follow_up_config=FollowUpConfig(
            enabled=True, idle_threshold_hours=1, max_attempts=3
        ),
    )
    service._assistant_service.get_assistant_internal = AsyncMock(return_value=assistant)
    service._follow_up_repo.count_since = AsyncMock(return_value=0)
    interlocutor = Interlocutor(
        id=conv.interlocutor_id,
        user_id="telegram_123",
        opted_out=False,
        blocked=False,
    )
    service._conversations_service.get_interlocutor_by_id = AsyncMock(
        return_value=interlocutor
    )
    conn = Connection(
        id=conv.connection_id,
        assistant_id=conv.assistant_id,
        channel=ConnectionChannel.TELEGRAM,
        status=ConnectionStatus.CONNECTED,
        settings=ConnectionSettings(),
    )
    service._connection_service.get_connection_internal = AsyncMock(return_value=conn)

    service._conversations_service.generate_follow_up_reminder = AsyncMock(return_value="Hi")
    service._publisher.publish_outgoing_message = AsyncMock(
        side_effect=RuntimeError("queue down")
    )
    service._follow_up_repo.append_log_entry = AsyncMock()

    r = await service.send_reminder(conv_id)

    assert r.sent is False
    assert r.reason == fu_service.REASON_LLM_ERROR
    service._follow_up_repo.append_log_entry.assert_not_called()
