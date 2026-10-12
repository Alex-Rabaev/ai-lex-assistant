"""Unit tests for AnalysisService."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.analysis.service import AnalysisService, ANALYSIS_CONFIG_KEY
from app.modules.analysis.schemas.config import (
    AnalysisConfig,
    AnalysisFramework,
    CategoryConfig,
    TagConfig,
)
from app.modules.assistants.models import Assistant


USER_ID = "admin@test.com"


def _make_assistant(metadata=None):
    """Create a mock Assistant."""
    return Assistant(
        org_id="org_1",
        owner_user_id=USER_ID,
        name="Test Assistant",
        metadata=metadata or {}
    )


class TestAnalysisServiceGetConfig:
    """Tests for AnalysisService.get_config."""
    
    @pytest.fixture
    def mock_assistant_service(self):
        svc = MagicMock()
        svc.get_assistant = AsyncMock()
        return svc
    
    @pytest.fixture
    def service(self, mock_assistant_service):
        return AnalysisService(assistant_service=mock_assistant_service)
    
    @pytest.mark.asyncio
    async def test_get_config_returns_existing(self, service, mock_assistant_service):
        """Test get_config returns existing config."""
        config_data = {
            "enabled": True,
            "framework": {
                "categories": [
                    {"name": "Intent", "description": "Purchase intent", "scoring_type": "scale", "min_score": 1, "max_score": 5}
                ],
                "tags": [],
                "custom_questions": []
            },
            "output": {}
        }
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={ANALYSIS_CONFIG_KEY: config_data})
        )
        
        result = await service.get_config("asst_123", USER_ID)
        
        assert result.enabled is True
        assert len(result.framework.categories) == 1
    
    @pytest.mark.asyncio
    async def test_get_config_returns_default_when_not_set(self, service, mock_assistant_service):
        """Test get_config returns default when not set."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={})
        )
        
        result = await service.get_config("asst_123", USER_ID)
        
        assert result.enabled is False
        assert result.framework.categories == []
    
    @pytest.mark.asyncio
    async def test_get_config_handles_none_metadata(self, service, mock_assistant_service):
        """Test get_config handles None metadata."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata=None)
        )
        
        result = await service.get_config("asst_123", USER_ID)
        
        assert result.enabled is False


class TestAnalysisServiceUpdateConfig:
    """Tests for AnalysisService.update_config."""
    
    @pytest.fixture
    def mock_assistant_service(self):
        svc = MagicMock()
        svc.get_assistant = AsyncMock(return_value=_make_assistant())
        svc.update_metadata_field_internal = AsyncMock(
            return_value=_make_assistant()
        )
        return svc
    
    @pytest.fixture
    def service(self, mock_assistant_service):
        return AnalysisService(assistant_service=mock_assistant_service)
    
    @pytest.mark.asyncio
    async def test_update_config_saves_to_metadata(self, service, mock_assistant_service):
        """Test that update_config saves config to assistant metadata."""
        config = AnalysisConfig(
            enabled=True,
            framework=AnalysisFramework(
                categories=[
                    CategoryConfig(name="Intent", description="Purchase intent", scoring_type="scale", min_score=1, max_score=5)
                ]
            )
        )
        
        result = await service.update_config("asst_123", USER_ID, config)
        
        mock_assistant_service.update_metadata_field_internal.assert_called_once()
        call_args = mock_assistant_service.update_metadata_field_internal.call_args
        assert call_args[0][0] == "asst_123"
        assert call_args[0][1] == ANALYSIS_CONFIG_KEY
        assert call_args[0][2]["enabled"] is True
    
    @pytest.mark.asyncio
    async def test_update_config_verifies_ownership(self, service, mock_assistant_service):
        """Test that update_config verifies assistant ownership."""
        config = AnalysisConfig()
        
        await service.update_config("asst_123", USER_ID, config)
        
        mock_assistant_service.get_assistant.assert_called_once_with("asst_123", USER_ID)
    
    @pytest.mark.asyncio
    async def test_update_config_sets_last_updated_at(self, service, mock_assistant_service):
        """Test that update_config sets last_updated_at."""
        config = AnalysisConfig()
        
        result = await service.update_config("asst_123", USER_ID, config)
        
        assert result.last_updated_at is not None
    
    @pytest.mark.asyncio
    async def test_update_config_returns_updated_config(self, service, mock_assistant_service):
        """Test that update_config returns the updated config."""
        config = AnalysisConfig(enabled=True)
        
        result = await service.update_config("asst_123", USER_ID, config)
        
        assert result.enabled is True


class TestAnalysisServiceGenerateConfig:
    """Tests for AnalysisService.generate_config."""
    
    @pytest.fixture
    def mock_assistant_service(self):
        svc = MagicMock()
        svc.get_assistant = AsyncMock()
        svc.get_steps_internal = AsyncMock(return_value=[])
        return svc
    
    @pytest.fixture
    def service(self, mock_assistant_service):
        return AnalysisService(assistant_service=mock_assistant_service)
    
    @pytest.mark.asyncio
    async def test_generate_config_calls_llm(self, service, mock_assistant_service):
        """Test that generate_config calls LLM with correct prompt."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {"assistant_goal": "Understand customer needs"}
            })
        )
        
        llm_response = json.dumps({
            "categories": [
                {"name": "Need Level", "description": "How strong is the need", "scoring_type": "scale", "min_score": 1, "max_score": 5}
            ],
            "tags": [
                {"name": "Industry", "extraction": "auto", "description": "Respondent industry"}
            ],
            "custom_questions": ["Is this respondent a decision maker?"]
        })
        
        mock_llm = AsyncMock(return_value=llm_response)
        
        result = await service.generate_config("asst_123", USER_ID, llm_callable=mock_llm)
        
        mock_llm.assert_called_once()
        assert len(result.categories) == 1
        assert result.categories[0].name == "Need Level"
        assert len(result.tags) == 1
        assert len(result.custom_questions) == 1
    
    @pytest.mark.asyncio
    async def test_generate_config_no_llm_returns_empty(self, service, mock_assistant_service):
        """Test that generate_config returns empty framework without LLM."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {"assistant_goal": "Test goal"}
            })
        )
        
        result = await service.generate_config("asst_123", USER_ID, llm_callable=None)
        
        assert result.categories == []
        assert result.tags == []
    
    @pytest.mark.asyncio
    async def test_generate_config_no_assistant_goal_raises(self, service, mock_assistant_service):
        """Test that generate_config raises ValueError when no assistant_goal."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={})
        )
        
        with pytest.raises(ValueError, match="assistant_goal must be set"):
            await service.generate_config("asst_123", USER_ID, llm_callable=AsyncMock())
    
    @pytest.mark.asyncio
    async def test_generate_config_handles_invalid_llm_json(self, service, mock_assistant_service):
        """Test that generate_config handles invalid JSON from LLM."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {"assistant_goal": "Test"}
            })
        )
        
        mock_llm = AsyncMock(return_value="not valid json")
        
        result = await service.generate_config("asst_123", USER_ID, llm_callable=mock_llm)
        
        assert result.categories == []
    
    @pytest.mark.asyncio
    async def test_generate_config_includes_step_questions(self, service, mock_assistant_service):
        """Test that generate_config includes questionnaire step data."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {"assistant_goal": "Test"}
            })
        )
        
        from app.modules.assistants.models import AssistantStep
        mock_step = MagicMock(spec=AssistantStep)
        mock_step.step_key = "questionnaire"
        mock_step.metadata = {"specific_questions": "Q1\nQ2\nQ3"}
        mock_assistant_service.get_steps_internal = AsyncMock(return_value=[mock_step])
        
        llm_response = json.dumps({
            "categories": [
                {"name": "Cat1", "description": "Desc", "scoring_type": "scale", "min_score": 1, "max_score": 5}
            ],
            "tags": [],
            "custom_questions": []
        })
        mock_llm = AsyncMock(return_value=llm_response)
        
        result = await service.generate_config("asst_123", USER_ID, llm_callable=mock_llm)
        
        # Verify LLM was called with prompt containing questions
        call_args = mock_llm.call_args[0][0]
        assert "Q1" in call_args


