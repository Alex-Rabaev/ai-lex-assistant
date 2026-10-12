"""REST API router for WebChat messages."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Path, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.modules.connections.vendors.webchat.service import (
    WebchatChannelService,
    WebchatValidationError,
    WebchatMessageNotFoundError
)
from app.modules.connections.vendors.webchat.connection_service import WebchatConnectionService
from app.modules.connections.vendors.webchat.schemas import (
    WebchatMessageResponse,
    MessageListResponse,
    UpdateMessageRequest,
    AssistantInfoResponse,
    ClaimSessionRequest,
    ClaimSessionResponse
)
from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.common.auth import get_user_id_from_token, validate_anonymous_user_id

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webchat",
    tags=["webchat"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


def get_webchat_service() -> WebchatChannelService:
    """Get webchat service instance."""
    return WebchatChannelService()


def get_assistant_service() -> AssistantService:
    """Get assistant service instance."""
    return AssistantService()


def get_connection_service() -> WebchatConnectionService:
    """Get webchat connection service instance."""
    return WebchatConnectionService()


async def get_current_webchat_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Auth0 authorization dependency for webchat users.
    
    Verifies the JWT token and extracts user identity.
    No role check - any authenticated user can access webchat.
    
    Returns:
        User ID (email) - no prefix, unified across all channels
    """
    return await get_user_id_from_token(f"Bearer {credentials.credentials}")


async def get_webchat_user_or_anonymous(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    x_anonymous_user_id: Optional[str] = Header(None, alias="X-Anonymous-User-Id")
) -> str:
    """
    Get user ID from JWT token OR anonymous header.
    
    Supports both authenticated and anonymous users:
    - If Authorization header present: verify JWT and return email
    - If X-Anonymous-User-Id header present: validate format and return anon_xxx
    - If neither: raise 401
    
    Returns:
        User ID (email or anon_xxx)
    """
    # Try JWT first
    if credentials:
        try:
            return await get_user_id_from_token(f"Bearer {credentials.credentials}")
        except Exception as e:
            logger.warning(f"JWT auth failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # Try anonymous
    if x_anonymous_user_id:
        if validate_anonymous_user_id(x_anonymous_user_id):
            return x_anonymous_user_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid anonymous user ID format. Expected: anon_{uuid}"
            )
    
    # Neither provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Authorization header or X-Anonymous-User-Id header."
    )


@router.get(
    "/{assistant_id}/messages",
    response_model=MessageListResponse,
    summary="Get message history",
    description="Get the last N webchat messages for the user (authenticated or anonymous), in chronological order."
)
async def get_messages(
    assistant_id: str = Path(..., description="Assistant ID"),
    skip: int = Query(0, ge=0, description="Skip this many most-recent messages (for pagination)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum messages to return (default: last 50)"),
    user_id: str = Depends(get_webchat_user_or_anonymous),
    service: WebchatChannelService = Depends(get_webchat_service)
) -> MessageListResponse:
    """
    Get message history for the user and assistant.

    Returns the **last** N messages (most recent) in chronological order (oldest first),
    so the client can display them as a chat without an extra request.
    - skip=0, limit=50 → last 50 messages, oldest first.
    - skip=50, limit=50 → previous 50 (older), for loading more history.

    Supports both authenticated and anonymous users:
    - Authenticated: Send Authorization header with JWT token
    - Anonymous: Send X-Anonymous-User-Id header with anon_{uuid}

    Soft-deleted messages are not included.
    
    Args:
        assistant_id: Assistant ID
        skip: Pagination offset
        limit: Maximum messages per page
        
    Returns:
        MessageListResponse with messages and total count
    """
    try:
        messages, total = await service.get_messages(
            assistant_id=assistant_id,
            user_id=user_id,
            limit=limit,
            skip=skip
        )
        return MessageListResponse(
            messages=[service.to_response(msg) for msg in messages],
            total=total
        )
        
    except Exception as e:
        logger.error(f"Error getting messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages"
        )


@router.get(
    "/{assistant_id}/messages/{message_id}",
    response_model=WebchatMessageResponse,
    summary="Get single message",
    description="Get a specific message by ID"
)
async def get_message(
    assistant_id: str = Path(..., description="Assistant ID"),
    message_id: str = Path(..., description="Message ID"),
    user_id: str = Depends(get_current_webchat_user),
    service: WebchatChannelService = Depends(get_webchat_service)
) -> WebchatMessageResponse:
    """
    Get a specific message by ID.
    
    User can only access their own messages.
    
    Args:
        assistant_id: Assistant ID
        message_id: Message ID
        
    Returns:
        WebchatMessageResponse
        
    Raises:
        404: Message not found or no access
    """
    try:
        message = await service.get_message(message_id, user_id)
        return service.to_response(message)
        
    except WebchatMessageNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message"
        )


