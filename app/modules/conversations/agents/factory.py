"""Factory for creating agents based on assistant type."""

import logging
from typing import Dict, Type

from app.modules.agents.base import BaseAgent
from app.modules.conversations.agents.test_agent import TestAgent
from app.modules.assistants.models import AssistantType

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating agents based on assistant type.
    
    Maps assistant.type to appropriate agent class.
    """
    
    # Mapping: AssistantType -> Agent Class
    _agents: Dict[AssistantType, Type[BaseAgent]] = {
        AssistantType.SURVEY: None,  # Will be set dynamically
        AssistantType.FAQ: TestAgent,      # Пока используем TestAgent
        AssistantType.SUPPORT: TestAgent,  # Пока используем TestAgent
    }
    
    @classmethod
    def _get_survey_agent(cls):
        """Lazy load SurveyAgent to avoid circular imports."""
        try:
            from app.modules.agents.survey_agent.agent import SurveyAgent
            return SurveyAgent
        except ImportError:
            logger.warning("SurveyAgent not available, falling back to TestAgent")
            return TestAgent
    
    @classmethod
    def get_agent(cls, assistant_type: AssistantType) -> BaseAgent:
        """
        Get agent instance for assistant type.
        
        Args:
            assistant_type: Type of assistant (from Assistant.type)
            
        Returns:
            Agent instance
            
        Raises:
            ValueError: If assistant type not supported
        """
        agent_class = cls._agents.get(assistant_type)
        
        # Lazy load SurveyAgent
        if assistant_type == AssistantType.SURVEY and agent_class is None:
            agent_class = cls._get_survey_agent()
        
        if not agent_class:
            logger.error(f"No agent found for type: {assistant_type}")
            raise ValueError(f"Unsupported assistant type: {assistant_type}")
        
        logger.debug(f"Creating agent: {agent_class.__name__} for type {assistant_type}")
        
        return agent_class()
    
    @classmethod
    def register_agent(cls, assistant_type: AssistantType, agent_class: Type[BaseAgent]):
        """
        Register new agent type.
        
        Allows adding new agent implementations dynamically.
        
        Args:
            assistant_type: Assistant type
            agent_class: Agent class to use
        """
        cls._agents[assistant_type] = agent_class
        logger.info(f"Registered agent: {agent_class.__name__} for type {assistant_type}")

