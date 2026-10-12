"""Tests for assistant models."""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import ValidationError

from app.modules.assistants.models import (
    Assistant, AssistantStep, AssistantType, AssistantStatus, FollowUpConfig
)


class TestAssistantModel:
    """Test Assistant model validation and serialization."""
    
    def test_create_valid_assistant(self):
        """Test creating a valid assistant."""
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Test Assistant",
            description="A test assistant",
            type=AssistantType.SURVEY,
            status=AssistantStatus.ACTIVE
        )

        assert assistant.org_id == "org_123"
        assert assistant.owner_user_id == "user_456"
        assert assistant.name == "Test Assistant"
        assert assistant.type == AssistantType.SURVEY
        assert assistant.status == AssistantStatus.ACTIVE
        assert assistant.created_at is not None
        assert assistant.updated_at is not None
    
    def test_assistant_name_validation(self):
        """Test assistant name validation."""
        # Empty name should fail
        with pytest.raises(ValidationError) as exc_info:
            Assistant(
                org_id="org_123",
                owner_user_id="user_456",
                name="",  # Empty name
                type=AssistantType.SURVEY
            )
        assert "at least 1 character" in str(exc_info.value).lower()
        
        # Whitespace-only name should fail
        with pytest.raises(ValidationError) as exc_info:
            Assistant(
                org_id="org_123",
                owner_user_id="user_456",
                name="   ",  # Only spaces
                type=AssistantType.SURVEY
            )
        assert "cannot be empty" in str(exc_info.value).lower()
        
        # Name with spaces should be trimmed
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="  Test Assistant  ",
            type=AssistantType.SURVEY
        )
        assert assistant.name == "Test Assistant"
    
    def test_assistant_default_values(self):
        """Test assistant default values."""
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Test"
        )
        
        assert assistant.type == AssistantType.SURVEY
        assert assistant.status == AssistantStatus.ACTIVE
        assert assistant.description is None
    
    def test_assistant_dict_serialization(self):
        """Test assistant serialization to dict."""
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Test Assistant"
        )
        
        data = assistant.model_dump()
        
        assert data["org_id"] == "org_123"
        assert data["owner_user_id"] == "user_456"
        assert data["name"] == "Test Assistant"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_assistant_with_follow_up_config(self):
        """Test assistant with follow_up_config."""
        config = FollowUpConfig(enabled=True, idle_threshold_hours=24, max_attempts=2)
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Survey Bot",
            follow_up_config=config
        )
        assert assistant.follow_up_config is not None
        assert assistant.follow_up_config.enabled is True
        assert assistant.follow_up_config.idle_threshold_hours == 24
        assert assistant.follow_up_config.max_attempts == 2

    def test_assistant_follow_up_config_defaults(self):
        """Test FollowUpConfig default values."""
        config = FollowUpConfig()
        assert config.enabled is True
        assert config.idle_threshold_hours == 23
        assert config.max_attempts == 1

    def test_assistant_without_follow_up_config(self):
        """Test assistant without follow_up_config (None)."""
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Simple Bot"
        )
        assert assistant.follow_up_config is None

    def test_follow_up_config_validation(self):
        """Test FollowUpConfig validation bounds."""
        with pytest.raises(ValidationError):
            FollowUpConfig(idle_threshold_hours=0)
        with pytest.raises(ValidationError):
            FollowUpConfig(idle_threshold_hours=200)
        with pytest.raises(ValidationError):
            FollowUpConfig(max_attempts=0)
        with pytest.raises(ValidationError):
            FollowUpConfig(max_attempts=11)
        # Valid boundary values
        config = FollowUpConfig(idle_threshold_hours=1, max_attempts=10)
        assert config.idle_threshold_hours == 1
        assert config.max_attempts == 10

    def test_assistant_with_survey_settings(self):
        """Test assistant with communication_style in metadata."""
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Survey Bot",
            metadata={
                "communication_style": "Friendly and professional",
                "self_introduction": "I am a survey assistant"
            }
        )
        
        assert assistant.metadata["communication_style"] == "Friendly and professional"


class TestAssistantStepModel:
    """Test AssistantStep model validation and serialization."""
    
    def test_create_valid_step(self):
        """Test creating a valid assistant step."""
        assistant_id = ObjectId()
        step = AssistantStep(
            assistant_id=assistant_id,
            step_key="profile",
            order_no=3,
            enabled=True,
            metadata={"prompt_template": "Tell me about yourself"}
        )
        
        assert step.assistant_id == assistant_id
        assert step.step_key == "profile"
        assert step.order_no == 3
        assert step.enabled == True
        assert step.metadata["prompt_template"] == "Tell me about yourself"
    
    def test_step_key_validation(self):
        """Test step key validation."""
        assistant_id = ObjectId()
        
        # Invalid characters should fail
        with pytest.raises(ValidationError) as exc_info:
            AssistantStep(
                assistant_id=assistant_id,
                step_key="invalid-key!",  # Has invalid characters
                order_no=1
            )
        assert "alphanumeric with underscores only" in str(exc_info.value).lower()
        
        # Empty key should fail
        with pytest.raises(ValidationError) as exc_info:
            AssistantStep(
                assistant_id=assistant_id,
                step_key="",
                order_no=1
            )
        assert "cannot be empty" in str(exc_info.value).lower()
        
        # Key should be converted to lowercase
        step = AssistantStep(
            assistant_id=assistant_id,
            step_key="Profile_Step",
            order_no=1
        )
        assert step.step_key == "profile_step"
    
    def test_order_no_validation(self):
        """Test order number validation."""
        assistant_id = ObjectId()
        
        # Order below 1 should fail
        with pytest.raises(ValidationError) as exc_info:
            AssistantStep(
                assistant_id=assistant_id,
                step_key="test",
                order_no=0
            )
        assert "greater than or equal to 1" in str(exc_info.value).lower()
        
        # Order above 100 should fail
        with pytest.raises(ValidationError) as exc_info:
            AssistantStep(
                assistant_id=assistant_id,
                step_key="test",
                order_no=101
            )
        assert "less than or equal to 100" in str(exc_info.value).lower()
    
    def test_step_enabled_default(self):
        """Test step enabled default value."""
        step = AssistantStep(
            assistant_id=ObjectId(),
            step_key="test",
            order_no=1
        )
        
        assert step.enabled == True
    
    def test_step_metadata_default(self):
        """Test step metadata default value."""
        step = AssistantStep(
            assistant_id=ObjectId(),
            step_key="test",
            order_no=1
        )
        
        assert step.metadata == {}
    
    def test_step_with_questionnaire_metadata(self):
        """Test step with questionnaire configuration in metadata."""
        step = AssistantStep(
            assistant_id=ObjectId(),
            step_key="questionnaire",
            order_no=4,
            metadata={
                "intro_prompt": "This survey will help us...",
                "specific_questions": "Q1?\nQ2?",
                "survey_goal": "Understand customer needs"
            }
        )
        
        assert step.metadata["intro_prompt"] == "This survey will help us..."
        assert "Q1?" in step.metadata["specific_questions"]


