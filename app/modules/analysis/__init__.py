"""Analysis module for respondent analytics and insights.

Contains Pydantic schemas for validation (NOT MongoDB models).
Data is stored in existing collections:
- WorkflowExecution.result — snapshot results
- Conversation.analytic_meta — respondent profiles
- Assistant.metadata["analysis_config"] — analysis configuration
"""

from app.modules.analysis.schemas.analytic_meta import (
    AnalyticMeta,
    CategoryScore,
    CustomAnswer,
    ExtractedTag,
)
from app.modules.analysis.schemas.config import (
    AnalysisConfig,
    AnalysisFramework,
    CategoryConfig,
    OutputConfig,
    TagConfig,
)

__all__ = [
    "AnalysisConfig",
    "AnalysisFramework",
    "AnalyticMeta",
    "CategoryConfig",
    "CategoryScore",
    "CustomAnswer",
    "ExtractedTag",
    "OutputConfig",
    "TagConfig",
]