@router.put(
    "/{assistant_id}/messages/{message_id}",
    response_model=WebchatMessageResponse,
    summary="Update message",
    description="Update a user message content"
)
async def update_message(
    assistant_id: str = Path(..., description="Assistant ID"),
    message_id: str = Path(..., description="Message ID"),
    request: UpdateMessageRequest = ...,
    user_id: str = Depends(get_current_webchat_user),
    service: WebchatChannelService = Depends(get_webchat_service)
) -> WebchatMessageResponse:
    """
    Update a message content.
    
    Only user messages can be updated (not assistant responses).
    
    Args:
        assistant_id: Assistant ID
        message_id: Message ID
        request: Update request with new content
        
    Returns:
        Updated WebchatMessageResponse
        
    Raises:
        400: Cannot edit (assistant message or empty content)
        404: Message not found or no access
    """
    try:
        message = await service.update_message(
            message_id=message_id,
            user_id=user_id,
            content=request.content
        )
        return service.to_response(message)
        
    except WebchatMessageNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except WebchatValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message"
        )


@router.delete(
    "/{assistant_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message",
    description="Soft delete a message"
)
async def delete_message(
    assistant_id: str = Path(..., description="Assistant ID"),
    message_id: str = Path(..., description="Message ID"),
    user_id: str = Depends(get_current_webchat_user),
    service: WebchatChannelService = Depends(get_webchat_service)
) -> None:
    """
    Soft delete a message.
    
    The message is not actually deleted, just marked as deleted.
    It will not appear in message history.
    
    Args:
        assistant_id: Assistant ID
        message_id: Message ID
        
    Raises:
        404: Message not found or no access
    """
    try:
        await service.delete_message(message_id, user_id)
        
    except WebchatMessageNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )


@router.get(
    "/{assistant_id}/info",
    response_model=AssistantInfoResponse,
    summary="Get assistant info",
    description="Get basic assistant information for webchat"
)
async def get_assistant_info(
    assistant_id: str = Path(..., description="Assistant ID"),
    assistant_service: AssistantService = Depends(get_assistant_service),
    connection_service: WebchatConnectionService = Depends(get_connection_service)
) -> AssistantInfoResponse:
    """
    Get basic assistant information for display in webchat.
    
    This endpoint is public (no user authentication required).
    
    Args:
        assistant_id: Assistant ID
        
    Returns:
        AssistantInfoResponse with name, description, and webchat_enabled status
        
    Raises:
        404: Assistant not found
    """
    try:
        assistant = await assistant_service.get_assistant_internal(assistant_id)
        
        # Check if webchat is enabled for this assistant
        connection = await connection_service.get_connection(assistant_id)
        webchat_enabled = connection is not None and connection.status == "connected"
        
        return AssistantInfoResponse(
            id=str(assistant.id),
            name=assistant.name,
            description=assistant.description,
            webchat_enabled=webchat_enabled
        )
        
    except AssistantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found"
        )
    except Exception as e:
        logger.error(f"Error getting assistant info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get assistant info"
        )


@router.post(
    "/claim-session",
    response_model=ClaimSessionResponse,
    summary="Claim anonymous session",
    description="Transfer anonymous chat session to authenticated user after login"
)
async def claim_session(
    request: ClaimSessionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    webchat_service: WebchatChannelService = Depends(get_webchat_service)
) -> ClaimSessionResponse:
    """
    Claim anonymous session after user logs in.
    
    This endpoint transfers all messages and conversation data from
    an anonymous user ID to the authenticated user's account.
    
    The frontend should call this endpoint after user logs in if they
    were previously chatting anonymously.
    
    Args:
        request: Contains anonymous_user_id and assistant_id
        credentials: JWT token (required - user must be authenticated)
        
    Returns:
        ClaimSessionResponse with transfer statistics
        
    Raises:
        400: Invalid anonymous user ID format
        401: Authentication required
        500: Transfer failed
    """
    try:
        # Get authenticated user ID from token
        authenticated_user_id = await get_user_id_from_token(credentials.credentials)
        
        # Claim the session
        result = await webchat_service.claim_anonymous_session(
            anonymous_user_id=request.anonymous_user_id,
            authenticated_user_id=authenticated_user_id,
            assistant_id=request.assistant_id
        )
        
        return ClaimSessionResponse(
            success=True,
            messages_transferred=result["messages_transferred"],
            interlocutor_updated=result["interlocutor_updated"],
            anonymous_user_id=result["anonymous_user_id"],
            authenticated_user_id=result["authenticated_user_id"]
        )
        
    except WebchatValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error claiming session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to claim session"
        )
