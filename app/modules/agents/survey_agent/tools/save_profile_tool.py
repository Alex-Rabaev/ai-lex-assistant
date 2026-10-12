"""Tool for saving profile summary."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

logger = logging.getLogger(__name__)


class SaveProfileInput(BaseModel):
    """Input schema for SaveProfileTool."""
    profile_summary: str = Field(description="Short business profile summary")
    next_step_key: str = Field(description="Next step key to transition to")


class SaveProfileTool(BaseTool):
    """Tool for saving profile summary and transitioning to next step."""
    
    name: str = "save_profile"
    description: str = "Save user's profile summary and transition to next step"
    args_schema: Type[BaseModel] = SaveProfileInput
    
    # Store conversation_id and interlocutor_id
    conversation_id: str = None
    interlocutor_id: str = None
    
    async def _arun(
        self,
        profile_summary: str,
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
                    "profile_summary": profile_summary,
                    "state": next_step_key
                }
            )
            
            # Save profile_summary to interlocutor.profile
            await service.update_interlocutor_profile(
                self.interlocutor_id,
                {"profile_summary": profile_summary}
            )
            
            logger.info(
                f"Profile saved: {profile_summary[:50]}..., "
                f"transitioned to {next_step_key}"
            )
            
            return f"Profile saved, moving to {next_step_key}"
        
        except Exception as e:
            logger.error(f"SaveProfileTool error: {e}")
            return f"Error saving profile: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")

