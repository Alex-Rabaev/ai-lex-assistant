"""
Webhook Router - HTTP endpoints for receiving webhook events.

This module provides secure webhook endpoints for different channels
with secret token validation to ensure authenticity of incoming requests.
"""

import logging
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query, Response
from fastapi.responses import JSONResponse

from app.modules.webhooks.repository import WebhookRepository
from app.modules.webhooks.publisher import WebhookPublisher
from app.common.messaging.connection import RabbitMQConnection
from app.modules.connections.models import ConnectionChannel
from app.modules.connections.service import ConnectionService
from app.common.utils.logging_context import set_log_context, generate_trace_id, clear_log_context

# Import vendor-specific services
from app.modules.webhooks.vendors.telegram.service import TelegramWebhookService
from app.modules.webhooks.vendors.whatsapp.service import WhatsAppWebhookService
from app.modules.webhooks.vendors.whatsapp.processor import WhatsAppProcessor
from app.modules.webhooks.vendors.webchat.service import WebchatWebhookService
from app.modules.connections.security import decrypt_token
from app.config import config

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/webhook",
    tags=["webhooks"],
    responses={
        403: {"description": "Invalid webhook secret"},
        404: {"description": "Assistant or connection not found"},
        500: {"description": "Internal server error"}
    }
)

# Global RabbitMQ connection and publisher (reused across requests)
_global_rabbitmq_connection: Optional[RabbitMQConnection] = None
_global_webhook_publisher: Optional[WebhookPublisher] = None


# Dependency functions
def get_webhook_repository() -> WebhookRepository:
    """Get webhook repository instance."""
    return WebhookRepository()


async def get_webhook_publisher() -> WebhookPublisher:
    """
    Get webhook publisher instance with shared RabbitMQ connection.
    
    Uses a global connection that is reused across all webhook requests
    to avoid connection leaks.
    """
    global _global_rabbitmq_connection, _global_webhook_publisher
    
    # Initialize global connection and publisher on first use
    if _global_webhook_publisher is None:
        logger.info("Initializing global RabbitMQ connection for webhooks")
        _global_rabbitmq_connection = RabbitMQConnection()
        _global_webhook_publisher = WebhookPublisher(_global_rabbitmq_connection)
    
    return _global_webhook_publisher


def validate_webhook_secret(
    secret_header: Optional[str],
    expected_secret: Optional[str],
    channel: str
) -> bool:
    """
    Validate webhook secret using constant-time comparison.
    
    Args:
        secret_header: Secret from request header
        expected_secret: Expected secret from connection
        channel: Channel name for logging
        
    Returns:
        True if secrets match, False otherwise
    """
    if not expected_secret:
        logger.warning(f"No webhook secret configured for {channel}")
        return False
    
    if not secret_header:
        logger.warning(f"No secret header provided for {channel} webhook")
        return False
    
    # Use constant-time comparison to prevent timing attacks
    is_valid = secrets.compare_digest(secret_header, expected_secret)
    
    if not is_valid:
        logger.error(f"Invalid webhook secret for {channel}")
    
    return is_valid


