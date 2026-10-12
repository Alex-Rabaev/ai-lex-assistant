"""Unit tests for AnalysisConfig schemas and helpers."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.modules.analysis.schemas.config import (
    AnalysisConfig,
    AnalysisFramework,
    CategoryConfig,
    OutputConfig,
    TagConfig,
    parse_analysis_config,
    dump_analysis_config,
)


class TestCategoryConfig:
    """Tests for CategoryConfig schema."""
    
    def test_valid_scale_category(self):
        """Test valid scale category."""
        cat = CategoryConfig(
            name="Purchase Intent",
            description="How likely to purchase",
            scoring_type="scale",
            min_score=1,
            max_score=5
        )
        assert cat.name == "Purchase Intent"
        assert cat.scoring_type == "scale"
    
    def test_valid_categorical_category(self):
        """Test valid categorical category."""
        cat = CategoryConfig(
            name="Budget Level",
            description="Budget range",
            scoring_type="categorical",
            options=["Low", "Medium", "High"]
        )
        assert cat.options == ["Low", "Medium", "High"]
    
    def test_valid_numeric_category(self):
        """Test valid numeric category."""
        cat = CategoryConfig(
            name="Team Size",
            description="Number of team members",
            scoring_type="numeric"
        )
        assert cat.scoring_type == "numeric"
    
    def test_rubric(self):
        """Test category with rubric descriptions."""
        cat = CategoryConfig(
            name="Interest",
            description="Interest level",
            scoring_type="scale",
            min_score=1,
            max_score=5,
            rubric={1: "No interest", 3: "Moderate", 5: "Very interested"}
        )
        assert cat.rubric[1] == "No interest"
    
    def test_invalid_scoring_type(self):
        """Test that invalid scoring_type raises error."""
        with pytest.raises(ValidationError):
            CategoryConfig(
                name="Test",
                description="Test",
                scoring_type="invalid"
            )
    
    def test_empty_name_rejected(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError):
            CategoryConfig(
                name="",
                description="Test",
                scoring_type="scale"
            )
    
    def test_missing_required_fields(self):
        """Test that missing required fields raise error."""
        with pytest.raises(ValidationError):
            CategoryConfig(name="Test")


class TestTagConfig:
    """Tests for TagConfig schema."""
    
    def test_valid_auto_tag(self):
        """Test valid auto-extraction tag."""
        tag = TagConfig(
            name="Industry",
            extraction="auto",
            description="The industry of the respondent"
        )
        assert tag.extraction == "auto"
    
    def test_valid_list_tag(self):
        """Test valid list-extraction tag."""
        tag = TagConfig(
            name="Company Size",
            extraction="list",
            options=["1-10", "11-50", "51-200", "200+"]
        )
        assert tag.extraction == "list"
        assert len(tag.options) == 4
    
    def test_invalid_extraction_type(self):
        """Test that invalid extraction type raises error."""
        with pytest.raises(ValidationError):
            TagConfig(name="Test", extraction="invalid")


class TestOutputConfig:
    """Tests for OutputConfig schema."""
    
    def test_defaults(self):
        """Test default values."""
        output = OutputConfig()
        assert output.include_summary is True
        assert output.include_recommendations is True
        assert output.include_evidence is True
        assert output.summary_max_length == 500
    
    def test_custom_values(self):
        """Test custom output config."""
        output = OutputConfig(
            include_summary=False,
            summary_max_length=1000
        )
        assert output.include_summary is False
        assert output.summary_max_length == 1000
    
    def test_summary_length_validation(self):
        """Test summary_max_length boundaries."""
        with pytest.raises(ValidationError):
            OutputConfig(summary_max_length=50)  # < 100
        
        with pytest.raises(ValidationError):
            OutputConfig(summary_max_length=3000)  # > 2000


class TestAnalysisFramework:
    """Tests for AnalysisFramework schema."""
    
    def test_empty_framework(self):
        """Test empty framework (defaults)."""
        framework = AnalysisFramework()
        assert framework.categories == []
        assert framework.tags == []
        assert framework.custom_questions == []
    
    def test_full_framework(self):
        """Test framework with all fields."""
        framework = AnalysisFramework(
            categories=[
                CategoryConfig(
                    name="Intent",
                    description="Purchase intent",
                    scoring_type="scale",
                    min_score=1,
                    max_score=5
                )
            ],
            tags=[
                TagConfig(name="Industry", extraction="auto")
            ],
            custom_questions=[
                "Is this respondent a decision maker?"
            ]
        )
        assert len(framework.categories) == 1
        assert len(framework.tags) == 1
        assert len(framework.custom_questions) == 1


class TestAnalysisConfig:
    """Tests for AnalysisConfig schema."""
    
    def test_defaults(self):
        """Test default config."""
        config = AnalysisConfig()
        assert config.enabled is False
        assert config.framework.categories == []
        assert config.output.include_summary is True
        assert config.generated_at is None
        assert config.last_updated_at is None
    
    def test_enabled_config(self):
        """Test enabled config with framework."""
        config = AnalysisConfig(
            enabled=True,
            framework=AnalysisFramework(
                categories=[
                    CategoryConfig(
                        name="Intent",
                        description="Purchase intent",
                        scoring_type="scale",
                        min_score=1,
                        max_score=5
                    )
                ]
            ),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        assert config.enabled is True
        assert len(config.framework.categories) == 1
        assert config.generated_at is not None
    
    def test_config_with_timestamps(self):
        """Test config with generation timestamps."""
        now = datetime.now(timezone.utc)
        config = AnalysisConfig(
            generated_at=now,
            last_updated_at=now
        )
        assert config.generated_at == now
        assert config.last_updated_at == now


class TestParseAnalysisConfig:
    """Tests for parse_analysis_config helper."""
    
    def test_parse_none(self):
        """Test parsing None returns None."""
        assert parse_analysis_config(None) is None
    
    def test_parse_valid_dict(self):
        """Test parsing valid dict."""
        data = {
            "enabled": True,
            "framework": {
                "categories": [
                    {
                        "name": "Intent",
                        "description": "Purchase intent",
                        "scoring_type": "scale",
                        "min_score": 1,
                        "max_score": 5
                    }
                ],
                "tags": [],
                "custom_questions": []
            },
            "output": {
                "include_summary": True,
                "include_recommendations": True,
                "include_evidence": True,
                "summary_max_length": 500
            }
        }
        
        config = parse_analysis_config(data)
        assert config is not None
        assert config.enabled is True
        assert len(config.framework.categories) == 1
        assert config.framework.categories[0].name == "Intent"
    
    def test_parse_minimal_dict(self):
        """Test parsing minimal dict with defaults."""
        data = {}
        config = parse_analysis_config(data)
        assert config is not None
        assert config.enabled is False
    
    def test_parse_invalid_dict(self):
        """Test parsing invalid dict raises ValidationError."""
        data = {
            "framework": {
                "categories": [
                    {"name": "Test"}  # Missing required fields
                ]
            }
        }
        
        with pytest.raises(ValidationError):
            parse_analysis_config(data)


class TestDumpAnalysisConfig:
    """Tests for dump_analysis_config helper."""
    
    def test_dump_default_config(self):
        """Test dumping default config to dict."""
        config = AnalysisConfig()
        data = dump_analysis_config(config)
        
        assert isinstance(data, dict)
        assert data["enabled"] is False
        assert data["framework"]["categories"] == []
    
    def test_dump_full_config(self):
        """Test dumping full config preserves all data."""
        config = AnalysisConfig(
            enabled=True,
            framework=AnalysisFramework(
                categories=[
                    CategoryConfig(
                        name="Intent",
                        description="Purchase intent",
                        scoring_type="scale",
                        min_score=1,
                        max_score=5
                    )
                ],
                tags=[
                    TagConfig(name="Industry", extraction="auto")
                ],
                custom_questions=["Is decision maker?"]
            ),
            output=OutputConfig(summary_max_length=1000),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        
        data = dump_analysis_config(config)
        
        assert data["enabled"] is True
        assert len(data["framework"]["categories"]) == 1
        assert data["framework"]["categories"][0]["name"] == "Intent"
        assert data["output"]["summary_max_length"] == 1000
    
    def test_roundtrip(self):
        """Test that dump -> parse produces identical config."""
        original = AnalysisConfig(
            enabled=True,
            framework=AnalysisFramework(
                categories=[
                    CategoryConfig(
                        name="Intent",
                        description="Purchase intent",
                        scoring_type="scale",
                        min_score=1,
                        max_score=5
                    )
                ]
            )
        )
        
        data = dump_analysis_config(original)
        restored = parse_analysis_config(data)
        
        assert restored.enabled == original.enabled
        assert len(restored.framework.categories) == len(original.framework.categories)
        assert restored.framework.categories[0].name == original.framework.categories[0].name
