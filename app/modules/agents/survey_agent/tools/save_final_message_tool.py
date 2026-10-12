"""Tool for saving final message and completing the survey."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

logger = logging.getLogger(__name__)


class SaveFinalMessageInput(BaseModel):
    """Input schema for SaveFinalMessageTool."""
    final_message: str = Field(description="The complete closing message to show the user")


class SaveFinalMessageTool(BaseTool):
    """Tool for saving final message and marking survey as completed."""
    
    name: str = "save_final_message"
    description: str = "Save the closing message and mark the survey as completed. This message will be shown on all future interactions."
    args_schema: Type[BaseModel] = SaveFinalMessageInput
    
    # Store conversation_id
    conversation_id: str = None
    
    async def _arun(
        self,
        final_message: str
    ) -> str:
        """Execute tool."""
        try:
            from app.modules.conversations.service import ConversationsService
            from app.modules.agents.survey_agent.state import SurveyAgentState
            
            service = ConversationsService()
            
            # Update agent metadata - save final message and set completed state
            await service.update_agent_metadata(
                self.conversation_id,
                {
                    "final_message": final_message,
                    "state": SurveyAgentState.COMPLETED.value
                }
            )
            
            logger.info(
                f"Survey completed: conversation={self.conversation_id}, "
                f"final_message_length={len(final_message)}"
            )
            
            # Return the final message to be sent to the user
            return final_message
        
        except Exception as e:
            logger.error(f"SaveFinalMessageTool error: {e}")
            return f"Error saving final message: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")

