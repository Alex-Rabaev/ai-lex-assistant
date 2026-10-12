"""Command handler for survey agent."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handler for special commands (/reset, /error)."""
    
    async def handle_command(
        self,
        command: str,
        conversation_id: str
    ) -> Optional[str]:
        """
        Handle command and return response.
        
        Args:
            command: Command text (e.g., "/reset", "/error")
            conversation_id: Conversation ID
            
        Returns:
            Response text or None if command not recognized
        """
        command = command.strip().lower()
        
        if command == "/reset":
            return await self._handle_reset(conversation_id)
        elif command == "/error":
            return await self._handle_error(conversation_id)
        else:
            logger.warning(f"Unknown command: {command}")
            return None
    
    async def _handle_reset(self, conversation_id: str) -> str:
        """
        Handle /reset command.
        
        Deletes all conversation history and resets state.
        """
        from app.modules.conversations.service import ConversationsService
        
        service = ConversationsService()
        
        # Reset conversation through service
        await service.reset_conversation(conversation_id)
        
        logger.info(f"Reset conversation: {conversation_id}")
        
        return "All data has been deleted. You can start the conversation again."
    
    async def _handle_error(self, conversation_id: str) -> str:
        """
        Handle /error command.
        
        Logs error and returns simple message to user.
        """
        logger.error(
            f"User triggered /error command: "
            f"conversation={conversation_id}"
        )
        
        return "Oops, something went wrong. Please try again later."

