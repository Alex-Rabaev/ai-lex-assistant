"""WhatsApp webhook service."""

import logging
from typing import Dict, Any, Optional

from app.modules.webhooks.vendors.whatsapp.processor import WhatsAppProcessor
from app.modules.webhooks.vendors.whatsapp.schemas import WhatsAppWebhook
from app.modules.webhooks.repository import WebhookRepository
from app.modules.webhooks.publisher import WebhookPublisher
from app.modules.webhooks.models import WebhookResponse, WebhookEvent, WebhookContent
from app.modules.outbound.vendors.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


class WhatsAppWebhookService:
    """Service for processing WhatsApp webhooks."""
    
    def __init__(
        self,
        webhook_repository: WebhookRepository,
        webhook_publisher: WebhookPublisher,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        """
        Initialize service.
        
        Args:
            webhook_repository: Repository for saving webhook events
            webhook_publisher: Publisher for RabbitMQ messages
            phone_number_id: WhatsApp Phone Number ID (for marking read and audio download)
            access_token: WhatsApp access token (for marking read and audio download)
        """
        # Initialize processor with credentials for audio download
        self._processor = WhatsAppProcessor(
            phone_number_id=phone_number_id,
            access_token=access_token
        )
        self._repository = webhook_repository
        self._publisher = webhook_publisher
        self._phone_number_id = phone_number_id
        self._access_token = access_token
    
    async def _mark_as_read_with_typing(self, message_id: str) -> None:
        """
        Mark message as read and show typing indicator.
        
        Shows blue checkmarks + typing bubble with three dots.
        """
        if not self._phone_number_id or not self._access_token:
            return
        
        try:
            client = WhatsAppClient(self._phone_number_id, self._access_token)
            await client.mark_as_read_with_typing(message_id)
            logger.debug(f"Marked as read with typing: {message_id}")
        except Exception as e:
            logger.warning(f"Failed to mark as read with typing: {e}")
    
    async def process_update(
        self,
        update: Dict[str, Any],
        assistant_id: str,
        connection_id: str,
        trace_id: str = None
    ) -> WebhookResponse:
        """
        Process WhatsApp webhook.
        
        Args:
            update: Raw webhook payload
            assistant_id: Assistant ID
            connection_id: Connection ID
            trace_id: Trace ID for logging
            
        Returns:
            WebhookResponse with processing status
        """
        try:
            # Parse webhook
            webhook = WhatsAppWebhook(**update)
            
            # Skip status updates (delivered, read, etc.)
            if webhook.is_status_update():
                logger.debug("Skipping status update")
                return WebhookResponse(success=True, message="Status update skipped")
            
            # Get messages
            messages = webhook.get_messages()
            if not messages:
                logger.debug("No messages in webhook")
                return WebhookResponse(success=True, message="No messages")
            
            # Process first message only (multiple messages rare)
            message = messages[0]
            
            # Only handle text and audio messages
            if message.type not in ("text", "audio"):
                logger.info(f"Skipping unsupported message type: {message.type}")
                return WebhookResponse(
                    success=True,
                    message=f"Message type skipped: {message.type}"
                )
            
            # Extract data
            user_id = self._processor.get_user_id(update)
            text = self._processor.extract_text(update)
            message_id = self._processor.get_message_id(update)
            user_info = self._processor.get_user_info(update)
            
            # Mark as read + show typing indicator (blue checkmarks + typing bubble)
            if message_id:
                await self._mark_as_read_with_typing(message_id)
            
            # Audio metadata for voice/audio messages
            audio_metadata: Optional[Dict[str, Any]] = None
            
            # Check for voice/audio messages
            audio_info, audio_type = self._processor.get_audio_or_voice_info(update)
            
            if audio_info and audio_type != "none":
                logger.info(
                    f"Voice/audio message detected: type={audio_type}, "
                    f"media_id={audio_info.get('id')}, mime_type={audio_info.get('mime_type')}"
                )
                
                # WhatsApp doesn't provide duration in webhook, use 0 as default
                # (WhatsApp voice messages don't include duration in payload)
                duration = 0
                
                # Process audio via AudioAwareProcessor
                transcribed_text, audio_metadata = await self._processor.handle_audio_message(
                    file_id=audio_info["id"],
                    duration=duration,
                    mime_type=audio_info.get("mime_type", "audio/ogg"),
                    message_type=audio_type,
                )
                
                # Use transcribed text instead of empty text
                text = transcribed_text
                
                logger.info(
                    f"Audio processed: message_type={audio_metadata.get('message_type')}, "
                    f"duration={audio_metadata.get('audio_duration_seconds')}s, "
                    f"text_length={len(text) if text else 0} chars"
                )
            
            if not user_id or not text:
                logger.warning("Missing user_id or text")
                return WebhookResponse(success=False, message="Missing required fields")
            
            # Save webhook event
            webhook_event = WebhookEvent(
                assistant_id=assistant_id,
                connection_id=connection_id,
                channel="whatsapp",
                user_id=user_id,
                message_id=message_id,
                type="message",
                content=WebhookContent(
                    text=text,
                    from_user=user_info or {},
                    raw=update
                ),
                processed=False
            )
            await self._repository.save_event(webhook_event)
            
            # Build message data for RabbitMQ
            message_data = {
                "type": "message",
                "text": text,
                "message_id": message_id
            }
            
            # Add audio metadata if present
            if audio_metadata:
                message_data["message_type"] = audio_metadata.get("message_type", "text")
                message_data["audio_duration_seconds"] = audio_metadata.get("audio_duration_seconds")
                if audio_metadata.get("audio_language"):
                    message_data["audio_language"] = audio_metadata["audio_language"]
            
            # Publish to RabbitMQ
            await self._publisher.publish_message(
                assistant_id=assistant_id,
                connection_id=connection_id,
                user_id=user_id,
                channel="whatsapp",
                message_data=message_data
            )
            
            logger.info(f"Published WhatsApp message: user={user_id}, msg_id={message_id}")
            return WebhookResponse(success=True, message="Message published")
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return WebhookResponse(success=False, message=str(e))

