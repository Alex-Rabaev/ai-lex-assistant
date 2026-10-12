"""
Centralized LangSmith configuration for survey agent.
"""

from langsmith import Client, configure
from app.config import config
import logging

logger = logging.getLogger(__name__)

# Create LangSmith client
langsmith_client = Client(
    api_url=config.LANGSMITH_ENDPOINT,
    api_key=config.LANGSMITH_API_KEY
)

# Configure LangSmith tracing
configure(
    client=langsmith_client,
    enabled=config.LANGSMITH_TRACING,
    project_name=config.LANGSMITH_PROJECT
)

logger.info(
    f"LangSmith configured: "
    f"project={config.LANGSMITH_PROJECT}, "
    f"enabled={config.LANGSMITH_TRACING}, "
    f"endpoint={config.LANGSMITH_ENDPOINT}"
)

# Export the configured client for use in prompts
__all__ = ['langsmith_client']

