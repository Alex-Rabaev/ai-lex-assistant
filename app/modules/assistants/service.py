"""Service layer for assistant business logic."""

from typing import Any, List, Optional
import logging

from app.modules.assistants.models import Assistant, AssistantStatus, AssistantStep, FollowUpConfig
from app.modules.assistants.repository import AssistantRepository
from app.modules.assistants.schemas import (
    CreateAssistantRequest,
    UpdateAssistantRequest,
    CloneAssistantRequest
)

logger = logging.getLogger(__name__)


class AssistantNotFoundError(Exception):
    """Raised when assistant is not found."""
    pass


class DuplicateNameError(Exception):
    """Raised when assistant name already exists."""
    pass


class InvalidStatusTransitionError(Exception):
    """Raised when status transition is not allowed."""
    pass


class AssistantService:
    """Service for assistant business logic."""
    
    STATUS_TRANSITIONS = {
        AssistantStatus.ACTIVE: [AssistantStatus.INACTIVE],
        AssistantStatus.INACTIVE: [AssistantStatus.ACTIVE],
    }
    
    def __init__(self):
        """Initialize service with repository."""
        self._repository = AssistantRepository()
    
    async def create_assistant(
        self,
        org_id: str,
        user_id: str,
        data: CreateAssistantRequest
    ) -> Assistant:
        """Create assistant with default steps.
        
        Business rules:
        - Name must be unique per user
        - Status starts as 'draft'
        - 6 default steps automatically created for Survey type
        
        Args:
            org_id: Organization ID (from config)
            user_id: User ID (email) of the creator
            data: Assistant creation data
            
        Returns:
            Created assistant
            
        Raises:
            DuplicateNameError: If name already exists for this user
        """
        logger.info(f"Creating assistant for org={org_id}, user={user_id}, name={data.name}")
        
        # Check name uniqueness for this user
        if await self._repository.exists_by_name(user_id, data.name):
            raise DuplicateNameError(f"Assistant with name '{data.name}' already exists")
        
        # Create assistant
        assistant = await self._repository.create(org_id, user_id, data)
        
        # Create default steps for the assistant
        from app.modules.assistants.steps.service import StepService
        step_service = StepService()
        await step_service.create_default_steps(str(assistant.id))
        
        logger.info(f"Created assistant id={assistant.id} with default steps")
        return assistant
    
    async def get_assistant(self, assistant_id: str, user_id: str) -> Assistant:
        """Get assistant by ID with user ownership check.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            
        Returns:
            Assistant model
            
        Raises:
            AssistantNotFoundError: If not found or no access
        """
        assistant = await self._repository.get_by_id(assistant_id, user_id)
        
        if not assistant:
            raise AssistantNotFoundError(f"Assistant {assistant_id} not found")
        
        return assistant
    
    async def find_enabled_follow_up_assistant_ids(self) -> List[str]:
        """IDs of active assistants with follow_up_config.enabled (internal / workers)."""
        return await self._repository.find_enabled_follow_up_assistant_ids()

    async def get_assistant_internal(self, assistant_id: str) -> Assistant:
        """Get assistant by ID without access control (for internal use by workers/services).
        
        This method is used by internal services like ConversationsService
        that don't have user context but need to access assistants.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            Assistant model
            
        Raises:
            AssistantNotFoundError: If not found
        """
        assistant = await self._repository.get_by_id_internal(assistant_id)
        
        if not assistant:
            raise AssistantNotFoundError(f"Assistant {assistant_id} not found")
        
        return assistant
    
    async def update_metadata_field_internal(
        self,
        assistant_id: str,
        field_key: str,
        field_value: Any
    ) -> Assistant:
        """Update a single field within Assistant.metadata (internal use).
        
        Args:
            assistant_id: Assistant ID
            field_key: Key within metadata (e.g., "analysis_config")
            field_value: Value to set
            
        Returns:
            Updated Assistant
            
        Raises:
            AssistantNotFoundError: If not found
        """
        result = await self._repository.update_metadata_field(
            assistant_id, field_key, field_value
        )
        
        if not result:
            raise AssistantNotFoundError(f"Assistant {assistant_id} not found")
        
        logger.info(f"Updated metadata.{field_key} for assistant {assistant_id}")
        return result
    
    async def get_steps_internal(self, assistant_id: str) -> List[AssistantStep]:
        """Get all steps for assistant without access control (for internal use).
        
        Used by agents to get step configurations.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            List of AssistantStep ordered by order_no
        """
        return await self._repository.get_steps_by_assistant(assistant_id)
    
    async def get_step_by_order(self, assistant_id: str, order_no: int) -> Optional[AssistantStep]:
        """Get step by order_no (for internal use).
        
        Args:
            assistant_id: Assistant ID
            order_no: Step order number
            
        Returns:
            AssistantStep or None if not found
        """
        return await self._repository.get_step_by_order(assistant_id, order_no)
    
    async def list_assistants(
        self,
        user_id: str,
        status: Optional[AssistantStatus] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Assistant], int]:
        """List assistants for user.
        
        Args:
            user_id: User ID (email) - owner of assistants
            status: Optional status filter
            skip: Pagination offset
            limit: Maximum items
            
        Returns:
            Tuple of (assistants list, total count)
        """
        return await self._repository.find_by_user(user_id, status, skip, limit)
    
    async def update_assistant(
        self,
        assistant_id: str,
        user_id: str,
        data: UpdateAssistantRequest
    ) -> Assistant:
        """Update assistant with validation.
        
        Business rules:
        - Name uniqueness check if changed
        - Status transition validation
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            data: Update data
            
        Returns:
            Updated assistant
            
        Raises:
            AssistantNotFoundError: If not found
            DuplicateNameError: If new name already exists
            InvalidStatusTransitionError: If status transition not allowed
        """
        # Get current assistant
        current = await self.get_assistant(assistant_id, user_id)
        
        # Check name uniqueness if changed
        if data.name and data.name != current.name:
            if await self._repository.exists_by_name(user_id, data.name, assistant_id):
                raise DuplicateNameError(f"Assistant with name '{data.name}' already exists")
        
        # Validate status transition
        if data.status and data.status != current.status:
            self._validate_status_transition(current.status, data.status)

        # Update
        updated = await self._repository.update(assistant_id, user_id, data)

        if not updated:
            raise AssistantNotFoundError(f"Assistant {assistant_id} not found")

        # Deactivate WebChat connection when assistant becomes inactive
        if data.status == AssistantStatus.INACTIVE and current.status != AssistantStatus.INACTIVE:
            try:
                from app.modules.connections.vendors.webchat.connection_service import WebchatConnectionService
                webchat_service = WebchatConnectionService()
                if await webchat_service.is_webchat_enabled(assistant_id):
                    await webchat_service.disable_webchat(assistant_id, user_id)
                    logger.info(f"Disabled webchat for deactivated assistant {assistant_id}")
            except Exception as e:
                logger.warning(f"Failed to disable webchat for assistant {assistant_id}: {e}")

        logger.info(f"Updated assistant id={assistant_id}")
        return updated

    async def get_follow_up_config(self, assistant_id: str, user_id: str) -> FollowUpConfig:
        """Get follow-up config for assistant (or defaults if not set).

        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control

        Returns:
            FollowUpConfig (from assistant or defaults)

        Raises:
            AssistantNotFoundError: If not found
        """
        assistant = await self.get_assistant(assistant_id, user_id)
        return assistant.follow_up_config or FollowUpConfig()

    async def update_follow_up_config(
        self, assistant_id: str, user_id: str, config: FollowUpConfig
    ) -> FollowUpConfig:
        """Update follow-up config for assistant.

        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            config: New follow-up configuration

        Returns:
            Updated FollowUpConfig

        Raises:
            AssistantNotFoundError: If not found
        """
        updated = await self._repository.update_follow_up_config(assistant_id, user_id, config)
        if not updated:
            raise AssistantNotFoundError(f"Assistant {assistant_id} not found")
        return updated.follow_up_config or FollowUpConfig()
    
    async def delete_assistant(self, assistant_id: str, user_id: str) -> bool:
        """Delete assistant and all related data.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID (email) for access control
            
        Returns:
            True if deleted
            
        Raises:
            AssistantNotFoundError: If not found
        """
        # Check exists
        await self.get_assistant(assistant_id, user_id)
        
        # Delete
        deleted = await self._repository.delete(assistant_id, user_id)
        
        if deleted:
            logger.info(f"Deleted assistant id={assistant_id}")
        
        return deleted
    
    async def clone_assistant(
        self,
        assistant_id: str,
        user_id: str,
        org_id: str,
        clone_data: CloneAssistantRequest
    ) -> Assistant:
        """Clone existing assistant with auto-unique name and step copying.

        Args:
            assistant_id: Source assistant ID
            user_id: User ID (email) for access control
            org_id: Organization ID (from config)
            clone_data: Clone configuration

        Returns:
            Cloned assistant

        Raises:
            AssistantNotFoundError: If source not found
        """
        # Get source assistant
        source = await self.get_assistant(assistant_id, user_id)

        # Resolve base name: use provided new_name or auto-generate from source name
        if clone_data.new_name:
            base_name = clone_data.new_name
        else:
            prefix = "Copy of "
            max_base_len = 100 - len(prefix)
            base_name = f"{prefix}{source.name[:max_base_len]}"

        # Auto-increment until a unique name is found: "Copy of X", "Copy of X (2)", ...
        unique_name = base_name
        counter = 2
        while await self._repository.exists_by_name(user_id, unique_name):
            suffix = f" ({counter})"
            truncated_base = base_name[:100 - len(suffix)]
            unique_name = f"{truncated_base}{suffix}"
            counter += 1

        # Build description, truncated to model limit
        raw_description = f"Cloned from: {source.name}. {source.description or ''}".strip()
        description = raw_description[:500]

        create_data = CreateAssistantRequest(
            name=unique_name,
            description=description,
            type=source.type,
            metadata=source.metadata or {},
        )

        # Create cloned assistant record
        cloned = await self._repository.create(org_id, user_id, create_data)

        # Clone steps from source, or create default steps as fallback
        try:
            source_steps = await self._repository.get_steps_by_assistant(str(source.id)) if clone_data.clone_steps else []

            if source_steps:
                steps_data = [
                    {
                        "step_key": step.step_key,
                        "order_no": step.order_no,
                        "enabled": step.enabled,
                        "metadata": step.metadata or {}
                    }
                    for step in source_steps
                ]
                await self._repository.create_steps(cloned.id, steps_data)
            else:
                from app.modules.assistants.steps.service import StepService
                step_service = StepService()
                await step_service.create_default_steps(str(cloned.id))
        except Exception as e:
            logger.error(
                f"Failed to clone steps from assistant {assistant_id} to {cloned.id}, "
                f"rolling back cloned assistant: {e}",
                exc_info=True
            )
            await self._repository.delete_internal(str(cloned.id))
            raise

        logger.info(f"Cloned assistant id={assistant_id} to new id={cloned.id} with name='{unique_name}'")
        return cloned
    
    async def get_current_step(
        self,
        assistant_id: str,
        current_step_key: Optional[str] = None
    ) -> Optional[AssistantStep]:
        """Get current step for assistant.
        
        Args:
            assistant_id: Assistant ID
            current_step_key: Current step key from conversation state (optional)
            
        Returns:
            Current AssistantStep or first step if no key provided
            
        Raises:
            AssistantNotFoundError: If assistant not found
        """
        # Get assistant (no user_id check - internal method)
        assistant = await self._repository.get_by_id_internal(assistant_id)
        if not assistant:
            raise AssistantNotFoundError(f"Assistant {assistant_id} not found")
        
        # Get all steps
        steps = await self._repository.get_steps_by_assistant(assistant_id)
        
        if not steps:
            return None
        
        # If no step key, return first step
        if not current_step_key:
            return steps[0] if steps else None
        
        # Get step by key
        for step in steps:
            if step.step_key == current_step_key:
                return step
        
        return None
    
    def _validate_status_transition(
        self,
        current_status: AssistantStatus,
        new_status: AssistantStatus
    ) -> None:
        """Validate if status transition is allowed.
        
        Args:
            current_status: Current status
            new_status: Desired new status
            
        Raises:
            InvalidStatusTransitionError: If transition not allowed
        """
        allowed = self.STATUS_TRANSITIONS.get(current_status, [])
        
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                f"Cannot transition from {current_status.value} to {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
