"""Configuration models for Survey Agent.

This module defines all survey-specific configurations:
- SurveyStepKey: step identifiers
- QuestionnaireConfig: questionnaire step configuration
- ClosingConfig: closing step configuration
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class SurveyStepKey(str, Enum):
    """Step keys for Survey Agent.
    
    Defines all possible steps in the survey flow.
    """
    LANG = "lang"
    INTRO = "intro"
    PROFILE = "profile"
    QUESTIONNAIRE = "questionnaire"
    ADDITIONAL_INFO = "additional_info"
    CLOSING = "closing"


# Steps that cannot be disabled
MANDATORY_STEPS = {
    SurveyStepKey.INTRO,
    SurveyStepKey.QUESTIONNAIRE,
    SurveyStepKey.CLOSING,
}


class QuestionnaireConfig(BaseModel):
    """Configuration for Questionnaire step.
    
    Consists of sub-parts:
    - intro_prompt: Introduction explaining survey purpose
    - questions_list: Parsed list of individual questions (preferred)
    - specific_questions: Free-form questions text (legacy, fallback)
    - survey_goal: Goal for dynamic question generation
    
    Priority: questions_list > specific_questions > survey_goal.
    At least one of questions_list, specific_questions, or survey_goal must be provided.
    """
    intro_prompt: Optional[str] = Field(
        None,
        max_length=1000,
        description="Introduction explaining survey purpose"
    )
    questions_list: Optional[List[str]] = Field(
        None,
        description="Parsed list of individual questions (preferred over specific_questions)"
    )
    specific_questions: Optional[str] = Field(
        None,
        max_length=4000,
        description="Free-form questions to ask (legacy, use questions_list instead)"
    )
    survey_goal: Optional[str] = Field(
        None,
        max_length=1000,
        description="Goal for dynamic question generation"
    )


class ClosingConfig(BaseModel):
    """Configuration for Closing step.
    
    Defines how the assistant should generate the closing message.
    """
    closing_generation_prompt: Optional[str] = Field(
        None,
        max_length=1000,
        description="Prompt for generating closing message based on survey insights"
    )


def validate_questionnaire_config(config: QuestionnaireConfig) -> None:
    """Validate questionnaire configuration.
    
    Rules:
    - At least one of questions_list, specific_questions, or survey_goal must be provided
    - questions_list takes priority over specific_questions
    
    Args:
        config: QuestionnaireConfig to validate
        
    Raises:
        ValueError: If validation fails
    """
    has_questions_list = config.questions_list and len(config.questions_list) > 0
    has_questions = config.specific_questions and config.specific_questions.strip()
    has_goal = config.survey_goal and config.survey_goal.strip()
    
    if not has_questions_list and not has_questions and not has_goal:
        raise ValueError(
            "Questionnaire must have at least one of: "
            "questions_list, specific_questions, or survey_goal"
        )


def get_questionnaire_config(step_metadata: Optional[Dict[str, Any]]) -> QuestionnaireConfig:
    """Extract QuestionnaireConfig from step metadata.
    
    Args:
        step_metadata: AssistantStep.metadata dict
        
    Returns:
        QuestionnaireConfig instance (with defaults if not found)
    """
    if not step_metadata:
        return QuestionnaireConfig()
    
    return QuestionnaireConfig(
        intro_prompt=step_metadata.get("intro_prompt"),
        questions_list=step_metadata.get("questions_list"),
        specific_questions=step_metadata.get("specific_questions"),
        survey_goal=step_metadata.get("survey_goal")
    )


def get_closing_config(step_metadata: Optional[Dict[str, Any]]) -> ClosingConfig:
    """Extract ClosingConfig from step metadata.
    
    Args:
        step_metadata: AssistantStep.metadata dict
        
    Returns:
        ClosingConfig instance (with defaults if not found)
    """
    if not step_metadata:
        return ClosingConfig()
    
    return ClosingConfig(
        closing_generation_prompt=step_metadata.get("closing_generation_prompt")
    )


def is_step_mandatory(step_key: SurveyStepKey) -> bool:
    """Check if a step is mandatory (cannot be disabled).
    
    Args:
        step_key: Step to check
        
    Returns:
        True if step is mandatory
    """
    return step_key in MANDATORY_STEPS


def get_survey_step_schema() -> Dict[str, Any]:
    """Get JSON schema for Survey assistant steps.
    
    Returns a schema describing each step's UI configuration,
    validation rules, and fields for the frontend to render.
    
    Returns:
        Dict with step schemas for UI rendering
    """
    return {
        "assistant_type": "survey",
        "global_settings": {
            "title": "Survey Settings",
            "description": "Global settings applied to all steps",
            "fields": {
                "communication_style": {
                    "type": "textarea",
                    "label": "Communication Style",
                    "placeholder": "Engage in a respectful, friendly manner...",
                    "max_length": 500,
                    "required": False,
                    "location": "assistant.metadata.communication_style"
                },
                "self_introduction": {
                    "type": "textarea",
                    "label": "Self Introduction",
                    "placeholder": "I am a professional AI assistant...",
                    "max_length": 500,
                    "required": False,
                    "location": "assistant.metadata.self_introduction"
                }
            }
        },
        "steps": [
            {
                "step_key": SurveyStepKey.LANG.value,
                "order": 1,
                "title": "Language Detection",
                "description": "Detect or ask user's preferred language",
                "mandatory": False,
                "can_disable": True,
                "fields": {
                    "enabled": {
                        "type": "toggle",
                        "label": "Enable step",
                        "default": True
                    },
                    "default_language": {
                        "type": "text",
                        "label": "Default Language",
                        "placeholder": "English",
                        "required_when_disabled": True,
                        "description": "Required when step is disabled. This language will be used for all conversations."
                    }
                }
            },
            {
                "step_key": SurveyStepKey.INTRO.value,
                "order": 2,
                "title": "Introduction",
                "description": "Greet user and collect their name",
                "mandatory": True,
                "can_disable": False,
                "fields": {}
            },
            {
                "step_key": SurveyStepKey.PROFILE.value,
                "order": 3,
                "title": "Profile Collection",
                "description": "Collect user's business profile/background",
                "mandatory": False,
                "can_disable": True,
                "fields": {
                    "enabled": {
                        "type": "toggle",
                        "label": "Enable step",
                        "default": True
                    },
                    "profile_prompt": {
                        "type": "textarea",
                        "label": "Profile Prompt",
                        "placeholder": "Tell me about your business or what you do professionally...",
                        "max_length": 1000,
                        "required": False,
                        "location": "step.metadata.profile_prompt",
                        "description": "Custom prompt for collecting user's profile/business information"
                    }
                }
            },
            {
                "step_key": SurveyStepKey.QUESTIONNAIRE.value,
                "order": 4,
                "title": "Questionnaire",
                "description": "Main survey questions",
                "mandatory": True,
                "can_disable": False,
                "fields": {
                    "intro_prompt": {
                        "type": "textarea",
                        "label": "Introduction Prompt",
                        "placeholder": "I'd like to ask you a few questions about...",
                        "max_length": 1000,
                        "required": True,
                        "location": "step.metadata.intro_prompt",
                        "description": "Introduces the survey purpose to the user"
                    },
                    "questions_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "label": "Questions List",
                        "required": False,
                        "location": "step.metadata.questions_list",
                        "description": "Parsed list of individual questions. Each question is a separate editable item. Preferred over Specific Questions text."
                    },
                    "specific_questions": {
                        "type": "textarea",
                        "label": "Specific Questions (legacy)",
                        "placeholder": "What is your budget?\nWhat is your timeline?\nWhat features are most important?",
                        "max_length": 4000,
                        "required": False,
                        "location": "step.metadata.specific_questions",
                        "description": "Free-form questions text (legacy). Use Questions List instead for better control."
                    },
                    "survey_goal": {
                        "type": "textarea",
                        "label": "Survey Goal",
                        "placeholder": "Understand user's needs regarding...",
                        "max_length": 1000,
                        "required": False,
                        "location": "step.metadata.survey_goal",
                        "description": "Goal for dynamic question generation. At least one required if Questions List is empty."
                    }
                },
                "validation": {
                    "rule": "at_least_one_of",
                    "fields": ["questions_list", "specific_questions", "survey_goal"],
                    "message": "At least one of 'Questions List', or 'Survey Goal' is required"
                }
            },
            {
                "step_key": SurveyStepKey.ADDITIONAL_INFO.value,
                "order": 5,
                "title": "Additional Information",
                "description": "Collect optional additional info (email, phone, etc.)",
                "mandatory": False,
                "can_disable": True,
                "fields": {
                    "enabled": {
                        "type": "toggle",
                        "label": "Enable step",
                        "default": True
                    },
                    "info_to_collect": {
                        "type": "textarea",
                        "label": "Information to Collect",
                        "placeholder": "Please collect user's email address...",
                        "max_length": 500,
                        "required": False,
                        "location": "step.metadata.info_to_collect",
                        "description": "Describe what additional information to collect (email, phone, company name, etc.)"
                    }
                }
            },
            {
                "step_key": SurveyStepKey.CLOSING.value,
                "order": 6,
                "title": "Closing",
                "description": "Generate personalized closing message based on survey results",
                "mandatory": True,
                "can_disable": False,
                "fields": {
                    "closing_generation_prompt": {
                        "type": "textarea",
                        "label": "Closing Generation Prompt",
                        "placeholder": "Generate a personalized closing message based on the user's responses...",
                        "max_length": 1000,
                        "required": False,
                        "location": "step.metadata.closing_generation_prompt",
                        "description": "Instructions for generating the closing message. Can reference survey answers."
                    }
                }
            }
        ]
    }

