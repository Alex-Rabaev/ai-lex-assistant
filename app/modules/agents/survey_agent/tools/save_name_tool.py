"""Tool for saving user's name and transitioning to profile step."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

logger = logging.getLogger(__name__)


class SaveNameInput(BaseModel):
    """Input schema for SaveNameTool."""
    name: str = Field(description="User's preferred name")
    next_step_key: str = Field(description="Next step key to transition to (should be 'profile')")


class SaveNameTool(BaseTool):
    """Tool for saving user's name and transitioning to profile step."""
    
    name: str = "save_name_and_transition"
    description: str = "Save user's preferred name and transition to profile collection step"
    args_schema: Type[BaseModel] = SaveNameInput
    
    # Store conversation_id and interlocutor_id
    conversation_id: str = None
    interlocutor_id: str = None
    
    async def _arun(
        self,
        name: str,
        next_step_key: str
    ) -> str:
        """Execute tool."""
        try:
            from app.modules.conversations.service import ConversationsService
            
            service = ConversationsService()
            
            # Update agent metadata through service
            await service.update_agent_metadata(
                self.conversation_id,
                {
                    "name": name,
                    "state": next_step_key
                }
            )
            
            # Save name to interlocutor
            await service.update_interlocutor_name(
                self.interlocutor_id,
                name
            )
            
            logger.info(
                f"Name saved: {name}, "
                f"transitioned to {next_step_key}"
            )
            
            return f"Name saved, moving to {next_step_key}"
        
        except Exception as e:
            logger.error(f"SaveNameTool error: {e}")
            return f"Error saving name: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")

