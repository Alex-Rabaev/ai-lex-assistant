"""Tool for saving additional information."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

logger = logging.getLogger(__name__)


class SaveAdditionalInfoInput(BaseModel):
    """Input schema for SaveAdditionalInfoTool."""
    info_type: str = Field(description="Type of information collected (e.g., 'email', 'phone', 'hobby')")
    info_value: str = Field(description="The actual value collected, or 'declined' if user refused")
    next_step_key: str = Field(description="Next step key to transition to (usually 'closing')")


class SaveAdditionalInfoTool(BaseTool):
    """Tool for saving additional information and transitioning to next step.
    
    Saves additional info in format: {"hobby": "value", "email": "value", ...}
    If user declines, nothing is added to additional_info.
    """
    
    name: str = "save_additional_info"
    description: str = "Save additional information (email, phone, hobby, etc.) and transition to next step"
    args_schema: Type[BaseModel] = SaveAdditionalInfoInput
    
    # Store conversation_id and interlocutor_id
    conversation_id: str = None
    interlocutor_id: str = None
    
    async def _arun(
        self,
        info_type: str,
        info_value: str,
        next_step_key: str
    ) -> str:
        """Execute tool."""
        try:
            from app.modules.conversations.service import ConversationsService
            
            service = ConversationsService()
            
            # Get current conversation to merge additional_info
            conversation = await service.get_conversation(self.conversation_id)
            current_metadata = conversation.get_agent_metadata()
            current_additional_info = current_metadata.get("additional_info", {})
            
            # Only add if user didn't decline
            if info_value.lower() != "declined":
                # Add new field to additional_info
                current_additional_info[info_type] = info_value
                
                # If it's an email, also save to interlocutor
                if info_type.lower() == "email":
                    await service.update_interlocutor_email(self.interlocutor_id, info_value)
                
                logger.info(f"Additional info saved: {info_type}={info_value}")
            else:
                logger.info(f"User declined to provide {info_type}")
            
            # Update agent metadata with merged additional_info
            await service.update_agent_metadata(
                self.conversation_id,
                {
                    "additional_info": current_additional_info,
                    "state": next_step_key
                }
            )
            
            logger.info(f"Transitioning to {next_step_key}, additional_info={current_additional_info}")
            
            return f"Additional info saved, moving to {next_step_key}"
        
        except Exception as e:
            logger.error(f"SaveAdditionalInfoTool error: {e}")
            return f"Error saving additional info: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")
