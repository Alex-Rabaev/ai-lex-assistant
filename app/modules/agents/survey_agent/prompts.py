"""Prompt loader from LangSmith."""

import logging
from langsmith import Client

from app.config import config
# Import langsmith_config to initialize tracing

logger = logging.getLogger(__name__)


class PromptLoader:
    """Loader for prompts from LangSmith."""
    
    def __init__(self):
        """Initialize LangSmith client."""
        self.client = Client(
            api_key=config.LANGSMITH_API_KEY,
            api_url=config.LANGSMITH_ENDPOINT
        )
        logger.info(f"PromptLoader initialized (endpoint: {config.LANGSMITH_ENDPOINT})")
    
    async def load_system_prompt(self) -> str:
        """
        Load general system prompt for survey agent.
        
        Returns:
            System prompt text (raw template from first message)
        """
        try:
            prompt = self.client.pull_prompt("survey_agent_system")
            # ChatPromptTemplate has 'messages' attribute
            # Get the first SystemMessage template text
            if hasattr(prompt, 'messages') and prompt.messages:
                first_msg = prompt.messages[0]
                if hasattr(first_msg, 'prompt') and hasattr(first_msg.prompt, 'template'):
                    template = first_msg.prompt.template
                    logger.info(f"Loaded system prompt from LangSmith ({len(template)} chars)")
                    logger.debug(f"System prompt preview: {template[:300]}...")
                    return template
            return str(prompt)
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            # Fallback prompt
            return "You are a helpful AI assistant conducting a survey."
    
    async def load_step_system_prompt(self, step_key: str) -> str:
        """
        Load system prompt for specific step.
        
        Args:
            step_key: Step key (e.g., 'intro', 'profile')
            
        Returns:
            Step system prompt text (raw template from first message)
        """
        try:
            prompt_name = f"survey_agent_step_{step_key}"
            prompt = self.client.pull_prompt(prompt_name)
            # ChatPromptTemplate has 'messages' attribute
            # Get the first SystemMessage template text
            if hasattr(prompt, 'messages') and prompt.messages:
                first_msg = prompt.messages[0]
                if hasattr(first_msg, 'prompt') and hasattr(first_msg.prompt, 'template'):
                    template = first_msg.prompt.template
                    logger.info(f"Loaded step prompt '{step_key}' from LangSmith ({len(template)} chars)")
                    logger.debug(f"Step prompt preview: {template[:300]}...")
                    return template
            return str(prompt)
        except Exception as e:
            logger.error(f"Failed to load step prompt for {step_key}: {e}")
            # Fallback prompt
            return f"You are conducting the '{step_key}' step of the survey."

    _DEFAULT_REMINDER_MODEL = "gpt-4.1-mini"

    async def load_reminder_prompt(self) -> tuple[str, str]:
        """Load follow-up reminder prompt and model name from LangSmith.

        Returns:
            (template_text, model_name)
        """
        fallback_template = (
            "You are a friendly survey assistant. Write a short, warm follow-up "
            "reminder in {language} encouraging {name} to continue the survey. "
            "1-3 sentences, no markdown, no HTML."
        )
        try:
            prompt = self.client.pull_prompt("survey_agent_reminder")
            model_name: str | None = None
            if hasattr(prompt, 'metadata') and isinstance(prompt.metadata, dict):
                model_name = prompt.metadata.get("model_name")

            if hasattr(prompt, 'messages') and prompt.messages:
                first_msg = prompt.messages[0]
                if hasattr(first_msg, 'prompt') and hasattr(first_msg.prompt, 'template'):
                    template = first_msg.prompt.template
                    logger.info("Loaded reminder prompt from LangSmith (%d chars, model=%s)", len(template), model_name)
                    return template, model_name or self._DEFAULT_REMINDER_MODEL
            return str(prompt), model_name or self._DEFAULT_REMINDER_MODEL
        except Exception as e:
            logger.error(f"Failed to load reminder prompt: {e}")
            return fallback_template, self._DEFAULT_REMINDER_MODEL

