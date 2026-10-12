"""WhatsApp connection vendor module."""

from app.modules.connections.vendors.whatsapp.client import WhatsAppClient
from app.modules.connections.vendors.whatsapp.service import WhatsAppConnectionService

__all__ = ["WhatsAppClient", "WhatsAppConnectionService"]


