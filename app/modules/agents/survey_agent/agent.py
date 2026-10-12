"""Survey agent with LLM integration."""

import logging
from typing import List, Optional

from app.modules.agents.base import BaseAgent
from app.modules.conversations.schemas import IncomingMessage, AgentResponse
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant, AssistantStep
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from app.modules.agents.survey_agent.commands import CommandHandler
from app.modules.agents.survey_agent.chain import SurveyChain
from app.modules.agents.survey_agent.prompts import PromptLoader
from app.modules.agents.survey_agent.state import SurveyAgentState
from app.modules.agents.survey_agent.config import (
    SurveyStepKey,
    get_questionnaire_config,
    validate_questionnaire_config
)
from app.modules.conversations.service import ConversationsService
from app.modules.assistants.service import AssistantService
from app.config import config

_FOLLOW_UP_EXCLUDED_STATES = [
    SurveyAgentState.COMPLETED.value,
    SurveyAgentState.CLOSING.value,
]

logger = logging.getLogger(__name__)


class SurveyAgent(BaseAgent):
    """
    Survey agent with LLM integration.
    
    Handles multi-step survey conversations with LangChain.
    All agent-specific logic (metadata init, history saving) is here.
    """
    
    def __init__(self):
        """Initialize survey agent."""
        self.chain = SurveyChain()
        self._conversations_service = ConversationsService()
        self._assistant_service = AssistantService()
    
    async def _get_next_step(
        self, 
        assistant_id: str, 
        current_order_no: int
    ) -> Optional[AssistantStep]:
        """Get the next step by order_no (current + 1)."""
        return await self._assistant_service.get_step_by_order(
            assistant_id, 
            current_order_no + 1
        )
    
    async def _initialize_agent_metadata(
        self,
        conversation: Conversation,
        assistant: Assistant,
        interlocutor: Interlocutor
    ) -> Conversation:
        """
        Initialize agent_metadata if empty (first message).
        
        Finds the first enabled step and sets it as initial state.
        If LANG step is disabled, saves the default_language from step metadata.
        
        Returns updated conversation.
        """
        # Check if already initialized with valid state
        agent_metadata = conversation.get_agent_metadata()
        if agent_metadata:
            current_state = agent_metadata.get("state")
            # Validate state is a known SurveyAgentState value
            valid_states = [s.value for s in SurveyAgentState]
            if current_state in valid_states:
                return conversation  # Already initialized with valid state
        
        # Get all steps (ordered by order_no)
        all_steps = await self._assistant_service.get_steps_internal(assistant.id)
        
        # Find first enabled step from all_steps
        first_enabled = next((s for s in all_steps if s.enabled), None)
        if not first_enabled:
            logger.error(f"No enabled steps found for assistant {assistant.id}")
            # Fallback to INTRO (mandatory step)
            initial_state = SurveyAgentState.INTRO.value
        else:
            initial_state = first_enabled.step_key
        
        # Initialize with first enabled step
        initial_metadata = {
            "state": initial_state
        }
        
        # Check if LANG step is disabled - if so, save default_language
        for step in all_steps:
            if step.step_key == SurveyStepKey.LANG.value and not step.enabled:
                # LANG step is disabled - get default_language from its metadata
                default_language = (step.metadata or {}).get("default_language")
                if default_language:
                    initial_metadata["language"] = default_language
                    logger.info(f"LANG step disabled, using default_language: {default_language}")
                else:
                    logger.warning(
                        f"LANG step disabled but no default_language set for assistant {assistant.id}"
                    )
                break
        
        await self._conversations_service.update_agent_metadata(
            conversation.id,
            initial_metadata
        )
        
        logger.info(f"Initialized agent_metadata: state={initial_state}")
        
        # Reload conversation with updated state
        return await self._conversations_service.get_conversation(conversation.id)
    
    async def _save_user_message(
        self,
        conversation: Conversation,
        message: IncomingMessage,
        interlocutor: Interlocutor,
        state: str
    ) -> None:
        """Save user message to history.
        
        Includes audio metadata for voice/audio messages.
        """
        if not message.text:  # Skip empty messages (from recursion)
            return
        
        await self._conversations_service.save_message(
            conversation_id=conversation.id,
            assistant_id=message.assistant_id,
            interlocutor_id=interlocutor.id,
            role="user",
            content=message.text,
            state=state,
            message_type=message.message_type,
            audio_duration_seconds=message.audio_duration_seconds
        )
        logger.debug(
            f"Saved user message to history: state={state}, "
            f"message_type={message.message_type}"
        )
    
    async def _save_assistant_message(
        self,
        conversation: Conversation,
        assistant_id: str,
        interlocutor_id: str,
        content: str,
        state: str
    ) -> None:
        """Save assistant message to history."""
        if not content:  # Skip empty responses
            return
        
        await self._conversations_service.save_message(
            conversation_id=conversation.id,
            assistant_id=assistant_id,
            interlocutor_id=interlocutor_id,
            role="assistant",
            content=content,
            state=state
        )
        logger.debug(f"Saved assistant message to history: state={state}")
    
    async def _save_tool_result(
        self,
        conversation: Conversation,
        assistant_id: str,
        interlocutor_id: str,
        tool_name: str,
        result: str,
        state: str
    ) -> None:
        """Save tool execution result to history as system message."""
        await self._conversations_service.save_message(
            conversation_id=conversation.id,
            assistant_id=assistant_id,
            interlocutor_id=interlocutor_id,
            role="system",
            content=f"[Tool: {tool_name}] {result}",
            state=state
        )
        logger.debug(f"Saved tool result to history: tool={tool_name}, state={state}")
    
    async def _validate_step_config(self, step: AssistantStep) -> None:
        """Validate step-specific configuration.
        
        Raises ValueError if configuration is invalid.
        """
        if step.step_key == SurveyStepKey.QUESTIONNAIRE.value:
            config = get_questionnaire_config(step.metadata)
            validate_questionnaire_config(config)
    
    async def process_message(
        self,
        message: IncomingMessage,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant
    ) -> AgentResponse:
        """
        Process message with LLM.
        
        Flow:
        1. Initialize agent_metadata if needed
        2. Check for commands (/reset, /error)
        3. Save user message to history
        4. Determine current step (skip disabled steps)
        5. Get conversation history for step
        6. Invoke LLM chain
        7. Save assistant response to history
        8. Check if step changed, recursively process if needed
        9. Return response
        """
        try:
            # 1. Check for commands (only /reset and /error, not /start)
            if message.text and message.text.startswith("/") and message.text.lower() not in ["/start"]:
                command_handler = CommandHandler()
                response_text = await command_handler.handle_command(
                    message.text,
                    conversation.id
                )
                if response_text:  # Only return if command was handled
                    return AgentResponse(response_text=response_text)
            
            # 2. Initialize agent_metadata if needed (first message)
            conversation = await self._initialize_agent_metadata(
                conversation, assistant, interlocutor
            )
            
            # 3. Check if conversation is completed
            agent_metadata = conversation.get_agent_metadata()
            current_state = agent_metadata.get("state")
            
            logger.info(f"Processing message: state={current_state}")
            
            if current_state == SurveyAgentState.COMPLETED.value:
                # Return saved final message without calling LLM
                final_message = agent_metadata.get("final_message", "")
                logger.info(f"Conversation completed, returning saved final message")
                return AgentResponse(response_text=final_message)
            
            # 4. Get current step
            current_step = await self._assistant_service.get_current_step(
                assistant.id,
                current_state
            )
            
            if not current_step:
                logger.error(f"No step found for state '{current_state}' in assistant {assistant.id}")
                return AgentResponse(
                    response_text="Configuration error. Please contact support."
                )
            
            # 5. Check if current step is disabled - skip to next step
            if not current_step.enabled:
                logger.info(f"Step '{current_step.step_key}' is disabled, finding next step")
                next_step = await self._get_next_step(assistant.id, current_step.order_no)
                
                if not next_step:
                    # No more enabled steps - mark as completed
                    final_msg = "Thank you for completing the survey!"
                    await self._conversations_service.update_agent_metadata(
                        conversation.id,
                        {
                            "state": SurveyAgentState.COMPLETED.value,
                            "final_message": final_msg
                        }
                    )
                    return AgentResponse(response_text=final_msg)
                
                # Update state to next enabled step and recursively process
                await self._conversations_service.update_agent_metadata(
                    conversation.id,
                    {"state": next_step.step_key}
                )
                conversation = await self._conversations_service.get_conversation(conversation.id)
                return await self.process_message(message, conversation, interlocutor, assistant)
            
            logger.info(f"Processing step: {current_step.step_key} (order {current_step.order_no})")
            
            # 5.5. Initialize questionnaire_progress if entering questionnaire with questions_list
            if current_step.step_key == SurveyStepKey.QUESTIONNAIRE.value:
                questions_list = (current_step.metadata or {}).get("questions_list")
                if questions_list:
                    agent_metadata = conversation.get_agent_metadata()
                    if "questionnaire_progress" not in agent_metadata:
                        await self._conversations_service.update_agent_metadata(
                            conversation.id,
                            {"questionnaire_progress": {"current_index": 0, "answers": []}}
                        )
                        conversation = await self._conversations_service.get_conversation(
                            conversation.id
                        )
                        logger.info(
                            f"Initialized questionnaire_progress: "
                            f"{len(questions_list)} questions"
                        )
            
            # 6. Validate step configuration
            try:
                await self._validate_step_config(current_step)
            except ValueError as e:
                logger.error(f"Invalid step configuration: {e}")
                return AgentResponse(
                    response_text="Configuration error. Please contact support."
                )
            
            # 7. Get conversation history BEFORE saving user message
            # This prevents the current message from appearing twice in the prompt
            # (once in history and once as user_input)
            history = await self._conversations_service.get_history(
                conversation.id,
                state=current_step.step_key
            )
            
            # 8. Save user message to history (after fetching history, before LLM call)
            await self._save_user_message(
                conversation, message, interlocutor, current_step.step_key
            )
            
            # 9. Invoke LLM chain
            llm_response, tool_results = await self.chain.invoke(
                message=message,
                conversation=conversation,
                interlocutor=interlocutor,
                assistant=assistant,
                current_step=current_step,
                history=history
            )
            
            # 11. Save tool results to history
            for tool_name, result in tool_results:
                await self._save_tool_result(
                    conversation,
                    message.assistant_id,
                    interlocutor.id,
                    tool_name,
                    result,
                    current_step.step_key
                )
            
            # 12. Check if step changed (after function calls)
            # Reload conversation from DB to get updated state
            conversation = await self._conversations_service.get_conversation(conversation.id)
            agent_metadata = conversation.get_agent_metadata()
            new_step_key = agent_metadata.get("state")
            
            logger.debug(
                f"After LLM: current_step={current_step.step_key}, "
                f"new_step_key={new_step_key}, "
                f"llm_response_length={len(llm_response)}"
            )
            
            # 13. Save assistant response to history (with CURRENT step, not new)
            await self._save_assistant_message(
                conversation,
                message.assistant_id,
                interlocutor.id,
                llm_response,
                current_step.step_key
            )
            
            # 14. If step changed and not completed, recursively process new step
            if new_step_key and new_step_key != current_step.step_key and new_step_key != SurveyAgentState.COMPLETED.value:
                logger.info(
                    f"Step transition detected: "
                    f"{current_step.step_key} → {new_step_key}"
                )
                
                # Recursively call for new step with empty input
                return await self.process_message(
                    message=IncomingMessage(
                        assistant_id=message.assistant_id,
                        connection_id=message.connection_id,
                        user_id=message.user_id,
                        type=message.type,
                        text="",  # Empty input for new step
                        message_id=None
                    ),
                    conversation=conversation,  # Use updated conversation instance
                    interlocutor=interlocutor,
                    assistant=assistant
                )
            
            # 15. Return response
            return AgentResponse(response_text=llm_response)
        
        except Exception as e:
            logger.error(f"SurveyAgent error: {e}", exc_info=True)
            raise  # Let service handle the error

    async def list_follow_up_candidate_conversation_ids(
        self,
        assistant_id: str,
    ) -> List[str]:
        """Conversations not completed/closing and not mock — no LLM call."""
        return await self._conversations_service.find_follow_up_candidates(
            assistant_id,
            extra_filter={"state.agent_metadata.state": {"$nin": _FOLLOW_UP_EXCLUDED_STATES}},
        )

    async def generate_reminder(
        self,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant,
    ) -> Optional[str]:
        """Generate follow-up reminder via LangSmith prompt + LLM."""
        agent_metadata = conversation.get_agent_metadata()
        state = agent_metadata.get("state")
        if state in (SurveyAgentState.COMPLETED.value, SurveyAgentState.CLOSING.value):
            return None

        prompt_loader = PromptLoader()
        template, model_name = await prompt_loader.load_reminder_prompt()
        language = self.resolve_language(conversation, interlocutor)

        history = await self._conversations_service.get_history(
            str(conversation.id), limit=10
        )
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in history if m.get("content")
        ) or "(no messages yet)"

        prompt_vars = {
            "name": interlocutor.first_name or "",
            "language": language,
            "current_step": state or "unknown",
            "assistant_name": assistant.name or "",
            "conversation_history": history_text,
        }
        formatted = self.format_prompt(template, prompt_vars)

        llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            model=model_name,
            temperature=0.6,
            max_tokens=256,
        )
        result = await llm.ainvoke([SystemMessage(content=formatted)])
        text = (result.content or "").strip()
        if not text:
            return None
        logger.info("Generated follow-up reminder for conversation=%s (%d chars)", conversation.id, len(text))
        return text
