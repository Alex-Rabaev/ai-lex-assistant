"""WhatsApp webhook vendor module."""

from app.modules.webhooks.vendors.whatsapp.processor import WhatsAppProcessor
from app.modules.webhooks.vendors.whatsapp.service import WhatsAppWebhookService

__all__ = ["WhatsAppProcessor", "WhatsAppWebhookService"]


