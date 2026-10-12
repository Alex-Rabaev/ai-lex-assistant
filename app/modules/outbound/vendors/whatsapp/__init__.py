"""WhatsApp outbound vendor module."""

from app.modules.outbound.vendors.whatsapp.client import WhatsAppClient
from app.modules.outbound.vendors.whatsapp.sender import WhatsAppSender

__all__ = ["WhatsAppClient", "WhatsAppSender"]


