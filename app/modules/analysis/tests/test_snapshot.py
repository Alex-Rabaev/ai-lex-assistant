"""Unit tests for snapshot result schemas."""

import pytest
from pydantic import ValidationError

from app.modules.analysis.schemas.snapshot import (
    AnalysisSnapshotResult,
    DropOffPoint,
    OverallStatistics,
    SnapshotConclusions,
    StageDistribution,
    TimeMetrics,
)


class TestStageDistribution:
    
    def test_valid(self):
        sd = StageDistribution(stage="questionnaire", count=42, percentage=0.6)
        assert sd.stage == "questionnaire"
        assert sd.count == 42
    
    def test_percentage_bounds(self):
        with pytest.raises(ValidationError):
            StageDistribution(stage="x", count=1, percentage=1.5)


class TestDropOffPoint:
    
    def test_valid(self):
        dp = DropOffPoint(stage="intro", count=5, percentage=0.1)
        assert dp.stage == "intro"
    
    def test_with_reasons(self):
        dp = DropOffPoint(
            stage="questionnaire", count=10, percentage=0.2,
            possible_reasons=["Too long", "Confusing questions"]
        )
        assert len(dp.possible_reasons) == 2


class TestTimeMetrics:
    
    def test_defaults(self):
        tm = TimeMetrics()
        assert tm.avg_completion_time_seconds is None
    
    def test_with_values(self):
        tm = TimeMetrics(
            avg_completion_time_seconds=120.5,
            median_completion_time_seconds=100.0,
            min_completion_time_seconds=30.0,
            max_completion_time_seconds=600.0
        )
        assert tm.avg_completion_time_seconds == 120.5


class TestOverallStatistics:
    
    def test_minimal(self):
        stats = OverallStatistics(total_respondents=50)
        assert stats.total_respondents == 50
        assert stats.completed_count == 0
        assert stats.completion_rate == 0.0
        assert stats.stage_distribution == []
    
    def test_full(self):
        stats = OverallStatistics(
            total_respondents=100,
            completed_count=80,
            in_progress_count=10,
            abandoned_count=10,
            completion_rate=0.8,
            stage_distribution=[
                StageDistribution(stage="completed", count=80, percentage=0.8),
                StageDistribution(stage="in_progress", count=10, percentage=0.1),
            ],
            drop_off_analysis=[
                DropOffPoint(stage="questionnaire", count=10, percentage=1.0)
            ],
            time_metrics=TimeMetrics(avg_completion_time_seconds=300.0)
        )
        assert stats.completion_rate == 0.8
        assert len(stats.stage_distribution) == 2


class TestSnapshotConclusions:
    
    def test_minimal(self):
        c = SnapshotConclusions(summary="Good results overall")
        assert c.summary == "Good results overall"
        assert c.key_findings == []
        assert c.confidence == 0.0
    
    def test_full(self):
        c = SnapshotConclusions(
            summary="Strong purchase intent detected",
            key_findings=["80% show high intent", "Budget is main concern"],
            recommendations=["Focus on ROI messaging"],
            suggested_deep_analysis=["Segment by industry"],
            goal_alignment_score=0.85,
            confidence=0.9
        )
        assert len(c.key_findings) == 2
        assert c.goal_alignment_score == 0.85


class TestAnalysisSnapshotResult:
    
    def test_valid(self):
        result = AnalysisSnapshotResult(
            statistics=OverallStatistics(total_respondents=50),
            conclusions=SnapshotConclusions(summary="Test summary"),
            conversations_analyzed=45,
            conversations_skipped=5,
        )
        assert result.conversations_analyzed == 45
        assert result.include_partial is True
    
    def test_with_failures(self):
        result = AnalysisSnapshotResult(
            statistics=OverallStatistics(total_respondents=50),
            conclusions=SnapshotConclusions(summary="Test"),
            conversations_analyzed=48,
            failed_conversations=[
                {"id": "conv_1", "error": "LLM timeout"},
                {"id": "conv_2", "error": "Invalid data"},
            ]
        )
        assert len(result.failed_conversations) == 2
    
    def test_serialization_roundtrip(self):
        original = AnalysisSnapshotResult(
            statistics=OverallStatistics(
                total_respondents=100,
                completed_count=80,
                completion_rate=0.8
            ),
            conclusions=SnapshotConclusions(
                summary="Test",
                key_findings=["Finding 1"],
                confidence=0.9
            ),
            conversations_analyzed=95,
            conversations_skipped=5,
        )
        
        data = original.model_dump(mode="json")
        restored = AnalysisSnapshotResult(**data)
        
        assert restored.statistics.total_respondents == 100
        assert restored.conclusions.confidence == 0.9
        assert restored.conversations_analyzed == 95