@router.post("/telegram/{assistant_id}")
async def telegram_webhook(
    assistant_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID"),
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
    webhook_publisher: WebhookPublisher = Depends(get_webhook_publisher)
) -> JSONResponse:
    """
    Receive and process Telegram webhook updates.
    
    This endpoint:
    1. Validates the webhook secret token
    2. Processes the update through TelegramWebhookService
    3. Always returns 200 OK to Telegram (even on errors)
    
    Args:
        assistant_id: ID of the assistant receiving the webhook
        request: FastAPI request object with webhook update
        x_telegram_bot_api_secret_token: Secret token from Telegram
        x_trace_id: Optional trace ID from upstream (load balancer, API gateway)
        webhook_repo: Repository for webhook events
        webhook_publisher: Publisher for RabbitMQ
        
    Returns:
        JSONResponse with {"ok": True} for Telegram
    """
    # Set up tracing context: use X-Trace-ID from headers or generate new one
    trace_id = x_trace_id or generate_trace_id()
    set_log_context(trace_id=trace_id, assistant_id=assistant_id)
    
    try:
        # Get webhook update
        update = await request.json()
        
        logger.info("Received Telegram webhook")
        logger.debug(f"Update data: {update}")
        
        # Get connection for secret validation
        connection_service = ConnectionService()
        connection = await connection_service.get_connection_by_assistant_and_channel_internal(
            assistant_id,
            ConnectionChannel.TELEGRAM
        )
        
        if not connection:
            logger.error(f"No Telegram connection found for assistant {assistant_id}")
            # Still return 200 to not trigger Telegram retries
            return JSONResponse(
                content={"ok": True, "error": "Connection not found"},
                status_code=200
            )
        
        # Validate webhook secret
        expected_secret = connection.settings.webhook_secret if connection.settings else None
        
        if expected_secret and not validate_webhook_secret(
            x_telegram_bot_api_secret_token,
            expected_secret,
            "telegram"
        ):
            logger.error(
                f"Security violation: Invalid webhook secret for assistant {assistant_id}"
            )
            # Return 403 for security violations
            raise HTTPException(
                status_code=403,
                detail="Invalid webhook secret"
            )
        
        # Get bot token for audio processing (decrypt if encrypted)
        bot_token = None
        if connection.settings and connection.settings.bot_token:
            try:
                bot_token = decrypt_token(
                    connection.settings.bot_token,
                    config.ENCRYPTION_KEY
                )
            except Exception as e:
                # Token might not be encrypted (test environment) or decryption failed
                logger.warning(f"Could not decrypt bot_token: {e}")
                # Voice message processing will be disabled for this request
        
        # Create service and process update
        service = TelegramWebhookService(
            webhook_repository=webhook_repo,
            webhook_publisher=webhook_publisher,
            bot_token=bot_token
        )
        
        result = await service.process_update(
            update=update,
            assistant_id=assistant_id,
            connection_id=str(connection.id)
        )
        
        if not result.success:
            logger.warning(f"Failed to process webhook: {result.message}")
        
        # Always return 200 OK to Telegram
        # This prevents Telegram from retrying the webhook
        return JSONResponse(
            content={"ok": True},
            status_code=200
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 403 for invalid secret)
        raise
        
    except Exception as e:
        # Log error but still return 200 to Telegram
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        
        # Return 200 to prevent retries
        return JSONResponse(
            content={"ok": True, "error": "Internal error"},
            status_code=200
        )
    
    finally:
        # Clear logging context after request
        clear_log_context()


@router.get("/whatsapp/{assistant_id}")
async def whatsapp_webhook_verify(
    assistant_id: str,
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
) -> Response:
    """
    WhatsApp webhook verification (challenge-response).
    
    Meta sends GET request with hub.mode, hub.challenge, hub.verify_token.
    Must return hub.challenge if verify_token matches.
    """
    from fastapi.responses import PlainTextResponse
    
    logger.info(f"WhatsApp webhook verification for assistant {assistant_id}")
    
    # Get connection to verify token
    connection_service = ConnectionService()
    connection = await connection_service.get_connection_by_assistant_and_channel_internal(
        assistant_id,
        ConnectionChannel.WHATSAPP
    )
    
    if not connection:
        logger.error(f"No WhatsApp connection for assistant {assistant_id}")
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check verify token
    expected_token = connection.settings.webhook_secret if connection.settings else None
    
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info(f"WhatsApp webhook verified for assistant {assistant_id}")
        return PlainTextResponse(content=hub_challenge)
    
    logger.error(f"WhatsApp webhook verification failed: mode={hub_mode}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/{assistant_id}")
