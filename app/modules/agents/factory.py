"""Factory for creating agents based on assistant type."""

import logging
from typing import Dict, Type

from app.modules.agents.base import BaseAgent
from app.modules.assistants.models import AssistantType

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating agents based on assistant type.
    
    Maps assistant.type to appropriate agent class.
    """
    
    # Mapping: AssistantType -> Agent Class
    # Will be updated when SurveyAgent is implemented
    _agents: Dict[AssistantType, Type[BaseAgent]] = {}
    
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

