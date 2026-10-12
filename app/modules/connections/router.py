"""API router for connections module."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status, Body

from app.common.auth import get_current_admin_auth0, AdminUser
from app.modules.connections.service import (
    ConnectionService,
    AssistantNotFoundError
)
from app.modules.connections.models import (
    ConnectionStatus,
    ConnectionChannel
)
from app.modules.connections.schemas import (
    CreateTelegramConnectionRequest,
    CreateWhatsAppConnectionRequest,
    ConnectionResponse,
    ConnectionListResponse,
    ConnectionHealthCheckResponse
)
from app.modules.connections.vendors.webchat.schemas import (
    EnableWebchatRequest,
    UpdateWebchatSettingsRequest,
    WebchatConnectionResponse
)
from app.modules.connections.exceptions import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    InvalidBotTokenError,
    InvalidAccessTokenError,
    WebhookSetupError
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["connections"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - No admin access"}
    }
)


async def get_connection_service() -> ConnectionService:
    """Get connection service instance."""
    return ConnectionService()


@router.post(
    "/assistants/{assistant_id}/connections/telegram",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Telegram connection",
    description="Connect a Telegram bot to the assistant"
)
async def create_telegram_connection(
    assistant_id: str = Path(..., description="Assistant ID"),
    request: CreateTelegramConnectionRequest = Body(...),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> ConnectionResponse:
    """
    Create a new Telegram connection for the assistant.
    
    This will:
    1. Validate the bot token with Telegram
    2. Encrypt and store the token
    3. Setup webhook for message reception
    
    Returns:
        ConnectionResponse with connection details
        
    Raises:
        404: Assistant not found or no access
        400: Invalid bot token
        409: Telegram connection already exists for this assistant
        500: Webhook setup failed
    """
    try:
        connection = await service.create_telegram_connection(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            bot_token=request.bot_token
        )
        
        return ConnectionResponse(
            id=str(connection.id),
            assistant_id=str(connection.assistant_id),
            channel=connection.channel,
            status=connection.status,
            bot_username=connection.settings.bot_username if connection.settings else None,
            bot_first_name=connection.settings.bot_first_name if connection.settings else None,
            webhook_url=connection.settings.webhook_url if connection.settings else None,
            last_error=connection.last_error,
            last_checked_at=connection.last_checked_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidBotTokenError as e:
        logger.warning(f"Invalid bot token: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DuplicateConnectionError as e:
        logger.warning(f"Duplicate connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create connection"
        )


@router.post(
    "/assistants/{assistant_id}/connections/whatsapp",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create WhatsApp connection",
    description="Connect a WhatsApp Business number to the assistant"
)
async def create_whatsapp_connection(
    assistant_id: str = Path(..., description="Assistant ID"),
    request: CreateWhatsAppConnectionRequest = Body(...),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> ConnectionResponse:
    """
    Create a new WhatsApp connection for the assistant.
    
    This will:
    1. Validate credentials with Meta API
    2. Encrypt and store tokens
    3. Return connection (webhook must be configured in Meta Portal)
    
    Returns:
        ConnectionResponse with connection details
        
    Raises:
        404: Assistant not found or no access
        400: Invalid credentials
        409: WhatsApp connection already exists for this assistant
    """
    try:
        connection = await service.create_whatsapp_connection(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            phone_number_id=request.phone_number_id,
            access_token=request.access_token,
            app_secret=request.app_secret,
            verify_token=request.verify_token
        )
        
        return ConnectionResponse(
            id=str(connection.id),
            assistant_id=str(connection.assistant_id),
            channel=connection.channel,
            status=connection.status,
            bot_username=connection.settings.bot_username if connection.settings else None,
            bot_first_name=connection.settings.bot_first_name if connection.settings else None,
            webhook_url=connection.settings.webhook_url if connection.settings else None,
            last_error=connection.last_error,
            last_checked_at=connection.last_checked_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidAccessTokenError as e:
        logger.warning(f"Invalid WhatsApp credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DuplicateConnectionError as e:
        logger.warning(f"Duplicate connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create WhatsApp connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create connection"
        )


# ==================== WebChat Endpoints ====================

@router.post(
    "/assistants/{assistant_id}/connections/webchat",
    response_model=WebchatConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enable WebChat",
    description="Enable webchat channel for the assistant"
)
async def enable_webchat(
    assistant_id: str = Path(..., description="Assistant ID"),
    request: EnableWebchatRequest = Body(default=EnableWebchatRequest()),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> WebchatConnectionResponse:
    """
    Enable webchat for the assistant.
    
    This creates a webchat connection that allows users to chat
    with the assistant via a web interface.
    
    Returns:
        WebchatConnectionResponse with connection details and chat URL
        
    Raises:
        404: Assistant not found or no access
    """
    try:
        connection = await service.enable_webchat(
            assistant_id=assistant_id,
            user_id=current_admin.email
        )
        
        return WebchatConnectionResponse.from_connection(connection)
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to enable webchat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable webchat"
        )


@router.delete(
    "/assistants/{assistant_id}/connections/webchat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable WebChat",
    description="Disable webchat channel for the assistant"
)
async def disable_webchat(
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> None:
    """
    Disable webchat for the assistant.
    
    The connection is not deleted, just set to inactive status.
    
    Raises:
        404: Assistant not found or no access
    """
    try:
        disabled = await service.disable_webchat(
            assistant_id=assistant_id,
            user_id=current_admin.email
        )
        
        if not disabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WebChat connection not found"
            )
            
        return None
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable webchat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable webchat"
        )


@router.get(
    "/assistants/{assistant_id}/connections/webchat",
    response_model=WebchatConnectionResponse,
    summary="Get WebChat connection",
    description="Get webchat connection status and settings"
)
async def get_webchat_connection(
    assistant_id: str = Path(..., description="Assistant ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> WebchatConnectionResponse:
    """
    Get webchat connection details.
    
    Returns:
        WebchatConnectionResponse with connection details
        
    Raises:
        404: Assistant not found or webchat not enabled
    """
    try:
        connection = await service.get_webchat_connection(
            assistant_id=assistant_id,
            user_id=current_admin.email
        )
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WebChat connection not found"
            )
        
        return WebchatConnectionResponse.from_connection(connection)
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get webchat connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get webchat connection"
        )


@router.patch(
    "/assistants/{assistant_id}/connections/webchat",
    response_model=WebchatConnectionResponse,
    summary="Update WebChat settings",
    description="Update webchat connection settings"
)
async def update_webchat_settings(
    assistant_id: str = Path(..., description="Assistant ID"),
    request: UpdateWebchatSettingsRequest = Body(...),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> WebchatConnectionResponse:
    """
    Update webchat settings.
    
    Returns:
        WebchatConnectionResponse with updated settings
        
    Raises:
        404: Assistant not found or webchat not enabled
    """
    try:
        connection = await service.update_webchat_settings(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            allow_anonymous=request.allow_anonymous
        )
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WebChat connection not found"
            )
        
        return WebchatConnectionResponse.from_connection(connection)
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update webchat settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update webchat settings"
        )


@router.get(
    "/assistants/{assistant_id}/connections",
    response_model=ConnectionListResponse,
    summary="List assistant connections",
    description="Get all connections for a specific assistant"
)
async def list_assistant_connections(
    assistant_id: str = Path(..., description="Assistant ID"),
    status: Optional[ConnectionStatus] = None,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> ConnectionListResponse:
    """
    List all connections for the assistant.
    
    Args:
        assistant_id: Assistant to get connections for
        status: Optional status filter
        
    Returns:
        List of connections
        
    Raises:
        404: Assistant not found or no access
    """
    try:
        connections = await service.list_connections(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            status=status
        )
        
        items = []
        for connection in connections:
                items.append(ConnectionResponse(
                    id=str(connection.id),
                    assistant_id=str(connection.assistant_id),
                    channel=connection.channel,
                    status=connection.status,
                    bot_username=connection.settings.bot_username if connection.settings else None,
                    bot_first_name=connection.settings.bot_first_name if connection.settings else None,
                    webhook_url=connection.settings.webhook_url if connection.settings else None,
                    last_error=connection.last_error,
                    last_checked_at=connection.last_checked_at,
                    created_at=connection.created_at,
                    updated_at=connection.updated_at
                ))
        
        return ConnectionListResponse(
            items=items,
            total=len(items),
            assistant_id=assistant_id
        )
        
    except AssistantNotFoundError as e:
        logger.warning(f"Assistant not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/connections/{connection_id}",
    response_model=ConnectionResponse,
    summary="Get connection details",
    description="Get detailed information about a specific connection"
)
async def get_connection(
    connection_id: str = Path(..., description="Connection ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> ConnectionResponse:
    """
    Get connection details.
    
    Args:
        connection_id: Connection to retrieve
        
    Returns:
        Connection details
        
    Raises:
        404: Connection not found or no access
    """
    try:
        connection = await service.get_connection(
            connection_id=connection_id,
            user_id=current_admin.email
        )
        
        return ConnectionResponse(
            id=str(connection.id),
            assistant_id=str(connection.assistant_id),
            channel=connection.channel,
            status=connection.status,
            bot_username=connection.settings.bot_username if connection.settings else None,
            bot_first_name=connection.settings.bot_first_name if connection.settings else None,
            webhook_url=connection.settings.webhook_url if connection.settings else None,
            last_error=connection.last_error,
            last_checked_at=connection.last_checked_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )
        
    except ConnectionNotFoundError as e:
        logger.warning(f"Connection not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete connection",
    description="Delete a connection and cleanup webhook"
)
async def delete_connection(
    connection_id: str = Path(..., description="Connection ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> None:
    """
    Delete connection and cleanup webhook.
    
    Args:
        connection_id: Connection to delete
        
    Raises:
        404: Connection not found or no access
    """
    try:
        deleted = await service.delete_connection(
            connection_id=connection_id,
            user_id=current_admin.email
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
            
        return None
        
    except ConnectionNotFoundError as e:
        logger.warning(f"Connection not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/connections/{connection_id}/health-check",
    response_model=ConnectionHealthCheckResponse,
    summary="Check connection health",
    description="Check and update connection health status"
)
async def check_connection_health(
    connection_id: str = Path(..., description="Connection ID"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ConnectionService = Depends(get_connection_service)
) -> ConnectionHealthCheckResponse:
    """
    Check connection health and update status.
    
    This will:
    1. Check webhook status with Telegram
    2. Update connection status based on results
    
    Args:
        connection_id: Connection to check
        
    Returns:
        Health check results
        
    Raises:
        404: Connection not found
    """
    try:
        # First verify user has access
        await service.get_connection(
            connection_id=connection_id,
            user_id=current_admin.email
        )
        
        # Then perform health check (no user check needed)
        connection = await service.check_connection_health(connection_id)
        
        return ConnectionHealthCheckResponse(
            id=str(connection.id),
            status=connection.status,
            is_healthy=connection.status in [ConnectionStatus.CONNECTED, ConnectionStatus.DEGRADED],
            last_error=connection.last_error,
            checked_at=connection.last_checked_at
        )
        
    except ConnectionNotFoundError as e:
        logger.warning(f"Connection not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
