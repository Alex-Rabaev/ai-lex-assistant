"""Tool for saving survey answers."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List

logger = logging.getLogger(__name__)


class SurveyQA(BaseModel):
    """Schema for a single question-answer pair."""
    question: str = Field(description="Survey question text")
    answer: str = Field(description="User's answer to the question")


class SaveSurveyInput(BaseModel):
    """Input schema for SaveSurveyAnswersTool."""
    survey_data: List[SurveyQA] = Field(
        description="Array of question-answer pairs extracted from the conversation"
    )
    next_step_key: str = Field(description="Next step key to transition to")


class SaveSurveyAnswersTool(BaseTool):
    """Tool for saving all survey answers and transitioning to next step."""
    
    name: str = "save_survey_answers"
    description: str = "Save all collected question-answer pairs and transition to next step"
    args_schema: Type[BaseModel] = SaveSurveyInput
    
    # Store conversation_id
    conversation_id: str = None
    
    async def _arun(
        self,
        survey_data: List[SurveyQA],
        next_step_key: str
    ) -> str:
        """Execute tool."""
        try:
            from app.modules.conversations.service import ConversationsService
            
            service = ConversationsService()
            
            # Convert to dict format
            survey_dict_list = []
            for qa in survey_data:
                if isinstance(qa, SurveyQA):
                    survey_dict_list.append({
                        "question": qa.question,
                        "answer": qa.answer
                    })
                elif isinstance(qa, dict):
                    survey_dict_list.append({
                        "question": qa.get("question", ""),
                        "answer": qa.get("answer", "")
                    })
            
            logger.info(f"Saving {len(survey_dict_list)} Q&A pairs")
            
            # Update agent metadata through service
            await service.update_agent_metadata(
                self.conversation_id,
                {
                    "survey_summary": survey_dict_list,
                    "state": next_step_key
                }
            )
            
            logger.info(
                f"Survey saved: {len(survey_dict_list)} answers, "
                f"transitioned to {next_step_key}"
            )
            
            return f"Survey saved, moving to {next_step_key}"
        
        except Exception as e:
            logger.error(f"SaveSurveyAnswersTool error: {e}")
            return f"Error saving survey: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")

