"""LangChain tools for survey agent."""

from app.modules.agents.survey_agent.tools.update_language_tool import UpdateLanguageTool
from app.modules.agents.survey_agent.tools.save_name_tool import SaveNameTool
from app.modules.agents.survey_agent.tools.save_profile_tool import SaveProfileTool
from app.modules.agents.survey_agent.tools.save_survey_tool import SaveSurveyAnswersTool
from app.modules.agents.survey_agent.tools.save_questionnaire_answer_tool import SaveQuestionnaireAnswerTool
from app.modules.agents.survey_agent.tools.save_additional_info_tool import SaveAdditionalInfoTool
from app.modules.agents.survey_agent.tools.save_final_message_tool import SaveFinalMessageTool
# Deprecated: SaveEmailTool - use SaveAdditionalInfoTool + SaveFinalMessageTool instead
from app.modules.agents.survey_agent.tools.save_email_tool import SaveEmailTool


def get_survey_tools(step_key: str = None, step_metadata: dict = None):
    """
    Get tools for survey agent, filtered by step.
    
    Args:
        step_key: Current step key (lang, intro, profile, questionnaire, additional_info, closing)
                  If None, returns all tools
        step_metadata: Step metadata dict (used to select questionnaire tool variant)
    
    Returns:
        List of tools available for the step
    """
    # For questionnaire: use incremental tool when questions_list is available
    if step_key == "questionnaire" and step_metadata:
        questions_list = step_metadata.get("questions_list")
        if questions_list and len(questions_list) > 0:
            return [SaveQuestionnaireAnswerTool()]
    
    # Default step-to-tool mapping
    step_tools = {
        "lang": [UpdateLanguageTool()],
        "intro": [SaveNameTool()],
        "profile": [SaveProfileTool()],
        "questionnaire": [SaveSurveyAnswersTool()],
        "additional_info": [SaveAdditionalInfoTool()],
        "closing": [SaveFinalMessageTool()]
    }
    
    # If step_key provided, return only tools for that step
    if step_key and step_key in step_tools:
        return step_tools[step_key]
    
    # Otherwise return all tools (for backward compatibility)
    return [
        UpdateLanguageTool(),
        SaveNameTool(),
        SaveProfileTool(),
        SaveSurveyAnswersTool(),
        SaveAdditionalInfoTool(),
        SaveFinalMessageTool()
    ]


__all__ = [
    "UpdateLanguageTool",
    "SaveNameTool",
    "SaveProfileTool",
    "SaveSurveyAnswersTool",
    "SaveQuestionnaireAnswerTool",
    "SaveAdditionalInfoTool",
    "SaveFinalMessageTool",
    "SaveEmailTool",  # Deprecated
    "get_survey_tools"
]
