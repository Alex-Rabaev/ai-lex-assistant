"""WhatsApp webhook processor."""

import logging
import hmac
import hashlib
from typing import Optional, Dict, Any, Tuple

from app.modules.webhooks.base.audio_processor import AudioAwareProcessor
from app.modules.webhooks.vendors.whatsapp.schemas import WhatsAppWebhook
from app.modules.outbound.vendors.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


class WhatsAppProcessor(AudioAwareProcessor):
    """
    Processor for WhatsApp webhook updates.
    
    Inherits from AudioAwareProcessor to support voice/audio message
    transcription via OpenAI Whisper API.
    """
    
    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        """
        Initialize WhatsApp processor.
        
        Args:
            phone_number_id: WhatsApp Phone Number ID for downloading audio.
            access_token: Meta Graph API access token for downloading audio.
        """
        super().__init__()
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._whatsapp_client: Optional[WhatsAppClient] = None
        
        if phone_number_id and access_token:
            self._whatsapp_client = WhatsAppClient(phone_number_id, access_token)
    
    async def download_audio_file(self, file_id: str) -> str:
        """
        Download audio file from WhatsApp using WhatsAppClient.
        
        Args:
            file_id: WhatsApp media ID.
            
        Returns:
            Path to downloaded temporary audio file.
            
        Raises:
            AudioDownloadError: If download fails or no client configured.
        """
        from app.common.audio.exceptions import AudioDownloadError
        
        if not self._whatsapp_client:
            raise AudioDownloadError(
                "WhatsAppClient not configured (missing phone_number_id or access_token)"
            )
        
        return await self._whatsapp_client.download_file(file_id)
    
    def extract_text(self, update: Dict[str, Any]) -> Optional[str]:
        """Extract text from WhatsApp message."""
        try:
            webhook = WhatsAppWebhook(**update)
            messages = webhook.get_messages()
            
            if messages and messages[0].type == "text" and messages[0].text:
                return messages[0].text.body
            
            return None
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return None
    
    def get_user_id(self, update: Dict[str, Any]) -> Optional[str]:
        """Get user ID as whatsapp_{phone_number}."""
        try:
            webhook = WhatsAppWebhook(**update)
            messages = webhook.get_messages()
            
            if messages:
                # Phone number without + prefix
                phone = messages[0].from_
                return f"whatsapp_{phone}"
            
            return None
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")
            return None
    
    def get_user_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract user info from contacts."""
        try:
            webhook = WhatsAppWebhook(**update)
            contacts = webhook.get_contacts()
            
            if contacts:
                contact = contacts[0]
                return {
                    "wa_id": contact.wa_id,
                    "name": contact.profile.name if contact.profile else None
                }
            
            return None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    def get_chat_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """WhatsApp is always 1:1, return metadata."""
        try:
            webhook = WhatsAppWebhook(**update)
            phone_number_id = webhook.get_phone_number_id()
            
            if phone_number_id:
                return {
                    "phone_number_id": phone_number_id,
                    "type": "private"
                }
            
            return None
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return None
    
    def get_message_type(self, update: Dict[str, Any]) -> Optional[str]:
        """Get message type: text, image, etc."""
        try:
            webhook = WhatsAppWebhook(**update)
            
            if webhook.is_status_update():
                return "status"
            
            messages = webhook.get_messages()
            if messages:
                return messages[0].type
            
            return None
        except Exception as e:
            logger.error(f"Error getting message type: {e}")
            return None
    
    def get_message_id(self, update: Dict[str, Any]) -> Optional[str]:
        """Get WhatsApp message ID."""
        try:
            webhook = WhatsAppWebhook(**update)
            messages = webhook.get_messages()
            
            if messages:
                return messages[0].id
            
            return None
        except Exception as e:
            logger.error(f"Error getting message ID: {e}")
            return None
    
    @staticmethod
    def verify_signature(payload: bytes, signature: str, app_secret: str) -> bool:
        """
        Verify webhook signature using SHA256 HMAC.
        
        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value (sha256=...)
            app_secret: App secret from Meta
            
        Returns:
            True if signature is valid
        """
        if not signature.startswith("sha256="):
            return False
        
        expected_signature = signature[7:]  # Remove "sha256=" prefix
        
        computed = hmac.new(
            app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed, expected_signature)
    
    # =========================================================================
    # Audio Detection Methods
    # =========================================================================
    
    def get_audio_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract audio message information from WhatsApp update.
        
        WhatsApp uses 'audio' type for both voice messages and audio files.
        The audio object contains: id, mime_type, sha256, voice (bool).
        
        Args:
            update: Raw WhatsApp webhook payload
            
        Returns:
            Dictionary with audio info (id, mime_type, voice) or None
        """
        try:
            webhook = WhatsAppWebhook(**update)
            messages = webhook.get_messages()
            
            if messages and messages[0].type == "audio" and messages[0].audio:
                audio = messages[0].audio
                return {
                    "id": audio.get("id"),
                    "mime_type": audio.get("mime_type", "audio/ogg"),
                    "sha256": audio.get("sha256"),
                    "voice": audio.get("voice", False),  # True if voice message
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting audio info: {e}")
            return None
    
    def is_audio_message(self, update: Dict[str, Any]) -> bool:
        """
        Check if the update contains an audio message.
        
        Args:
            update: Raw WhatsApp webhook payload
            
        Returns:
            True if this is an audio message
        """
        return self.get_audio_info(update) is not None
    
    def is_voice_message(self, update: Dict[str, Any]) -> bool:
        """
        Check if the update contains a voice message (not just audio file).
        
        WhatsApp distinguishes voice messages with audio.voice = true.
        
        Args:
            update: Raw WhatsApp webhook payload
            
        Returns:
            True if this is a voice message
        """
        audio_info = self.get_audio_info(update)
        return audio_info is not None and audio_info.get("voice", False)
    
    def get_audio_or_voice_info(
        self,
        update: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Get audio info and determine message type.
        
        For WhatsApp, both voice and audio files have type="audio",
        but voice messages have audio.voice=true.
        
        Args:
            update: Raw WhatsApp webhook payload
            
        Returns:
            Tuple of (info_dict, message_type) where:
            - info_dict: Audio info or None
            - message_type: "voice", "audio", or "none"
        """
        audio_info = self.get_audio_info(update)
        
        if audio_info:
            # WhatsApp voice messages have voice=true
            if audio_info.get("voice", False):
                return audio_info, "voice"
            else:
                return audio_info, "audio"
        
        return None, "none"