class TestAnalysisServiceGetSuggestions:
    """Tests for AnalysisService.get_suggestions."""
    
    @pytest.fixture
    def mock_assistant_service(self):
        svc = MagicMock()
        svc.get_assistant = AsyncMock()
        return svc
    
    @pytest.fixture
    def service(self, mock_assistant_service):
        return AnalysisService(assistant_service=mock_assistant_service)
    
    @pytest.mark.asyncio
    async def test_no_config_suggests_create(self, service, mock_assistant_service):
        """Test suggestion to create config when none exists."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={})
        )
        
        result = await service.get_suggestions("asst_123", USER_ID)
        
        assert result["has_config"] is False
        assert any(s["type"] == "create_config" for s in result["suggestions"])
    
    @pytest.mark.asyncio
    async def test_empty_categories_suggests_generate(self, service, mock_assistant_service):
        """Test suggestion to generate categories when empty."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {"enabled": False, "framework": {"categories": [], "tags": [], "custom_questions": []}, "output": {}}
            })
        )
        
        result = await service.get_suggestions("asst_123", USER_ID)
        
        assert result["has_config"] is True
        assert result["has_categories"] is False
        assert any(s["type"] == "generate_categories" for s in result["suggestions"])
    
    @pytest.mark.asyncio
    async def test_disabled_config_suggests_enable(self, service, mock_assistant_service):
        """Test suggestion to enable config when disabled."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {
                    "enabled": False,
                    "framework": {
                        "categories": [{"name": "X", "description": "Y", "scoring_type": "scale", "min_score": 1, "max_score": 5}],
                        "tags": [], "custom_questions": []
                    },
                    "output": {}
                }
            })
        )
        
        result = await service.get_suggestions("asst_123", USER_ID)
        
        assert any(s["type"] == "enable_config" for s in result["suggestions"])
    
    @pytest.mark.asyncio
    async def test_no_survey_goal_suggests_add(self, service, mock_assistant_service):
        """Test suggestion to add survey goal."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {
                    "enabled": True,
                    "framework": {
                        "categories": [{"name": "X", "description": "Y", "scoring_type": "scale", "min_score": 1, "max_score": 5}],
                        "tags": [], "custom_questions": []
                    },
                    "output": {}
                }
            })
        )
        
        result = await service.get_suggestions("asst_123", USER_ID)
        
        assert any(s["type"] == "add_assistant_goal" for s in result["suggestions"])
    
    @pytest.mark.asyncio
    async def test_fully_configured_no_suggestions(self, service, mock_assistant_service):
        """Test no suggestions when fully configured."""
        mock_assistant_service.get_assistant = AsyncMock(
            return_value=_make_assistant(metadata={
                ANALYSIS_CONFIG_KEY: {
                    "assistant_goal": "Test goal",
                    "enabled": True,
                    "framework": {
                        "categories": [{"name": "X", "description": "Y", "scoring_type": "scale", "min_score": 1, "max_score": 5}],
                        "tags": [], "custom_questions": []
                    },
                    "output": {}
                }
            })
        )
        
        result = await service.get_suggestions("asst_123", USER_ID)
        
        assert result["has_config"] is True
        assert result["config_enabled"] is True
        assert result["has_categories"] is True
        assert len(result["suggestions"]) == 0


