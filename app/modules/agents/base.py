"""Base agent interface for processing messages."""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.modules.conversations.schemas import IncomingMessage, AgentResponse
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Each agent type (survey, support, etc.) must implement this interface.
    
    Agent responsibilities:
    - Process incoming message
    - Update conversation.state (by calling conversation.update_state())
    - Generate response text (or return None if no response needed)
    """
    
    @abstractmethod
    async def process_message(
        self,
        message: IncomingMessage,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant
    ) -> AgentResponse:
        """
        Process incoming message and generate response.
        
        Agent must:
        1. Analyze message and current conversation.state
        2. Update conversation.state if needed (call conversation.update_state())
        3. Generate response text (or return None)
        
        Args:
            message: Incoming message from user
            conversation: Current conversation with state
            interlocutor: User information
            assistant: Assistant configuration
            
        Returns:
            AgentResponse with response_text (or None)
            
        Raises:
            Exception: If processing fails (will be caught by service)
        """
        pass

    async def list_follow_up_candidate_conversation_ids(
        self,
        assistant_id: str,
    ) -> List[str]:
        """Return conversation IDs the agent considers eligible for follow-up (no LLM)."""
        return []

    async def generate_reminder(
        self,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant,
    ) -> Optional[str]:
        """
        Follow-up reminder text after v4 checks passed.

        None or empty string means decline / not implemented (manual API: llm_error).
        """
        return None

    @staticmethod
    def resolve_language(conversation: Conversation, interlocutor: Interlocutor) -> str:
        """Determine language: agent_metadata → interlocutor profile → English."""
        lang = conversation.get_agent_metadata().get("language")
        return lang or interlocutor.language or "English"

    @staticmethod
    def format_prompt(template: str, variables: dict) -> str:
        """Safe prompt formatting with fallback for missing keys."""
        try:
            return template.format_map(variables)
        except (KeyError, IndexError):
            result = template
            for k, v in variables.items():
                result = result.replace(f"{{{k}}}", str(v))
            return result

