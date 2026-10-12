"""Unit tests for Survey Agent tools.

Each tool is tested in isolation with mocked ConversationsService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.modules.agents.survey_agent.tools import (
    UpdateLanguageTool,
    SaveNameTool,
    SaveProfileTool,
    SaveSurveyAnswersTool,
    SaveQuestionnaireAnswerTool,
    SaveAdditionalInfoTool,
    SaveFinalMessageTool,
    get_survey_tools
)
from app.modules.agents.survey_agent.tools.save_survey_tool import SurveyQA


class TestUpdateLanguageTool:
    """Tests for UpdateLanguageTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = UpdateLanguageTool()
        tool.conversation_id = str(ObjectId())
        tool.interlocutor_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        service.update_interlocutor_language = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_update_language_success(self, tool, mock_service):
        """Test successful language update."""
        # ConversationsService is imported inside _arun, so patch at source
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(language="English")
            
            # Verify result
            assert "English" in result
            
            # Verify service calls
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args
            assert call_args[0][0] == tool.conversation_id
            assert call_args[0][1]["language"] == "English"
            assert call_args[0][1]["state"] == "intro"
            
            mock_service.update_interlocutor_language.assert_called_once_with(
                tool.interlocutor_id, "English"
            )
    
    @pytest.mark.asyncio
    async def test_update_language_russian(self, tool, mock_service):
        """Test language update with Russian."""
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(language="Русский")
            
            assert "Русский" in result
            mock_service.update_agent_metadata.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_language_error_handling(self, tool):
        """Test error handling when service fails."""
        mock_service = MagicMock()
        mock_service.update_agent_metadata = AsyncMock(side_effect=Exception("DB error"))
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(language="English")
            
            assert "Error" in result


class TestSaveNameTool:
    """Tests for SaveNameTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = SaveNameTool()
        tool.conversation_id = str(ObjectId())
        tool.interlocutor_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        service.update_interlocutor_name = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_save_name_success(self, tool, mock_service):
        """Test successful name save."""
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(name="Alex", next_step_key="profile")
            
            assert "saved" in result.lower()
            assert "profile" in result
            
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["name"] == "Alex"
            assert call_args[1]["state"] == "profile"
            
            mock_service.update_interlocutor_name.assert_called_once_with(
                tool.interlocutor_id, "Alex"
            )
    
    @pytest.mark.asyncio
    async def test_save_name_transitions_to_questionnaire(self, tool, mock_service):
        """Test name save with direct transition to questionnaire (skip profile)."""
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(name="John", next_step_key="questionnaire")
            
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["state"] == "questionnaire"


class TestSaveProfileTool:
    """Tests for SaveProfileTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = SaveProfileTool()
        tool.conversation_id = str(ObjectId())
        tool.interlocutor_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        service.update_interlocutor_profile = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_save_profile_success(self, tool, mock_service):
        """Test successful profile save."""
        profile = "Software developer at a startup, works on AI products"
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                profile_summary=profile, 
                next_step_key="questionnaire"
            )
            
            assert "saved" in result.lower()
            
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["profile_summary"] == profile
            assert call_args[1]["state"] == "questionnaire"
            
            mock_service.update_interlocutor_profile.assert_called_once_with(
                tool.interlocutor_id, {"profile_summary": profile}
            )


