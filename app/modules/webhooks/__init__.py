"""Webhooks module for processing incoming messages from various channels."""

from .models import WebhookEvent
from .service import WebhookService

__all__ = [
    "WebhookEvent",
    "WebhookService",
]
