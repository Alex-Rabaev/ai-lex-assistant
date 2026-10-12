"""Service for Survey Agent step configuration.

This service provides:
- Default steps for new Survey assistants
- Validation for step updates (mandatory steps, metadata)
- Step-specific configuration validation
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from app.modules.agents.survey_agent.config import (
    SurveyStepKey,
    MANDATORY_STEPS,
    QuestionnaireConfig,
    validate_questionnaire_config
)

logger = logging.getLogger(__name__)


class SurveyAgentService:
    """Service for Survey Agent step operations."""
    
    def get_default_steps(self) -> List[Dict[str, Any]]:
        """Get default steps for a new Survey assistant.
        
        Returns list of step definitions (without assistant_id).
        Steps:
        - LANG (order 1, enabled by default)
        - INTRO (order 2, enabled, mandatory)
        - PROFILE (order 3, disabled by default)
        - QUESTIONNAIRE (order 4, enabled, mandatory)
        - ADDITIONAL_INFO (order 5, disabled by default)
        - CLOSING (order 6, enabled, mandatory)
        
        Returns:
            List of step dicts ready for insertion
        """
        now = datetime.now(timezone.utc)
        
        return [
            {
                "step_key": SurveyStepKey.LANG.value,
                "order_no": 1,
                "enabled": True,
                "metadata": {},
                "created_at": now,
                "updated_at": now
            },
            {
                "step_key": SurveyStepKey.INTRO.value,
                "order_no": 2,
                "enabled": True,
                "metadata": {},
                "created_at": now,
                "updated_at": now
            },
            {
                "step_key": SurveyStepKey.PROFILE.value,
                "order_no": 3,
                "enabled": False,  # Optional, disabled by default
                "metadata": {},
                "created_at": now,
                "updated_at": now
            },
            {
                "step_key": SurveyStepKey.QUESTIONNAIRE.value,
                "order_no": 4,
                "enabled": True,
                "metadata": {
                    # Default: goal-driven survey
                    "survey_goal": "Conduct a survey to understand the respondent's needs and preferences."
                },
                "created_at": now,
                "updated_at": now
            },
            {
                "step_key": SurveyStepKey.ADDITIONAL_INFO.value,
                "order_no": 5,
                "enabled": False,  # Optional, disabled by default
                "metadata": {},
                "created_at": now,
                "updated_at": now
            },
            {
                "step_key": SurveyStepKey.CLOSING.value,
                "order_no": 6,
                "enabled": True,
                "metadata": {},
                "created_at": now,
                "updated_at": now
            }
        ]
    
    def validate_step_can_be_disabled(self, step_key: str) -> None:
        """Validate that a step can be disabled.
        
        Args:
            step_key: Step key to check
            
        Raises:
            ValueError: If step is mandatory and cannot be disabled
        """
        try:
            survey_step = SurveyStepKey(step_key)
            if survey_step in MANDATORY_STEPS:
                raise ValueError(
                    f"Step '{step_key}' is mandatory and cannot be disabled"
                )
        except ValueError as e:
            if "mandatory" in str(e):
                raise
            # Not a survey step key - allow disabling
            pass
    
    def validate_step_metadata(
        self, 
        step_key: str, 
        metadata: Dict[str, Any],
        is_enabled: bool = True
    ) -> None:
        """Validate step metadata based on step type.
        
        Args:
            step_key: Step key
            metadata: Metadata to validate
            is_enabled: Whether step is enabled
            
        Raises:
            ValueError: If metadata is invalid
        """
        try:
            survey_step = SurveyStepKey(step_key)
        except ValueError:
            # Not a survey step - no validation needed
            return
        
        # LANG step: requires default_language when disabled
        if survey_step == SurveyStepKey.LANG and not is_enabled:
            default_language = metadata.get("default_language")
            if not default_language or not default_language.strip():
                raise ValueError(
                    "Step 'lang' requires 'default_language' in metadata when disabled"
                )
        
        # QUESTIONNAIRE step: requires questions_list, specific_questions, or survey_goal
        if survey_step == SurveyStepKey.QUESTIONNAIRE and is_enabled:
            config = QuestionnaireConfig(
                intro_prompt=metadata.get("intro_prompt"),
                questions_list=metadata.get("questions_list"),
                specific_questions=metadata.get("specific_questions"),
                survey_goal=metadata.get("survey_goal")
            )
            validate_questionnaire_config(config)
    
    def merge_step_metadata(
        self,
        existing_metadata: Optional[Dict[str, Any]],
        new_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge new metadata with existing.
        
        Args:
            existing_metadata: Current metadata (may be None)
            new_metadata: New metadata to merge
            
        Returns:
            Merged metadata dict
        """
        if not existing_metadata:
            return new_metadata
        return {**existing_metadata, **new_metadata}
    
    def process_step_update(
        self,
        existing_step,  # AssistantStep
        new_enabled: Optional[bool],
        new_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process step update: validate and return what to save.
        
        Args:
            existing_step: Current step from DB
            new_enabled: New enabled value (None = no change)
            new_metadata: New metadata to merge (None = no change)
            
        Returns:
            Dict with fields to update in DB
            
        Raises:
            ValueError: If validation fails
        """
        update_doc: Dict[str, Any] = {}
        
        # Determine final enabled state
        final_enabled = new_enabled if new_enabled is not None else existing_step.enabled
        
        # Check if trying to disable a mandatory step
        if new_enabled is False:
            self.validate_step_can_be_disabled(existing_step.step_key)
        
        if new_enabled is not None:
            update_doc["enabled"] = new_enabled
        
        # Process metadata
        if new_metadata is not None:
            # Merge with existing
            final_metadata = self.merge_step_metadata(
                existing_step.metadata,
                new_metadata
            )
            # Validate
            self.validate_step_metadata(
                existing_step.step_key,
                final_metadata,
                is_enabled=final_enabled
            )
            update_doc["metadata"] = final_metadata
        else:
            # If only changing enabled, still validate existing metadata
            if new_enabled is not None:
                self.validate_step_metadata(
                    existing_step.step_key,
                    existing_step.metadata or {},
                    is_enabled=final_enabled
                )
        
        return update_doc