class TestAnalysisServiceCreateSnapshot:
    """Tests for AnalysisService.create_snapshot."""
    
    @pytest.fixture
    def mock_services(self):
        asst = MagicMock()
        asst.get_assistant = AsyncMock(return_value=_make_assistant())
        conv = MagicMock()
        wf = MagicMock()
        wf.start_workflow = AsyncMock(return_value="exec_123")
        return asst, conv, wf
    
    @pytest.fixture
    def service(self, mock_services):
        asst, conv, wf = mock_services
        return AnalysisService(
            assistant_service=asst,
            conversations_service=conv,
            workflow_service=wf
        )
    
    @pytest.mark.asyncio
    async def test_create_snapshot_starts_workflow(self, service, mock_services):
        """Test that create_snapshot starts Temporal workflow."""
        _, _, wf = mock_services
        
        result = await service.create_snapshot("asst_123", USER_ID)
        
        wf.start_workflow.assert_called_once()
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_create_snapshot_verifies_ownership(self, service, mock_services):
        """Test that create_snapshot verifies assistant ownership."""
        asst, _, _ = mock_services
        
        await service.create_snapshot("asst_123", USER_ID)
        
        asst.get_assistant.assert_called_once_with("asst_123", USER_ID)
    
    @pytest.mark.asyncio
    async def test_create_snapshot_passes_params(self, service, mock_services):
        """Test that create_snapshot passes correct params to workflow."""
        _, _, wf = mock_services
        
        await service.create_snapshot(
            "asst_123", USER_ID,
            force_recalculate=True,
            version_name="Q1 2026"
        )
        
        call_kwargs = wf.start_workflow.call_args[1]
        assert call_kwargs["workflow_name"] == "SnapshotWorkflow"
        assert call_kwargs["workflow_type"] == "analysis_snapshot"
        assert call_kwargs["version_name"] == "Q1 2026"


