"""Telegram webhook service implementation."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.modules.webhooks.base.service import BaseWebhookService
from app.modules.webhooks.vendors.telegram.processor import TelegramProcessor
from app.modules.webhooks.models import WebhookEvent, WebhookResponse
from app.modules.webhooks.repository import WebhookRepository
from app.modules.webhooks.exceptions import (
    WebhookValidationError
)
from app.modules.connections.service import ConnectionService
from app.modules.connections.models import ConnectionStatus, ConnectionChannel
from app.modules.connections.security import decrypt_token
from app.modules.assistants.service import AssistantService
from app.modules.webhooks.publisher import WebhookPublisher
from app.config import config

logger = logging.getLogger(__name__)


class TelegramWebhookService(BaseWebhookService):
    """
    Service for processing Telegram webhook updates.
    
    Supports voice and audio messages via AudioAwareProcessor.
    """
    
    def __init__(
        self,
        webhook_repository: WebhookRepository,
        webhook_publisher: Optional[WebhookPublisher] = None,
        bot_token: Optional[str] = None
    ):
        """
        Initialize Telegram webhook service.
        
        Args:
            webhook_repository: Repository for webhook events
            webhook_publisher: Optional webhook publisher for RabbitMQ
            bot_token: Optional bot token for audio downloads.
                       If not provided, voice messages cannot be processed.
        """
        self.processor = TelegramProcessor(bot_token=bot_token)
        self.webhook_repo = webhook_repository
        self.webhook_publisher = webhook_publisher
        self._connection_service = ConnectionService()
        self._assistant_service = AssistantService()
    
    async def process_update(
        self,
        update: Dict[str, Any],
        assistant_id: str,
        connection_id: str
    ) -> WebhookResponse:
        """
        Process Telegram webhook update.
        
        Flow:
        1. Extract data using processor
        2. Validate assistant exists
        3. Save webhook event (for debugging and audit)
        4. Publish to RabbitMQ for async processing
        5. Return success response
        
        Args:
            update: Raw Telegram webhook update
            assistant_id: Assistant ID from URL
            connection_id: Connection ID (already retrieved in router)
            
        Returns:
            WebhookResponse with status
        """
        logger.info(f"📨 TELEGRAM WEBHOOK: Received update {update.get('update_id')} for assistant {assistant_id}")
        
        try:
            # Get connection for status updates
            connection = await self._connection_service.get_connection_internal(connection_id)
            
            if not connection:
                logger.error(f"Connection not found: {connection_id}")
                return WebhookResponse(
                    success=False,
                    message="Connection not found"
                )
            
            # 1. Extract data from update
            user_id = self.processor.get_user_id(update)
            if not user_id:
                logger.warning("Could not extract user_id from update")
                return WebhookResponse(
                    success=False,
                    message="Invalid update: no user_id"
                )
            
            # Get update details
            # Note: get_update_id may generate update_id from hash if missing
            update_id = self.processor.get_update_id(update, assistant_id, user_id)
            message_id = self.processor.get_message_id(update)
            message_type = self.processor.get_message_type(update)
            text = self.processor.extract_text(update)
            user_info = self.processor.get_user_info(update)
            
            # Audio metadata for voice/audio messages
            audio_metadata: Optional[Dict[str, Any]] = None
            
            # Check for voice/audio messages
            audio_info, audio_type = self.processor.get_audio_or_voice_info(update)
            
            if audio_info and audio_type != "none":
                logger.info(
                    f"Voice/audio message detected: type={audio_type}, "
                    f"duration={audio_info.get('duration')}s, "
                    f"mime_type={audio_info.get('mime_type')}"
                )
                
                # Process audio: validate, download, transcribe
                transcribed_text, audio_metadata = await self.processor.handle_audio_message(
                    file_id=audio_info["file_id"],
                    duration=audio_info.get("duration", 0),
                    mime_type=audio_info.get("mime_type", "audio/ogg"),
                    message_type=audio_type,
                )
                
                # Use transcribed text (or system error message) as the message text
                text = transcribed_text
                
                logger.info(
                    f"Audio processed: message_type={audio_metadata.get('message_type')}, "
                    f"duration={audio_metadata.get('audio_duration_seconds')}s, "
                    f"text_length={len(text)} chars"
                )
            
            # Check for deduplication
            existing = await self.webhook_repo.get_by_update_id(update_id)
            if existing:
                logger.info(f"Duplicate update_id={update_id}, skipping")
                return WebhookResponse(
                    success=True,
                    message="Duplicate update (already processed)"
                )
            
            # 2. Get assistant
            # For webhooks, we don't have user_id context, use internal method
            try:
                assistant = await self._assistant_service.get_assistant_internal(assistant_id)
            except Exception:
                logger.error(f"Assistant not found: {assistant_id}")
                return WebhookResponse(
                    success=False,
                    message=f"Assistant not found: {assistant_id}"
                )
            
            # 3. Connection already retrieved and validated above
            # Update status if needed (webhook proves connection is working)
            if connection.status != ConnectionStatus.CONNECTED:
                logger.info(f"Updating connection status from {connection.status} to connected (webhook received)")
                await self._connection_service.update_connection_status_internal(
                    str(connection.id),
                    ConnectionStatus.CONNECTED
                )
                # Reload connection to get updated status
                connection = await self._connection_service.get_connection_internal(str(connection.id))
            
            # Build content
            content_dict = {
                "text": text or "",
                "user": user_info or {},
                "type": message_type
            }
            
            # Handle callback queries
            if message_type == "callback_query":
                callback_data = update.get("callback_query", {}).get("data", "")
                callback_id = update.get("callback_query", {}).get("id", "")
                content_dict["callback_data"] = callback_data
                content_dict["callback_id"] = callback_id
            
            # 4. Create and save webhook event
            webhook_event = WebhookEvent(
                assistant_id=assistant_id,
                connection_id=str(connection.id),
                channel=connection.channel.value,
                user_id=user_id,
                type=message_type,
                content=content_dict,
                raw_data=update,
                update_id=update_id,
                message_id=message_id,
                processed=False
            )
            
            saved_event = await self.webhook_repo.save_event(webhook_event)
            
            logger.info(
                f"Webhook event saved: "
                f"event_id={saved_event.id}, "
                f"assistant={assistant_id}, "
                f"user={user_id}, "
                f"type={message_type}"
            )
            
            # 5. Publish to RabbitMQ for async processing
            try:
                connection_id = str(connection.id)
                channel = connection.channel.value  # Extract channel from connection
                
                # Build message data based on type
                message_data = {
                    "type": message_type,
                    "message_id": message_id
                }
                
                # Add type-specific fields
                if message_type == "callback_query":
                    callback_data = update.get("callback_query", {}).get("data", "")
                    callback_id = update.get("callback_query", {}).get("id", "")
                    message_data["callback_data"] = callback_data
                    message_data["callback_id"] = callback_id
                elif text:
                    message_data["text"] = text
                
                # Add audio metadata for voice/audio messages
                if audio_metadata:
                    message_data["message_type"] = audio_metadata.get("message_type", "text")
                    message_data["audio_duration_seconds"] = audio_metadata.get(
                        "audio_duration_seconds"
                    )
                    if audio_metadata.get("audio_language"):
                        message_data["audio_language"] = audio_metadata["audio_language"]
                
                await self.webhook_publisher.publish_message(
                    assistant_id=assistant_id,
                    connection_id=connection_id,
                    user_id=user_id,
                    channel=channel,
                    message_data=message_data
                )
                
                logger.info(
                    f"Webhook processed and queued: "
                    f"event_id={saved_event.id}, "
                    f"assistant={assistant_id}, "
                    f"user={user_id}, "
                    f"type={message_type}"
                )
            except Exception as e:
                logger.error(f"Error publishing to queue: {e}", exc_info=True)
                # Don't fail webhook processing if publishing fails
                # Event is already saved, can be processed later
            
            return WebhookResponse(
                success=True,
                message="Webhook received and saved",
                data={
                    "event_id": str(saved_event.id),
                    "update_id": update_id
                }
            )
            
        except WebhookValidationError as e:
            logger.error(f"Validation error: {e}")
            return WebhookResponse(
                success=False,
                message=f"Validation error: {str(e)}"
            )
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            
            # Try to save error event for debugging
            try:
                error_event = WebhookEvent(
                    assistant_id=assistant_id,
                    channel="telegram",  # Default for error events
                    user_id=user_id if 'user_id' in locals() else "unknown",
                    type="error",
                    content={"error": str(e)},
                    raw_data=update,
                    processed=False,
                    error=str(e)
                )
                await self.webhook_repo.save_event(error_event)
            except:
                pass  # Best effort
            
            return WebhookResponse(
                success=False,
                message=f"Processing error: {str(e)}"
            )
