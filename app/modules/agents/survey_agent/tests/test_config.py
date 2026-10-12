"""Unit tests for Survey Agent configuration.

Tests configuration models, validation, and step schemas.
"""

import pytest

from app.modules.agents.survey_agent.config import (
    SurveyStepKey,
    MANDATORY_STEPS,
    QuestionnaireConfig,
    ClosingConfig,
    validate_questionnaire_config,
    get_questionnaire_config,
    get_closing_config,
    is_step_mandatory,
    get_survey_step_schema
)


class TestSurveyStepKey:
    """Tests for SurveyStepKey enum."""
    
    def test_all_step_keys_defined(self):
        """Test all expected step keys are defined."""
        assert SurveyStepKey.LANG.value == "lang"
        assert SurveyStepKey.INTRO.value == "intro"
        assert SurveyStepKey.PROFILE.value == "profile"
        assert SurveyStepKey.QUESTIONNAIRE.value == "questionnaire"
        assert SurveyStepKey.ADDITIONAL_INFO.value == "additional_info"
        assert SurveyStepKey.CLOSING.value == "closing"
    
    def test_step_key_is_string_enum(self):
        """Test SurveyStepKey is a string enum."""
        assert isinstance(SurveyStepKey.LANG.value, str)
        # Can use directly as string
        assert SurveyStepKey.LANG == "lang"


class TestMandatorySteps:
    """Tests for mandatory steps configuration."""
    
    def test_mandatory_steps_contains_intro(self):
        """Test INTRO is mandatory."""
        assert SurveyStepKey.INTRO in MANDATORY_STEPS
    
    def test_mandatory_steps_contains_questionnaire(self):
        """Test QUESTIONNAIRE is mandatory."""
        assert SurveyStepKey.QUESTIONNAIRE in MANDATORY_STEPS
    
    def test_mandatory_steps_contains_closing(self):
        """Test CLOSING is mandatory."""
        assert SurveyStepKey.CLOSING in MANDATORY_STEPS
    
    def test_lang_is_not_mandatory(self):
        """Test LANG is optional."""
        assert SurveyStepKey.LANG not in MANDATORY_STEPS
    
    def test_profile_is_not_mandatory(self):
        """Test PROFILE is optional."""
        assert SurveyStepKey.PROFILE not in MANDATORY_STEPS
    
    def test_additional_info_is_not_mandatory(self):
        """Test ADDITIONAL_INFO is optional."""
        assert SurveyStepKey.ADDITIONAL_INFO not in MANDATORY_STEPS


class TestQuestionnaireConfig:
    """Tests for QuestionnaireConfig model."""
    
    def test_create_with_all_fields(self):
        """Test creating config with all fields."""
        config = QuestionnaireConfig(
            intro_prompt="Welcome to the survey",
            questions_list=["Q1?", "Q2?"],
            specific_questions="Q1?\nQ2?",
            survey_goal="Understand customer needs"
        )
        
        assert config.intro_prompt == "Welcome to the survey"
        assert config.questions_list == ["Q1?", "Q2?"]
        assert config.specific_questions == "Q1?\nQ2?"
        assert config.survey_goal == "Understand customer needs"
    
    def test_create_with_questions_list(self):
        """Test creating config with questions_list."""
        config = QuestionnaireConfig(
            questions_list=["What is your budget?", "What is your timeline?"]
        )
        
        assert config.questions_list == ["What is your budget?", "What is your timeline?"]
        assert config.specific_questions is None
        assert config.survey_goal is None
    
    def test_create_with_only_questions(self):
        """Test creating config with only specific_questions."""
        config = QuestionnaireConfig(
            specific_questions="What is your budget?"
        )
        
        assert config.specific_questions == "What is your budget?"
        assert config.questions_list is None
        assert config.survey_goal is None
    
    def test_create_with_only_goal(self):
        """Test creating config with only survey_goal."""
        config = QuestionnaireConfig(
            survey_goal="Understand project requirements"
        )
        
        assert config.specific_questions is None
        assert config.questions_list is None
        assert config.survey_goal == "Understand project requirements"
    
    def test_create_empty_config(self):
        """Test creating empty config (should be allowed by model)."""
        config = QuestionnaireConfig()
        
        assert config.intro_prompt is None
        assert config.questions_list is None
        assert config.specific_questions is None
        assert config.survey_goal is None


