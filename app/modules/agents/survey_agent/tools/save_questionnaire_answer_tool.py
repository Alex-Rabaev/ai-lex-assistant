"""Tool for saving individual questionnaire answers incrementally."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

logger = logging.getLogger(__name__)


class SaveQuestionnaireAnswerInput(BaseModel):
    """Input schema for SaveQuestionnaireAnswerTool."""
    answer: str = Field(description="User's answer to the current question")


class SaveQuestionnaireAnswerTool(BaseTool):
    """Tool for saving a single questionnaire answer and advancing to the next question.
    
    Tracks progress via agent_metadata.questionnaire_progress:
    - current_index: which question we're on (0-based)
    - answers: list of {question, answer} pairs collected so far
    
    When the last question is answered, automatically saves survey_summary
    and transitions to the next step.
    """
    
    name: str = "save_questionnaire_answer"
    description: str = "Save the user's answer to the current survey question and proceed to the next one"
    args_schema: Type[BaseModel] = SaveQuestionnaireAnswerInput
    
    conversation_id: str = None
    assistant_id: str = None
    
    async def _arun(self, answer: str) -> str:
        """Save answer for current question, advance progress."""
        try:
            from app.modules.conversations.service import ConversationsService
            from app.modules.assistants.service import AssistantService
            
            conv_service = ConversationsService()
            assistant_service = AssistantService()
            
            # Get current conversation state
            conversation = await conv_service.get_conversation(self.conversation_id)
            agent_metadata = conversation.get_agent_metadata()
            progress = agent_metadata.get("questionnaire_progress", {})
            current_index = progress.get("current_index", 0)
            answers = progress.get("answers", [])
            
            # Get questions_list from step metadata
            current_step = await assistant_service.get_current_step(
                self.assistant_id, "questionnaire"
            )
            if not current_step:
                return "Error: questionnaire step not found"
            
            questions_list = (current_step.metadata or {}).get("questions_list", [])
            if not questions_list:
                return "Error: no questions_list configured"
            
            total = len(questions_list)
            
            if current_index >= total:
                return "Error: all questions already answered"
            
            # Save current Q&A pair
            current_question = questions_list[current_index]
            answers.append({
                "question": current_question,
                "answer": answer
            })
            new_index = current_index + 1
            
            logger.info(
                f"Saving answer {new_index}/{total}: "
                f"Q='{current_question[:50]}...', A='{answer[:50]}...'"
            )
            
            # Check if this was the last question
            if new_index >= total:
                # All questions answered — save survey_summary and transition
                next_step = await assistant_service.get_step_by_order(
                    self.assistant_id,
                    current_step.order_no + 1
                )
                next_step_key = next_step.step_key if next_step else "completed"
                
                await conv_service.update_agent_metadata(
                    self.conversation_id,
                    {
                        "questionnaire_progress": {
                            "current_index": new_index,
                            "answers": answers
                        },
                        "survey_summary": answers,
                        "state": next_step_key
                    }
                )
                
                logger.info(
                    f"Questionnaire complete: {total} answers saved, "
                    f"transitioning to {next_step_key}"
                )
                return f"Survey complete ({total} answers), moving to {next_step_key}"
            else:
                # More questions remain — just save progress
                await conv_service.update_agent_metadata(
                    self.conversation_id,
                    {
                        "questionnaire_progress": {
                            "current_index": new_index,
                            "answers": answers
                        }
                    }
                )
                
                return ""
        
        except Exception as e:
            logger.error(f"SaveQuestionnaireAnswerTool error: {e}", exc_info=True)
            return f"Error saving answer: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")
