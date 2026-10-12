"""Tool for updating user's language."""

import logging
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

logger = logging.getLogger(__name__)


class UpdateLanguageInput(BaseModel):
    """Input schema for UpdateLanguageTool."""
    language: str = Field(description="User's preferred language (e.g., 'English', 'Русский')")


class UpdateLanguageTool(BaseTool):
    """Tool for updating user's language in agent_metadata."""
    
    name: str = "update_language"
    description: str = "Update the user's preferred language in conversation metadata"
    args_schema: Type[BaseModel] = UpdateLanguageInput
    
    # Store conversation_id and interlocutor_id
    conversation_id: str = None
    interlocutor_id: str = None
    
    async def _arun(
        self,
        language: str
    ) -> str:
        """Execute tool."""
        try:
            from app.modules.conversations.service import ConversationsService
            
            service = ConversationsService()
            
            # Update agent metadata through service
            await service.update_agent_metadata(
                self.conversation_id,
                {
                    "language": language,
                    "state": "intro"
                }
            )
            
            # Update interlocutor language (same as in conversation)
            await service.update_interlocutor_language(
                self.interlocutor_id,
                language
            )
            
            logger.info(f"Language updated to: {language}, transitioning to intro, conversation_id={self.conversation_id}")
            
            return f"Language set to {language}"
        
        except Exception as e:
            logger.error(f"UpdateLanguageTool error: {e}")
            return f"Error updating language: {e}"
    
    def _run(self, *args, **kwargs):
        """Sync version (not used)."""
        raise NotImplementedError("Use async version")

