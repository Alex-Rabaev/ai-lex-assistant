"""Base classes for webhooks module."""

from .processor import BaseProcessor
from .service import BaseWebhookService

__all__ = [
    "BaseProcessor",
    "BaseWebhookService",
]
