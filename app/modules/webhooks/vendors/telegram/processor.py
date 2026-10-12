"""Telegram webhook processor."""

import logging
from typing import Optional, Dict, Any, Tuple

from app.modules.webhooks.base.audio_processor import AudioAwareProcessor
from app.modules.webhooks.vendors.telegram.schemas import TelegramUpdate
from app.modules.outbound.vendors.telegram.client import TelegramClient

logger = logging.getLogger(__name__)


class TelegramProcessor(AudioAwareProcessor):
    """
    Processor for Telegram webhook updates.
    Extracts and normalizes data from Telegram Bot API format.
    
    Inherits from AudioAwareProcessor to support voice/audio message
    transcription via OpenAI Whisper API.
    """
    
    def __init__(self, bot_token: Optional[str] = None):
        """
        Initialize Telegram processor.
        
        Args:
            bot_token: Telegram bot token for downloading audio files.
                       Required for voice/audio message processing.
        """
        super().__init__()
        self._bot_token = bot_token
        self._telegram_client: Optional[TelegramClient] = None
        
        if bot_token:
            self._telegram_client = TelegramClient(bot_token)
    
    async def download_audio_file(self, file_id: str) -> str:
        """
        Download audio file from Telegram using TelegramClient.
        
        Args:
            file_id: Telegram file identifier.
            
        Returns:
            Path to downloaded temporary audio file.
            
        Raises:
            AudioDownloadError: If download fails or no client configured.
        """
        from app.common.audio.exceptions import AudioDownloadError
        
        if not self._telegram_client:
            raise AudioDownloadError(
                "TelegramClient not configured (missing bot_token)"
            )
        
        return await self._telegram_client.download_file(file_id)
    
    def extract_text(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract text message from Telegram update.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Extracted text or None if not a text message
        """
        try:
            # Parse update
            telegram_update = TelegramUpdate(**update)
            
            # Check callback query data first (priority for callback data)
            if telegram_update.callback_query and telegram_update.callback_query.data:
                return telegram_update.callback_query.data
            
            # Then check for regular message
            message = telegram_update.get_message()
            if message:
                # Return text or caption (for media messages)
                return message.text or message.caption
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting text from Telegram update: {e}")
            return None
    
    def get_user_id(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract and format user ID from Telegram update.
        Format: telegram_{chat_id} (we use chat_id for consistency)
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Formatted user ID (telegram_123456) or None
        """
        try:
            telegram_update = TelegramUpdate(**update)
            
            # Get chat ID (more reliable than user ID for our use case)
            chat = telegram_update.get_chat()
            if chat:
                return f"telegram_{chat.id}"
            
            # Fallback to callback query chat
            if telegram_update.callback_query and telegram_update.callback_query.message:
                return f"telegram_{telegram_update.callback_query.message.chat.id}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user ID from Telegram update: {e}")
            return None
    
    def get_user_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract user information from Telegram update.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Dictionary with user information or None
        """
        try:
            telegram_update = TelegramUpdate(**update)
            user = telegram_update.get_user()
            
            if user:
                return {
                    "id": user.id,
                    "is_bot": user.is_bot,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "language_code": user.language_code,
                    "is_premium": user.is_premium
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user info from Telegram update: {e}")
            return None
    
    def get_chat_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract chat/conversation information from Telegram update.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Dictionary with chat information or None
        """
        try:
            telegram_update = TelegramUpdate(**update)
            chat = telegram_update.get_chat()
            
            if chat:
                return {
                    "id": chat.id,
                    "type": chat.type,
                    "title": chat.title,
                    "username": chat.username,
                    "first_name": chat.first_name,
                    "last_name": chat.last_name,
                    "is_forum": chat.is_forum
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting chat info from Telegram update: {e}")
            return None
    
    def get_message_type(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Determine the type of message from Telegram update.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Message type: 'message', 'callback_query', 'edited_message', 'command', etc.
        """
        try:
            telegram_update = TelegramUpdate(**update)
            
            # Check for callback query first
            if telegram_update.callback_query:
                return "callback_query"
            
            # Check for edited message
            if telegram_update.edited_message or telegram_update.edited_channel_post:
                return "edited_message"
            
            # Check for regular message
            # Note: Commands are treated as regular messages (no special handling)
            if telegram_update.message or telegram_update.channel_post:
                return "message"
            
            return None
            
        except Exception as e:
            logger.error(f"Error determining message type from Telegram update: {e}")
            return None
    
    def get_message_id(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract message ID from Telegram update.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Message ID as string or None
        """
        try:
            telegram_update = TelegramUpdate(**update)
            
            # For callback queries, use the query ID (priority)
            if telegram_update.callback_query:
                return telegram_update.callback_query.id
            
            # For regular messages
            message = telegram_update.get_message()
            if message:
                return str(message.message_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting message ID from Telegram update: {e}")
            return None
    
    def get_update_id(
        self, 
        update: Dict[str, Any],
        assistant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Extract Telegram update_id for deduplication.
        If update_id is missing, generates it from hash of assistant_id, user_id, message_date, and text.
        
        Args:
            update: Raw Telegram webhook update
            assistant_id: Assistant ID (required for hash generation if update_id missing)
            user_id: User ID (required for hash generation if update_id missing)
            
        Returns:
            Update ID or None
        """
        try:
            telegram_update = TelegramUpdate(**update)
            update_id = telegram_update.update_id
            
            # Generate update_id from hash if missing
            if not update_id and assistant_id and user_id:
                import hashlib
                # Extract message date from update
                message_date = None
                if update.get("message"):
                    message_date = update["message"].get("date")
                elif update.get("callback_query") and update["callback_query"].get("message"):
                    message_date = update["callback_query"]["message"].get("date")
                
                # Extract text
                text = self.extract_text(update) or ""
                
                # Create hash from: assistant_id + user_id + message_date + message_text
                hash_string = f"{assistant_id}_{user_id}_{message_date}_{text}"
                update_id = int(hashlib.md5(hash_string.encode()).hexdigest()[:8], 16)
                logger.info(f"Generated update_id from hash: {update_id}")
            
            return update_id
            
        except Exception as e:
            logger.error(f"Error getting update_id from Telegram update: {e}")
            return None
    
    def process(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Telegram update and extract all relevant information.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Dictionary with extracted and normalized information
        """
        result = super().process(update)
        
        # Add Telegram-specific fields
        result["update_id"] = self.get_update_id(update)
        
        # Parse the update for validation
        try:
            telegram_update = TelegramUpdate(**update)
            result["is_valid"] = True
            
            # Add parsed update for convenience
            result["parsed_update"] = telegram_update
            
        except Exception as e:
            logger.warning(f"Failed to parse Telegram update: {e}")
            result["is_valid"] = False
            result["parse_error"] = str(e)
        
        return result
    
    # =========================================================================
    # Voice/Audio Detection Methods
    # =========================================================================
    
    def get_voice_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract voice message information from Telegram update.
        
        Voice messages are recorded directly in Telegram (typically OGG format).
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Dictionary with voice info (file_id, duration, mime_type, file_size)
            or None if not a voice message
        """
        try:
            telegram_update = TelegramUpdate(**update)
            message = telegram_update.get_message()
            
            if message and message.voice:
                voice = message.voice
                return {
                    "file_id": voice.get("file_id"),
                    "file_unique_id": voice.get("file_unique_id"),
                    "duration": voice.get("duration", 0),
                    "mime_type": voice.get("mime_type", "audio/ogg"),
                    "file_size": voice.get("file_size"),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting voice info from Telegram update: {e}")
            return None
    
    def get_audio_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract audio file information from Telegram update.
        
        Audio files are music files sent as attachments (MP3, etc.).
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Dictionary with audio info (file_id, duration, mime_type, etc.)
            or None if not an audio message
        """
        try:
            telegram_update = TelegramUpdate(**update)
            message = telegram_update.get_message()
            
            if message and message.audio:
                audio = message.audio
                return {
                    "file_id": audio.get("file_id"),
                    "file_unique_id": audio.get("file_unique_id"),
                    "duration": audio.get("duration", 0),
                    "mime_type": audio.get("mime_type", "audio/mpeg"),
                    "file_size": audio.get("file_size"),
                    "performer": audio.get("performer"),
                    "title": audio.get("title"),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting audio info from Telegram update: {e}")
            return None
    
    def is_voice_message(self, update: Dict[str, Any]) -> bool:
        """
        Check if the update contains a voice message.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            True if this is a voice message
        """
        return self.get_voice_info(update) is not None
    
    def is_audio_message(self, update: Dict[str, Any]) -> bool:
        """
        Check if the update contains an audio file.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            True if this is an audio file message
        """
        return self.get_audio_info(update) is not None
    
    def is_video_message(self, update: Dict[str, Any]) -> bool:
        """
        Check if the update contains a video or video_note.
        
        Video messages should NOT be processed as audio.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            True if this is a video message
        """
        try:
            telegram_update = TelegramUpdate(**update)
            message = telegram_update.get_message()
            
            if message:
                return bool(message.video or message.video_note)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking video message: {e}")
            return False
    
    def get_audio_or_voice_info(
        self, 
        update: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Get audio/voice info and determine message type.
        
        Convenience method that returns both the media info and the type.
        Prioritizes voice over audio.
        
        Args:
            update: Raw Telegram webhook update
            
        Returns:
            Tuple of (info_dict, message_type) where:
            - info_dict: Media info or None
            - message_type: "voice", "audio", or "none"
        """
        voice_info = self.get_voice_info(update)
        if voice_info:
            return voice_info, "voice"
        
        audio_info = self.get_audio_info(update)
        if audio_info:
            return audio_info, "audio"
        
        return None, "none"
