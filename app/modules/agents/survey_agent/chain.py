"""LangChain chain for survey agent."""

import logging
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.modules.conversations.schemas import IncomingMessage
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.assistants.models import Assistant, AssistantStep
from app.modules.conversations.models import ConversationMessage
from app.modules.agents.survey_agent.prompts import PromptLoader
from app.modules.agents.survey_agent.tools import get_survey_tools
from app.modules.agents.base import BaseAgent
from app.config import config

logger = logging.getLogger(__name__)


class SurveyChain:
    """LangChain chain for survey conversations."""
    
    def __init__(self):
        """Initialize chain with LLM."""
        # gpt-4.1: better instruction following, 1M context, improved function calling
        self.llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            model="gpt-4.1",
            temperature=0.3,
            max_tokens=1024
        )
        
        logger.info("SurveyChain initialized with gpt-4.1")
    
    async def invoke(
        self,
        message: IncomingMessage,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant,
        current_step: AssistantStep,
        history: List[ConversationMessage]
    ) -> tuple[str, list[tuple[str, str]]]:
        """
        Invoke LLM chain for current step.
        
        Args:
            message: Incoming message
            conversation: Current conversation
            interlocutor: User info
            assistant: Assistant config (contains assistant_settings in metadata)
            current_step: Current step config (contains step_metadata)
            history: Conversation history
            
        Returns:
            Tuple of (response_text, list of (tool_name, result) pairs)
        """
        try:
            logger.info(
                f"SurveyChain: processing step={current_step.step_key}, "
                f"history_length={len(history)}"
            )
            
            # Get tools for current step (pass step_metadata for questionnaire tool selection)
            self.tools = get_survey_tools(
                current_step.step_key,
                step_metadata=current_step.metadata
            )
            logger.debug(f"Tools for step '{current_step.step_key}': {[t.name for t in self.tools]}")
            
            # Bind tools to LLM
            self.llm_with_tools = self.llm.bind_tools(self.tools)
            
            # Load prompts from LangSmith
            prompt_loader = PromptLoader()
            system_prompt = await prompt_loader.load_system_prompt()
            step_system_prompt = await prompt_loader.load_step_system_prompt(
                current_step.step_key
            )
            
            # Build messages
            messages = self._build_messages(
                system_prompt=system_prompt,
                step_system_prompt=step_system_prompt,
                history=history,
                user_input=message.text or "",
                interlocutor=interlocutor,
                conversation_metadata=conversation.get_agent_metadata(),
                assistant_settings=assistant.metadata or {},
                step_metadata=current_step.metadata or {}
            )
            
            logger.debug(f"Built {len(messages)} messages for LLM (step={current_step.step_key})")
            
            # Invoke LLM
            result = await self.llm_with_tools.ainvoke(messages)
            
            logger.info(f"LLM response: tool_calls={bool(result.tool_calls)}, content_length={len(result.content or '')}")
            
            # Handle function calls
            tool_results = []
            if result.tool_calls:
                logger.info(f"Tool calls: {[(tc.get('name'), tc.get('args')) for tc in result.tool_calls]}")
                final_tool_result, tool_results = await self._handle_tool_calls(
                    result.tool_calls,
                    conversation,
                    interlocutor
                )
                # Prefer LLM's text content if available
                llm_content = (result.content or "").strip()
                if llm_content:
                    response_text = llm_content
                elif final_tool_result:
                    response_text = final_tool_result.strip()
                else:
                    response_text = ""
                
                # If save_questionnaire_answer was called and no text was generated,
                # make a second LLM call WITHOUT tools to ask the next question
                questionnaire_saved = any(
                    name == "save_questionnaire_answer" for name, _ in tool_results
                )
                if questionnaire_saved and not response_text:
                    response_text = await self._ask_next_question(
                        conversation, interlocutor, assistant, current_step, history
                    )
            else:
                logger.warning(f"No tool calls! LLM returned text instead: {result.content[:200]}")
                response_text = (result.content or "").strip()
            
            logger.info(f"Returning response: {len(response_text)} chars")
            
            return response_text, tool_results
        
        except Exception as e:
            logger.error(f"SurveyChain error: {e}", exc_info=True)
            raise
    
    async def _ask_next_question(
        self,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant,
        current_step: AssistantStep,
        history: List
    ) -> str:
        """Make a second LLM call without tools to ask the next question.
        
        Called after save_questionnaire_answer when the LLM didn't produce
        text content alongside the tool call. Uses LLM without bind_tools
        so it can only generate text.
        """
        # Reload conversation to get updated questionnaire_progress
        from app.modules.conversations.service import ConversationsService
        conv_service = ConversationsService()
        conversation = await conv_service.get_conversation(str(conversation.id))
        
        updated_metadata = conversation.get_agent_metadata()
        language = BaseAgent.resolve_language(conversation, interlocutor)
        
        progress = updated_metadata.get("questionnaire_progress", {})
        current_index = progress.get("current_index", 0)
        questions_list = (current_step.metadata or {}).get("questions_list", [])
        
        if current_index >= len(questions_list):
            return ""
        
        next_question = questions_list[current_index]
        
        # Build a simple prompt asking LLM to present the next question
        ask_msg = SystemMessage(content=(
            f"Ask the following survey question naturally, translated to {language}. "
            f"Just ask the question, nothing else. "
            f"Do NOT translate words wrapped in backticks — keep them in the original language and display WITHOUT backticks.\n\n"
            f"Question: \"{next_question}\""
        ))
        
        logger.info(f"Asking next question ({current_index + 1}/{len(questions_list)}) via second LLM call")
        
        # Call LLM WITHOUT tools — can only generate text
        result = await self.llm.ainvoke([ask_msg])
        response = (result.content or "").strip()
        
        logger.info(f"Next question generated: {len(response)} chars")
        return response
    
    def _get_questionnaire_progress_message(
        self,
        conversation_metadata: dict,
        step_metadata: dict,
        language: str
    ) -> Optional[str]:
        """Build questionnaire progress tracking message for the LLM.
        
        Reads current_index from questionnaire_progress in agent_metadata
        and tells the LLM which question is current and how to handle answers.
        
        Returns None if not applicable (no questions_list or not in questionnaire).
        """
        questions_list = step_metadata.get("questions_list")
        if not questions_list:
            return None
        
        progress = conversation_metadata.get("questionnaire_progress", {})
        current_index = progress.get("current_index", 0)
        total = len(questions_list)
        
        if current_index >= total:
            return None
        
        current_question = questions_list[current_index]
        intro_prompt = step_metadata.get("intro_prompt", "")
        
        # First question: include intro_prompt instruction
        intro_instruction = ""
        if current_index == 0 and intro_prompt:
            intro_instruction = (
                f"\nIMPORTANT: This is the FIRST question. Before asking it, "
                f"present the following introduction to the user:\n"
                f"\"{intro_prompt}\"\n"
                f"Then ask the first question.\n"
            )
        
        return (
            f"## Current Question ({current_index + 1} of {total})\n"
            f"\"{current_question}\"\n"
            f"{intro_instruction}\n"
            f"RULES:\n"
            f"- If the user answered the question → call save_questionnaire_answer(answer=\"their answer\") "
            f"AND include the next question in your text response\n"
            f"- If the user replied with option numbers (e.g. \"1 2 3\"), convert them to the FULL TEXT of the selected options before saving\n"
            f"- If the user asked a clarifying question or needs more context → just answer naturally, do NOT call the tool\n"
            f"- Do NOT move to the next question until the current one is answered\n"
            f"- Respond in {language}\n"
            f"- Do NOT translate words wrapped in backticks (`...`). These are UI/technical terms — keep them in the original language and display WITHOUT backticks"
        )
    
    def _build_messages(
        self,
        system_prompt: str,
        step_system_prompt: str,
        history: List,
        user_input: str,
        interlocutor: Interlocutor,
        conversation_metadata: dict,
        assistant_settings: dict,
        step_metadata: dict
    ) -> List:
        """Build messages for LLM.
        
        Prompt composition:
        1. System prompt (from LangSmith) - general instructions
        2. Step system prompt (from LangSmith) - step-specific instructions
        3. Questionnaire progress tracking (if applicable)
        4. Chat history (as structured messages)
        5. Current user input
        """
        messages = []
        
        language = conversation_metadata.get("language") or interlocutor.language or "English"
        
        # Build prompt_vars from all sources using spread
        # NOTE: chat_history is NOT included as text in system prompts to avoid duplication.
        # History is passed as structured HumanMessage/AIMessage below instead.
        prompt_vars = {
            # From interlocutor
            "name": interlocutor.first_name or "",
            "language": language,
            # From conversation_metadata
            "profile_summary": conversation_metadata.get("profile_summary", ""),
            "survey_summary": str(conversation_metadata.get("survey_summary", [])),
            # Chat context — history is provided as separate messages, not inline text
            "chat_history": "(provided as conversation messages)",
            "input": user_input,
            # Spread assistant_settings and step_metadata
            **assistant_settings,
            **step_metadata,
        }
        
        # 1. System prompt (general) - substitute variables
        formatted_system = self._format_prompt(system_prompt, prompt_vars)
        messages.append(SystemMessage(content=formatted_system))
        
        # 2. Step system prompt (step-specific) - substitute variables
        formatted_step = self._format_prompt(step_system_prompt, prompt_vars)
        messages.append(SystemMessage(content=formatted_step))
        
        # 3. Questionnaire progress tracking (if questions_list is used)
        progress_msg = self._get_questionnaire_progress_message(
            conversation_metadata, step_metadata, language
        )
        if progress_msg:
            messages.append(SystemMessage(content=progress_msg))
            logger.info(f"Questionnaire progress injected: {progress_msg[:120]}...")
        
        # 4. Chat history (as structured messages)
        for msg in history:
            if msg['role'] == "user":
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == "assistant":
                messages.append(AIMessage(content=msg['content']))
        
        # 5. Current user input (only if not empty)
        if user_input:
            messages.append(HumanMessage(content=user_input))
        
        return messages
    
    def _format_prompt(self, prompt: str, vars: dict) -> str:
        """Format prompt template with variables.
        
        Tries format_map first, falls back to manual replacement.
        """
        try:
            return prompt.format_map(vars)
        except (KeyError, IndexError) as e:
            logger.debug(f"Prompt formatting fallback: {e}")
            # Fallback: manual replacement
            result = prompt
            for key, value in vars.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result
    
    async def _handle_tool_calls(
        self,
        tool_calls: list,
        conversation: Conversation,
        interlocutor: Interlocutor
    ) -> tuple[str, list[tuple[str, str]]]:
        """
        Execute tool calls from LLM.
        
        Returns:
            Tuple of (final_result, list of (tool_name, result) pairs)
        """
        tool_results = []
        final_result = ""
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            logger.info(f"Executing tool: {tool_name}")
            
            # Find and execute tool
            for tool in self.tools:
                if tool.name == tool_name:
                    # Inject conversation_id (all tools need it)
                    tool.conversation_id = str(conversation.id)
                    
                    # Inject assistant_id for tools that need step/next_step lookup
                    if tool_name == "save_questionnaire_answer":
                        tool.assistant_id = str(conversation.assistant_id)
                    
                    # Some tools need interlocutor_id
                    if tool_name in ["save_email", "update_language", "save_profile", "save_name_and_transition", "save_additional_info"]:
                        tool.interlocutor_id = str(interlocutor.id)
                    
                    result = await tool._arun(**tool_args)
                    logger.info(f"Tool result: {result}")
                    
                    # Always record that tool was called (even with empty result)
                    tool_results.append((tool_name, result or ""))
                    if result:
                        final_result = result  # Last non-empty result becomes response
                    break
        
        return final_result, tool_results
