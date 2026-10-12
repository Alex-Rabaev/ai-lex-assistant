"""Dataclass input parameters for Temporal Activities.

These are serializable dataclasses used as inputs to Temporal Activities.
Temporal requires Activity inputs to be serializable (dataclasses or Pydantic models).

Concrete workflow-specific params (e.g., ProfileParams, ConclusionsParams)
will be defined in their respective implementations/ directories.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SnapshotInput:
    """Input parameters for SnapshotWorkflow.

    Passed when starting the workflow via Temporal Client.
    """
    assistant_id: str
    execution_id: str
    force_recalculate: bool = False
    include_partial: bool = True
    include_mock: bool = False  # If True, include mock respondents (test snapshot)
    analysis_language: str = "English"  # Language for AI-generated analysis output


@dataclass
class ProfileParams:
    """Input parameters for generate_profile Activity."""
    conversation_id: str
    assistant_id: str
    analysis_config: Dict[str, Any] = field(default_factory=dict)
    force_recalculate: bool = False
    analysis_language: str = "English"


@dataclass
class ConclusionsParams:
    """Input parameters for generate_conclusions Activity."""
    assistant_id: str
    execution_id: str
    statistics: Dict[str, Any] = field(default_factory=dict)
    profile_ids: List[str] = field(default_factory=list)
    analysis_language: str = "English"


@dataclass
class SaveSnapshotParams:
    """Input parameters for save_snapshot Activity."""
    execution_id: str
    statistics: Dict[str, Any] = field(default_factory=dict)
    conclusions: Dict[str, Any] = field(default_factory=dict)
    conversations_analyzed: int = 0
    conversations_skipped: int = 0
    failed_conversations: List[Dict[str, Any]] = field(default_factory=list)
    include_partial: bool = True


@dataclass
class NotifyParams:
    """Input parameters for notify_websocket Activity."""
    execution_id: str
    status: str = "processing"
    progress: Dict[str, Any] = field(default_factory=dict)
    connection_id: Optional[str] = None
