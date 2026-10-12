"""Tests for assistant schemas."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.modules.assistants import (
    CreateAssistantRequest,
    UpdateAssistantRequest,
    AssistantResponse,
    AssistantListResponse,
    CloneAssistantRequest,
    AssistantType,
    AssistantStatus
)


class TestCreateAssistantRequest:
    """Test CreateAssistantRequest schema."""
    
    def test_valid_create_request(self):
        """Test valid create request."""
        request = CreateAssistantRequest(
            name="Test Assistant",
            description="Test description",
            type=AssistantType.SURVEY
        )
        
        assert request.name == "Test Assistant"
        assert request.description == "Test description"
        assert request.type == AssistantType.SURVEY
    
    def test_minimal_create_request(self):
        """Test minimal valid request (only required fields)."""
        request = CreateAssistantRequest(
            name="Minimal Bot",
            type=AssistantType.SURVEY
        )
        
        assert request.name == "Minimal Bot"
        assert request.description is None
        assert request.type == AssistantType.SURVEY
    
    def test_empty_name_fails(self):
        """Test that empty name fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            CreateAssistantRequest(name="")
        assert "at least 1 character" in str(exc_info.value).lower()
    
    def test_too_long_name_fails(self):
        """Test that name over 100 chars fails."""
        with pytest.raises(ValidationError):
            CreateAssistantRequest(name="A" * 101)
    
    def test_too_long_description_fails(self):
        """Test that description over 500 chars fails."""
        with pytest.raises(ValidationError):
            CreateAssistantRequest(
                name="Test",
                description="A" * 501
            )


class TestUpdateAssistantRequest:
    """Test UpdateAssistantRequest schema."""
    
    def test_valid_update_request(self):
        """Test valid update request."""
        request = UpdateAssistantRequest(
            name="Updated Name",
            status=AssistantStatus.ACTIVE
        )
        
        assert request.name == "Updated Name"
        assert request.status == AssistantStatus.ACTIVE
    
    def test_partial_update(self):
        """Test partial update (only some fields)."""
        request = UpdateAssistantRequest(status=AssistantStatus.INACTIVE)

        assert request.status == AssistantStatus.INACTIVE
        assert request.name is None
        assert request.description is None
    
    def test_empty_update_is_valid(self):
        """Test that update with no fields is valid (will be handled by service)."""
        request = UpdateAssistantRequest()
        
        assert request.name is None
        assert request.status is None


class TestAssistantResponse:
    """Test AssistantResponse schema."""
    
    def test_valid_response(self):
        """Test creating valid response."""
        response = AssistantResponse(
            id="507f1f77bcf86cd799439011",
            org_id="org_123",
            owner_user_id="user_456",
            name="Test Assistant",
            type=AssistantType.SURVEY,
            status=AssistantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        assert response.id == "507f1f77bcf86cd799439011"
        assert response.name == "Test Assistant"
        assert response.type == AssistantType.SURVEY
        assert response.status == AssistantStatus.ACTIVE


class TestAssistantListResponse:
    """Test AssistantListResponse schema."""
    
    def test_valid_list_response(self):
        """Test creating valid list response."""
        response = AssistantListResponse(
            items=[],
            total=0,
            skip=0,
            limit=20
        )
        
        assert response.items == []
        assert response.total == 0
        assert response.skip == 0
        assert response.limit == 20
    
    def test_pagination_params(self):
        """Test pagination parameters."""
        response = AssistantListResponse(
            items=[],
            total=100,
            skip=20,
            limit=10
        )
        
        assert response.total == 100
        assert response.skip == 20
        assert response.limit == 10


class TestCloneAssistantRequest:
    """Test CloneAssistantRequest schema."""
    
    def test_valid_clone_request(self):
        """Test valid clone request."""
        request = CloneAssistantRequest(
            new_name="Cloned Bot",
            clone_steps=True
        )
        
        assert request.new_name == "Cloned Bot"
        assert request.clone_steps is True
    
    def test_clone_without_steps(self):
        """Test cloning without steps."""
        request = CloneAssistantRequest(
            new_name="Cloned Bot",
            clone_steps=False
        )
        
        assert request.clone_steps is False
    
    def test_default_clone_steps(self):
        """Test default value for clone_steps."""
        request = CloneAssistantRequest(new_name="Cloned Bot")
        
        assert request.clone_steps is True
    
    def test_empty_new_name_fails(self):
        """Test that empty new_name fails."""
        with pytest.raises(ValidationError):
            CloneAssistantRequest(new_name="")

    def test_clone_request_without_new_name(self):
        """VA-151: CloneAssistantRequest is valid without new_name (auto-generated by service)."""
        request = CloneAssistantRequest()
        assert request.new_name is None
        assert request.clone_steps is True

    def test_clone_request_new_name_too_long_fails(self):
        """VA-151: new_name over 100 chars still fails schema validation."""
        with pytest.raises(ValidationError):
            CloneAssistantRequest(new_name="A" * 101)

