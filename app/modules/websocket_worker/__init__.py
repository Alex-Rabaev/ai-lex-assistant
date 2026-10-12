"""WebSocket Worker module for real-time message delivery."""

from app.modules.websocket_worker.manager import ConnectionManager
from app.modules.websocket_worker.router import router as websocket_router, get_connection_manager

__all__ = [
    "ConnectionManager",
    "get_connection_manager",
    "websocket_router",
]