class TestSaveSurveyAnswersTool:
    """Tests for SaveSurveyAnswersTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = SaveSurveyAnswersTool()
        tool.conversation_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_save_survey_with_pydantic_objects(self, tool, mock_service):
        """Test saving survey with SurveyQA Pydantic objects."""
        survey_data = [
            SurveyQA(question="What is your budget?", answer="$5000"),
            SurveyQA(question="What is your timeline?", answer="3 months")
        ]
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                survey_data=survey_data, 
                next_step_key="additional_info"
            )
            
            assert "saved" in result.lower()
            
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            
            saved_survey = call_args[1]["survey_summary"]
            assert len(saved_survey) == 2
            assert saved_survey[0]["question"] == "What is your budget?"
            assert saved_survey[0]["answer"] == "$5000"
    
    @pytest.mark.asyncio
    async def test_save_survey_with_dict_objects(self, tool, mock_service):
        """Test saving survey with dict objects (from LLM)."""
        survey_data = [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"}
        ]
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                survey_data=survey_data, 
                next_step_key="closing"
            )
            
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["state"] == "closing"


class TestSaveAdditionalInfoTool:
    """Tests for SaveAdditionalInfoTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = SaveAdditionalInfoTool()
        tool.conversation_id = str(ObjectId())
        tool.interlocutor_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        service.update_interlocutor_email = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_conversation(self):
        """Create mock conversation with existing metadata."""
        conv = MagicMock()
        conv.get_agent_metadata.return_value = {"additional_info": {}}
        return conv
    
    @pytest.mark.asyncio
    async def test_save_email(self, tool, mock_service, mock_conversation):
        """Test saving email address."""
        mock_service.get_conversation = AsyncMock(return_value=mock_conversation)
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                info_type="email",
                info_value="alex@test.com",
                next_step_key="closing"
            )
            
            assert "saved" in result.lower()
            
            # Should update interlocutor email
            mock_service.update_interlocutor_email.assert_called_once_with(
                tool.interlocutor_id, "alex@test.com"
            )
            
            # Should update agent metadata
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["additional_info"]["email"] == "alex@test.com"
            assert call_args[1]["state"] == "closing"
    
    @pytest.mark.asyncio
    async def test_save_declined_email(self, tool, mock_service, mock_conversation):
        """Test handling declined email - should not save."""
        mock_service.get_conversation = AsyncMock(return_value=mock_conversation)
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                info_type="email",
                info_value="declined",
                next_step_key="closing"
            )
            
            # Should NOT update interlocutor email
            mock_service.update_interlocutor_email.assert_not_called()
            
            # Should still update state
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            # Email should NOT be in additional_info
            assert "email" not in call_args[1]["additional_info"]
            assert call_args[1]["state"] == "closing"
    
    @pytest.mark.asyncio
    async def test_save_phone_number(self, tool, mock_service, mock_conversation):
        """Test saving phone number (non-email field)."""
        mock_service.get_conversation = AsyncMock(return_value=mock_conversation)
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                info_type="phone",
                info_value="+1234567890",
                next_step_key="closing"
            )
            
            # Should NOT update interlocutor email (it's phone)
            mock_service.update_interlocutor_email.assert_not_called()
            
            # Should save phone in additional_info
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["additional_info"]["phone"] == "+1234567890"
    
    @pytest.mark.asyncio
    async def test_merge_with_existing_additional_info(self, tool, mock_service):
        """Test merging new info with existing additional_info."""
        conv = MagicMock()
        conv.get_agent_metadata.return_value = {
            "additional_info": {"phone": "+1234567890"}
        }
        mock_service.get_conversation = AsyncMock(return_value=conv)
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(
                info_type="email",
                info_value="alex@test.com",
                next_step_key="closing"
            )
            
            call_args = mock_service.update_agent_metadata.call_args[0]
            additional_info = call_args[1]["additional_info"]
            # Both phone and email should be present
            assert additional_info["phone"] == "+1234567890"
            assert additional_info["email"] == "alex@test.com"


