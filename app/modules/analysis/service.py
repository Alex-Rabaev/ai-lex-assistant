"""Analysis service for managing analysis configuration, snapshots, and analytics.

Provides business logic for:
- Analysis configuration (read, update, auto-generate)
- Snapshot management (create, list, get)
- Respondent analytics (analytic_meta)

Uses AssistantService, ConversationsService, WorkflowService
for data access (Services Boundary principle).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.modules.analysis.schemas.config import (
    AnalysisConfig,
    AnalysisFramework,
    CategoryConfig,
    OutputConfig,
    TagConfig,
    dump_analysis_config,
    parse_analysis_config,
)
from bson import ObjectId

from app.config import config as app_config
from app.modules.assistants.service import AssistantService
from app.modules.connections.service import ConnectionService
from app.modules.conversations.service import ConversationsService
from app.modules.workflows.models.execution import WorkflowExecution
from app.modules.workflows.models.params import SnapshotInput
from app.modules.workflows.service import WorkflowService
from app.modules.analysis.mock_generator import generate_mock_dialogues

logger = logging.getLogger(__name__)

# Key in Assistant.metadata where analysis config is stored
ANALYSIS_CONFIG_KEY = "analysis_config"

# Prompt for auto-generating analysis categories
GENERATE_CONFIG_PROMPT = """You are an expert survey analyst. Based on the survey goals and questions below, generate an analysis framework.

Survey Goal: {survey_goal}

Survey Questions/Topics: {survey_questions}

Generate a JSON object with the following structure:
{{
    "categories": [
        {{
            "name": "Category Name",
            "description": "What this category measures",
            "scoring_type": "scale",
            "min_score": 1,
            "max_score": 5
        }}
    ],
    "tags": [
        {{
            "name": "Tag Name",
            "extraction": "auto",
            "description": "What to extract"
        }}
    ],
    "custom_questions": [
        "A business question to answer about each respondent"
    ]
}}

Rules:
- Generate 3-7 scoring categories relevant to the survey goals
- Generate 2-5 tags for respondent categorization
- Generate 2-4 custom business questions
- Use "scale" scoring (1-5) for subjective assessments
- Use "categorical" for discrete options
- Use "numeric" for quantitative values
- Keep descriptions clear and actionable

