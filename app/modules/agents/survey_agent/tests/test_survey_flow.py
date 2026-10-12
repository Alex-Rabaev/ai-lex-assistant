"""Integration tests for Survey Agent flow.

Tests the complete survey flow from LANG to COMPLETED,
mocking LLM responses and external services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from app.modules.agents.survey_agent.agent import SurveyAgent

from .conftest import (
    create_conversation,
    create_step,
    create_incoming_message,
    llm_response_lang,
    llm_response_intro,
    llm_response_profile,
    llm_response_questionnaire,
    llm_response_additional_info,
    llm_response_closing,
    llm_response_text_only,
    ConversationStateTracker,
)


class TestFullSurveyFlow:
    """Test complete survey flow from start to finish."""
    
    @pytest.fixture
    def state_tracker(self):
        """Track conversation state across the flow."""
        return ConversationStateTracker()
    
    @pytest.fixture
    def mock_steps(self, assistant_id: str):
        """All steps enabled."""
        return [
            create_step(assistant_id, "lang", 1, True, {"default_language": "English"}),
            create_step(assistant_id, "intro", 2, True),
            create_step(assistant_id, "profile", 3, True),
            create_step(assistant_id, "questionnaire", 4, True, {
                "intro_prompt": "Let me ask some questions",
                "specific_questions": "What is your budget?"
            }),
            create_step(assistant_id, "additional_info", 5, True, {"info_to_collect": "email"}),
            create_step(assistant_id, "closing", 6, True),
        ]
    
    def _get_step_by_key(self, steps: List, step_key: str):
        """Find step by key."""
        for step in steps:
            if step.step_key == step_key:
                return step
        return None
    
    def _get_step_by_order(self, steps: List, order_no: int):
        """Find step by order."""
        for step in steps:
            if step.order_no == order_no:
                return step
        return None
    
    @pytest.mark.asyncio
    async def test_full_survey_flow_all_steps(
        self,
        assistant_id: str,
        connection_id: str,
        conversation_id: str,
        interlocutor_id: str,
        user_id: str,
        mock_assistant,
        mock_interlocutor,
        mock_steps,
        state_tracker
    ):
        """
        Test complete flow: LANG → INTRO → PROFILE → QUESTIONNAIRE → ADDITIONAL_INFO → CLOSING → COMPLETED.
        
        This test simulates a user going through the entire survey flow.
        Each step:
        1. Receives user message
        2. LLM processes and calls appropriate tool
        3. Tool updates state and transitions to next step
        4. Agent recursively processes new step (with empty input)
        """
        # Track all LLM calls to return appropriate responses
        llm_call_count = 0
        llm_responses = [
            # Step 1: LANG - user sends /start, LLM greets and asks language
            llm_response_text_only("Hello! What language do you prefer? English or Русский?"),
            # Step 2: LANG - user says "English", LLM calls update_language
            llm_response_lang("English"),
            # Step 3: INTRO - automatic after lang, LLM greets in English
            llm_response_text_only("Great! I'm your survey assistant. What's your name?"),
            # Step 4: INTRO - user says name, LLM calls save_name
            llm_response_intro("Alex", "profile"),
            # Step 5: PROFILE - automatic after intro, LLM asks about business
            llm_response_text_only("Nice to meet you, Alex! Tell me about your business."),
            # Step 6: PROFILE - user describes business, LLM calls save_profile
            llm_response_profile("Software developer at startup", "questionnaire"),
            # Step 7: QUESTIONNAIRE - automatic, LLM asks first question
            llm_response_text_only("Thanks! Let me ask you a few questions. What is your budget?"),
            # Step 8: QUESTIONNAIRE - user answers, LLM saves and transitions
            llm_response_questionnaire(
                [{"question": "What is your budget?", "answer": "$5000"}],
                "additional_info"
            ),
            # Step 9: ADDITIONAL_INFO - automatic, LLM asks for email
            llm_response_text_only("Almost done! Could you share your email?"),
            # Step 10: ADDITIONAL_INFO - user provides email, LLM saves
            llm_response_additional_info("email", "alex@startup.com", "closing"),
            # Step 11: CLOSING - automatic, LLM generates final message
            llm_response_closing("Thank you Alex! Based on your budget of $5000, we'll be in touch at alex@startup.com.")
        ]
        
        async def mock_llm_invoke(messages):
            nonlocal llm_call_count
            response = llm_responses[llm_call_count] if llm_call_count < len(llm_responses) else llm_responses[-1]
            llm_call_count += 1
            return response
        
        # Create conversation factory that returns updated state
        def create_updated_conversation():
            return create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id,
                state=state_tracker.get_state(),
                agent_metadata=state_tracker.get_metadata()
            )
        
        # Mock services
        mock_conv_service = MagicMock()
        mock_conv_service.update_agent_metadata = AsyncMock(side_effect=lambda cid, meta: state_tracker.update(meta))
        mock_conv_service.save_message = AsyncMock()
        mock_conv_service.get_history = AsyncMock(return_value=[])
        mock_conv_service.get_conversation = AsyncMock(side_effect=lambda cid: create_updated_conversation())
        mock_conv_service.update_interlocutor_language = AsyncMock()
        mock_conv_service.update_interlocutor_name = AsyncMock()
        mock_conv_service.update_interlocutor_profile = AsyncMock()
        mock_conv_service.update_interlocutor_email = AsyncMock()
        
        mock_asst_service = MagicMock()
        mock_asst_service.get_steps_internal = AsyncMock(return_value=mock_steps)
        mock_asst_service.get_step_by_order = AsyncMock(
            side_effect=lambda aid, order: self._get_step_by_order(mock_steps, order)
        )
        mock_asst_service.get_current_step = AsyncMock(
            side_effect=lambda aid, key: self._get_step_by_key(mock_steps, key) if key else mock_steps[0]
        )
        
        mock_prompt_loader = MagicMock()
        mock_prompt_loader.load_system_prompt = AsyncMock(return_value="You are a survey assistant.")
        mock_prompt_loader.load_step_system_prompt = AsyncMock(return_value="Conduct the step.")
        
        # Apply patches
        with patch('app.modules.agents.survey_agent.agent.ConversationsService', return_value=mock_conv_service), \
             patch('app.modules.agents.survey_agent.agent.AssistantService', return_value=mock_asst_service), \
             patch('app.modules.agents.survey_agent.chain.PromptLoader', return_value=mock_prompt_loader), \
             patch.object(SurveyAgent, '__init__', lambda self: None):
            
            # Create agent and set mocked dependencies
            agent = SurveyAgent()
            agent._conversations_service = mock_conv_service
            agent._assistant_service = mock_asst_service
            
            # Mock the chain
            mock_chain = MagicMock()
            mock_chain.invoke = AsyncMock(side_effect=lambda **kwargs: (
                llm_responses[llm_call_count - 1].content if llm_call_count > 0 else "",
                [(tc["name"], f"Result of {tc['name']}") for tc in (llm_responses[llm_call_count - 1].tool_calls if llm_call_count > 0 else [])]
            ))
            agent.chain = mock_chain
            
            # Override chain.invoke to use our mock and execute tools
            async def mock_chain_invoke(**kwargs):
                nonlocal llm_call_count
                response = llm_responses[llm_call_count] if llm_call_count < len(llm_responses) else llm_responses[-1]
                llm_call_count += 1
                
                tool_results = []
                # Execute tools to update state
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc["args"]
                    
                    if tool_name == "update_language":
                        state_tracker.update({"language": tool_args["language"], "state": "intro"})
                        tool_results.append((tool_name, f"Language set to {tool_args['language']}"))
                    elif tool_name == "save_name_and_transition":
                        state_tracker.update({"name": tool_args["name"], "state": tool_args["next_step_key"]})
                        tool_results.append((tool_name, f"Name saved, moving to {tool_args['next_step_key']}"))
                    elif tool_name == "save_profile":
                        state_tracker.update({"profile_summary": tool_args["profile_summary"], "state": tool_args["next_step_key"]})
                        tool_results.append((tool_name, f"Profile saved, moving to {tool_args['next_step_key']}"))
                    elif tool_name == "save_survey_answers":
                        state_tracker.update({"survey_summary": tool_args["survey_data"], "state": tool_args["next_step_key"]})
                        tool_results.append((tool_name, f"Survey saved, moving to {tool_args['next_step_key']}"))
                    elif tool_name == "save_additional_info":
                        current_info = state_tracker.agent_metadata.get("additional_info", {})
                        current_info[tool_args["info_type"]] = tool_args["info_value"]
                        state_tracker.update({"additional_info": current_info, "state": tool_args["next_step_key"]})
                        tool_results.append((tool_name, f"Additional info saved, moving to {tool_args['next_step_key']}"))
                    elif tool_name == "save_final_message":
                        state_tracker.update({"final_message": tool_args["final_message"], "state": "completed"})
                        tool_results.append((tool_name, tool_args["final_message"]))
                
                return response.content, tool_results
            
            agent.chain.invoke = AsyncMock(side_effect=mock_chain_invoke)
            
            # ================================================================
            # STEP 1: /start - First message, initialize and ask for language
            # ================================================================
            initial_conversation = create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id
            )
            message1 = create_incoming_message(assistant_id, connection_id, user_id, "/start")
            
            response1 = await agent.process_message(
                message1, initial_conversation, mock_interlocutor, mock_assistant
            )
            
            # After first message, state should be "lang"
            assert state_tracker.get_state() == "lang", f"Expected 'lang', got {state_tracker.get_state()}"
            assert response1.response_text is not None
            
            # ================================================================
            # STEP 2: User says "English" - transition to INTRO
            # ================================================================
            message2 = create_incoming_message(assistant_id, connection_id, user_id, "English")
            conv2 = create_updated_conversation()
            
            response2 = await agent.process_message(
                message2, conv2, mock_interlocutor, mock_assistant
            )
            
            # After language selection, should be in "intro"
            assert state_tracker.get_state() == "intro", f"Expected 'intro', got {state_tracker.get_state()}"
            assert state_tracker.agent_metadata.get("language") == "English"
            
            # ================================================================
            # STEP 3: User says name - transition to PROFILE
            # ================================================================
            message3 = create_incoming_message(assistant_id, connection_id, user_id, "My name is Alex")
            conv3 = create_updated_conversation()
            
            response3 = await agent.process_message(
                message3, conv3, mock_interlocutor, mock_assistant
            )
            
            assert state_tracker.get_state() == "profile", f"Expected 'profile', got {state_tracker.get_state()}"
            assert state_tracker.agent_metadata.get("name") == "Alex"
            
            # ================================================================
            # STEP 4: User describes business - transition to QUESTIONNAIRE
            # ================================================================
            message4 = create_incoming_message(assistant_id, connection_id, user_id, "I'm a software developer at a startup")
            conv4 = create_updated_conversation()
            
            response4 = await agent.process_message(
                message4, conv4, mock_interlocutor, mock_assistant
            )
            
            assert state_tracker.get_state() == "questionnaire", f"Expected 'questionnaire', got {state_tracker.get_state()}"
            assert "developer" in state_tracker.agent_metadata.get("profile_summary", "").lower()
            
            # ================================================================
            # STEP 5: User answers questions - transition to ADDITIONAL_INFO
            # ================================================================
            message5 = create_incoming_message(assistant_id, connection_id, user_id, "My budget is $5000")
            conv5 = create_updated_conversation()
            
            response5 = await agent.process_message(
                message5, conv5, mock_interlocutor, mock_assistant
            )
            
            assert state_tracker.get_state() == "additional_info", f"Expected 'additional_info', got {state_tracker.get_state()}"
            assert state_tracker.agent_metadata.get("survey_summary") is not None
            
            # ================================================================
            # STEP 6: User provides email - transition to CLOSING then COMPLETED
            # ================================================================
            # Note: After additional_info, the flow is:
            # 1. Tool saves email and transitions to "closing"
            # 2. Agent recursively processes "closing" step
            # 3. Closing step calls save_final_message which transitions to "completed"
            # So after this message, we end up in "completed" state
            message6 = create_incoming_message(assistant_id, connection_id, user_id, "alex@startup.com")
            conv6 = create_updated_conversation()
            
            response6 = await agent.process_message(
                message6, conv6, mock_interlocutor, mock_assistant
            )
            
            # Flow goes through closing and ends at completed
            assert state_tracker.get_state() == "completed", f"Expected 'completed', got {state_tracker.get_state()}"
            assert state_tracker.agent_metadata.get("additional_info", {}).get("email") == "alex@startup.com"
            assert state_tracker.agent_metadata.get("final_message") is not None
            
            # ================================================================
            # VERIFY: Message after completion returns saved final message
            # ================================================================
            message_after = create_incoming_message(assistant_id, connection_id, user_id, "Hello?")
            conv_completed = create_updated_conversation()
            
            response_after = await agent.process_message(
                message_after, conv_completed, mock_interlocutor, mock_assistant
            )
            
            # Should return the saved final message without calling LLM
            assert response_after.response_text == state_tracker.agent_metadata.get("final_message")
    
    @pytest.mark.asyncio
    async def test_survey_flow_with_lang_disabled(
        self,
        assistant_id: str,
        connection_id: str,
        conversation_id: str,
        interlocutor_id: str,
        user_id: str,
        mock_assistant,
        mock_interlocutor
    ):
        """
        Test flow when LANG step is disabled.
        
        Should start directly at INTRO with default_language set.
        """
        state_tracker = ConversationStateTracker()
        
        # Steps with LANG disabled
        mock_steps = [
            create_step(assistant_id, "lang", 1, False, {"default_language": "English"}),
            create_step(assistant_id, "intro", 2, True),
            create_step(assistant_id, "profile", 3, True),
            create_step(assistant_id, "questionnaire", 4, True, {"specific_questions": "Q1?"}),
            create_step(assistant_id, "additional_info", 5, True),
            create_step(assistant_id, "closing", 6, True),
        ]
        
        def get_step_by_key(steps, key):
            return next((s for s in steps if s.step_key == key), None)
        
        def get_step_by_order(steps, order):
            return next((s for s in steps if s.order_no == order), None)
        
        llm_responses = [
            # INTRO - greet user
            llm_response_text_only("Hello! What's your name?"),
        ]
        llm_call_count = 0
        
        async def mock_chain_invoke(**kwargs):
            nonlocal llm_call_count
            response = llm_responses[min(llm_call_count, len(llm_responses) - 1)]
            llm_call_count += 1
            return response.content, []
        
        def create_updated_conversation():
            return create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id,
                state=state_tracker.get_state(),
                agent_metadata=state_tracker.get_metadata()
            )
        
        mock_conv_service = MagicMock()
        mock_conv_service.update_agent_metadata = AsyncMock(side_effect=lambda cid, meta: state_tracker.update(meta))
        mock_conv_service.save_message = AsyncMock()
        mock_conv_service.get_history = AsyncMock(return_value=[])
        mock_conv_service.get_conversation = AsyncMock(side_effect=lambda cid: create_updated_conversation())
        
        mock_asst_service = MagicMock()
        mock_asst_service.get_steps_internal = AsyncMock(return_value=mock_steps)
        mock_asst_service.get_step_by_order = AsyncMock(
            side_effect=lambda aid, order: get_step_by_order(mock_steps, order)
        )
        mock_asst_service.get_current_step = AsyncMock(
            side_effect=lambda aid, key: get_step_by_key(mock_steps, key) if key else mock_steps[0]
        )
        
        with patch('app.modules.agents.survey_agent.agent.ConversationsService', return_value=mock_conv_service), \
             patch('app.modules.agents.survey_agent.agent.AssistantService', return_value=mock_asst_service), \
             patch.object(SurveyAgent, '__init__', lambda self: None):
            
            agent = SurveyAgent()
            agent._conversations_service = mock_conv_service
            agent._assistant_service = mock_asst_service
            
            mock_chain = MagicMock()
            mock_chain.invoke = AsyncMock(side_effect=mock_chain_invoke)
            agent.chain = mock_chain
            
            # First message
            initial_conversation = create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id
            )
            message = create_incoming_message(assistant_id, connection_id, user_id, "/start")
            
            await agent.process_message(
                message, initial_conversation, mock_interlocutor, mock_assistant
            )
            
            # Should have skipped LANG and started at INTRO
            # Also default_language should be set
            assert state_tracker.get_state() == "intro", f"Expected 'intro', got {state_tracker.get_state()}"
            assert state_tracker.agent_metadata.get("language") == "English", \
                f"Expected 'English', got {state_tracker.agent_metadata.get('language')}"
    
    @pytest.mark.asyncio
    async def test_survey_flow_user_declines_email(
        self,
        assistant_id: str,
        connection_id: str,
        conversation_id: str,
        interlocutor_id: str,
        user_id: str,
        mock_assistant,
        mock_interlocutor
    ):
        """
        Test flow when user declines to provide email.
        
        Should still complete successfully with "declined" value.
        """
        state_tracker = ConversationStateTracker()
        state_tracker.update({
            "state": "additional_info",
            "language": "English",
            "name": "Alex",
            "profile_summary": "Developer",
            "survey_summary": [{"question": "Q1?", "answer": "A1"}]
        })
        
        mock_steps = [
            create_step(assistant_id, "lang", 1, True),
            create_step(assistant_id, "intro", 2, True),
            create_step(assistant_id, "profile", 3, True),
            create_step(assistant_id, "questionnaire", 4, True, {"specific_questions": "Q1?"}),
            create_step(assistant_id, "additional_info", 5, True, {"info_to_collect": "email"}),
            create_step(assistant_id, "closing", 6, True),
        ]
        
        def get_step_by_key(steps, key):
            return next((s for s in steps if s.step_key == key), None)
        
        # User declines email
        llm_responses = [
            llm_response_additional_info("email", "declined", "closing"),
            llm_response_closing("Thank you for completing the survey!")
        ]
        llm_call_count = 0
        
        async def mock_chain_invoke(**kwargs):
            nonlocal llm_call_count
            response = llm_responses[min(llm_call_count, len(llm_responses) - 1)]
            llm_call_count += 1
            
            tool_results = []
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                
                if tool_name == "save_additional_info":
                    # Note: "declined" values are NOT added to additional_info
                    if tool_args["info_value"].lower() != "declined":
                        current_info = state_tracker.agent_metadata.get("additional_info", {})
                        current_info[tool_args["info_type"]] = tool_args["info_value"]
                        state_tracker.update({"additional_info": current_info})
                    state_tracker.update({"state": tool_args["next_step_key"]})
                    tool_results.append((tool_name, f"Moving to {tool_args['next_step_key']}"))
                elif tool_name == "save_final_message":
                    state_tracker.update({"final_message": tool_args["final_message"], "state": "completed"})
                    tool_results.append((tool_name, tool_args["final_message"]))
            
            return response.content, tool_results
        
        def create_updated_conversation():
            return create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id,
                state=state_tracker.get_state(),
                agent_metadata=state_tracker.get_metadata()
            )
        
        mock_conv_service = MagicMock()
        mock_conv_service.update_agent_metadata = AsyncMock(side_effect=lambda cid, meta: state_tracker.update(meta))
        mock_conv_service.save_message = AsyncMock()
        mock_conv_service.get_history = AsyncMock(return_value=[])
        mock_conv_service.get_conversation = AsyncMock(side_effect=lambda cid: create_updated_conversation())
        
        mock_asst_service = MagicMock()
        mock_asst_service.get_steps_internal = AsyncMock(return_value=mock_steps)
        mock_asst_service.get_current_step = AsyncMock(
            side_effect=lambda aid, key: get_step_by_key(mock_steps, key) if key else mock_steps[0]
        )
        
        with patch('app.modules.agents.survey_agent.agent.ConversationsService', return_value=mock_conv_service), \
             patch('app.modules.agents.survey_agent.agent.AssistantService', return_value=mock_asst_service), \
             patch.object(SurveyAgent, '__init__', lambda self: None):
            
            agent = SurveyAgent()
            agent._conversations_service = mock_conv_service
            agent._assistant_service = mock_asst_service
            
            mock_chain = MagicMock()
            mock_chain.invoke = AsyncMock(side_effect=mock_chain_invoke)
            agent.chain = mock_chain
            
            # User declines email
            conv = create_updated_conversation()
            message = create_incoming_message(assistant_id, connection_id, user_id, "No, I prefer not to share")
            
            await agent.process_message(
                message, conv, mock_interlocutor, mock_assistant
            )
            
            # Should have moved to closing, then completed
            # Email should NOT be in additional_info
            additional_info = state_tracker.agent_metadata.get("additional_info", {})
            assert "email" not in additional_info, f"Email should not be saved when declined: {additional_info}"
            assert state_tracker.get_state() in ["closing", "completed"]


class TestSurveyFlowResetCommand:
    """Test /reset command during survey flow."""
    
    @pytest.mark.asyncio
    async def test_reset_during_survey(
        self,
        assistant_id: str,
        connection_id: str,
        conversation_id: str,
        interlocutor_id: str,
        user_id: str,
        mock_assistant,
        mock_interlocutor
    ):
        """Test /reset command resets conversation state."""
        state_tracker = ConversationStateTracker()
        state_tracker.update({
            "state": "profile",
            "language": "English",
            "name": "Alex"
        })
        
        mock_conv_service = MagicMock()
        mock_conv_service.reset_conversation = AsyncMock()
        
        # Patch ConversationsService where it's imported (in the service module)
        with patch('app.modules.conversations.service.ConversationsService', return_value=mock_conv_service), \
             patch('app.modules.agents.survey_agent.agent.ConversationsService', return_value=mock_conv_service), \
             patch.object(SurveyAgent, '__init__', lambda self: None):
            
            agent = SurveyAgent()
            agent._conversations_service = mock_conv_service
            agent._assistant_service = MagicMock()
            agent.chain = MagicMock()
            
            conv = create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id,
                state="profile",
                agent_metadata=state_tracker.get_metadata()
            )
            message = create_incoming_message(assistant_id, connection_id, user_id, "/reset")
            
            response = await agent.process_message(
                message, conv, mock_interlocutor, mock_assistant
            )
            
            # Should return reset confirmation
            assert response.response_text is not None
            assert "deleted" in response.response_text.lower()
            
            # Should have called reset_conversation (with ObjectId from conversation)
            mock_conv_service.reset_conversation.assert_called_once()
            call_args = mock_conv_service.reset_conversation.call_args[0][0]
            assert str(call_args) == conversation_id


class TestSurveyFlowCompletedState:
    """Test behavior when survey is already completed."""
    
    @pytest.mark.asyncio
    async def test_message_after_completion_returns_final_message(
        self,
        assistant_id: str,
        connection_id: str,
        conversation_id: str,
        interlocutor_id: str,
        user_id: str,
        mock_assistant,
        mock_interlocutor
    ):
        """
        Test that messages after completion return the saved final_message
        without calling LLM.
        """
        final_message = "Thank you! Your survey is complete."
        
        # Conversation already in COMPLETED state
        conv = create_conversation(
            conversation_id, interlocutor_id, assistant_id, connection_id,
            state="completed",
            agent_metadata={
                "state": "completed",
                "final_message": final_message,
                "language": "English",
                "name": "Alex"
            }
        )
        
        mock_conv_service = MagicMock()
        mock_conv_service.get_conversation = AsyncMock(return_value=conv)
        
        mock_asst_service = MagicMock()
        mock_asst_service.get_steps_internal = AsyncMock(return_value=[])
        
        with patch('app.modules.agents.survey_agent.agent.ConversationsService', return_value=mock_conv_service), \
             patch('app.modules.agents.survey_agent.agent.AssistantService', return_value=mock_asst_service), \
             patch.object(SurveyAgent, '__init__', lambda self: None):
            
            agent = SurveyAgent()
            agent._conversations_service = mock_conv_service
            agent._assistant_service = mock_asst_service
            
            # This should NOT be called
            mock_chain = MagicMock()
            mock_chain.invoke = AsyncMock()
            agent.chain = mock_chain
            
            message = create_incoming_message(assistant_id, connection_id, user_id, "Hello? Are you there?")
            
            response = await agent.process_message(
                message, conv, mock_interlocutor, mock_assistant
            )
            
            # Should return saved final_message
            assert response.response_text == final_message
            
            # LLM should NOT have been called
            mock_chain.invoke.assert_not_called()


class TestSurveyFlowSkippedSteps:
    """Test flows with various steps disabled."""
    
    @pytest.mark.asyncio
    async def test_skip_profile_step(
        self,
        assistant_id: str,
        connection_id: str,
        conversation_id: str,
        interlocutor_id: str,
        user_id: str,
        mock_assistant,
        mock_interlocutor
    ):
        """
        Test flow when PROFILE step is disabled.
        
        Should go directly from INTRO to QUESTIONNAIRE.
        """
        state_tracker = ConversationStateTracker()
        state_tracker.update({
            "state": "intro",
            "language": "English"
        })
        
        # PROFILE disabled
        mock_steps = [
            create_step(assistant_id, "lang", 1, True),
            create_step(assistant_id, "intro", 2, True),
            create_step(assistant_id, "profile", 3, False),  # Disabled!
            create_step(assistant_id, "questionnaire", 4, True, {"specific_questions": "Q1?"}),
            create_step(assistant_id, "additional_info", 5, True),
            create_step(assistant_id, "closing", 6, True),
        ]
        
        def get_step_by_key(steps, key):
            return next((s for s in steps if s.step_key == key), None)
        
        def get_step_by_order(steps, order):
            return next((s for s in steps if s.order_no == order), None)
        
        # LLM saves name and transitions to "profile" (the disabled step)
        llm_responses = [
            llm_response_intro("Alex", "profile"),
            llm_response_text_only("Let me ask you some questions!")  # QUESTIONNAIRE
        ]
        llm_call_count = 0
        
        async def mock_chain_invoke(**kwargs):
            nonlocal llm_call_count
            response = llm_responses[min(llm_call_count, len(llm_responses) - 1)]
            llm_call_count += 1
            
            tool_results = []
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                
                if tool_name == "save_name_and_transition":
                    state_tracker.update({"name": tool_args["name"], "state": tool_args["next_step_key"]})
                    tool_results.append((tool_name, f"Name saved"))
            
            return response.content, tool_results
        
        def create_updated_conversation():
            return create_conversation(
                conversation_id, interlocutor_id, assistant_id, connection_id,
                state=state_tracker.get_state(),
                agent_metadata=state_tracker.get_metadata()
            )
        
        mock_conv_service = MagicMock()
        mock_conv_service.update_agent_metadata = AsyncMock(side_effect=lambda cid, meta: state_tracker.update(meta))
        mock_conv_service.save_message = AsyncMock()
        mock_conv_service.get_history = AsyncMock(return_value=[])
        mock_conv_service.get_conversation = AsyncMock(side_effect=lambda cid: create_updated_conversation())
        mock_conv_service.update_interlocutor_name = AsyncMock()
        
        mock_asst_service = MagicMock()
        mock_asst_service.get_steps_internal = AsyncMock(return_value=mock_steps)
        mock_asst_service.get_step_by_order = AsyncMock(
            side_effect=lambda aid, order: get_step_by_order(mock_steps, order)
        )
        mock_asst_service.get_current_step = AsyncMock(
            side_effect=lambda aid, key: get_step_by_key(mock_steps, key) if key else mock_steps[0]
        )
        
        with patch('app.modules.agents.survey_agent.agent.ConversationsService', return_value=mock_conv_service), \
             patch('app.modules.agents.survey_agent.agent.AssistantService', return_value=mock_asst_service), \
             patch.object(SurveyAgent, '__init__', lambda self: None):
            
            agent = SurveyAgent()
            agent._conversations_service = mock_conv_service
            agent._assistant_service = mock_asst_service
            
            mock_chain = MagicMock()
            mock_chain.invoke = AsyncMock(side_effect=mock_chain_invoke)
            agent.chain = mock_chain
            
            # User provides name at INTRO step
            conv = create_updated_conversation()
            message = create_incoming_message(assistant_id, connection_id, user_id, "My name is Alex")
            
            await agent.process_message(
                message, conv, mock_interlocutor, mock_assistant
            )
            
            # Tool transitioned to "profile", but profile is disabled
            # Agent should auto-skip to "questionnaire"
            assert state_tracker.get_state() == "questionnaire", \
                f"Expected 'questionnaire' (skipped profile), got {state_tracker.get_state()}"

