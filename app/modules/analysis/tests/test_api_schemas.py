"""Unit tests for API request/response schemas."""

import pytest
from pydantic import ValidationError

from app.modules.analysis.schemas.api import (
    CreateSnapshotRequest,
    MockRespondentsRequest,
    MockRespondentsResponse,
    ProfileResponse,
    SnapshotCreatedResponse,
    SnapshotResponse,
    UpdateSnapshotRequest,
)


class TestCreateSnapshotRequest:
    
    def test_defaults(self):
        req = CreateSnapshotRequest()
        assert req.force_recalculate is False
        assert req.include_partial is True
        assert req.include_mock is False
        assert req.version_name is None

    def test_with_values(self):
        req = CreateSnapshotRequest(
            force_recalculate=True,
            include_partial=False,
            include_mock=True,
            version_name="Q1 2026"
        )
        assert req.force_recalculate is True
        assert req.include_mock is True
        assert req.version_name == "Q1 2026"
    
    def test_version_name_max_length(self):
        with pytest.raises(ValidationError):
            CreateSnapshotRequest(version_name="x" * 201)


class TestSnapshotResponse:
    
    def test_minimal(self):
        resp = SnapshotResponse(
            id="exec_123",
            status="pending",
            triggered_by="user@test.com"
        )
        assert resp.id == "exec_123"
        assert resp.result is None
    
    def test_completed(self):
        resp = SnapshotResponse(
            id="exec_123",
            status="completed",
            triggered_by="user@test.com",
            result={"statistics": {}, "conclusions": {}},
            version_name="Q1 2026"
        )
        assert resp.result is not None
        assert resp.version_name == "Q1 2026"


class TestSnapshotCreatedResponse:
    
    def test_creation(self):
        resp = SnapshotCreatedResponse(execution_id="exec_123")
        assert resp.execution_id == "exec_123"
        assert resp.status == "pending"


class TestUpdateSnapshotRequest:
    
    def test_update_name(self):
        req = UpdateSnapshotRequest(version_name="Updated Name")
        assert req.version_name == "Updated Name"
        assert req.is_archived is None
    
    def test_archive(self):
        req = UpdateSnapshotRequest(is_archived=True)
        assert req.is_archived is True


class TestProfileResponse:
    
    def test_with_meta(self):
        resp = ProfileResponse(
            conversation_id="conv_123",
            analytic_meta={"summary": "Test"},
            is_mock=False,
        )
        assert resp.analytic_meta is not None
        assert resp.is_mock is False

    def test_without_meta(self):
        resp = ProfileResponse(conversation_id="conv_123")
        assert resp.analytic_meta is None
        assert resp.is_mock is False


class TestMockRespondentsRequest:
    def test_defaults(self):
        req = MockRespondentsRequest()
        assert req.count == 10
        assert req.language == "en"
        assert req.include_abandoned is True

    def test_with_values(self):
        req = MockRespondentsRequest(count=5, language="ru", include_abandoned=False)
        assert req.count == 5
        assert req.language == "ru"
        assert req.include_abandoned is False

    def test_count_validation(self):
        with pytest.raises(ValidationError):
            MockRespondentsRequest(count=0)
        with pytest.raises(ValidationError):
            MockRespondentsRequest(count=101)


class TestMockRespondentsResponse:
    def test_creation(self):
        resp = MockRespondentsResponse(created=3, conversation_ids=["c1", "c2", "c3"])
        assert resp.created == 3
        assert resp.conversation_ids == ["c1", "c2", "c3"]
