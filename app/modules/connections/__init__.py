"""Connections module for managing assistant channel integrations."""

from .models import Connection, ConnectionChannel, ConnectionStatus
from .schemas import (
    CreateTelegramConnectionRequest,
    ConnectionResponse,
    ConnectionListResponse,
    ConnectionHealthCheckResponse,
    BotInfo
)

__all__ = [
    # Models
    'Connection',
    'ConnectionChannel',
    'ConnectionStatus',
    
    # Schemas
    'CreateTelegramConnectionRequest',
    'ConnectionResponse', 
    'ConnectionListResponse',
    'ConnectionHealthCheckResponse',
    'BotInfo'
]
