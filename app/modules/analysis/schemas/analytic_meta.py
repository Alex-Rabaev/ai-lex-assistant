"""Analytic metadata schemas for respondent profiles.

These schemas define the structure for storing analytics data
in Conversation.analytic_meta field.
"""

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class CategoryScore(BaseModel):
    """Score for a single analysis category.
    
    Represents the evaluation of a respondent on one category
    defined in the analysis configuration.
    """
    
    category_name: str = Field(..., description="Name of the category being scored")
    score: Union[float, str] = Field(
        ...,
        description="Numeric score (e.g., 1-5) or categorical value (e.g., 'high', 'low')"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level of the score (0.0 - 1.0)"
    )
    reasoning: str = Field(..., description="Explanation for the assigned score")
    evidence: List[str] = Field(
        default_factory=list,
        description="Quotes from the dialogue supporting the score"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "category_name": "Purchase Intent",
                "score": 4.5,
                "confidence": 0.85,
                "reasoning": "User expressed strong interest in the product",
                "evidence": ["I'm definitely considering buying this", "The price seems reasonable"]
            }
        }
    }


class ExtractedTag(BaseModel):
    """Automatically extracted tag from conversation.
    
    Tags are metadata extracted from the conversation that help
    categorize and filter respondents.
    """
    
    tag_name: str = Field(..., description="Name of the tag (e.g., 'Industry', 'Team Size')")
    value: Union[str, List[str]] = Field(
        ...,
        description="Extracted value(s) for this tag"
    )
    source: str = Field(
        ...,
        description="Source of extraction: 'profile', 'questionnaire', or 'additional_info'"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "tag_name": "Industry",
                "value": "Technology",
                "source": "profile"
            }
        }
    }


class CustomAnswer(BaseModel):
    """Answer to a custom business question.
    
    Custom questions are defined in the analysis configuration
    and answered based on conversation analysis.
    """
    
    question: str = Field(..., description="The custom business question")
    answer: str = Field(..., description="Answer derived from conversation analysis")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level of the answer (0.0 - 1.0)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Is the respondent a decision maker?",
                "answer": "Yes, they mentioned being the CEO and final approver",
                "confidence": 0.9
            }
        }
    }


class AnalyticMeta(BaseModel):
    """Analytics metadata for a respondent.
    
    This schema defines the structure for storing analytics data
    in the Conversation.analytic_meta field. It contains:
    - Category scores based on analysis configuration
    - Extracted tags for filtering and categorization
    - Answers to custom business questions
    - Quality metrics and status information
    
    Note: This is stored as an embedded document in Conversation,
    NOT as a separate collection.
    """
    
    # Category scores (from analysis_config)
    category_scores: List[CategoryScore] = Field(
        default_factory=list,
        description="Scores for each category defined in analysis config"
    )
    overall_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Overall respondent score (0.0 - 5.0)"
    )
    
    # Extracted data
    extracted_tags: List[ExtractedTag] = Field(
        default_factory=list,
        description="Automatically extracted tags"
    )
    custom_answers: List[CustomAnswer] = Field(
        default_factory=list,
        description="Answers to custom business questions"
    )
    
    # Text output
    summary: Optional[str] = Field(
        default=None,
        description="Text summary of the respondent profile"
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Recommendations based on respondent analysis"
    )
    
    # Profile quality metrics
    data_completeness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Percentage of collected data (0.0 - 1.0)"
    )
    analysis_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the analysis (0.0 - 1.0)"
    )
    
    # Survey status at the time of analysis
    survey_status: str = Field(
        ...,
        description="Survey status: 'completed', 'in_progress', or 'abandoned'"
    )
    final_stage: str = Field(
        ...,
        description="Last reached step in the survey flow"
    )
    
    # Data quality flag
    sufficient_data: bool = Field(
        default=True,
        description="False when data_completeness < 0.25 or analysis_confidence < 0.25. "
        "Low-quality profiles are excluded from main statistics and conclusions."
    )

    # Metadata
    analyzed_at: datetime = Field(
        ...,
        description="Timestamp when the analysis was performed"
    )
    snapshot_execution_id: Optional[str] = Field(
        default=None,
        description="ID of WorkflowExecution if created as part of snapshot"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "category_scores": [
                    {
                        "category_name": "Purchase Intent",
                        "score": 4.5,
                        "confidence": 0.85,
                        "reasoning": "Strong interest shown",
                        "evidence": ["I want to buy this"]
                    }
                ],
                "overall_score": 4.2,
                "extracted_tags": [
                    {"tag_name": "Industry", "value": "Tech", "source": "profile"}
                ],
                "custom_answers": [],
                "summary": "High-intent prospect from tech industry",
                "recommendations": ["Schedule demo call", "Send pricing"],
                "data_completeness": 0.85,
                "analysis_confidence": 0.80,
                "survey_status": "completed",
                "final_stage": "survey_complete",
                "analyzed_at": "2026-02-01T10:00:00Z",
                "snapshot_execution_id": "675a1234567890abcdef1234"
            }
        }
    }
