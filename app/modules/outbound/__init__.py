"""Outbound module for sending messages to users via communication channels."""

from app.modules.outbound.exceptions import (
    OutboundError,
    SendError,
    DeliveryError,
    UserBlockedError,
    InvalidTokenError,
    RateLimitError,
    TemporaryError,
)
from app.modules.outbound.schemas import OutgoingMessage, SendResult
from app.modules.outbound.base import BaseSender

__all__ = [
    # Exceptions
    "OutboundError",
    "SendError",
    "DeliveryError",
    "UserBlockedError",
    "InvalidTokenError",
    "RateLimitError",
    "TemporaryError",
    # Schemas
    "OutgoingMessage",
    "SendResult",
    # Base classes
    "BaseSender",
]