class TestSaveFinalMessageTool:
    """Tests for SaveFinalMessageTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = SaveFinalMessageTool()
        tool.conversation_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_save_final_message(self, tool, mock_service):
        """Test saving final message and marking completed."""
        final_message = "Thank you Alex! Based on your responses, we recommend..."
        
        with patch('app.modules.conversations.service.ConversationsService', 
                   return_value=mock_service):
            result = await tool._arun(final_message=final_message)
            
            # Should return the final message
            assert result == final_message
            
            mock_service.update_agent_metadata.assert_called_once()
            call_args = mock_service.update_agent_metadata.call_args[0]
            assert call_args[1]["final_message"] == final_message
            assert call_args[1]["state"] == "completed"


class TestSaveQuestionnaireAnswerTool:
    """Tests for SaveQuestionnaireAnswerTool."""
    
    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        tool = SaveQuestionnaireAnswerTool()
        tool.conversation_id = str(ObjectId())
        tool.assistant_id = str(ObjectId())
        return tool
    
    @pytest.fixture
    def mock_conv_service(self):
        """Create mock ConversationsService."""
        service = MagicMock()
        service.update_agent_metadata = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_assistant_service(self):
        """Create mock AssistantService."""
        service = MagicMock()
        return service
    
    @pytest.mark.asyncio
    async def test_save_answer_mid_survey(self, tool, mock_conv_service, mock_assistant_service):
        """Test saving an answer when more questions remain."""
        # Setup conversation with progress at question 1
        mock_conversation = MagicMock()
        mock_conversation.get_agent_metadata.return_value = {
            "state": "questionnaire",
            "questionnaire_progress": {"current_index": 1, "answers": [
                {"question": "Q1?", "answer": "A1"}
            ]}
        }
        mock_conv_service.get_conversation = AsyncMock(return_value=mock_conversation)
        
        # Setup step with 3 questions
        mock_step = MagicMock()
        mock_step.metadata = {"questions_list": ["Q1?", "Q2?", "Q3?"]}
        mock_step.order_no = 4
        mock_assistant_service.get_current_step = AsyncMock(return_value=mock_step)
        
        with patch('app.modules.conversations.service.ConversationsService',
                   return_value=mock_conv_service), \
             patch('app.modules.assistants.service.AssistantService',
                   return_value=mock_assistant_service):
            result = await tool._arun(answer="A2")
        
        # Tool returns empty for non-final answers (LLM provides next question in content)
        assert result == ""
        mock_conv_service.update_agent_metadata.assert_called_once()
        call_args = mock_conv_service.update_agent_metadata.call_args[0]
        progress = call_args[1]["questionnaire_progress"]
        assert progress["current_index"] == 2
        assert len(progress["answers"]) == 2
        assert progress["answers"][1]["answer"] == "A2"
        # State should NOT change (not in the update)
        assert "state" not in call_args[1]
    
    @pytest.mark.asyncio
    async def test_save_last_answer_transitions(self, tool, mock_conv_service, mock_assistant_service):
        """Test saving the last answer triggers state transition."""
        # Setup conversation with progress at last question
        mock_conversation = MagicMock()
        mock_conversation.get_agent_metadata.return_value = {
            "state": "questionnaire",
            "questionnaire_progress": {"current_index": 1, "answers": [
                {"question": "Q1?", "answer": "A1"}
            ]}
        }
        mock_conv_service.get_conversation = AsyncMock(return_value=mock_conversation)
        
        # Setup step with 2 questions (so index 1 is the last)
        mock_step = MagicMock()
        mock_step.metadata = {"questions_list": ["Q1?", "Q2?"]}
        mock_step.order_no = 4
        mock_assistant_service.get_current_step = AsyncMock(return_value=mock_step)
        
        # Next step
        mock_next_step = MagicMock()
        mock_next_step.step_key = "additional_info"
        mock_assistant_service.get_step_by_order = AsyncMock(return_value=mock_next_step)
        
        with patch('app.modules.conversations.service.ConversationsService',
                   return_value=mock_conv_service), \
             patch('app.modules.assistants.service.AssistantService',
                   return_value=mock_assistant_service):
            result = await tool._arun(answer="A2")
        
        assert "complete" in result.lower()
        mock_conv_service.update_agent_metadata.assert_called_once()
        call_args = mock_conv_service.update_agent_metadata.call_args[0]
        assert call_args[1]["state"] == "additional_info"
        assert call_args[1]["survey_summary"] == [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"}
        ]
    
    @pytest.mark.asyncio
    async def test_save_answer_error_no_questions_list(self, tool, mock_conv_service, mock_assistant_service):
        """Test error when no questions_list configured."""
        mock_conversation = MagicMock()
        mock_conversation.get_agent_metadata.return_value = {
            "questionnaire_progress": {"current_index": 0, "answers": []}
        }
        mock_conv_service.get_conversation = AsyncMock(return_value=mock_conversation)
        
        mock_step = MagicMock()
        mock_step.metadata = {}
        mock_assistant_service.get_current_step = AsyncMock(return_value=mock_step)
        
        with patch('app.modules.conversations.service.ConversationsService',
                   return_value=mock_conv_service), \
             patch('app.modules.assistants.service.AssistantService',
                   return_value=mock_assistant_service):
            result = await tool._arun(answer="test")
        
        assert "error" in result.lower()


class TestGetSurveyTools:
    """Tests for get_survey_tools function."""
    
    def test_get_tools_for_lang_step(self):
        """Test getting tools for lang step."""
        tools = get_survey_tools("lang")
        
        assert len(tools) == 1
        assert tools[0].name == "update_language"
    
    def test_get_tools_for_intro_step(self):
        """Test getting tools for intro step."""
        tools = get_survey_tools("intro")
        
        assert len(tools) == 1
        assert tools[0].name == "save_name_and_transition"
    
    def test_get_tools_for_profile_step(self):
        """Test getting tools for profile step."""
        tools = get_survey_tools("profile")
        
        assert len(tools) == 1
        assert tools[0].name == "save_profile"
    
    def test_get_tools_for_questionnaire_step_default(self):
        """Test getting tools for questionnaire step without questions_list."""
        tools = get_survey_tools("questionnaire")
        
        assert len(tools) == 1
        assert tools[0].name == "save_survey_answers"
    
    def test_get_tools_for_questionnaire_with_questions_list(self):
        """Test getting incremental tool when questions_list is available."""
        tools = get_survey_tools(
            "questionnaire",
            step_metadata={"questions_list": ["Q1?", "Q2?"]}
        )
        
        assert len(tools) == 1
        assert tools[0].name == "save_questionnaire_answer"
    
    def test_get_tools_for_questionnaire_with_empty_questions_list(self):
        """Test fallback to save_survey_answers when questions_list is empty."""
        tools = get_survey_tools(
            "questionnaire",
            step_metadata={"questions_list": []}
        )
        
        assert len(tools) == 1
        assert tools[0].name == "save_survey_answers"
    
    def test_get_tools_for_additional_info_step(self):
        """Test getting tools for additional_info step."""
        tools = get_survey_tools("additional_info")
        
        assert len(tools) == 1
        assert tools[0].name == "save_additional_info"
    
    def test_get_tools_for_closing_step(self):
        """Test getting tools for closing step."""
        tools = get_survey_tools("closing")
        
        assert len(tools) == 1
        assert tools[0].name == "save_final_message"
    
    def test_get_all_tools(self):
        """Test getting all tools (no step specified)."""
        tools = get_survey_tools(None)
        
        # Should have all 6 tools
        assert len(tools) == 6
        tool_names = [t.name for t in tools]
        assert "update_language" in tool_names
        assert "save_name_and_transition" in tool_names
        assert "save_profile" in tool_names
        assert "save_survey_answers" in tool_names
        assert "save_additional_info" in tool_names
        assert "save_final_message" in tool_names
    
    def test_get_tools_for_unknown_step(self):
        """Test getting tools for unknown step returns all."""
        tools = get_survey_tools("unknown_step")
        
        # Should return all tools as fallback
        assert len(tools) == 6

