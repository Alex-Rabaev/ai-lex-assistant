"""Test agent for MVP - generates simple test responses."""

import logging
from typing import Optional

from app.modules.agents.base import BaseAgent
from app.modules.conversations.schemas import IncomingMessage, AgentResponse
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant
from app.common.db.database import get_database

logger = logging.getLogger(__name__)


class TestAgent(BaseAgent):
    """
    Test agent for MVP.
    
    Generates simple echo responses and updates state with message count.
    """
    
    async def process_message(
        self,
        message: IncomingMessage,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant
    ) -> AgentResponse:
        """
        Process message and generate test response.
        
        Updates state with message count and last message.
        """
        logger.info(
            f"TestAgent processing: "
            f"user={interlocutor.user_id}, "
            f"assistant={assistant.name}"
        )
        
        # Update state
        current_count = conversation.state.get("message_count", 0)
        new_state = {
            "message_count": current_count + 1,
            "last_message": message.text,
            "last_message_type": message.type,
            "interlocutor_name": interlocutor.first_name or "Unknown"
        }
        
        # Agent updates state itself
        db = await get_database()
        await conversation.update_state(new_state, db)
        
        logger.info(f"Updated conversation state: message_count={new_state['message_count']}")
        
        # Generate response
        if message.type == "message":
            response_text = self._generate_message_response(message, interlocutor, new_state)
        elif message.type == "callback_query":
            response_text = self._generate_callback_response(message, new_state)
        else:
            response_text = None
        
        return AgentResponse(response_text=response_text)
    
    def _generate_message_response(
        self,
        message: IncomingMessage,
        interlocutor: Interlocutor,
        state: dict
    ) -> str:
        """Generate response for regular message."""
        name = interlocutor.first_name or "Friend"
        count = state["message_count"]
        
        return (
            f"🤖 Test Agent Response\n\n"
            f"👋 Hello, {name}!\n"
            f"📝 You said: {message.text}\n"
            f"📊 This is message #{count} in our conversation\n\n"
            f"💡 This is a test response. Real LLM agent coming soon!"
        )
    
    def _generate_callback_response(self, message: IncomingMessage, state: dict) -> str:
        """Generate response for callback query."""
        count = state["message_count"]
        
        return (
            f"✅ Button pressed!\n\n"
            f"📊 Callback data: {message.callback_data}\n"
            f"📈 Total interactions: {count}"
        )

