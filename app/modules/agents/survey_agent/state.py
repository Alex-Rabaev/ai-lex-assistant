"""Survey agent state enum."""

from enum import Enum


class SurveyAgentState(str, Enum):
    """
    Survey agent states.
    
    Used to track conversation progress within the survey agent.
    Maps to SurveyStepKey values plus COMPLETED state.
    """
    LANG = "lang"
    INTRO = "intro"
    PROFILE = "profile"
    QUESTIONNAIRE = "questionnaire"  # was: GOALS
    ADDITIONAL_INFO = "additional_info"  # NEW
    CLOSING = "closing"
    COMPLETED = "completed"  # Survey finished
