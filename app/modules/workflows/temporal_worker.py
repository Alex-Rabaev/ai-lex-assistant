"""Temporal Worker for executing Workflows and Activities.

Runs as a separate process that polls the Temporal Task Queue
and executes registered Workflows and Activities.

Usage:
    python -m app.modules.workflows.temporal_worker
"""

import asyncio
import logging
import signal
from datetime import timedelta
from typing import List, Type

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleIntervalSpec, ScheduleSpec
from temporalio.worker import Worker

from app.config import config

FOLLOW_UP_SCHEDULE_ID = "follow-up-every-5-min"

logger = logging.getLogger(__name__)



def get_workflow_classes() -> List[Type]:
    """Get all registered Workflow classes.
    
    Returns:
        List of Workflow classes to register with the Worker.
        
    Note:
        Add new workflow classes here as they are implemented.
        Example:
            from app.modules.workflows.implementations.analysis_snapshot.workflow import SnapshotWorkflow
            return [SnapshotWorkflow]
    """
    from app.modules.workflows.implementations.analysis_snapshot.workflow import SnapshotWorkflow
    from app.modules.workflows.implementations.follow_up.workflow import FollowUpScheduledWorkflow

    return [SnapshotWorkflow, FollowUpScheduledWorkflow]


def get_activity_functions() -> list:
    """Get all registered Activity functions.
    
    Returns:
        List of Activity functions to register with the Worker.
        
    Note:
        Add new activity functions here as they are implemented.
        Example:
            from app.modules.workflows.implementations.analysis_snapshot.activities import (
                generate_profile, generate_conclusions, save_snapshot, notify_websocket
            )
            return [generate_profile, generate_conclusions, save_snapshot, notify_websocket]
    """
    from app.modules.workflows.implementations.analysis_snapshot.activities import (
        load_assistant,
        load_conversations,
        compute_statistics,
        generate_profile,
        generate_conclusions,
        save_snapshot,
        notify_websocket,
    )
    from app.modules.workflows.implementations.follow_up.activities import (
        find_enabled_assistants,
        process_follow_ups,
    )

    return [
        load_assistant,
        load_conversations,
        compute_statistics,
        generate_profile,
        generate_conclusions,
        save_snapshot,
        notify_websocket,
        find_enabled_assistants,
        process_follow_ups,
    ]


async def run_worker(
    temporal_host: str = None,
    temporal_namespace: str = None,
    task_queue: str = None,
    max_concurrent_activities: int = None,
    max_concurrent_workflows: int = None,
) -> None:
    """Start and run the Temporal Worker.
    
    Connects to Temporal Service, registers Workflows and Activities,
    and begins polling the Task Queue for work.
    
    Args:
        temporal_host: Temporal gRPC endpoint
        temporal_namespace: Temporal namespace
        task_queue: Task Queue to poll
        max_concurrent_activities: Max concurrent Activity executions
        max_concurrent_workflows: Max concurrent Workflow executions
    """
    host = temporal_host or config.TEMPORAL_HOST
    namespace = temporal_namespace or config.TEMPORAL_NAMESPACE
    task_queue = task_queue or config.TEMPORAL_TASK_QUEUE
    max_concurrent_activities = max_concurrent_activities or config.TEMPORAL_MAX_CONCURRENT_ACTIVITIES
    max_concurrent_workflows = max_concurrent_workflows or config.TEMPORAL_MAX_CONCURRENT_WORKFLOWS
    
    logger.info(
        f"Starting Temporal Worker: "
        f"host={host}, namespace={namespace}, "
        f"task_queue={task_queue}"
    )
    
    # Connect to Temporal
    connect_kwargs = {"target_host": host, "namespace": namespace}
    
    api_key = config.TEMPORAL_API_KEY
    if api_key:
        connect_kwargs["api_key"] = api_key
        connect_kwargs["tls"] = True
        logger.info("Using Temporal Cloud (API Key + TLS)")
    
    client = await Client.connect(**connect_kwargs)
    logger.info("Connected to Temporal Service")
    
    # Get registered workflows and activities
    workflows = get_workflow_classes()
    activities = get_activity_functions()
    
    logger.info(
        f"Registered {len(workflows)} workflows, "
        f"{len(activities)} activities"
    )
    
    # Ensure follow-up schedule exists (idempotent)
    await _ensure_follow_up_schedule(client, task_queue)

    # Setup shutdown event
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run Worker
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=workflows,
        activities=activities,
        max_concurrent_activities=max_concurrent_activities,
        max_concurrent_workflow_tasks=max_concurrent_workflows,
    )
    
    logger.info(
        f"Temporal Worker started, polling '{task_queue}' "
        f"(max_activities={max_concurrent_activities}, "
        f"max_workflows={max_concurrent_workflows})"
    )
    
    # Run worker until shutdown signal
    async with worker:
        await shutdown_event.wait()
    
    logger.info("Temporal Worker stopped")


async def _ensure_follow_up_schedule(client: Client, task_queue: str) -> None:
    """Create the follow-up schedule if it doesn't already exist."""
    try:
        handle = client.get_schedule_handle(FOLLOW_UP_SCHEDULE_ID)
        desc = await handle.describe()
        logger.info("Follow-up schedule already exists (id=%s)", FOLLOW_UP_SCHEDULE_ID)
    except Exception:
        try:
            await client.create_schedule(
                FOLLOW_UP_SCHEDULE_ID,
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        "FollowUpScheduledWorkflow",
                        id="follow-up-scheduled-run",
                        task_queue=task_queue,
                    ),
                    spec=ScheduleSpec(
                        intervals=[ScheduleIntervalSpec(every=timedelta(minutes=5))],
                    ),
                ),
            )
            logger.info("Created follow-up schedule: every 5 min (id=%s)", FOLLOW_UP_SCHEDULE_ID)
        except Exception as e:
            logger.error("Failed to create follow-up schedule: %s", e)


async def main():
    """Main entry point for the Temporal Worker."""
    await run_worker()


if __name__ == "__main__":
    # Configure structured JSON logging
    from app.common.utils import setup_structured_logging
    setup_structured_logging()
    
    # Run worker
    asyncio.run(main())