Return ONLY the JSON object, no other text."""


class AnalysisService:
    """Service for analysis configuration, snapshots, and analytics.
    
    Manages:
    - Analysis config in Assistant.metadata["analysis_config"]
    - Snapshots via WorkflowService (Temporal)
    - Respondent analytics in Conversation.analytic_meta
    
    All methods require user_id for access control.
    """
    
    def __init__(
        self,
        assistant_service: Optional[AssistantService] = None,
        conversations_service: Optional[ConversationsService] = None,
        workflow_service: Optional[WorkflowService] = None,
        connection_service: Optional[ConnectionService] = None
    ):
        """Initialize service.
        
        Args:
            assistant_service: Optional AssistantService instance
            conversations_service: Optional ConversationsService instance
            workflow_service: Optional WorkflowService instance
            connection_service: Optional ConnectionService instance (for mock respondents)
        """
        self.assistant_service = assistant_service or AssistantService()
        self.conversations_service = conversations_service or ConversationsService()
        self.workflow_service = workflow_service or WorkflowService()
        self.connection_service = connection_service or ConnectionService()
    
    async def get_config(
        self,
        assistant_id: str,
        user_id: str
    ) -> AnalysisConfig:
        """Get analysis config for assistant.
        
        Returns default config if not set.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            
        Returns:
            AnalysisConfig (validated)
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        assistant = await self.assistant_service.get_assistant(assistant_id, user_id)
        
        raw_config = assistant.metadata.get(ANALYSIS_CONFIG_KEY) if assistant.metadata else None
        config = parse_analysis_config(raw_config)
        
        if config is None:
            config = AnalysisConfig()
        
        return config
    
    async def update_config(
        self,
        assistant_id: str,
        user_id: str,
        config: AnalysisConfig
    ) -> AnalysisConfig:
        """Update analysis config for assistant.
        
        Validates ownership, then saves config to Assistant.metadata.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            config: Validated AnalysisConfig
            
        Returns:
            Updated AnalysisConfig
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        # Verify ownership
        await self.assistant_service.get_assistant(assistant_id, user_id)
        
        # Set last_updated_at
        config.last_updated_at = datetime.now(timezone.utc)
        
        # Serialize and save
        config_data = dump_analysis_config(config)
        
        await self.assistant_service.update_metadata_field_internal(
            assistant_id,
            ANALYSIS_CONFIG_KEY,
            config_data
        )
        
        logger.info(f"Updated analysis config for assistant {assistant_id}")
        return config
    
    async def generate_config(
        self,
        assistant_id: str,
        user_id: str,
        llm_callable=None
    ) -> AnalysisFramework:
        """Auto-generate analysis framework from survey goals.
        
        Loads assistant data, extracts survey goals, calls LLM
        to generate suggested categories, tags, and questions.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            llm_callable: Async callable for LLM (for dependency injection/testing).
                          Signature: async (prompt: str) -> str
            
        Returns:
            Suggested AnalysisFramework
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
        """
        assistant = await self.assistant_service.get_assistant(assistant_id, user_id)
        
        # Get assistant_goal from analysis config
        raw_config = assistant.metadata.get(ANALYSIS_CONFIG_KEY) if assistant.metadata else None
        config = parse_analysis_config(raw_config)
        
        assistant_goal = config.assistant_goal if config else None
        
        if not assistant_goal:
            raise ValueError(
                "assistant_goal must be set in analysis config before generating. "
                "Update the analysis config with an assistant_goal first."
            )
        
        # Get step data for additional context
        survey_questions = ""
        try:
            steps = await self.assistant_service.get_steps_internal(assistant_id)
            for step in steps:
                if step.step_key == "questionnaire" and step.metadata:
                    survey_questions = step.metadata.get("specific_questions", "")
        except Exception as e:
            logger.warning(f"Could not load steps for assistant {assistant_id}: {e}")
        
        # Build prompt
        prompt = GENERATE_CONFIG_PROMPT.format(
            survey_goal=assistant_goal,
            survey_questions=survey_questions or "Not specified"
        )
        
        # Call LLM
        if llm_callable is None:
            logger.warning("No LLM callable provided, returning empty framework")
            return AnalysisFramework()
        
        try:
            response_text = await llm_callable(prompt)
            parsed = json.loads(response_text)
            
            framework = AnalysisFramework(
                categories=[CategoryConfig(**c) for c in parsed.get("categories", [])],
                tags=[TagConfig(**t) for t in parsed.get("tags", [])],
                custom_questions=parsed.get("custom_questions", [])
            )
            
            logger.info(
                f"Generated analysis framework for assistant {assistant_id}: "
                f"{len(framework.categories)} categories, "
                f"{len(framework.tags)} tags, "
                f"{len(framework.custom_questions)} questions"
            )
            
            return framework
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return AnalysisFramework()
        except Exception as e:
            logger.error(f"Failed to generate analysis config: {e}")
            raise
    
    async def get_suggestions(
        self,
        assistant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get suggestions for analysis config setup.
        
        Returns hints for the frontend based on current state:
        - Whether config needs to be created
        - Whether config needs to be updated (goals changed)
        - Whether config is ready for snapshot
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            
        Returns:
            Dict with suggestion flags and messages
        """
        assistant = await self.assistant_service.get_assistant(assistant_id, user_id)
        
        raw_config = assistant.metadata.get(ANALYSIS_CONFIG_KEY) if assistant.metadata else None
        config = parse_analysis_config(raw_config)
        
        suggestions: Dict[str, Any] = {
            "has_config": config is not None,
            "config_enabled": config.enabled if config else False,
            "has_categories": bool(config and config.framework.categories),
            "suggestions": []
        }
        
        # No config at all
        if config is None:
            suggestions["suggestions"].append({
                "type": "create_config",
                "message": "Analysis config not set. Generate categories from survey goals.",
                "action": "POST /analysis-config/generate"
            })
            return suggestions
        
        # Config exists but no categories
        if not config.framework.categories:
            suggestions["suggestions"].append({
                "type": "generate_categories",
                "message": "No scoring categories configured. Generate from survey goals.",
                "action": "POST /analysis-config/generate"
            })
        
        # Config not enabled
        if not config.enabled:
            suggestions["suggestions"].append({
                "type": "enable_config",
                "message": "Analysis is configured but not enabled.",
                "action": "PUT /analysis-config"
            })
        
        # Check if assistant_goal is set in config
        if not (config and config.assistant_goal):
            suggestions["suggestions"].append({
                "type": "add_assistant_goal",
                "message": "No assistant goal set. Define what you want to learn from respondents.",
                "action": "PUT /analysis-config with assistant_goal"
            })
        
        return suggestions
    
    # ==================== Snapshot Methods ====================
    
    async def create_snapshot(
        self,
        assistant_id: str,
        user_id: str,
        force_recalculate: bool = False,
        include_partial: bool = True,
        include_mock: bool = False,
        version_name: Optional[str] = None
    ) -> str:
        """Create a new analysis snapshot.

        Starts SnapshotWorkflow via Temporal through WorkflowService.
        Deduplication is handled natively by Temporal Workflow ID.

        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            force_recalculate: Force recalculation of all profiles
            include_partial: Include partial conversations
            include_mock: Include mock respondents (test snapshot). If False, only real.
            version_name: Optional user-defined version name

        Returns:
            execution_id (str)
        """
        assistant = await self.assistant_service.get_assistant(assistant_id, user_id)

        # Read analysis_language from AnalysisConfig stored in assistant metadata
        analysis_language = "English"
        if assistant.metadata:
            raw_config = assistant.metadata.get(ANALYSIS_CONFIG_KEY)
            if isinstance(raw_config, dict):
                analysis_language = raw_config.get("analysis_language", "English") or "English"

        unique_suffix = str(uuid4())[:8]
        workflow_id = f"snapshot-{assistant_id}-{unique_suffix}"

        # start_workflow creates MongoDB record, injects its ObjectId
        # into input_data.execution_id, then starts Temporal workflow
        execution_id = await self.workflow_service.start_workflow(
            workflow_name="SnapshotWorkflow",
            workflow_id=workflow_id,
            workflow_type="analysis_snapshot",
            input_data=SnapshotInput(
                assistant_id=assistant_id,
                execution_id="",  # Injected by start_workflow after MongoDB create
                force_recalculate=force_recalculate,
                include_partial=include_partial,
                include_mock=include_mock,
                analysis_language=analysis_language,
            ),
            task_queue=app_config.TEMPORAL_TASK_QUEUE,
            user_id=user_id,
            payload={
                "assistant_id": assistant_id,
                "force_recalculate": force_recalculate,
                "include_partial": include_partial,
                "include_mock": include_mock,
                "analysis_language": analysis_language,
            },
            version_name=version_name,
        )
        
        logger.info(
            f"Started snapshot workflow: "
            f"assistant_id={assistant_id}, execution_id={execution_id}"
        )
        return execution_id
    
    async def get_snapshots(
        self,
        assistant_id: str,
        user_id: str,
        include_archived: bool = False
    ) -> List[WorkflowExecution]:
        """Get all snapshots for assistant.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            include_archived: Include archived snapshots
            
        Returns:
            List of WorkflowExecution records
        """
        await self.assistant_service.get_assistant(assistant_id, user_id)
        
        filters: Dict[str, Any] = {
            "payload": {"assistant_id": assistant_id}
        }
        
        return await self.workflow_service.get_executions(
            workflow_type="analysis_snapshot",
            filters=filters
        )
    
    async def get_snapshot(
        self,
        execution_id: str,
        user_id: str
    ) -> Optional[WorkflowExecution]:
        """Get snapshot by execution ID.
        
        Args:
            execution_id: Execution ID
            user_id: User ID for access control
            
        Returns:
            WorkflowExecution or None
        """
        execution = await self.workflow_service.get_execution(execution_id)
        
        if execution and execution.payload.get("assistant_id"):
            try:
                await self.assistant_service.get_assistant(
                    execution.payload["assistant_id"], user_id
                )
            except Exception:
                return None
        
        return execution
    
    # ==================== Analytics Methods ====================
    
    async def get_analytic_meta(
        self,
        conversation_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get analytic_meta for a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID for access control
            
        Returns:
            AnalyticMeta dict or None
        """
        conversation = await self.conversations_service.get_conversation(conversation_id)
        
        if not conversation:
            return None
        
        try:
            await self.assistant_service.get_assistant(
                str(conversation.assistant_id), user_id
            )
        except Exception:
            return None

        return {
            "analytic_meta": conversation.analytic_meta,
            "is_mock": getattr(conversation, "is_mock", False),
        }

    async def get_analytic_meta_by_assistant(
        self,
        assistant_id: str,
        user_id: str,
        include_mock: Optional[bool] = None,
        sufficient_data_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get all analytic_meta for assistant's conversations.

        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            include_mock: If False, only real respondents. If True, only mock. If None, all.
            sufficient_data_only: If True, only return profiles with sufficient_data=True.

        Returns:
            List of {conversation_id, analytic_meta, is_mock, sufficient_data} dicts
        """
        await self.assistant_service.get_assistant(assistant_id, user_id)

        conversations = await self.conversations_service.get_conversations_by_assistant(
            assistant_id, include_mock=None
        )

        results = []
        for conv in conversations:
            if include_mock is not None and conv.is_mock != include_mock:
                continue
            if conv.analytic_meta is None:
                continue
            sd = conv.analytic_meta.get("sufficient_data", True) if isinstance(conv.analytic_meta, dict) else True
            if sufficient_data_only and not sd:
                continue
            results.append({
                "conversation_id": str(conv.id),
                "analytic_meta": conv.analytic_meta,
                "is_mock": getattr(conv, "is_mock", False),
                "sufficient_data": sd,
            })

        return results
    
    # ==================== Mock Respondents ====================
    
    async def generate_mock_respondents(
        self,
        assistant_id: str,
        user_id: str,
        count: int = 10,
        language: str = "en",
        include_abandoned: bool = True
    ) -> Dict[str, Any]:
        """Create mock respondents (conversations with message history) for testing snapshots.
        
        Uses template-based dialogue generation. Requires assistant to have at least
        one connection (for conversation creation).
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control
            count: Number of mock respondents to create
            language: Language code for dialogues (reserved for localization)
            include_abandoned: If True, some respondents will be in ABANDONED state
            
        Returns:
            Dict with "created" (int) and "conversation_ids" (list of str)
            
        Raises:
            AssistantNotFoundError: If assistant not found or no access
            ValueError: If assistant has no connections
        """
        assistant = await self.assistant_service.get_assistant(assistant_id, user_id)

        connections = await self.connection_service.list_connections(
            assistant_id, user_id
        )
        if not connections:
            raise ValueError(
                "Assistant must have at least one connection to create mock respondents. "
                "Create a connection (e.g. WebChat) for the assistant first."
            )
        connection_id = str(connections[0].id)

        # Load enabled steps ordered by order_no for full dialogue generation
        steps_data: List[Dict[str, Any]] = []
        try:
            all_steps = await self.assistant_service.get_steps_internal(assistant_id)
            steps_data = [
                {
                    "step_key": s.step_key,
                    "enabled": s.enabled,
                    "order_no": s.order_no,
                    "metadata": s.metadata or {},
                }
                for s in all_steps
                if s.enabled
            ]
        except Exception as e:
            logger.warning(f"Could not load steps for mock generation: {e}")

        # Generate dialogues via LLM (primary) or fallback to templates
        from app.modules.analysis.mock_generator import dialogues_to_tuples, generate_mock_dialogues
        raw_dialogues: List[Dict[str, Any]] = []
        if steps_data:
            from app.modules.analysis.llm import generate_full_mock_dialogues_llm
            raw_dialogues = await generate_full_mock_dialogues_llm(
                steps=steps_data,
                count=count,
                include_partial=include_abandoned,
            )

        if not raw_dialogues:
            # Fallback: template-based using questionnaire questions only
            questions: List[str] = []
            for s in steps_data:
                if s["step_key"] == "questionnaire":
                    meta = s["metadata"]
                    ql = meta.get("questions_list")
                    if ql and isinstance(ql, list):
                        questions = [q.strip() for q in ql if isinstance(q, str) and q.strip()]
                    else:
                        raw = meta.get("specific_questions", "")
                        questions = [q.strip() for q in raw.splitlines() if q.strip()]
                    break
            from app.modules.analysis.llm import generate_mock_answers_llm
            question_answers = await generate_mock_answers_llm(questions) if questions else {}
            fallback_context = {"questions": questions, "question_answers": question_answers} if questions else None
            legacy = generate_mock_dialogues(
                count=count,
                language=language,
                include_abandoned=include_abandoned,
                assistant_context=fallback_context,
            )
            raw_dialogues = [
                {"respondent_name": f"Mock User {i+1}", "final_state": stage,
                 "messages": [{"role": r, "content": c, "state": st} for r, c, st in msgs]}
                for i, (stage, msgs) in enumerate(legacy)
            ]

        named_dialogues = dialogues_to_tuples(raw_dialogues)
        conversation_ids: List[str] = []
        for idx, (mock_name, stage, messages) in enumerate(named_dialogues):
            conv_id = await self.conversations_service.create_mock_conversation(
                assistant_id=assistant_id,
                connection_id=connection_id,
                stage=stage,
                messages=messages,
                mock_name=mock_name,
                respondent_index=idx + 1,
            )
            conversation_ids.append(conv_id)
        
        logger.info(
            f"Created {len(conversation_ids)} mock respondents for assistant {assistant_id}"
        )
        return {
            "created": len(conversation_ids),
            "conversation_ids": conversation_ids,
        }

    async def delete_mock_respondents(
        self,
        assistant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Delete all mock respondents (conversations with is_mock=True) for an assistant.

        Args:
            assistant_id: Assistant ID
            user_id: User ID for access control

        Returns:
            Dict with "deleted" (int) — number of conversations removed
        """
        await self.assistant_service.get_assistant(assistant_id, user_id)
        deleted = await self.conversations_service.delete_mock_conversations_for_assistant(
            assistant_id
        )
        return {"deleted": deleted}
