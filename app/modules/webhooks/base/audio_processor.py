"""Audio-aware webhook processor base class.

Extends BaseProcessor with audio message handling capabilities.
Telegram and WhatsApp processors inherit from this class.
"""

import logging
import os
from abc import abstractmethod
from typing import Dict, Any, Tuple

from app.modules.webhooks.base.processor import BaseProcessor
from app.common.audio import (
    AudioTranscriptionService,
    validate_audio_duration,
    validate_audio_format,
    AudioTooLongError,
    UnsupportedFormatError,
    TranscriptionError,
    AudioDownloadError,
    AUDIO_TOO_LONG,
    TRANSCRIPTION_FAILED,
    UNSUPPORTED_FORMAT,
)

logger = logging.getLogger(__name__)


class AudioAwareProcessor(BaseProcessor):
    """Base processor with audio message handling capability.
    
    Extends BaseProcessor to add:
    - Audio validation (duration, format)
    - Audio download (abstract, implemented by subclasses)
    - Transcription via OpenAI Whisper API
    - Error handling with system messages
    - Temporary file cleanup
    
    Subclasses must implement:
    - download_audio_file(file_id) -> temp file path
    - All BaseProcessor abstract methods
    """
    
    def __init__(self):
        """Initialize audio-aware processor."""
        self._transcription_service = AudioTranscriptionService()
    
    @abstractmethod
    async def download_audio_file(self, file_id: str) -> str:
        """Download audio file and return path to temporary file.
        
        This method must be implemented by subclasses (TelegramProcessor,
        WhatsAppProcessor) to handle platform-specific download logic.
        
        Args:
            file_id: Platform-specific file identifier.
            
        Returns:
            Path to downloaded temporary audio file.
            
        Raises:
            AudioDownloadError: If download fails after retries.
        """
        pass
    
    async def handle_audio_message(
        self,
        file_id: str,
        duration: int,
        mime_type: str,
        message_type: str = "voice",
    ) -> Tuple[str, Dict[str, Any]]:
        """Process audio message: validate, download, transcribe.
        
        Orchestrates the full audio processing pipeline:
        1. Validate duration (< 5 min)
        2. Validate format (supported MIME types)
        3. Download audio file to temp location
        4. Transcribe using Whisper API
        5. Clean up temp file (always, in finally block)
        
        Args:
            file_id: Platform-specific file identifier.
            duration: Audio duration in seconds.
            mime_type: MIME type of the audio (e.g., "audio/ogg").
            message_type: Type of message ("voice" or "audio").
            
        Returns:
            Tuple of (content, metadata) where:
            - content: Transcript text OR system error message
            - metadata: {"message_type": str, "audio_duration_seconds": int}
        """
        # Prepare base metadata (always returned)
        metadata = {
            "message_type": message_type,
            "audio_duration_seconds": duration,
        }
        
        # Step 1: Validate duration BEFORE any downloads
        try:
            validate_audio_duration(duration)
        except AudioTooLongError:
            logger.warning(
                f"Audio too long: {duration}s exceeds limit"
            )
            return AUDIO_TOO_LONG, metadata
        
        # Step 2: Validate format
        try:
            validate_audio_format(mime_type)
        except UnsupportedFormatError:
            logger.warning(
                f"Unsupported audio format: {mime_type}"
            )
            return UNSUPPORTED_FORMAT, metadata
        
        # Step 3-4: Download and transcribe with cleanup
        temp_path = None
        try:
            # Download audio file
            logger.info(
                f"Downloading audio: file_id={file_id}, "
                f"duration={duration}s, mime_type={mime_type}"
            )
            temp_path = await self.download_audio_file(file_id)
            
            # Transcribe
            result = await self._transcription_service.transcribe(
                audio_file_path=temp_path,
                message_type=message_type,
            )
            
            logger.info(
                f"Transcription successful: duration={result.duration_seconds}s, "
                f"language={result.language}, text_length={len(result.text)} chars"
            )
            
            # Update metadata with actual values from transcription
            metadata["audio_duration_seconds"] = result.duration_seconds
            if result.language:
                metadata["audio_language"] = result.language
            
            return result.text, metadata
            
        except AudioDownloadError as e:
            logger.error(f"Audio download failed: {e}")
            return TRANSCRIPTION_FAILED, metadata
            
        except TranscriptionError as e:
            logger.error(f"Transcription failed: {e}")
            return TRANSCRIPTION_FAILED, metadata
            
        except Exception as e:
            logger.error(
                f"Unexpected error in audio processing: {type(e).__name__}: {e}",
                exc_info=True
            )
            return TRANSCRIPTION_FAILED, metadata
            
        finally:
            # Step 5: ALWAYS clean up temp file (security requirement)
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temp audio file: {temp_path}")
                except OSError as e:
                    logger.warning(f"Failed to delete temp file {temp_path}: {e}")
