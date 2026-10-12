"""WhatsApp webhook schemas (Meta Cloud API format)."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WhatsAppProfile(BaseModel):
    """User profile info."""
    name: Optional[str] = None


class WhatsAppContact(BaseModel):
    """Contact in webhook."""
    wa_id: str = Field(..., description="WhatsApp ID (phone number)")
    profile: Optional[WhatsAppProfile] = None


class WhatsAppTextMessage(BaseModel):
    """Text message content."""
    body: str


class WhatsAppMessage(BaseModel):
    """Individual message in webhook."""
    id: str = Field(..., description="Message ID")
    from_: str = Field(..., alias="from", description="Sender phone number")
    timestamp: str
    type: str  # text, image, audio, video, document, etc.
    text: Optional[WhatsAppTextMessage] = None
    
    # Other message types (not processed in v1)
    image: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None
    document: Optional[Dict[str, Any]] = None


class WhatsAppMetadata(BaseModel):
    """Webhook metadata."""
    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    """Webhook value object."""
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[Dict[str, Any]]] = None  # Delivery statuses


class WhatsAppChange(BaseModel):
    """Webhook change object."""
    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    """Webhook entry object."""
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhook(BaseModel):
    """Root webhook payload from Meta."""
    object: str  # "whatsapp_business_account"
    entry: List[WhatsAppEntry]
    
    def get_messages(self) -> List[WhatsAppMessage]:
        """Extract all messages from webhook."""
        messages = []
        for entry in self.entry:
            for change in entry.changes:
                if change.value.messages:
                    messages.extend(change.value.messages)
        return messages
    
    def get_contacts(self) -> List[WhatsAppContact]:
        """Extract all contacts from webhook."""
        contacts = []
        for entry in self.entry:
            for change in entry.changes:
                if change.value.contacts:
                    contacts.extend(change.value.contacts)
        return contacts
    
    def get_phone_number_id(self) -> Optional[str]:
        """Get phone number ID from metadata."""
        if self.entry and self.entry[0].changes:
            return self.entry[0].changes[0].value.metadata.phone_number_id
        return None
    
    def is_status_update(self) -> bool:
        """Check if this is a status update (not a message)."""
        for entry in self.entry:
            for change in entry.changes:
                if change.value.statuses and not change.value.messages:
                    return True
        return False

