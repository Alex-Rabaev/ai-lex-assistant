"""Pydantic schemas for analysis configuration.

AnalysisConfig is stored in Assistant.metadata["analysis_config"].
These are validation schemas, NOT MongoDB models.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError


class CategoryConfig(BaseModel):
    """Configuration for a single scoring category.
    
    Defines how respondents are evaluated on a specific dimension.
    Categories are either auto-generated from survey goals or
    manually configured by the user.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Category name (e.g., 'Purchase Intent', 'Budget Level')"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="What this category measures"
    )
    scoring_type: Literal["scale", "categorical", "numeric"] = Field(
        ...,
        description="Type of scoring: scale (1-5), categorical (options), numeric (value)"
    )
    min_score: Optional[int] = Field(
        default=None,
        description="Minimum score value (for scale type)"
    )
    max_score: Optional[int] = Field(
        default=None,
        description="Maximum score value (for scale type)"
    )
    options: Optional[List[str]] = Field(
        default=None,
        description="Available options (for categorical type)"
    )
    rubric: Optional[Dict[int, str]] = Field(
        default=None,
        description="Score descriptions (e.g., {1: 'Low interest', 5: 'Very interested'})"
    )


class TagConfig(BaseModel):
    """Configuration for an auto-extracted tag.
    
    Tags are metadata extracted from conversations
    for filtering and categorization.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Tag name (e.g., 'Industry', 'Team Size')"
    )
    extraction: Literal["auto", "list"] = Field(
        ...,
        description="Extraction method: 'auto' (free-form) or 'list' (predefined options)"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description of what to extract"
    )
    options: Optional[List[str]] = Field(
        default=None,
        description="Predefined options (for 'list' extraction type)"
    )


class OutputConfig(BaseModel):
    """Configuration for analysis output format.
    
    Controls what is included in the analysis results.
    """
    include_summary: bool = Field(
        default=True,
        description="Include text summary in respondent profile"
    )
    include_recommendations: bool = Field(
        default=True,
        description="Include recommendations in respondent profile"
    )
    include_evidence: bool = Field(
        default=True,
        description="Include evidence quotes from dialogue"
    )
    summary_max_length: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Maximum length of text summary"
    )


class AnalysisFramework(BaseModel):
    """Analysis framework defining what and how to analyze.
    
    Contains categories for scoring, tags for extraction,
    and custom business questions.
    """
    categories: List[CategoryConfig] = Field(
        default_factory=list,
        description="Scoring categories for respondent evaluation"
    )
    tags: List[TagConfig] = Field(
        default_factory=list,
        description="Tags to extract from conversations"
    )
    custom_questions: List[str] = Field(
        default_factory=list,
        description="Custom business questions to answer about each respondent"
    )


class AnalysisConfig(BaseModel):
    """Analysis configuration for an assistant.
    
    STORED IN: Assistant.metadata["analysis_config"]
    NOT a separate collection.
    
    This config defines how respondents are analyzed:
    - assistant_goal: what we want to learn from respondents
    - Which categories to score
    - Which tags to extract
    - What business questions to answer
    - Output format settings
    """
    assistant_goal: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Goal of the analysis — what we want to learn from respondents. "
        "Used by AI to generate categories and analyze conversations. "
        "Not the same as survey_goal from questionnaire step."
    )
    analysis_language: str = Field(
        default="English",
        max_length=50,
        description="Language for AI-generated analysis output (profiles, conclusions, summaries). "
        "E.g. 'English', 'Russian', 'Spanish'. "
        "Respondent conversations may be in any language; this controls the output language only."
    )
    enabled: bool = Field(
        default=False,
        description="Whether analysis is enabled for this assistant"
    )
    framework: AnalysisFramework = Field(
        default_factory=AnalysisFramework,
        description="Analysis framework (categories, tags, questions)"
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output format configuration"
    )
    generated_at: Optional[datetime] = Field(
        default=None,
        description="When the config was auto-generated"
    )
    last_updated_at: Optional[datetime] = Field(
        default=None,
        description="When the config was last updated"
    )


def parse_analysis_config(data: Optional[Dict[str, Any]]) -> Optional[AnalysisConfig]:
    """Parse analysis config from Assistant.metadata dict.
    
    Args:
        data: Raw dict from Assistant.metadata["analysis_config"]
        
    Returns:
        Validated AnalysisConfig or None if data is None
        
    Raises:
        ValidationError: If data is invalid
    """
    if data is None:
        return None
    return AnalysisConfig(**data)


def dump_analysis_config(config: AnalysisConfig) -> Dict[str, Any]:
    """Serialize AnalysisConfig to dict for storing in Assistant.metadata.
    
    Args:
        config: Validated AnalysisConfig
        
    Returns:
        Dict suitable for storing in MongoDB
    """
    return config.model_dump(mode="json")
