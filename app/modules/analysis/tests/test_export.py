"""Unit tests for export schemas and ExportService CSV/JSON generation."""

import csv
import io
from datetime import datetime, timezone

import pytest

from app.modules.analysis.schemas.export import (
    BulkMessagesExport,
    BulkRespondentExport,
    BulkRespondentMessages,
    ExportMessageItem,
    RespondentSurveyExport,
    SurveyItem,
)
from app.modules.analysis.export_service import ExportService


# ==================== Schema Tests ====================


class TestExportMessageItem:
    def test_creation(self):
        item = ExportMessageItem(
            date="2025-09-16 15:29:29.443000",
            role="user",
            message="/start",
            respondent="68c98259b936da42d4649bb9",
            stage="language",
        )
        assert item.role == "user"
        assert item.respondent == "68c98259b936da42d4649bb9"

    def test_stage_optional(self):
        item = ExportMessageItem(
            date="2025-09-16 15:29:29.443000",
            role="assistant",
            message="Hello",
            respondent="abc123",
        )
        assert item.stage is None


class TestSurveyItem:
    def test_creation(self):
        item = SurveyItem(question="What is your name?", answer="John")
        assert item.question == "What is your name?"
        assert item.answer == "John"


class TestRespondentSurveyExport:
    def test_full(self):
        r = RespondentSurveyExport(
            respondent_id="abc123",
            name="Надя",
            email="nadya@example.com",
            profile_summary="Мастер по маникюру",
            survey=[SurveyItem(question="Q1", answer="A1")],
        )
        assert r.name == "Надя"
        assert len(r.survey) == 1

    def test_defaults(self):
        r = RespondentSurveyExport(respondent_id="abc123")
        assert r.name is None
        assert r.email is None
        assert r.survey == []


class TestBulkRespondentExport:
    def test_creation(self):
        export = BulkRespondentExport(
            export_date=datetime.now(timezone.utc),
            total_respondents=1,
            total_responses=2,
            respondents=[
                RespondentSurveyExport(
                    respondent_id="abc",
                    survey=[
                        SurveyItem(question="Q1", answer="A1"),
                        SurveyItem(question="Q2", answer="A2"),
                    ],
                )
            ],
        )
        assert export.total_responses == 2


class TestBulkMessagesExport:
    def test_creation(self):
        export = BulkMessagesExport(
            export_date=datetime.now(timezone.utc),
            total_respondents=1,
            total_messages=3,
            respondents=[
                BulkRespondentMessages(
                    respondent_id="abc",
                    name="Test",
                    messages=[
                        ExportMessageItem(
                            date="2025-01-01 00:00:00.000000",
                            role="user",
                            message="hi",
                            respondent="abc",
                        )
                    ],
                )
            ],
        )
        assert export.total_messages == 3


# ==================== CSV Generation Tests ====================


class TestSingleMessagesCsv:
    def _parse_csv(self, csv_text: str):
        content = csv_text.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)

    def test_empty(self):
        svc = ExportService.__new__(ExportService)
        result = svc.single_messages_to_csv([])
        rows = self._parse_csv(result)
        assert rows == []

    def test_with_rows(self):
        svc = ExportService.__new__(ExportService)
        data = [
            {
                "date": "2025-09-16 15:29:29.443000",
                "role": "user",
                "message": "/start",
                "respondent": "abc123",
                "stage": "language",
            },
            {
                "date": "2025-09-16 15:29:33.077000",
                "role": "assistant",
                "message": "What language?",
                "respondent": "abc123",
                "stage": "language",
            },
        ]
        result = svc.single_messages_to_csv(data)
        rows = self._parse_csv(result)
        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[1]["message"] == "What language?"

    def test_utf8_bom(self):
        svc = ExportService.__new__(ExportService)
        result = svc.single_messages_to_csv([])
        assert result.startswith("\ufeff")

    def test_cyrillic_content(self):
        svc = ExportService.__new__(ExportService)
        data = [
            {
                "date": "2025-09-16 15:29:29.443000",
                "role": "user",
                "message": "Русский",
                "respondent": "abc123",
                "stage": "language",
            }
        ]
        result = svc.single_messages_to_csv(data)
        rows = self._parse_csv(result)
        assert rows[0]["message"] == "Русский"


class TestBulkMessagesCsv:
    def _parse_csv(self, csv_text: str):
        content = csv_text.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)

    def test_empty_respondents(self):
        svc = ExportService.__new__(ExportService)
        data = {"respondents": []}
        result = svc.bulk_messages_to_csv(data)
        rows = self._parse_csv(result)
        assert rows == []

    def test_multiple_respondents(self):
        svc = ExportService.__new__(ExportService)
        data = {
            "respondents": [
                {
                    "respondent_id": "r1",
                    "name": "Alice",
                    "messages": [
                        {"date": "2025-01-01", "role": "user", "message": "hi", "stage": "intro"},
                        {"date": "2025-01-01", "role": "assistant", "message": "hello", "stage": "intro"},
                    ],
                },
                {
                    "respondent_id": "r2",
                    "name": "Bob",
                    "messages": [
                        {"date": "2025-01-02", "role": "user", "message": "hey", "stage": "profile"},
                    ],
                },
            ]
        }
        result = svc.bulk_messages_to_csv(data)
        rows = self._parse_csv(result)
        assert len(rows) == 3
        assert rows[0]["respondent_id"] == "r1"
        assert rows[0]["respondent_name"] == "Alice"
        assert rows[2]["respondent_id"] == "r2"
        assert rows[2]["respondent_name"] == "Bob"


