"""Activity functions for FollowUpScheduledWorkflow.

Two activities:
1. find_enabled_assistants — query DB for active assistants with follow-ups on
2. process_follow_ups — for one assistant: get candidates, FollowUpService.send_reminder each
"""

import logging
from dataclasses import dataclass
from typing import List

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class ProcessFollowUpsResult:
    assistant_id: str
    sent: int = 0
    skipped: int = 0
    errors: int = 0


@activity.defn
async def find_enabled_assistants() -> List[str]:
    """Return IDs of active assistants with follow_up_config.enabled == true."""
    from app.modules.assistants.service import AssistantService

    ids = await AssistantService().find_enabled_follow_up_assistant_ids()
    logger.info("find_enabled_assistants: found %d assistants", len(ids))
    return ids


@activity.defn
async def process_follow_ups(assistant_id: str) -> ProcessFollowUpsResult:
    """For one assistant: find candidates via ConversationsService, then send_reminder each."""
    from app.modules.assistants.service import AssistantService, AssistantNotFoundError
    from app.modules.conversations.service import ConversationsService
    from app.modules.follow_ups.service import FollowUpService

    result = ProcessFollowUpsResult(assistant_id=assistant_id)

    try:
        assistant = await AssistantService().get_assistant_internal(assistant_id)
    except AssistantNotFoundError:
        logger.warning("process_follow_ups: assistant %s not found, skipping", assistant_id)
        return result

    conv_service = ConversationsService()
    candidate_ids = await conv_service.get_follow_up_candidate_ids(
        assistant_id, assistant.type
    )
    if not candidate_ids:
        logger.info("process_follow_ups: assistant=%s, 0 candidates", assistant_id)
        return result

    service = FollowUpService()
    for conv_id in candidate_ids:
        try:
            r = await service.send_reminder(conv_id, auto=True)
            if r.sent:
                result.sent += 1
            else:
                result.skipped += 1
        except Exception:
            logger.exception("process_follow_ups: error conv=%s", conv_id)
            result.errors += 1

    logger.info(
        "process_follow_ups: assistant=%s sent=%d skipped=%d errors=%d",
        assistant_id, result.sent, result.skipped, result.errors,
    )
    return result
