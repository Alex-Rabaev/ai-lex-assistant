"""Follow-up service (v4): shared checks, agent reminder text, publish, append log on success."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.modules.assistants.models import FollowUpConfig
from app.modules.assistants.service import AssistantNotFoundError, AssistantService
from app.modules.connections.service import ConnectionService
from app.modules.conversations.publisher import ConversationsPublisher
from app.modules.conversations.service import ConversationsService
from app.modules.follow_ups.models import SendReminderResult
from app.modules.follow_ups.repository import FollowUpRepository

logger = logging.getLogger(__name__)

# v4 API reason codes (see follow-ups-implementation-ru.md)
REASON_CONVERSATION_NOT_FOUND = "conversation_not_found"
REASON_INTERLOCUTOR_NOT_FOUND = "interlocutor_not_found"
REASON_CONNECTION_NOT_FOUND = "connection_not_found"
REASON_OPTED_OUT = "opted_out"
REASON_BLOCKED = "blocked"
REASON_WHATSAPP_24H_PASSED = "whatsapp_24h_passed"
REASON_MAX_ATTEMPTS_REACHED = "max_attempts_reached"
REASON_NO_DELIVERY_CHANNEL = "no_delivery_channel"
REASON_AGENT_DECLINED = "agent_declined"
REASON_LLM_ERROR = "llm_error"

WHATSAPP_24H_HOURS = 24


def _channel_str(channel: object) -> str:
    if hasattr(channel, "value"):
        return str(channel.value)
    return str(channel)


class FollowUpService:
    """
    v4 follow-up pipeline.

    Checks → ConversationsService.generate_follow_up_reminder → publish →
    append follow_ups log only after publish succeeds.
    """

    def __init__(
        self,
        *,
        publisher: Optional[ConversationsPublisher] = None,
    ) -> None:
        self._follow_up_repo = FollowUpRepository()
        self._assistant_service = AssistantService()
        self._connection_service = ConnectionService()
        self._conversations_service = ConversationsService()
        self._publisher = publisher or ConversationsPublisher()

    def _skip(self, conversation_id: str, reason: str, **extra) -> SendReminderResult:
        detail = extra.get("detail", "")
        logger.info(
            "follow_up_skip conversation=%s reason=%s detail=%s",
            conversation_id, reason, detail or "-",
        )
        return SendReminderResult(sent=False, reason=reason)

    async def _load_assistant(self, assistant_id: str):
        try:
            return await self._assistant_service.get_assistant_internal(assistant_id)
        except AssistantNotFoundError:
            return None

    async def send_reminder(
        self, conversation_id: str, *, auto: bool = False
    ) -> SendReminderResult:
        """Send a follow-up reminder.

        Args:
            conversation_id: target conversation
            auto: True when called from Temporal workflow — applies idle
                  threshold, max_attempts and interval checks.  Manual
                  (admin-triggered) calls leave auto=False to bypass limits.
        """
        conversation = await self._conversations_service.get_conversation_internal(
            conversation_id
        )
        if not conversation:
            return self._skip(conversation_id, REASON_CONVERSATION_NOT_FOUND)

        aid = str(conversation.assistant_id)
        assistant = None

        interlocutor = await self._conversations_service.get_interlocutor_by_id(
            str(conversation.interlocutor_id)
        )
        if not interlocutor:
            return self._skip(conversation_id, REASON_INTERLOCUTOR_NOT_FOUND, assistant_id=aid)
        if interlocutor.opted_out:
            return self._skip(conversation_id, REASON_OPTED_OUT, assistant_id=aid)
        if interlocutor.blocked:
            return self._skip(conversation_id, REASON_BLOCKED, assistant_id=aid)

        anchor = conversation.last_user_message_at
        if anchor is None:
            return self._skip(conversation_id, REASON_AGENT_DECLINED, assistant_id=aid, detail="no_user_messages")
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        if auto:
            assistant = await self._load_assistant(aid)
            if assistant is None:
                return self._skip(
                    conversation_id, REASON_AGENT_DECLINED, assistant_id=aid, detail="assistant_not_found"
                )
            config: FollowUpConfig = assistant.follow_up_config or FollowUpConfig()
            sent_count = await self._follow_up_repo.count_since(conversation_id, anchor)

            if sent_count == 0:
                if now < anchor + timedelta(hours=config.idle_threshold_hours):
                    idle_hours = (now - anchor).total_seconds() / 3600
                    return self._skip(
                        conversation_id, REASON_AGENT_DECLINED, assistant_id=aid,
                        detail=f"idle_threshold_not_met: {idle_hours:.1f}h < {config.idle_threshold_hours}h",
                    )

            if sent_count >= config.max_attempts:
                return self._skip(conversation_id, REASON_MAX_ATTEMPTS_REACHED, assistant_id=aid)

            if sent_count > 0:
                last_sent = await self._follow_up_repo.last_sent_at_since(
                    conversation_id, anchor
                )
                if last_sent is not None:
                    if now < last_sent + timedelta(hours=config.idle_threshold_hours):
                        return self._skip(conversation_id, REASON_AGENT_DECLINED, assistant_id=aid, detail="interval_not_met")

        connection = await self._connection_service.get_connection_internal(
            str(conversation.connection_id)
        )
        if not connection:
            return self._skip(conversation_id, REASON_CONNECTION_NOT_FOUND, assistant_id=aid)

        channel = _channel_str(connection.channel).lower()

        if channel == "whatsapp":
            if anchor < now - timedelta(hours=WHATSAPP_24H_HOURS):
                return self._skip(conversation_id, REASON_WHATSAPP_24H_PASSED, assistant_id=aid)

        if assistant is None:
            assistant = await self._load_assistant(aid)
            if assistant is None:
                return self._skip(
                    conversation_id, REASON_AGENT_DECLINED, assistant_id=aid, detail="assistant_not_found"
                )

        try:
            reminder_text = await self._conversations_service.generate_follow_up_reminder(
                conversation, interlocutor, assistant
            )
        except Exception:
            logger.exception(
                "follow_up_error conversation=%s stage=generate_reminder", conversation_id,
                extra={"conversation_id": conversation_id, "assistant_id": aid},
            )
            return self._skip(conversation_id, REASON_LLM_ERROR, assistant_id=aid, detail="generate_reminder_exception")

        if not (reminder_text and reminder_text.strip()):
            return self._skip(conversation_id, REASON_LLM_ERROR, assistant_id=aid, detail="empty_reminder_text")

        try:
            await self._publisher.publish_outgoing_message(
                assistant_id=aid,
                connection_id=str(conversation.connection_id),
                user_id=interlocutor.user_id,
                response_text=reminder_text.strip(),
                message_type="message",
                parse_mode="HTML",
                conversation_id=conversation_id,
            )
        except Exception:
            logger.exception(
                "follow_up_error conversation=%s stage=publish", conversation_id,
                extra={"conversation_id": conversation_id, "assistant_id": aid},
            )
            return self._skip(conversation_id, REASON_LLM_ERROR, assistant_id=aid, detail="publish_exception")

        await self._follow_up_repo.append_log_entry(
            conversation_id=conversation_id,
            assistant_id=aid,
            interlocutor_id=str(conversation.interlocutor_id),
        )

        logger.info(
            "follow_up_sent conversation=%s assistant=%s channel=%s",
            conversation_id, aid, channel,
            extra={"conversation_id": conversation_id, "assistant_id": aid, "sent": True, "channel": channel},
        )
        return SendReminderResult(sent=True)
