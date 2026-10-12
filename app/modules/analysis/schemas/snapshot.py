"""Pydantic schemas for Analysis Snapshot results.

AnalysisSnapshotResult is stored in WorkflowExecution.result field,
NOT in a separate collection.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StageDistribution(BaseModel):
    """Distribution of respondents across survey stages."""
    stage: str = Field(..., description="Stage name/key")
    count: int = Field(..., ge=0, description="Number of respondents at this stage")
    percentage: float = Field(..., ge=0.0, le=1.0, description="Fraction of total (0.0-1.0)")


class DropOffPoint(BaseModel):
    """Point where respondents abandoned the survey."""
    stage: str = Field(..., description="Stage where drop-off occurred")
    count: int = Field(..., ge=0, description="Number who dropped off here")
    percentage: float = Field(..., ge=0.0, le=1.0, description="Fraction of total drop-offs")
    possible_reasons: Optional[List[str]] = Field(
        default=None,
        description="AI-suggested reasons for drop-off"
    )


class TimeMetrics(BaseModel):
    """Time-related metrics for survey completion."""
    avg_completion_time_seconds: Optional[float] = Field(
        default=None, ge=0, description="Average time to complete survey"
    )
    median_completion_time_seconds: Optional[float] = Field(
        default=None, ge=0, description="Median time to complete survey"
    )
    min_completion_time_seconds: Optional[float] = Field(
        default=None, ge=0, description="Fastest completion"
    )
    max_completion_time_seconds: Optional[float] = Field(
        default=None, ge=0, description="Slowest completion"
    )


class OverallStatistics(BaseModel):
    """Aggregated statistics across all respondents."""
    total_respondents: int = Field(..., ge=0, description="Total respondents analyzed")
    completed_count: int = Field(0, ge=0, description="Fully completed surveys")
    in_progress_count: int = Field(0, ge=0, description="Still in progress")
    abandoned_count: int = Field(0, ge=0, description="Abandoned surveys")
    insufficient_data_count: int = Field(
        0, ge=0,
        description="Respondents excluded from analysis due to insufficient data "
        "(data_completeness < 0.25 or analysis_confidence < 0.25)"
    )
    completion_rate: float = Field(0.0, ge=0.0, le=1.0, description="Completion rate (0.0-1.0)")
    stage_distribution: List[StageDistribution] = Field(
        default_factory=list, description="Distribution across stages"
    )
    drop_off_analysis: List[DropOffPoint] = Field(
        default_factory=list, description="Drop-off analysis points"
    )
    time_metrics: TimeMetrics = Field(
        default_factory=TimeMetrics, description="Time metrics"
    )


class SnapshotConclusions(BaseModel):
    """AI-generated conclusions based on survey goals."""
    summary: str = Field(..., description="Brief summary of analysis")
    key_findings: List[str] = Field(
        default_factory=list, description="Key findings from analysis"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )
    suggested_deep_analysis: List[str] = Field(
        default_factory=list, description="Suggested directions for deep analysis"
    )
    goal_alignment_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="How well results align with survey goals (0.0-1.0)"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Confidence in conclusions (0.0-1.0)"
    )


class AnalysisSnapshotResult(BaseModel):
    """Complete snapshot result.
    
    STORED IN: WorkflowExecution.result
    NOT a separate collection.
    """
    statistics: OverallStatistics = Field(..., description="Aggregated statistics")
    conclusions: SnapshotConclusions = Field(..., description="AI-generated conclusions")
    
    conversations_analyzed: int = Field(0, ge=0, description="Profiles created/recalculated")
    conversations_skipped: int = Field(0, ge=0, description="Skipped (profile up-to-date)")
    failed_conversations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {id, error} for failed profile generations"
    )
    include_partial: bool = Field(
        True, description="Whether partial conversations were included"
    )
