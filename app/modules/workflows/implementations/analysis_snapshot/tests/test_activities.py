"""Unit tests for SnapshotWorkflow Activities."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.workflows.implementations.analysis_snapshot.activities import (
    load_assistant,
    load_conversations,
    compute_statistics,
    generate_profile,
    save_snapshot,
    notify_websocket,
)
from app.modules.workflows.models.params import (
    ProfileParams,
    SaveSnapshotParams,
    NotifyParams,
)


class TestLoadAssistant:
    """Tests for load_assistant Activity."""
    
    @pytest.mark.asyncio
    async def test_load_assistant_returns_data(self):
        """Test that load_assistant returns assistant data."""
        mock_assistant = MagicMock()
        mock_assistant.name = "Test Assistant"
        mock_assistant.metadata = {
            "survey_goal": "Test goal",
            "analysis_config": {"enabled": True}
        }
        
        mock_step = MagicMock()
        mock_step.step_key = "questionnaire"
        mock_step.metadata = {"specific_questions": "Q1\nQ2"}
        
        with patch(
            "app.modules.assistants.service.AssistantService.get_assistant_internal",
            new_callable=AsyncMock, return_value=mock_assistant
        ), patch(
            "app.modules.assistants.service.AssistantService.get_steps_internal",
            new_callable=AsyncMock, return_value=[mock_step]
        ):
            result = await load_assistant("asst_123")
        
        assert result["assistant_id"] == "asst_123"
        assert result["survey_goal"] == "Test goal"
        assert result["analysis_config"] == {"enabled": True}
        assert result["survey_questions"] == "Q1\nQ2"
    
    @pytest.mark.asyncio
    async def test_load_assistant_no_metadata(self):
        """Test load_assistant with empty metadata."""
        mock_assistant = MagicMock()
        mock_assistant.name = "Test"
        mock_assistant.metadata = {}
        
        with patch(
            "app.modules.assistants.service.AssistantService.get_assistant_internal",
            new_callable=AsyncMock, return_value=mock_assistant
        ), patch(
            "app.modules.assistants.service.AssistantService.get_steps_internal",
            new_callable=AsyncMock, return_value=[]
        ):
            result = await load_assistant("asst_123")
        
        assert result["survey_goal"] == ""
        assert result["analysis_config"] is None


class TestLoadConversations:
    """Tests for load_conversations Activity."""
    
    @pytest.mark.asyncio
    async def test_load_conversations_returns_list(self):
        """Test that load_conversations returns conversation dicts."""
        mock_conv = MagicMock()
        mock_conv.id = "conv_1"
        mock_conv.state = {"agent_metadata": {"state": "questionnaire"}}
        mock_conv.analytic_meta = None
        mock_conv.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_conv.updated_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        
        with patch(
            "app.modules.conversations.service.ConversationsService.get_conversations_by_assistant",
            new_callable=AsyncMock, return_value=[mock_conv]
        ):
            result = await load_conversations("asst_123")
        
        assert len(result) == 1
        assert result[0]["id"] == "conv_1"
    
    @pytest.mark.asyncio
    async def test_load_conversations_empty(self):
        """Test load_conversations with no conversations."""
        with patch(
            "app.modules.conversations.service.ConversationsService.get_conversations_by_assistant",
            new_callable=AsyncMock, return_value=[]
        ):
            result = await load_conversations("asst_123")
        
        assert result == []


class TestComputeStatistics:
    """Tests for compute_statistics Activity."""
    
    @pytest.mark.asyncio
    async def test_empty_conversations(self):
        """Test statistics with no conversations."""
        result = await compute_statistics([])
        
        assert result["total_respondents"] == 0
        assert result["completion_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_mixed_statuses(self):
        """Test statistics with mixed conversation statuses."""
        conversations = [
            {"state": {"agent_metadata": {"state": "COMPLETED"}}},
            {"state": {"agent_metadata": {"state": "COMPLETED"}}},
            {"state": {"agent_metadata": {"state": "questionnaire"}}},
            {"state": {"agent_metadata": {"state": "ABANDONED"}}},
            {"state": {}},
        ]
        
        result = await compute_statistics(conversations)
        
        assert result["total_respondents"] == 5
        assert result["completed_count"] == 2
        assert result["abandoned_count"] == 1
        assert result["in_progress_count"] == 2
        assert result["completion_rate"] == 0.4
    
    @pytest.mark.asyncio
    async def test_all_completed(self):
        """Test statistics when all conversations are completed."""
        conversations = [
            {"state": {"agent_metadata": {"state": "COMPLETED"}}},
            {"state": {"agent_metadata": {"state": "COMPLETED"}}},
        ]
        
        result = await compute_statistics(conversations)
        
        assert result["completion_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_stage_distribution(self):
        """Test that stage distribution is calculated."""
        conversations = [
            {"state": {"agent_metadata": {"state": "intro"}}},
            {"state": {"agent_metadata": {"state": "questionnaire"}}},
            {"state": {"agent_metadata": {"state": "questionnaire"}}},
        ]
        
        result = await compute_statistics(conversations)
        
        assert len(result["stage_distribution"]) == 2
        # Sorted by count descending
        assert result["stage_distribution"][0]["stage"] == "questionnaire"
        assert result["stage_distribution"][0]["count"] == 2


class TestGenerateProfileSmartRecalculation:
    """Tests for generate_profile smart recalculation logic."""
    
    @pytest.mark.asyncio
    async def test_skip_when_up_to_date(self):
        """Test that profile is skipped when up to date."""
        mock_conv = MagicMock()
        mock_conv.analytic_meta = {"analyzed_at": "2026-02-01T00:00:00"}
        mock_conv.updated_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
        mock_conv.state = {}
        
        params = ProfileParams(
            conversation_id="conv_1",
            assistant_id="asst_1",
            analysis_config={"last_updated_at": "2026-01-10T00:00:00"},
            force_recalculate=False
        )
        
        with patch(
            "app.modules.conversations.service.ConversationsService.get_conversation",
            new_callable=AsyncMock, return_value=mock_conv
        ):
            result = await generate_profile(params)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_recalculate_when_conv_updated(self):
        """Test that profile is recalculated when conversation was updated."""
        mock_conv = MagicMock()
        mock_conv.analytic_meta = {"analyzed_at": "2026-01-01T00:00:00"}
        mock_conv.updated_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        mock_conv.state = {"agent_metadata": {"state": "COMPLETED"}}
        
        mock_msg = MagicMock()
        mock_msg.role = "user"
        mock_msg.content = "test message"
        
        params = ProfileParams(
            conversation_id="conv_1",
            assistant_id="asst_1",
            analysis_config={},
            force_recalculate=False
        )
        
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "category_scores": [],
            "extracted_tags": [],
            "custom_answers": [],
            "summary": "Test",
            "data_completeness": 0.5,
            "analysis_confidence": 0.7
        })
        
        with patch(
            "app.modules.conversations.service.ConversationsService.get_conversation",
            new_callable=AsyncMock, return_value=mock_conv
        ), patch(
            "app.modules.conversations.service.ConversationsService.get_full_history",
            new_callable=AsyncMock, return_value=[mock_msg]
        ), patch(
            "app.modules.conversations.service.ConversationsService.update_analytic_meta",
            new_callable=AsyncMock
        ) as mock_update, patch(
            "app.modules.workflows.implementations.analysis_snapshot.activities._load_prompt_template",
            return_value="Analyze: {categories} {tags} {custom_questions} {conversation_history} {assistant_goal} {final_stage} {survey_status} {summary_max_length}"
        ), patch(
            "app.modules.workflows.implementations.analysis_snapshot.activities._get_llm"
        ) as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm
            
            result = await generate_profile(params)
        
        assert result is not None
        assert "analyzed_at" in result
        mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_force_recalculate(self):
        """Test that force_recalculate ignores existing profile."""
        mock_conv = MagicMock()
        mock_conv.analytic_meta = {"analyzed_at": "2026-02-01T00:00:00"}
        mock_conv.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_conv.state = {"agent_metadata": {"state": "COMPLETED"}}
        
        mock_msg = MagicMock()
        mock_msg.role = "user"
        mock_msg.content = "test"
        
        params = ProfileParams(
            conversation_id="conv_1",
            assistant_id="asst_1",
            analysis_config={},
            force_recalculate=True
        )
        
        mock_response = MagicMock()
        mock_response.content = json.dumps({"category_scores": [], "extracted_tags": [], "custom_answers": []})
        
        with patch(
            "app.modules.conversations.service.ConversationsService.get_conversation",
            new_callable=AsyncMock, return_value=mock_conv
        ), patch(
            "app.modules.conversations.service.ConversationsService.get_full_history",
            new_callable=AsyncMock, return_value=[mock_msg]
        ), patch(
            "app.modules.conversations.service.ConversationsService.update_analytic_meta",
            new_callable=AsyncMock
        ), patch(
            "app.modules.workflows.implementations.analysis_snapshot.activities._load_prompt_template",
            return_value="{categories} {tags} {custom_questions} {conversation_history} {assistant_goal} {final_stage} {survey_status} {summary_max_length}"
        ), patch(
            "app.modules.workflows.implementations.analysis_snapshot.activities._get_llm"
        ) as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm
            
            result = await generate_profile(params)
        
        # Should NOT skip — force_recalculate=True
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_conversation_not_found(self):
        """Test that missing conversation returns None."""
        params = ProfileParams(
            conversation_id="nonexistent",
            assistant_id="asst_1"
        )
        
        with patch(
            "app.modules.conversations.service.ConversationsService.get_conversation",
            new_callable=AsyncMock, return_value=None
        ):
            result = await generate_profile(params)
        
        assert result is None


class TestSaveSnapshot:
    """Tests for save_snapshot Activity."""
    
    @pytest.mark.asyncio
    async def test_save_snapshot_calls_service(self):
        """Test that save_snapshot calls WorkflowService."""
        params = SaveSnapshotParams(
            execution_id="exec_123",
            statistics={"total_respondents": 50},
            conclusions={"summary": "Test"},
            conversations_analyzed=45,
            conversations_skipped=5,
        )
        
        with patch(
            "app.modules.workflows.service.WorkflowService.complete_execution",
            new_callable=AsyncMock
        ) as mock_complete:
            result = await save_snapshot(params)
        
        assert result == "exec_123"
        mock_complete.assert_called_once()


class TestNotifyWebsocket:
    """Tests for notify_websocket Activity."""
    
    @pytest.mark.asyncio
    async def test_notify_does_not_raise(self):
        """Test that notify_websocket runs without error."""
        params = NotifyParams(
            execution_id="exec_123",
            status="completed",
            progress={"step": "done"}
        )
        
        # Should not raise
        await notify_websocket(params)
