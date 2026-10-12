"""Tool for saving email and final message."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Any

logger = logging.getLogger(__name__)


class SaveEmailInput(BaseModel):
    """Input schema for SaveEmailTool."""
    email: str = Field(description="User's email address")
    final_message: str = Field(description="Final message to show the user")


class SaveEmailTool(BaseTool):
    """Tool for saving email and final message."""
    
    name: str = "save_email"
    description: str = "Save user's email and final message, transition to completed state"
    args_schema: Type[BaseModel] = SaveEmailInput
    
    # Store conversation_id and interlocutor_id
    conversation_id: str = None
    interlocutor_id: str = None
    
    async def _arun(
        self,
        email: str,
        final_message: str
    ) -> str:
        """Execute tool."""
        try:
            from app.modules.conversations.service import ConversationsService
            from app.modules.agents.survey_agent.state import SurveyAgentState
            
            service = ConversationsService()
            
            # Update agent metadata through service
            # Transition to 'completed' state
            await service.update_agent_metadata(
                self.conversation_id,
                {
                    "final_message": final_message,
                    "state": SurveyAgentState.COMPLETED.value
                }
            )
            
            # Update interlocutor email through service
            await service.update_interlocutor_email(self.interlocutor_id, email)
            
            logger.info(
                f"Email saved, conversation completed: {self.conversation_id}"
            )
            
            # Return final_message to be sent to user (not technical message)
            return final_message
        
        except Exception as e:
            logger.error(f"SaveEmailTool error: {e}")
            return f"Error saving email: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")

