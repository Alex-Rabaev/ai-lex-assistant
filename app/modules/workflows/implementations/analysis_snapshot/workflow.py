"""SnapshotWorkflow — Temporal Workflow for analysis snapshot generation.

This workflow orchestrates the full snapshot generation process:
1. Load assistant data (goals, config)
2. Load all conversations
3. Compute basic statistics (programmatic)
4. Generate respondent profiles (LLM, per conversation)
5. Generate conclusions and drop-off analysis (LLM)
6. Save snapshot result to MongoDB
7. Notify client via WebSocket

Deterministic: no I/O in run(), all I/O delegated to Activities.
"""

from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from app.modules.workflows.models.params import (
        ConclusionsParams,
        NotifyParams,
        ProfileParams,
        SaveSnapshotParams,
        SnapshotInput,
    )

# Activity retry policy
RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)

# Timeouts
SHORT_TIMEOUT = timedelta(seconds=30)
LLM_TIMEOUT = timedelta(minutes=5)
NOTIFY_TIMEOUT = timedelta(seconds=10)


@workflow.defn(name="SnapshotWorkflow")
class SnapshotWorkflow:
    """Temporal Workflow for generating Analysis Snapshot.
    
    Each step is an Activity with its own RetryPolicy.
    Progress is tracked via self._progress and queryable via get_progress().
    """
    
    def __init__(self) -> None:
        self._progress: Dict[str, Any] = {
            "step": "init",
            "processed": 0,
            "total": 0,
            "status": "pending"
        }
    
    @workflow.run
    async def run(self, input: SnapshotInput) -> dict:
        """Orchestrate all steps of snapshot generation.
        
        Args:
            input: SnapshotInput with assistant_id, execution_id, etc.
            
        Returns:
            Dict with status, analyzed count, and failed list
        """
        self._progress = {
            "step": "load_assistant",
            "processed": 0,
            "total": 0,
            "status": "processing"
        }
        
        # Step 1: Load assistant data
        assistant_data = await workflow.execute_activity(
            "load_assistant",
            input.assistant_id,
            start_to_close_timeout=SHORT_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )
        
        # Step 2: Load conversations
        self._progress["step"] = "load_conversations"
        conversations = await workflow.execute_activity(
            "load_conversations",
            args=[input.assistant_id, "INTRO", input.include_mock],
            start_to_close_timeout=SHORT_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )
        
        total = len(conversations)
        self._progress["total"] = total
        
        # Step 3: Compute statistics (programmatic, no LLM)
        self._progress["step"] = "compute_statistics"
        statistics = await workflow.execute_activity(
            "compute_statistics",
            conversations,
            start_to_close_timeout=SHORT_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )
        
        # Step 4: Generate profiles (per conversation, with LLM)
        self._progress["step"] = "generate_profiles"
        
        analysis_config = assistant_data.get("analysis_config", {})
        analysis_language = assistant_data.get("analysis_language", "English")
        processed_ids: List[str] = []
        sufficient_ids: List[str] = []  # profiles with sufficient_data=True
        skipped_count = 0
        insufficient_data_count = 0
        failed_conversations: List[Dict[str, str]] = []

        for i, conv in enumerate(conversations):
            try:
                params = ProfileParams(
                    conversation_id=conv["id"],
                    assistant_id=input.assistant_id,
                    analysis_config=analysis_config,
                    force_recalculate=input.force_recalculate,
                    analysis_language=analysis_language,
                )
                
                result = await workflow.execute_activity(
                    "generate_profile",
                    params,
                    start_to_close_timeout=LLM_TIMEOUT,
                    retry_policy=RETRY_POLICY,
                )
                
                if result is not None:
                    processed_ids.append(conv["id"])
                    if result.get("sufficient_data", True):
                        sufficient_ids.append(conv["id"])
                    else:
                        insufficient_data_count += 1
                else:
                    skipped_count += 1
                    
            except ActivityError as e:
                failed_conversations.append({
                    "id": conv["id"],
                    "error": str(e)
                })
            
            self._progress["processed"] = i + 1
            
            # Progress notification every 10 profiles
            if (i + 1) % 10 == 0 or (i + 1) == total:
                try:
                    await workflow.execute_activity(
                        "notify_websocket",
                        NotifyParams(
                            execution_id=input.execution_id,
                            status="processing",
                            progress={
                                "step": "generate_profiles",
                                "processed": i + 1,
                                "total": total,
                            },
                        ),
                        start_to_close_timeout=NOTIFY_TIMEOUT,
                    )
                except ActivityError:
                    pass  # Non-critical, continue
        
        # Enrich statistics with data quality info
        if isinstance(statistics, dict):
            statistics["insufficient_data_count"] = insufficient_data_count
            statistics["sufficient_data_count"] = len(sufficient_ids)
            statistics["effective_total"] = max(0, statistics.get("total_respondents", 0) - insufficient_data_count)

        # Step 5: Generate conclusions (LLM) — use only sufficient_data profiles
        self._progress["step"] = "generate_conclusions"
        conclusions_params = ConclusionsParams(
            assistant_id=input.assistant_id,
            execution_id=input.execution_id,
            statistics=statistics,
            profile_ids=sufficient_ids,
            analysis_language=analysis_language,
        )
        
        conclusions = await workflow.execute_activity(
            "generate_conclusions",
            conclusions_params,
            start_to_close_timeout=LLM_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )
        
        # Step 6: Save snapshot to MongoDB
        self._progress["step"] = "save_snapshot"
        save_params = SaveSnapshotParams(
            execution_id=input.execution_id,
            statistics=statistics,
            conclusions=conclusions,
            conversations_analyzed=len(processed_ids),
            conversations_skipped=skipped_count,
            failed_conversations=failed_conversations,
            include_partial=input.include_partial,
        )
        
        await workflow.execute_activity(
            "save_snapshot",
            save_params,
            start_to_close_timeout=SHORT_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )
        
        # Step 7: Final notification
        self._progress["step"] = "notify"
        try:
            await workflow.execute_activity(
                "notify_websocket",
                NotifyParams(
                    execution_id=input.execution_id,
                    status="completed",
                    progress={"analyzed": len(processed_ids), "failed": len(failed_conversations)},
                ),
                start_to_close_timeout=NOTIFY_TIMEOUT,
            )
        except ActivityError:
            pass  # Non-critical
        
        self._progress = {
            "step": "completed",
            "processed": total,
            "total": total,
            "status": "completed"
        }
        
        return {
            "status": "completed",
            "execution_id": input.execution_id,
            "assistant_id": input.assistant_id,
            "conversations_analyzed": len(processed_ids),
            "conversations_skipped": skipped_count,
            "failed_conversations": len(failed_conversations),
        }
    
    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """Query current workflow progress (read-only)."""
        return self._progress