class TestAnalysisServiceGetSnapshots:
    """Tests for AnalysisService.get_snapshots."""
    
    @pytest.fixture
    def mock_services(self):
        asst = MagicMock()
        asst.get_assistant = AsyncMock(return_value=_make_assistant())
        conv = MagicMock()
        wf = MagicMock()
        wf.get_executions = AsyncMock(return_value=[])
        return asst, conv, wf
    
    @pytest.fixture
    def service(self, mock_services):
        asst, conv, wf = mock_services
        return AnalysisService(
            assistant_service=asst,
            conversations_service=conv,
            workflow_service=wf
        )
    
    @pytest.mark.asyncio
    async def test_get_snapshots_returns_list(self, service, mock_services):
        _, _, wf = mock_services
        
        result = await service.get_snapshots("asst_123", USER_ID)
        
        assert result == []
        wf.get_executions.assert_called_once()


class TestAnalysisServiceGetAnalyticMeta:
    """Tests for AnalysisService analytics methods."""
    
    @pytest.fixture
    def mock_services(self):
        asst = MagicMock()
        asst.get_assistant = AsyncMock(return_value=_make_assistant())
        conv = MagicMock()
        conv.get_conversation = AsyncMock()
        conv.get_conversations_by_assistant = AsyncMock(return_value=[])
        wf = MagicMock()
        return asst, conv, wf
    
    @pytest.fixture
    def service(self, mock_services):
        asst, conv, wf = mock_services
        return AnalysisService(
            assistant_service=asst,
            conversations_service=conv,
            workflow_service=wf
        )
    
    @pytest.mark.asyncio
    async def test_get_analytic_meta_returns_data(self, service, mock_services):
        _, conv, _ = mock_services

        mock_conv = MagicMock()
        mock_conv.analytic_meta = {"summary": "Test"}
        mock_conv.assistant_id = "asst_123"
        mock_conv.is_mock = False
        conv.get_conversation = AsyncMock(return_value=mock_conv)

        result = await service.get_analytic_meta("conv_123", USER_ID)

        assert result["analytic_meta"] == {"summary": "Test"}
        assert result["is_mock"] is False

    @pytest.mark.asyncio
    async def test_get_analytic_meta_not_found(self, service, mock_services):
        _, conv, _ = mock_services
        conv.get_conversation = AsyncMock(return_value=None)

        result = await service.get_analytic_meta("nonexistent", USER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_analytic_meta_by_assistant(self, service, mock_services):
        _, conv, _ = mock_services

        mock_conv1 = MagicMock()
        mock_conv1.id = "c1"
        mock_conv1.analytic_meta = {"summary": "Profile 1"}
        mock_conv1.is_mock = False

        mock_conv2 = MagicMock()
        mock_conv2.id = "c2"
        mock_conv2.analytic_meta = None
        mock_conv2.is_mock = True

        conv.get_conversations_by_assistant = AsyncMock(return_value=[mock_conv1, mock_conv2])

        result = await service.get_analytic_meta_by_assistant("asst_123", USER_ID)

        assert len(result) == 1
        assert result[0]["conversation_id"] == "c1"
        assert result[0]["is_mock"] is False


class TestAnalysisServiceGenerateMockRespondents:
    """Tests for AnalysisService.generate_mock_respondents."""

    @pytest.fixture
    def mock_assistant_service(self):
        svc = MagicMock()
        svc.get_assistant = AsyncMock(return_value=_make_assistant())
        return svc

    @pytest.fixture
    def mock_connection_service(self):
        svc = MagicMock()
        conn = MagicMock()
        conn.id = "conn_123"
        svc.list_connections = AsyncMock(return_value=[conn])
        return svc

    @pytest.fixture
    def mock_conversations_service(self):
        svc = MagicMock()
        svc.create_mock_conversation = AsyncMock(side_effect=["conv_1", "conv_2", "conv_3"])
        return svc

    @pytest.fixture
    def service(
        self,
        mock_assistant_service,
        mock_connection_service,
        mock_conversations_service,
    ):
        return AnalysisService(
            assistant_service=mock_assistant_service,
            connection_service=mock_connection_service,
            conversations_service=mock_conversations_service,
        )

    @pytest.mark.asyncio
    async def test_generate_mock_respondents_returns_created_and_ids(
        self, service, mock_conversations_service
    ):
        """generate_mock_respondents returns created count and conversation_ids."""
        with patch("app.modules.analysis.service.generate_mock_dialogues") as mock_dialogues:
            mock_dialogues.return_value = [
                ("COMPLETED", [("user", "Hi", "intro"), ("assistant", "Hello", "intro")]),
                ("questionnaire", [("user", "Yes", "questionnaire")]),
            ]
            result = await service.generate_mock_respondents(
                assistant_id="asst_123",
                user_id=USER_ID,
                count=2,
                language="en",
                include_abandoned=True,
            )
        assert result["created"] == 2
        assert len(result["conversation_ids"]) == 2
        assert mock_conversations_service.create_mock_conversation.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_mock_respondents_raises_when_no_connections(
        self, mock_assistant_service, mock_conversations_service
    ):
        """Raises ValueError when assistant has no connections."""
        mock_connection_service = MagicMock()
        mock_connection_service.list_connections = AsyncMock(return_value=[])
        service = AnalysisService(
            assistant_service=mock_assistant_service,
            connection_service=mock_connection_service,
            conversations_service=mock_conversations_service,
        )
        with pytest.raises(ValueError) as exc_info:
            await service.generate_mock_respondents(
                assistant_id="asst_123",
                user_id=USER_ID,
                count=5,
            )
        assert "at least one connection" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_mock_respondents_calls_list_connections(
        self, service, mock_connection_service
    ):
        """Uses first connection from list_connections."""
        with patch("app.modules.analysis.service.generate_mock_dialogues") as mock_dialogues:
            mock_dialogues.return_value = [("COMPLETED", [("user", "Hi", "intro")])]
            await service.generate_mock_respondents(
                assistant_id="asst_123",
                user_id=USER_ID,
                count=1,
            )
        mock_connection_service.list_connections.assert_called_once_with(
            "asst_123", USER_ID
        )


class TestAnalysisServiceDeleteMockRespondents:
    """Tests for AnalysisService.delete_mock_respondents."""

    @pytest.fixture
    def mock_services(self):
        asst = MagicMock()
        asst.get_assistant = AsyncMock()
        conv = MagicMock()
        conv.delete_mock_conversations_for_assistant = AsyncMock(return_value=3)
        return asst, conv

    @pytest.fixture
    def service(self, mock_services):
        asst, conv = mock_services
        return AnalysisService(
            assistant_service=asst,
            conversations_service=conv,
        )

    @pytest.mark.asyncio
    async def test_delete_mock_respondents_returns_deleted_count(self, service, mock_services):
        _, conv_svc = mock_services
        result = await service.delete_mock_respondents("asst_123", USER_ID)
        assert result["deleted"] == 3
        conv_svc.delete_mock_conversations_for_assistant.assert_called_once_with("asst_123")

    @pytest.mark.asyncio
    async def test_delete_mock_respondents_verifies_ownership(self, service, mock_services):
        asst, _ = mock_services
        await service.delete_mock_respondents("asst_123", USER_ID)
        asst.get_assistant.assert_called_once_with("asst_123", USER_ID)


class TestAnalysisServiceDefaults:
    """Tests for default instances."""
    
    def test_creates_default_services(self):
        service = AnalysisService()
        
        from app.modules.assistants.service import AssistantService
        from app.modules.connections.service import ConnectionService
        from app.modules.conversations.service import ConversationsService
        from app.modules.workflows.service import WorkflowService
        
        assert isinstance(service.assistant_service, AssistantService)
        assert isinstance(service.conversations_service, ConversationsService)
        assert isinstance(service.workflow_service, WorkflowService)
        assert isinstance(service.connection_service, ConnectionService)