class TestBulkRespondentsCsv:
    def _parse_csv(self, csv_text: str):
        content = csv_text.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)

    def test_empty(self):
        svc = ExportService.__new__(ExportService)
        data = {"respondents": []}
        result = svc.bulk_respondents_to_csv(data)
        rows = self._parse_csv(result)
        assert rows == []

    def test_email_in_header(self):
        svc = ExportService.__new__(ExportService)
        result = svc.bulk_respondents_to_csv({"respondents": []})
        assert "email" in result

    def test_email_first_row_only(self):
        svc = ExportService.__new__(ExportService)
        data = {
            "respondents": [
                {
                    "respondent_id": "r1",
                    "name": "Надя",
                    "email": "nadya@example.com",
                    "profile_summary": "Мастер по маникюру",
                    "survey": [
                        {"question": "Q1", "answer": "A1"},
                        {"question": "Q2", "answer": "A2"},
                    ],
                }
            ]
        }
        result = svc.bulk_respondents_to_csv(data)
        rows = self._parse_csv(result)
        assert rows[0]["email"] == "nadya@example.com"
        assert rows[1]["email"] == ""

    def test_profile_summary_first_row_only(self):
        svc = ExportService.__new__(ExportService)
        data = {
            "respondents": [
                {
                    "respondent_id": "r1",
                    "name": "Надя",
                    "email": "nadya@example.com",
                    "profile_summary": "Мастер по маникюру",
                    "survey": [
                        {"question": "Q1", "answer": "A1"},
                        {"question": "Q2", "answer": "A2"},
                        {"question": "Q3", "answer": "A3"},
                    ],
                }
            ]
        }
        result = svc.bulk_respondents_to_csv(data)
        rows = self._parse_csv(result)
        assert len(rows) == 3
        assert rows[0]["profile_summary"] == "Мастер по маникюру"
        assert rows[1]["profile_summary"] == ""
        assert rows[2]["profile_summary"] == ""

    def test_row_numbering(self):
        svc = ExportService.__new__(ExportService)
        data = {
            "respondents": [
                {
                    "respondent_id": "r1",
                    "name": "A",
                    "survey": [{"question": "Q1", "answer": "A1"}],
                },
                {
                    "respondent_id": "r2",
                    "name": "B",
                    "survey": [{"question": "Q2", "answer": "A2"}],
                },
            ]
        }
        result = svc.bulk_respondents_to_csv(data)
        rows = self._parse_csv(result)
        assert rows[0]["#"] == "1"
        assert rows[1]["#"] == "2"

    def test_respondent_without_survey(self):
        svc = ExportService.__new__(ExportService)
        data = {
            "respondents": [
                {
                    "respondent_id": "r1",
                    "name": "Empty",
                    "email": "empty@example.com",
                    "profile_summary": "No survey",
                    "survey": [],
                }
            ]
        }
        result = svc.bulk_respondents_to_csv(data)
        rows = self._parse_csv(result)
        assert len(rows) == 1
        assert rows[0]["name"] == "Empty"
        assert rows[0]["email"] == "empty@example.com"
        assert rows[0]["question"] == ""

    def test_multiple_respondents_with_surveys(self):
        svc = ExportService.__new__(ExportService)
        data = {
            "respondents": [
                {
                    "respondent_id": "r1",
                    "name": "Надя",
                    "email": "nadya@example.com",
                    "profile_summary": "Summary 1",
                    "survey": [
                        {"question": "Q1", "answer": "A1"},
                        {"question": "Q2", "answer": "A2"},
                    ],
                },
                {
                    "respondent_id": "r2",
                    "name": "Саша",
                    "email": None,
                    "profile_summary": "Summary 2",
                    "survey": [
                        {"question": "Q3", "answer": "A3"},
                    ],
                },
            ]
        }
        result = svc.bulk_respondents_to_csv(data)
        rows = self._parse_csv(result)
        assert len(rows) == 3
        assert rows[0]["respondent_id"] == "r1"
        assert rows[0]["email"] == "nadya@example.com"
        assert rows[0]["profile_summary"] == "Summary 1"
        assert rows[1]["profile_summary"] == ""
        assert rows[2]["respondent_id"] == "r2"
        assert rows[2]["email"] == ""
        assert rows[2]["profile_summary"] == "Summary 2"