class TestValidateQuestionnaireConfig:
    """Tests for validate_questionnaire_config function."""
    
    def test_valid_with_questions_list(self):
        """Test validation passes with questions_list."""
        config = QuestionnaireConfig(
            questions_list=["Q1?", "Q2?"]
        )
        
        # Should not raise
        validate_questionnaire_config(config)
    
    def test_valid_with_specific_questions(self):
        """Test validation passes with specific_questions."""
        config = QuestionnaireConfig(
            specific_questions="What is your budget?\nWhat is your timeline?"
        )
        
        # Should not raise
        validate_questionnaire_config(config)
    
    def test_valid_with_survey_goal(self):
        """Test validation passes with survey_goal."""
        config = QuestionnaireConfig(
            survey_goal="Understand customer requirements for CRM"
        )
        
        # Should not raise
        validate_questionnaire_config(config)
    
    def test_valid_with_all(self):
        """Test validation passes with all fields."""
        config = QuestionnaireConfig(
            questions_list=["Q1?"],
            specific_questions="Q1?",
            survey_goal="Goal"
        )
        
        # Should not raise
        validate_questionnaire_config(config)
    
    def test_invalid_with_nothing(self):
        """Test validation fails when nothing provided."""
        config = QuestionnaireConfig()
        
        with pytest.raises(ValueError) as exc_info:
            validate_questionnaire_config(config)
        
        assert "at least one" in str(exc_info.value).lower()
    
    def test_invalid_with_empty_list_and_empty_strings(self):
        """Test validation fails with empty list and empty strings."""
        config = QuestionnaireConfig(
            questions_list=[],
            specific_questions="   ",
            survey_goal=""
        )
        
        with pytest.raises(ValueError):
            validate_questionnaire_config(config)
    
    def test_invalid_with_whitespace_only(self):
        """Test validation fails with whitespace only."""
        config = QuestionnaireConfig(
            specific_questions="\n\t  ",
            survey_goal=None
        )
        
        with pytest.raises(ValueError):
            validate_questionnaire_config(config)


class TestClosingConfig:
    """Tests for ClosingConfig model."""
    
    def test_create_with_prompt(self):
        """Test creating config with closing prompt."""
        config = ClosingConfig(
            closing_generation_prompt="Generate personalized recommendation"
        )
        
        assert config.closing_generation_prompt == "Generate personalized recommendation"
    
    def test_create_empty(self):
        """Test creating empty config."""
        config = ClosingConfig()
        
        assert config.closing_generation_prompt is None


class TestGetQuestionnaireConfig:
    """Tests for get_questionnaire_config function."""
    
    def test_extract_from_metadata(self):
        """Test extracting config from step metadata."""
        metadata = {
            "intro_prompt": "Welcome!",
            "questions_list": ["Q1?", "Q2?"],
            "specific_questions": "Q1?\nQ2?",
            "survey_goal": "Understand needs"
        }
        
        config = get_questionnaire_config(metadata)
        
        assert config.intro_prompt == "Welcome!"
        assert config.questions_list == ["Q1?", "Q2?"]
        assert config.specific_questions == "Q1?\nQ2?"
        assert config.survey_goal == "Understand needs"
    
    def test_extract_with_questions_list(self):
        """Test extracting config with questions_list."""
        metadata = {
            "questions_list": ["What is your budget?", "What is your timeline?"]
        }
        
        config = get_questionnaire_config(metadata)
        
        assert config.questions_list == ["What is your budget?", "What is your timeline?"]
        assert config.specific_questions is None
    
    def test_extract_partial_metadata(self):
        """Test extracting config with partial metadata."""
        metadata = {
            "specific_questions": "What is your budget?"
        }
        
        config = get_questionnaire_config(metadata)
        
        assert config.intro_prompt is None
        assert config.questions_list is None
        assert config.specific_questions == "What is your budget?"
        assert config.survey_goal is None
    
    def test_extract_from_none(self):
        """Test extracting config from None metadata."""
        config = get_questionnaire_config(None)
        
        assert config.intro_prompt is None
        assert config.specific_questions is None
        assert config.survey_goal is None
    
    def test_extract_from_empty_dict(self):
        """Test extracting config from empty dict."""
        config = get_questionnaire_config({})
        
        assert config.intro_prompt is None