async def whatsapp_webhook(
    assistant_id: str,
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID"),
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
    webhook_publisher: WebhookPublisher = Depends(get_webhook_publisher)
) -> JSONResponse:
    """
    Receive and process WhatsApp webhook updates.
    
    1. Verify signature (X-Hub-Signature-256)
    2. Process messages through WhatsAppWebhookService
    3. Return 200 OK
    """
    trace_id = x_trace_id or generate_trace_id()
    set_log_context(trace_id=trace_id, assistant_id=assistant_id)
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        update = await request.json()
        
        logger.info("Received WhatsApp webhook")
        
        # Get connection
        connection_service = ConnectionService()
        connection = await connection_service.get_connection_by_assistant_and_channel_internal(
            assistant_id,
            ConnectionChannel.WHATSAPP
        )
        
        if not connection:
            logger.error(f"No WhatsApp connection for assistant {assistant_id}")
            return JSONResponse(content={"status": "ok"}, status_code=200)
        
        # Verify signature
        if x_hub_signature_256:
            app_secret_encrypted = connection.settings.bot_info.get("app_secret_encrypted")
            if app_secret_encrypted:
                app_secret = decrypt_token(app_secret_encrypted, config.ENCRYPTION_KEY)
                
                if not WhatsAppProcessor.verify_signature(body, x_hub_signature_256, app_secret):
                    logger.error("Invalid webhook signature")
                    raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Get credentials for mark_as_read and audio download
        phone_number_id = connection.settings.bot_info.get("phone_number_id")
        access_token = None
        
        try:
            access_token = decrypt_token(connection.settings.bot_token, config.ENCRYPTION_KEY)
        except Exception as e:
            # Token might not be encrypted in test environments
            logger.warning(f"Could not decrypt WhatsApp access_token: {e}")
            # Voice message processing will be disabled for this request
        
        # Process webhook
        service = WhatsAppWebhookService(
            webhook_repository=webhook_repo,
            webhook_publisher=webhook_publisher,
            phone_number_id=phone_number_id,
            access_token=access_token
        )
        
        result = await service.process_update(
            update=update,
            assistant_id=assistant_id,
            connection_id=str(connection.id),
            trace_id=trace_id
        )
        
        if not result.success:
            logger.warning(f"Webhook processing: {result.message}")
        
        return JSONResponse(content={"status": "ok"}, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}", exc_info=True)
        return JSONResponse(content={"status": "ok"}, status_code=200)
    finally:
        clear_log_context()


# ==================== WebChat Webhook ====================

