"""Workflows module for asynchronous background task processing.

This module provides generic workflow infrastructure for:
- Analysis snapshot generation
- Respondent profile creation
- Any other background tasks (with or without LLM)

Orchestration: Temporal (durable execution, crash recovery, retry, event history).

Note: WorkflowService and TemporalClientManager are NOT re-exported here
to avoid Temporal sandbox restrictions (they import app.config which
triggers I/O at module level). Import them directly:
    from app.modules.workflows.service import WorkflowService
    from app.modules.workflows.temporal_client import TemporalClientManager
"""

from app.modules.workflows.models import (
    ConclusionsParams,
    NotifyParams,
    ProfileParams,
    SaveSnapshotParams,
    SnapshotInput,
    WorkflowExecution,
    WorkflowStatus,
)
from app.modules.workflows.prompts import PromptConfig

__all__ = [
    "ConclusionsParams",
    "NotifyParams",
    "ProfileParams",
    "PromptConfig",
    "SaveSnapshotParams",
    "SnapshotInput",
    "WorkflowExecution",
    "WorkflowStatus",
]
