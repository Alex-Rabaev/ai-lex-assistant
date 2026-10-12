"""API router for follow-up reminders."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.common.auth import get_current_admin_auth0, AdminUser
from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.modules.conversations.service import ConversationsService
from app.modules.follow_ups.models import SendReminderResponse
from app.modules.follow_ups.service import FollowUpService

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["follow-ups"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - No admin access"},
        404: {"description": "Conversation or assistant not found"},
    },
)


def get_follow_up_service() -> FollowUpService:
    """Get follow-up service instance."""
    return FollowUpService()


@router.post(
    "/{conversation_id}/send-reminder",
    response_model=SendReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Send manual follow-up reminder",
    description=(
        "Run v4 checks (idle threshold, max attempts, interval, opted_out, blocked, "
        "WhatsApp 24h window, delivery channel), generate reminder text via the agent, "
        "publish to outbound queue, and append to follow_ups log on success. "
        "Always returns 200 with `sent` flag and optional `reason` code."
    ),
)
async def send_manual_reminder(
    conversation_id: str = Path(..., description="Conversation ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    follow_up_service: FollowUpService = Depends(get_follow_up_service),
) -> SendReminderResponse:
    """Send manual follow-up reminder. Verifies conversation belongs to user's assistant."""
    conversation = await ConversationsService().get_conversation_internal(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    try:
        await AssistantService().get_assistant(
            assistant_id=str(conversation.assistant_id),
            user_id=current_admin.email,
        )
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found or no access",
        )

    result = await follow_up_service.send_reminder(conversation_id)
    return SendReminderResponse(
        sent=result.sent,
        conversation_id=conversation_id,
        reason=result.reason,
    )
