"""API router for Conversations admin operations."""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status

from app.common.auth import get_current_admin_auth0, AdminUser
from app.modules.conversations.interlocutor_service import InterlocutorService
from app.modules.conversations.message_service import MessageService
from app.modules.conversations.schemas import (
    InterlocutorListQuery,
    InterlocutorListResponse,
    InterlocutorDetail,
    InterlocutorUpdate,
    MessageListQuery,
    MessageListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["conversations"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - No admin access"},
        404: {"description": "Resource not found"}
    }
)


def get_interlocutor_service() -> InterlocutorService:
    """Get interlocutor service instance."""
    return InterlocutorService()


def get_message_service() -> MessageService:
    """Get message service instance."""
    return MessageService()


# ============================================================================
# INTERLOCUTOR ENDPOINTS
# ============================================================================

@router.get(
    "/assistants/{assistant_id}/interlocutors",
    response_model=InterlocutorListResponse,
    summary="List interlocutors",
    description="Get paginated list of interlocutors for the assistant"
)
async def list_interlocutors(
    assistant_id: str = Path(..., description="Assistant ID"),
    q: Optional[str] = Query(None, description="Search in first_name, username, email"),
    stage: Optional[List[str]] = Query(None, description="Filter by stages"),
    language: Optional[List[str]] = Query(None, description="Filter by language"),
    has_email: Optional[bool] = Query(None, description="Filter by email presence"),
    date_from: Optional[str] = Query(None, description="Filter from date (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter to date (ISO format)"),
    sort: str = Query("-created_at", description="Sort field (prefix '-' for DESC)"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum items to return"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: InterlocutorService = Depends(get_interlocutor_service)
) -> InterlocutorListResponse:
    """List interlocutors for assistant with filters and pagination."""
    
    # Parse dates
    from datetime import datetime
    date_from_parsed = None
    date_to_parsed = None
    
    if date_from:
        try:
            date_from_parsed = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use ISO format."
            )
    
    if date_to:
        try:
            date_to_parsed = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use ISO format."
            )
    
    query = InterlocutorListQuery(
        q=q,
        stage=stage,
        language=language,
        has_email=has_email,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        sort=sort,
        skip=skip,
        limit=limit
    )
    
    try:
        return await service.list_interlocutors(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            query=query
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/assistants/{assistant_id}/interlocutors/{interlocutor_id}",
    response_model=InterlocutorDetail,
    summary="Get interlocutor details",
    description="Get detailed information about a specific interlocutor"
)
async def get_interlocutor(
    assistant_id: str = Path(..., description="Assistant ID"),
    interlocutor_id: str = Path(..., description="Interlocutor ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: InterlocutorService = Depends(get_interlocutor_service)
) -> InterlocutorDetail:
    """Get detailed interlocutor information."""
    
    try:
        return await service.get_interlocutor(
            assistant_id=assistant_id,
            interlocutor_id=interlocutor_id,
            user_id=current_admin.email
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch(
    "/assistants/{assistant_id}/interlocutors/{interlocutor_id}",
    response_model=InterlocutorDetail,
    summary="Update interlocutor",
    description="Update interlocutor data (name, language, profile)"
)
async def update_interlocutor(
    data: InterlocutorUpdate,
    assistant_id: str = Path(..., description="Assistant ID"),
    interlocutor_id: str = Path(..., description="Interlocutor ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: InterlocutorService = Depends(get_interlocutor_service)
) -> InterlocutorDetail:
    """Update interlocutor data."""
    
    try:
        return await service.update_interlocutor(
            assistant_id=assistant_id,
            interlocutor_id=interlocutor_id,
            user_id=current_admin.email,
            data=data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ============================================================================
# MESSAGE ENDPOINTS
# ============================================================================

@router.get(
    "/assistants/{assistant_id}/interlocutors/{interlocutor_id}/messages",
    response_model=MessageListResponse,
    summary="List messages",
    description="Get paginated message history for interlocutor-assistant conversation"
)
async def list_messages(
    assistant_id: str = Path(..., description="Assistant ID"),
    interlocutor_id: str = Path(..., description="Interlocutor ID"),
    state: Optional[List[str]] = Query(None, description="Filter by stages"),
    role: Optional[List[str]] = Query(None, description="Filter by role (user, assistant, system)"),
    date_from: Optional[str] = Query(None, description="Filter from date (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter to date (ISO format)"),
    sort: str = Query("created_at", description="Sort field (prefix '-' for DESC)"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: MessageService = Depends(get_message_service)
) -> MessageListResponse:
    """List messages for interlocutor-assistant conversation."""
    
    # Parse dates
    from datetime import datetime
    date_from_parsed = None
    date_to_parsed = None
    
    if date_from:
        try:
            date_from_parsed = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use ISO format."
            )
    
    if date_to:
        try:
            date_to_parsed = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use ISO format."
            )
    
    query = MessageListQuery(
        state=state,
        role=role,
        date_from=date_from_parsed,
        date_to=date_to_parsed,
        sort=sort,
        skip=skip,
        limit=limit
    )
    
    try:
        return await service.list_messages(
            assistant_id=assistant_id,
            interlocutor_id=interlocutor_id,
            user_id=current_admin.email,
            query=query
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