class TestAdditionalValidations:
    """Additional important test cases."""
    
    def test_assistant_with_objectid(self):
        """Test creating assistant with existing ObjectId."""
        obj_id = ObjectId()
        assistant = Assistant(
            id=obj_id,
            org_id="org_123",
            owner_user_id="user_456",
            name="Test Assistant"
        )
        assert assistant.id == obj_id
        assert isinstance(assistant.id, ObjectId)
    
    def test_assistant_status_enum_values(self):
        """Test all status enum values."""
        for s in [AssistantStatus.ACTIVE, AssistantStatus.INACTIVE]:
            assistant = Assistant(
                org_id="org_123",
                owner_user_id="user_456",
                name=f"Test {s}",
                status=s,
            )
            assert assistant.status == s
    
    def test_assistant_name_edge_cases(self):
        """Test edge cases for assistant name."""
        # Maximum length name (100 chars)
        max_name = "A" * 100
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name=max_name
        )
        assert assistant.name == max_name
        assert len(assistant.name) == 100
        
        # Over maximum should fail
        with pytest.raises(ValidationError) as exc_info:
            Assistant(
                org_id="org_123",
                owner_user_id="user_456",
                name="A" * 101  # Too long
            )
        assert "at most 100 characters" in str(exc_info.value).lower()
    
    def test_step_order_boundary_values(self):
        """Test boundary values for step order_no."""
        # Minimum valid order (1)
        step_min = AssistantStep(
            assistant_id=ObjectId(),
            step_key="first",
            order_no=1
        )
        assert step_min.order_no == 1
        
        # Maximum valid order (100)
        step_max = AssistantStep(
            assistant_id=ObjectId(),
            step_key="last",
            order_no=100
        )
        assert step_max.order_no == 100
        
        # Zero order should fail
        with pytest.raises(ValidationError):
            AssistantStep(
                assistant_id=ObjectId(),
                step_key="zero",
                order_no=0
            )
        
        # Order > 100 should fail
        with pytest.raises(ValidationError):
            AssistantStep(
                assistant_id=ObjectId(),
                step_key="overflow",
                order_no=101
            )
    
    def test_assistant_full_json_roundtrip(self):
        """Test full JSON serialization/deserialization."""
        assistant = Assistant(
            org_id="org_123",
            owner_user_id="user_456",
            name="Test Assistant",
            description="Test description",
            type=AssistantType.SURVEY,
            status=AssistantStatus.ACTIVE
        )
        
        # Serialize to dict
        data = assistant.model_dump(by_alias=True)
        
        # Verify required fields are present
        assert "org_id" in data
        assert "name" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Create new instance from dict
        assistant2 = Assistant(**assistant.model_dump())
        assert assistant2.name == assistant.name
        assert assistant2.org_id == assistant.org_id
        assert assistant2.status == assistant.status
        assert assistant2.type == assistant.type
    
    def test_invalid_objectid_string(self):
        """Test invalid ObjectId string raises error."""
        with pytest.raises(ValidationError):
            Assistant(
                id="invalid_object_id",  # Invalid ObjectId format
                org_id="org_123",
                owner_user_id="user_456",
                name="Test"
            )


class TestFollowUpConfig:
    """Validation tests for FollowUpConfig boundary values."""

    def test_defaults(self):
        c = FollowUpConfig()
        assert c.enabled is True
        assert c.idle_threshold_hours == 23
        assert c.max_attempts == 1

    def test_min_bounds(self):
        c = FollowUpConfig(idle_threshold_hours=1, max_attempts=1)
        assert c.idle_threshold_hours == 1
        assert c.max_attempts == 1

    def test_max_bounds(self):
        c = FollowUpConfig(idle_threshold_hours=168, max_attempts=10)
        assert c.idle_threshold_hours == 168
        assert c.max_attempts == 10

    def test_idle_threshold_below_min(self):
        with pytest.raises(ValidationError):
            FollowUpConfig(idle_threshold_hours=0)

    def test_idle_threshold_above_max(self):
        with pytest.raises(ValidationError):
            FollowUpConfig(idle_threshold_hours=169)

    def test_max_attempts_below_min(self):
        with pytest.raises(ValidationError):
            FollowUpConfig(max_attempts=0)

    def test_max_attempts_above_max(self):
        with pytest.raises(ValidationError):
            FollowUpConfig(max_attempts=11)
