"""Service layer for managing assistant steps."""

import json
from typing import List, Optional, Dict, Any
import logging
from bson import ObjectId

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.modules.assistants.models import AssistantStep
from app.modules.assistants.repository import AssistantRepository
from app.modules.assistants.steps.repository import StepRepository
from .schemas import UpdateStepRequest
from app.config import config

logger = logging.getLogger(__name__)


class StepService:
    """Service for managing assistant steps."""
    
    def __init__(self):
        """Initialize service with repositories."""
        self._step_repo = StepRepository()
        self._assistant_repo = AssistantRepository()
    
    async def get_assistant_steps(
        self, 
        assistant_id: str, 
        user_id: str
    ) -> List[AssistantStep]:
        """
        Get all steps for an assistant.
        
        Business rules:
        - Must verify assistant belongs to user
        - Returns steps ordered by order_no
        """
        # Verify assistant ownership
        assistant = await self._assistant_repo.get_by_id(assistant_id, user_id)
        if not assistant:
            raise ValueError(f"Assistant {assistant_id} not found")
        
        return await self._step_repo.get_by_assistant(assistant_id)
    
    async def get_step(
        self, 
        assistant_id: str,
        step_id: str,
        user_id: str
    ) -> Optional[AssistantStep]:
        """
        Get a specific step.
        
        Business rules:
        - Must verify assistant belongs to user
        """
        # Verify assistant ownership
        assistant = await self._assistant_repo.get_by_id(assistant_id, user_id)
        if not assistant:
            raise ValueError(f"Assistant {assistant_id} not found")
        
        return await self._step_repo.get_by_id(step_id, assistant_id)
    
    async def update_step(
        self,
        assistant_id: str,
        step_id: str,
        user_id: str,
        data: UpdateStepRequest
    ) -> Optional[AssistantStep]:
        """
        Update a step.
        
        Business rules:
        - Must verify assistant belongs to user
        - Mandatory steps cannot be disabled (validated by agent service)
        - Metadata validated by agent service
        - Can update enabled and metadata
        """
        # Verify assistant ownership
        assistant = await self._assistant_repo.get_by_id(assistant_id, user_id)
        if not assistant:
            raise ValueError(f"Assistant {assistant_id} not found")
        
        # Verify step exists
        existing_step = await self._step_repo.get_by_id(step_id, assistant_id)
        if not existing_step:
            raise ValueError(f"Step {step_id} not found")
        
        # Get agent service to process update (validates and returns what to save)
        from app.modules.agents.survey_agent.service import SurveyAgentService
        agent_service = SurveyAgentService()
        
        # Agent service processes the update: validates and returns final update_doc
        # Raises ValueError if validation fails
        update_doc = agent_service.process_step_update(
            existing_step=existing_step,
            new_enabled=data.enabled,
            new_metadata=data.metadata
        )
        
        if not update_doc:
            return existing_step
        
        updated = await self._step_repo.update(step_id, assistant_id, update_doc)
        
        return updated if updated else existing_step
    
    async def parse_questions_from_text(self, text: str) -> List[str]:
        """Parse free-form text into a list of individual questions using LLM.
        
        Args:
            text: Free-form text containing questions
            
        Returns:
            List of individual question strings
            
        Raises:
            ValueError: If parsing fails or no questions found
        """
        llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            model="gpt-4.1-mini",
            temperature=0,
            max_tokens=4096
        )
        
        messages = [
            SystemMessage(content=(
                "Extract individual questions from the user's text. "
                "Return ONLY a valid JSON array of strings, each string being one complete question. "
                "Preserve the original language of the questions. "
                "Remove top-level numbering (1., 2., etc.) but KEEP answer options/variants as part of the question text. "
                "For example, if a question has options like '1. Yes 2. No 3. Maybe', include them in the string.\n\n"
                "Example input: '1. How often do you exercise?\\n   - 1. Daily\\n   - 2. Weekly\\n   - 3. Never'\n"
                "Example output: [\"How often do you exercise?\\n- Daily\\n- Weekly\\n- Never\"]"
            )),
            HumanMessage(content=text)
        ]
        
        try:
            result = await llm.ainvoke(messages)
            content = result.content.strip()
            
            # Strip markdown code block if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3].strip()
            
            questions = json.loads(content)
            
            if not isinstance(questions, list) or len(questions) == 0:
                raise ValueError("LLM returned empty or invalid questions list")
            
            # Ensure all items are strings and non-empty
            questions = [q.strip() for q in questions if isinstance(q, str) and q.strip()]
            
            if not questions:
                raise ValueError("No valid questions found in the text")
            
            logger.info(f"Parsed {len(questions)} questions from text ({len(text)} chars)")
            return questions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise ValueError(f"Failed to parse questions: invalid LLM response")
        except Exception as e:
            logger.error(f"Failed to parse questions: {e}")
            raise
    
    async def create_default_steps(self, assistant_id: str):
        """
        Create default steps for a new Survey assistant.
        
        Gets default step definitions from the agent service.
        """
        # Get default steps from agent service
        from app.modules.agents.survey_agent.service import SurveyAgentService
        agent_service = SurveyAgentService()
        
        default_steps = agent_service.get_default_steps()
        
        # Add assistant_id to each step
        for step in default_steps:
            step["assistant_id"] = ObjectId(assistant_id)
        
        # Insert all steps via repository
        inserted_ids = await self._step_repo.create_many(default_steps)
        
        logger.info(f"Created {len(inserted_ids)} default steps for assistant={assistant_id}")
        
        return inserted_ids
