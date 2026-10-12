"""FollowUpScheduledWorkflow — Temporal Workflow that runs every 5 minutes.

1. Activity: find_enabled_assistants → list of assistant IDs
2. For each assistant (max 20 in parallel): activity process_follow_ups
No retry — what fails this run will be picked up in the next 5-minute window.
"""

from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from app.modules.workflows.implementations.follow_up.activities import (
        ProcessFollowUpsResult,
    )

NO_RETRY = RetryPolicy(maximum_attempts=1)
FIND_TIMEOUT = timedelta(seconds=30)
PROCESS_TIMEOUT = timedelta(minutes=4)
MAX_PARALLEL = 20


@workflow.defn(name="FollowUpScheduledWorkflow")
class FollowUpScheduledWorkflow:
    """Scheduled every 5 min: find enabled assistants → process follow-ups for each."""

    @workflow.run
    async def run(self) -> Dict[str, Any]:
        assistant_ids: List[str] = await workflow.execute_activity(
            "find_enabled_assistants",
            start_to_close_timeout=FIND_TIMEOUT,
            retry_policy=NO_RETRY,
        )

        if not assistant_ids:
            return {"status": "completed", "assistants": 0, "total_sent": 0}

        total_sent = 0
        total_skipped = 0
        total_errors = 0

        for batch_start in range(0, len(assistant_ids), MAX_PARALLEL):
            batch = assistant_ids[batch_start : batch_start + MAX_PARALLEL]
            handles = []
            for aid in batch:
                h = workflow.start_activity(
                    "process_follow_ups",
                    aid,
                    start_to_close_timeout=PROCESS_TIMEOUT,
                    retry_policy=NO_RETRY,
                )
                handles.append(h)

            for h in handles:
                try:
                    result = await h
                    if isinstance(result, dict):
                        total_sent += result.get("sent", 0)
                        total_skipped += result.get("skipped", 0)
                        total_errors += result.get("errors", 0)
                    else:
                        total_sent += result.sent
                        total_skipped += result.skipped
                        total_errors += result.errors
                except ActivityError as e:
                    total_errors += 1
                    workflow.logger.warning("process_follow_ups activity failed: %s", e)

        return {
            "status": "completed",
            "assistants": len(assistant_ids),
            "total_sent": total_sent,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
        }