class TestGetClosingConfig:
    """Tests for get_closing_config function."""
    
    def test_extract_from_metadata(self):
        """Test extracting closing config from step metadata."""
        metadata = {
            "closing_generation_prompt": "Thank the user and provide recommendations"
        }
        
        config = get_closing_config(metadata)
        
        assert config.closing_generation_prompt == "Thank the user and provide recommendations"
    
    def test_extract_from_none(self):
        """Test extracting config from None metadata."""
        config = get_closing_config(None)
        
        assert config.closing_generation_prompt is None
    
    def test_extract_from_empty_dict(self):
        """Test extracting config from empty dict."""
        config = get_closing_config({})
        
        assert config.closing_generation_prompt is None


class TestIsStepMandatory:
    """Tests for is_step_mandatory function."""
    
    def test_mandatory_steps(self):
        """Test mandatory steps return True."""
        assert is_step_mandatory(SurveyStepKey.INTRO) is True
        assert is_step_mandatory(SurveyStepKey.QUESTIONNAIRE) is True
        assert is_step_mandatory(SurveyStepKey.CLOSING) is True
    
    def test_optional_steps(self):
        """Test optional steps return False."""
        assert is_step_mandatory(SurveyStepKey.LANG) is False
        assert is_step_mandatory(SurveyStepKey.PROFILE) is False
        assert is_step_mandatory(SurveyStepKey.ADDITIONAL_INFO) is False


class TestGetSurveyStepSchema:
    """Tests for get_survey_step_schema function."""
    
    def test_schema_has_assistant_type(self):
        """Test schema includes assistant_type."""
        schema = get_survey_step_schema()
        
        assert schema["assistant_type"] == "survey"
    
    def test_schema_has_global_settings(self):
        """Test schema includes global_settings."""
        schema = get_survey_step_schema()
        
        assert "global_settings" in schema
        assert "fields" in schema["global_settings"]
        assert "communication_style" in schema["global_settings"]["fields"]
        assert "self_introduction" in schema["global_settings"]["fields"]
    
    def test_schema_has_all_steps(self):
        """Test schema includes all 6 steps."""
        schema = get_survey_step_schema()
        
        assert len(schema["steps"]) == 6
        
        step_keys = [s["step_key"] for s in schema["steps"]]
        assert "lang" in step_keys
        assert "intro" in step_keys
        assert "profile" in step_keys
        assert "questionnaire" in step_keys
        assert "additional_info" in step_keys
        assert "closing" in step_keys
    
    def test_schema_steps_are_ordered(self):
        """Test schema steps have correct order."""
        schema = get_survey_step_schema()
        
        orders = [s["order"] for s in schema["steps"]]
        assert orders == [1, 2, 3, 4, 5, 6]
    
    def test_schema_mandatory_steps_marked(self):
        """Test mandatory steps are marked correctly."""
        schema = get_survey_step_schema()
        
        for step in schema["steps"]:
            if step["step_key"] in ["intro", "questionnaire", "closing"]:
                assert step["mandatory"] is True
                assert step["can_disable"] is False
            else:
                assert step["mandatory"] is False
                assert step["can_disable"] is True
    
    def test_questionnaire_step_has_validation(self):
        """Test questionnaire step has validation rules."""
        schema = get_survey_step_schema()
        
        questionnaire_step = next(
            s for s in schema["steps"] if s["step_key"] == "questionnaire"
        )
        
        assert "validation" in questionnaire_step
        assert questionnaire_step["validation"]["rule"] == "at_least_one_of"
        assert "questions_list" in questionnaire_step["validation"]["fields"]
        assert "specific_questions" in questionnaire_step["validation"]["fields"]
        assert "survey_goal" in questionnaire_step["validation"]["fields"]
    
    def test_questionnaire_step_has_questions_list_field(self):
        """Test questionnaire step has questions_list field."""
        schema = get_survey_step_schema()
        
        questionnaire_step = next(
            s for s in schema["steps"] if s["step_key"] == "questionnaire"
        )
        
        assert "questions_list" in questionnaire_step["fields"]
        assert questionnaire_step["fields"]["questions_list"]["type"] == "array"
    
    def test_lang_step_has_default_language_field(self):
        """Test lang step has default_language field for when disabled."""
        schema = get_survey_step_schema()
        
        lang_step = next(s for s in schema["steps"] if s["step_key"] == "lang")
        
        assert "default_language" in lang_step["fields"]
        assert lang_step["fields"]["default_language"]["required_when_disabled"] is True

