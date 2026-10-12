"""API router for assistants module."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
import logging

from app.common.auth import get_current_admin_auth0, AdminUser
from app.modules.assistants.service import (
    AssistantService,
    AssistantNotFoundError,
    DuplicateNameError,
    InvalidStatusTransitionError
)
from app.modules.assistants.schemas import (
    CreateAssistantRequest,
    UpdateAssistantRequest,
    AssistantResponse,
    AssistantListResponse,
    CloneAssistantRequest
)
from app.modules.assistants.models import AssistantStatus, AssistantType, FollowUpConfig
from app.config import config
from app.modules.assistants.steps.router import router as steps_router
from app.modules.agents.survey_agent.config import get_survey_step_schema

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["assistants"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - No admin access"}
    }
)


async def get_assistant_service() -> AssistantService:
    """Get assistant service instance."""
    return AssistantService()


@router.get(
    "",
    response_model=AssistantListResponse,
    summary="List assistants",
    description="Get a paginated list of assistants for the organization"
)
async def list_assistants(
    status: Optional[AssistantStatus] = Query(None, description="Filter by status"),
    type: Optional[AssistantType] = Query(None, description="Filter by type"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of items to return"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> AssistantListResponse:
    """List all assistants for the user."""
    # user_id is email from token
    user_id = current_admin.email
    
    # Apply filters
    assistants, total = await service.list_assistants(
        user_id=user_id,
        status=status,
        skip=skip,
        limit=limit
    )
    
    # Convert to response format
    items = [
        AssistantResponse(
            id=str(assistant.id),
            org_id=assistant.org_id,
            owner_user_id=assistant.owner_user_id,
            name=assistant.name,
            description=assistant.description,
            type=assistant.type,
            status=assistant.status,
            metadata=assistant.metadata or {},
            created_at=assistant.created_at,
            updated_at=assistant.updated_at
        )
        for assistant in assistants
    ]
    
    return AssistantListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.post(
    "",
    response_model=AssistantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create assistant",
    description="Create a new assistant"
)
async def create_assistant(
    data: CreateAssistantRequest,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> AssistantResponse:
    """Create a new assistant."""
    # org_id from config, user_id from token (email)
    org_id = config.DEFAULT_ORG_ID
    user_id = current_admin.email
    
    try:
        assistant = await service.create_assistant(
            org_id=org_id,
            user_id=user_id,
            data=data
        )
        
        return AssistantResponse(
            id=str(assistant.id),
            org_id=assistant.org_id,
            owner_user_id=assistant.owner_user_id,
            name=assistant.name,
            description=assistant.description,
            type=assistant.type,
            status=assistant.status,
            metadata=assistant.metadata or {},
            created_at=assistant.created_at,
            updated_at=assistant.updated_at
        )
        
    except DuplicateNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.get(
    "/{assistant_id}",
    response_model=AssistantResponse,
    summary="Get assistant",
    description="Get a specific assistant by ID"
)
async def get_assistant(
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> AssistantResponse:
    """Get assistant by ID."""
    # user_id is email from token
    user_id = current_admin.email
    
    try:
        assistant = await service.get_assistant(
            assistant_id=assistant_id,
            user_id=user_id
        )
        
        return AssistantResponse(
            id=str(assistant.id),
            org_id=assistant.org_id,
            owner_user_id=assistant.owner_user_id,
            name=assistant.name,
            description=assistant.description,
            type=assistant.type,
            status=assistant.status,
            metadata=assistant.metadata or {},
            created_at=assistant.created_at,
            updated_at=assistant.updated_at
        )
        
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )


@router.put(
    "/{assistant_id}",
    response_model=AssistantResponse,
    summary="Update assistant",
    description="Update an existing assistant"
)
async def update_assistant(
    data: UpdateAssistantRequest,
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> AssistantResponse:
    """Update assistant."""
    # user_id is email from token
    user_id = current_admin.email
    
    try:
        assistant = await service.update_assistant(
            assistant_id=assistant_id,
            user_id=user_id,
            data=data
        )
        
        return AssistantResponse(
            id=str(assistant.id),
            org_id=assistant.org_id,
            owner_user_id=assistant.owner_user_id,
            name=assistant.name,
            description=assistant.description,
            type=assistant.type,
            status=assistant.status,
            metadata=assistant.metadata or {},
            created_at=assistant.created_at,
            updated_at=assistant.updated_at
        )
        
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )
    except DuplicateNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.delete(
    "/{assistant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete assistant",
    description="Delete an assistant and all its steps"
)
async def delete_assistant(
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> None:
    """Delete assistant and all related data."""
    # user_id is email from token
    user_id = current_admin.email
    
    try:
        await service.delete_assistant(
            assistant_id=assistant_id,
            user_id=user_id
        )
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )


@router.post(
    "/{assistant_id}/clone",
    response_model=AssistantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone assistant",
    description="Create a copy of an existing assistant"
)
async def clone_assistant(
    data: CloneAssistantRequest,
    assistant_id: str = Path(..., description="Assistant ID to clone"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> AssistantResponse:
    """Clone an existing assistant."""
    # org_id from config, user_id from token (email)
    org_id = config.DEFAULT_ORG_ID
    user_id = current_admin.email
    
    try:
        cloned = await service.clone_assistant(
            assistant_id=assistant_id,
            user_id=user_id,
            org_id=org_id,
            clone_data=data
        )
        
        return AssistantResponse(
            id=str(cloned.id),
            org_id=cloned.org_id,
            owner_user_id=cloned.owner_user_id,
            name=cloned.name,
            description=cloned.description,
            type=cloned.type,
            status=cloned.status,
            metadata=cloned.metadata or {},
            created_at=cloned.created_at,
            updated_at=cloned.updated_at
        )
        
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )
    except DuplicateNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error cloning assistant {assistant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while cloning the assistant"
        )


@router.get(
    "/{assistant_id}/follow-up-config",
    response_model=FollowUpConfig,
    summary="Get follow-up config",
    description="Get follow-up reminder configuration for the assistant"
)
async def get_follow_up_config(
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> FollowUpConfig:
    """Get follow-up configuration (returns defaults if not set)."""
    try:
        return await service.get_follow_up_config(
            assistant_id=assistant_id,
            user_id=current_admin.email
        )
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )


@router.put(
    "/{assistant_id}/follow-up-config",
    response_model=FollowUpConfig,
    summary="Update follow-up config",
    description="Update follow-up reminder configuration for the assistant"
)
async def update_follow_up_config(
    data: FollowUpConfig,
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AssistantService = Depends(get_assistant_service)
) -> FollowUpConfig:
    """Update follow-up configuration."""
    try:
        return await service.update_follow_up_config(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            config=data
        )
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )


@router.get(
    "/types/{assistant_type}/step-schema",
    summary="Get step schema for assistant type",
    description="Get JSON schema describing step configuration for a specific assistant type. Used by frontend to render step configuration UI."
)
async def get_step_schema(
    assistant_type: AssistantType = Path(..., description="Assistant type (survey, faq, support)"),
    current_admin: AdminUser = Depends(get_current_admin_auth0)
) -> dict:
    """Get step schema for assistant type.
    
    Returns a JSON schema describing:
    - All steps for the assistant type
    - Fields for each step (type, label, placeholder, validation)
    - Global settings for the assistant type
    - Validation rules
    
    Frontend uses this to dynamically render step configuration UI.
    """
    if assistant_type == AssistantType.SURVEY:
        return get_survey_step_schema()
    
    # For other types, return empty schema (not implemented yet)
    return {
        "assistant_type": assistant_type.value,
        "message": f"Step schema for '{assistant_type.value}' type is not implemented yet",
        "global_settings": {},
        "steps": []
    }


# Include steps subrouter - provides endpoints for managing assistant steps
router.include_router(
    steps_router,
    prefix="",  # Paths already include /assistants/{id}/steps
)
