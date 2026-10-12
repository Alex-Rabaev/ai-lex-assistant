"""WebSocket router - endpoint for WebSocket connections."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.common.auth import get_user_id_from_token, validate_anonymous_user_id

logger = logging.getLogger(__name__)

# Keepalive: if no message from client for this many seconds, server sends ping.
# Reduces proxy/ngrok closing idle connections (e.g. close code 1005).
WS_RECEIVE_TIMEOUT_SEC = 25

router = APIRouter(
    prefix="",
    tags=["websocket"]
)

# Global connection manager (singleton)
_connection_manager = None


def get_connection_manager():
    """Get or create the connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        from app.modules.websocket_worker.manager import ConnectionManager
        _connection_manager = ConnectionManager()
    return _connection_manager


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time communication.
    
    Protocol:
    1. Client connects
    2. Client sends auth message (one of two formats):
       - Authenticated: {"type": "auth", "token": "Bearer xxx"}
       - Anonymous: {"type": "auth_anon", "user_id": "anon_xxx"}
    3. Server validates, creates RabbitMQ queue, responds: {"type": "auth_success", ...}
    4. Client subscribes: {"type": "subscribe", "pattern": "webchat.{user_id}.*"}
    5. Server binds queue, confirms: {"type": "subscribed", "pattern": "..."}
    6. Server forwards messages from RabbitMQ to client
    
    Security:
    - Client MUST authenticate before subscribing
    - Client can only subscribe to patterns containing their user_id
    
    Example patterns:
    - "webchat.user@example.com.*" - all webchat messages for authenticated user
    - "webchat.anon_550e8400-e29b-41d4.*" - all webchat messages for anonymous user
    - "notifications.user@example.com.*" - all notifications for user
    """
    manager = get_connection_manager()
    connection_id: Optional[str] = None
    authenticated = False
    user_id: Optional[str] = None
    is_anonymous = False
    
    try:
        # Accept connection (but not authenticated yet)
        await websocket.accept()
        
        logger.info("WebSocket connection initiated, waiting for auth...")
        
        # Wait for messages (with timeout so server can send keepalive ping)
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=WS_RECEIVE_TIMEOUT_SEC
                )
                message_type = data.get("type")
                
                if not authenticated:
                    # Auth messages allowed before authentication
                    if message_type == "auth":
                        # JWT token authentication
                        result = await _authenticate_with_token(manager, websocket, data)
                        if result:
                            user_id, connection_id = result
                            authenticated = True
                            is_anonymous = False
                            await websocket.send_json({
                                "type": "auth_success",
                                "user_id": user_id,
                                "connection_id": connection_id,
                                "is_anonymous": False
                            })
                            logger.info(f"WebSocket authenticated (JWT): user_id={user_id}, connection_id={connection_id}")
                        else:
                            await websocket.send_json({
                                "type": "auth_error",
                                "error": "Authentication failed"
                            })
                    elif message_type == "auth_anon":
                        # Anonymous authentication
                        result = await _authenticate_anonymous(manager, websocket, data)
                        if result:
                            user_id, connection_id = result
                            authenticated = True
                            is_anonymous = True
                            await websocket.send_json({
                                "type": "auth_success",
                                "user_id": user_id,
                                "connection_id": connection_id,
                                "is_anonymous": True
                            })
                            logger.info(f"WebSocket authenticated (anon): user_id={user_id}, connection_id={connection_id}")
                        else:
                            await websocket.send_json({
                                "type": "auth_error",
                                "error": "Invalid anonymous user ID format"
                            })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "error": "Authentication required. Send 'auth' or 'auth_anon' message."
                        })
                else:
                    # Handle authenticated messages
                    await _handle_message(manager, websocket, connection_id, user_id, data)
                    
            except asyncio.TimeoutError:
                # No message from client within timeout — send keepalive ping
                # so proxies/ngrok do not close the connection (1005).
                try:
                    await websocket.send_json({"type": "ping"})
                    logger.debug("Sent keepalive ping to client")
                except Exception as e:
                    logger.warning(f"Failed to send keepalive ping: {e}")
                    break
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: user_id={user_id}, anonymous={is_anonymous}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        
    finally:
        # Cleanup
        if connection_id:
            await manager.disconnect(connection_id)


async def _authenticate_with_token(
    manager,
    websocket: WebSocket,
    data: dict
) -> Optional[tuple[str, str]]:
    """
    Authenticate user with JWT token and create RabbitMQ connection.
    
    Args:
        manager: Connection manager
        websocket: WebSocket connection
        data: Auth message data with "token" field
        
    Returns:
        Tuple of (user_id, connection_id) or None if auth failed
    """
    token = data.get("token", "")
    
    if not token:
        logger.warning("❌ WebSocket auth: No token provided")
        return None
    
    try:
        # Use common auth utility - returns email without prefix
        user_id = await get_user_id_from_token(token)
        logger.info(f"✅ WebSocket JWT auth successful: user_id={user_id}")
        
        # Create RabbitMQ connection immediately after auth
        connection_id = await manager.connect(websocket, user_id)
        logger.info(f"✅ RabbitMQ connection created: connection_id={connection_id}")
        
        return user_id, connection_id
        
    except Exception as e:
        logger.error(f"❌ WebSocket JWT auth failed: {type(e).__name__}: {e}", exc_info=True)
        return None


async def _authenticate_anonymous(
    manager,
    websocket: WebSocket,
    data: dict
) -> Optional[tuple[str, str]]:
    """
    Authenticate anonymous user and create RabbitMQ connection.
    
    Args:
        manager: Connection manager
        websocket: WebSocket connection
        data: Auth message data with "user_id" field (anon_{uuid} format)
        
    Returns:
        Tuple of (user_id, connection_id) or None if invalid
    """
    user_id = data.get("user_id", "")
    
    if not user_id:
        logger.warning("❌ WebSocket anon auth: No user_id provided")
        return None
    
    # Validate anonymous user ID format
    if not validate_anonymous_user_id(user_id):
        logger.warning(f"❌ WebSocket anon auth: Invalid format: {user_id}")
        return None
    
    try:
        logger.info(f"✅ WebSocket anonymous auth: user_id={user_id}")
        
        # Create RabbitMQ connection
        connection_id = await manager.connect(websocket, user_id)
        logger.info(f"✅ RabbitMQ connection created: connection_id={connection_id}")
        
        return user_id, connection_id
        
    except Exception as e:
        logger.error(f"❌ WebSocket anon connection failed: {type(e).__name__}: {e}", exc_info=True)
        return None


async def _handle_message(
    manager,  # ConnectionManager
    websocket: WebSocket,
    connection_id: str,
    user_id: str,
    data: dict
) -> None:
    """
    Handle authenticated client messages.
    
    Args:
        manager: Connection manager
        websocket: WebSocket connection
        connection_id: Connection ID
        user_id: Authenticated user ID
        data: Message data
    """
    message_type = data.get("type")
    
    if message_type == "subscribe":
        # Subscribe to a pattern
        pattern = data.get("pattern")
        if pattern:
            success = await manager.subscribe(connection_id, pattern)
            if success:
                await websocket.send_json({
                    "type": "subscribed",
                    "pattern": pattern
                })
            else:
                await websocket.send_json({
                    "type": "subscribe_error",
                    "pattern": pattern,
                    "error": "Subscription not allowed"
                })
        else:
            await websocket.send_json({
                "type": "error",
                "error": "Pattern required for subscribe"
            })
    
    elif message_type == "unsubscribe":
        # Unsubscribe from a pattern
        pattern = data.get("pattern")
        if pattern:
            success = await manager.unsubscribe(connection_id, pattern)
            await websocket.send_json({
                "type": "unsubscribed",
                "pattern": pattern,
                "success": success
            })
    
    elif message_type == "ping":
        # Keep-alive ping
        await websocket.send_json({"type": "pong"})
    
    else:
        logger.debug(f"Unknown message type from {user_id}: {message_type}")
        await websocket.send_json({
            "type": "error",
            "error": f"Unknown message type: {message_type}"
        })


@router.get("/health")
async def websocket_health():
    """
    Health check endpoint for WebSocket service.
    
    Returns:
        Connection statistics
    """
    manager = get_connection_manager()
    
    return {
        "service": "websocket",
        "status": "healthy",
        "active_connections": manager.get_connection_count()
    }