@router.post("/webchat/{assistant_id}")
async def webchat_webhook(
    assistant_id: str,
    request: Request,
    authorization: Optional[str] = Header(None, description="Bearer token for authentication (optional if anonymous)"),
    x_anonymous_user_id: Optional[str] = Header(None, alias="X-Anonymous-User-Id", description="Anonymous user ID (required if no auth)"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID"),
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
    webhook_publisher: WebhookPublisher = Depends(get_webhook_publisher)
) -> JSONResponse:
    """
    Receive and process WebChat messages.
    
    Supports both authenticated and anonymous users:
    - Authenticated: Send Authorization header with Bearer token
    - Anonymous: Send X-Anonymous-User-Id header with anon_{uuid} format
    
    This endpoint:
    1. Authenticates user via JWT token OR validates anonymous ID
    2. Gets the webchat connection for the assistant
    3. Validates the message via WebchatChannelService
    4. Saves message to webchat_messages collection
    5. Publishes to incoming_messages queue for agent processing
    
    Args:
        assistant_id: ID of the assistant receiving the message
        request: FastAPI request object with message content
        authorization: Bearer token from Authorization header (optional)
        x_anonymous_user_id: Anonymous user ID (required if no auth)
        x_trace_id: Optional trace ID for request tracing
        webhook_repo: Repository for webhook events
        webhook_publisher: Publisher for RabbitMQ
        
    Returns:
        JSONResponse with message_id and status
    """
    from app.common.auth import get_user_id_from_token, validate_anonymous_user_id
    
    # Set up tracing context
    trace_id = x_trace_id or generate_trace_id()
    set_log_context(trace_id=trace_id, assistant_id=assistant_id)
    
    try:
        # 1. Authenticate user - supports both JWT and anonymous
        user_id = None
        
        if authorization:
            # Try JWT authentication
            try:
                user_id = await get_user_id_from_token(authorization)
                logger.debug(f"Authenticated user via JWT: {user_id}")
            except Exception as e:
                logger.warning(f"JWT authentication failed: {e}")
                return JSONResponse(
                    content={"success": False, "error": "Authentication failed"},
                    status_code=401
                )
        else:
            # Fallback: read X-Anonymous-User-Id from headers (some proxies normalize header names)
            anon_header = x_anonymous_user_id or request.headers.get("X-Anonymous-User-Id") or request.headers.get("x-anonymous-user-id")
            if anon_header:
                if validate_anonymous_user_id(anon_header):
                    user_id = anon_header
                    logger.debug(f"Anonymous user: {user_id}")
                else:
                    logger.warning(f"Invalid anonymous user ID format: {anon_header}")
                    return JSONResponse(
                        content={"success": False, "error": "Invalid anonymous user ID format. Expected: anon_{uuid}"},
                        status_code=400
                    )
            else:
                # No auth provided
                return JSONResponse(
                    content={"success": False, "error": "Authentication required. Provide Authorization header or X-Anonymous-User-Id header."},
                    status_code=401
                )
        
        # 2. Get connection (like telegram/whatsapp)
        connection_service = ConnectionService()
        connection = await connection_service.get_connection_by_assistant_and_channel_internal(
            assistant_id,
            ConnectionChannel.WEBCHAT
        )
        
        if not connection:
            logger.warning(f"No WebChat connection found for assistant {assistant_id}")
            return JSONResponse(
                content={"success": False, "error": "WebChat not enabled for this assistant"},
                status_code=404
            )
        
        # 3. Check connection settings
        # TODO: Check allow_anonymous if user is anonymous (post-MVP)
        
        # 4. Parse request body
        body = await request.json()
        content = body.get("content", "")
        
        if not content or not content.strip():
            return JSONResponse(
                content={"success": False, "error": "Message content is required"},
                status_code=400
            )
        
        # 5. Create service and process message
        service = WebchatWebhookService(
            webhook_repository=webhook_repo,
            webhook_publisher=webhook_publisher
        )
        
        result = await service.process_message(
            assistant_id=assistant_id,
            connection_id=str(connection.id),
            user_id=user_id,
            content=content.strip()
        )
        
        if not result.success:
            logger.warning(f"WebChat webhook failed: {result.message}")
            return JSONResponse(
                content={
                    "success": False,
                    "error": result.message
                },
                status_code=400
            )
        
        return JSONResponse(
            content={
                "success": True,
                "message_id": result.data.get("message_id") if result.data else None,
                "status": "queued"
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error processing WebChat webhook: {e}", exc_info=True)
        
        return JSONResponse(
            content={
                "success": False,
                "error": "Internal server error"
            },
            status_code=500
        )
    finally:
        clear_log_context()
    

@router.get("/health")
async def webhook_health(
    webhook_publisher: WebhookPublisher = Depends(get_webhook_publisher)
) -> Dict[str, Any]:
    """
    Health check endpoint for webhook service.
    
    Returns:
        Status of webhook service
    """
    # Check RabbitMQ connection status
    rabbitmq_status = "connected" if webhook_publisher.connection.is_connected else "disconnected"
    
    return {
        "service": "webhooks",
        "status": "healthy",
        "channels": ["telegram", "webchat"],
        "features": [
            "secret_validation",
            "event_storage",
            "ttl_cleanup",
            "rabbitmq_publishing"
        ],
        "rabbitmq": {
            "status": rabbitmq_status,
            "url": webhook_publisher.connection.url
        }
    }
