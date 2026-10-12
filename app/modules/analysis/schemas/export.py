"""Pydantic schemas for export endpoints (CSV / JSON)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ==================== Single Conversation Messages ====================


class ExportMessageItem(BaseModel):
    """Single message in export output."""
    date: str = Field(..., description="Message timestamp")
    role: str = Field(..., description="user or assistant")
    message: str = Field(..., description="Message content")
    respondent: str = Field(..., description="Interlocutor ID (ObjectId)")
    stage: Optional[str] = Field(None, description="Dialogue stage when message was sent")


# ==================== Bulk Messages Export ====================


class BulkRespondentMessages(BaseModel):
    """One respondent's messages inside bulk export."""
    respondent_id: str
    name: Optional[str] = None
    messages: List[ExportMessageItem]


class BulkMessagesExport(BaseModel):
    """Root object for bulk messages JSON export."""
    export_date: datetime
    total_respondents: int
    total_messages: int
    respondents: List[BulkRespondentMessages]


# ==================== Bulk Survey/Respondents Export ====================


class SurveyItem(BaseModel):
    """Single question-answer pair."""
    question: str
    answer: str


class RespondentSurveyExport(BaseModel):
    """One respondent's profile + survey answers."""
    respondent_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    profile_summary: Optional[str] = None
    survey: List[SurveyItem] = Field(default_factory=list)


class BulkRespondentExport(BaseModel):
    """Root object for bulk respondent/survey JSON export."""
    export_date: datetime
    total_respondents: int
    total_responses: int
    respondents: List[RespondentSurveyExport]
