"""Audio transcription service using OpenAI Whisper API.

Provides audio-to-text conversion with retry logic and error handling.
"""

import logging
import os
from pathlib import Path

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.common.audio.schemas import TranscriptionResult
from app.common.audio.exceptions import TranscriptionError
from app.config import config

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """Service for transcribing audio using OpenAI Whisper API.
    
    Features:
    - Async transcription via OpenAI Whisper API
    - Automatic retry with exponential backoff (1s, 2s, 4s)
    - Returns structured TranscriptionResult
    - No audio data logging (security requirement)
    """
    
    def __init__(self, client: AsyncOpenAI | None = None):
        """Initialize transcription service.
        
        Args:
            client: Optional AsyncOpenAI client for dependency injection (testing).
                   If not provided, creates client using config.OPENAI_API_KEY.
        """
        self._client = client or AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _call_whisper_api(
        self,
        audio_file_path: str,
        language_hint: str | None = None,
    ) -> dict:
        """Call Whisper API with retry logic.
        
        Args:
            audio_file_path: Path to the audio file.
            language_hint: Optional ISO-639-1 language code hint.
            
        Returns:
            Raw API response dict with 'text' field.
            
        Raises:
            Exception: On API errors (will be retried up to 3 times).
        """
        # Log only metadata, never audio content
        file_size = os.path.getsize(audio_file_path)
        logger.info(
            f"Calling Whisper API: file_size={file_size} bytes, "
            f"language_hint={language_hint}"
        )
        
        with open(audio_file_path, "rb") as audio_file:
            kwargs = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json",
            }
            if language_hint:
                kwargs["language"] = language_hint
            
            response = await self._client.audio.transcriptions.create(**kwargs)
        
        return response
    
    async def transcribe(
        self,
        audio_file_path: str,
        message_type: str = "voice",
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio file to text.
        
        Args:
            audio_file_path: Path to the audio file.
            message_type: Type of message ("voice" or "audio").
            language_hint: Optional ISO-639-1 language code hint for accuracy.
            
        Returns:
            TranscriptionResult with transcript text and metadata.
            
        Raises:
            TranscriptionError: After 3 failed retries.
            FileNotFoundError: If audio file doesn't exist.
        """
        # Validate file exists
        if not Path(audio_file_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
        
        try:
            response = await self._call_whisper_api(
                audio_file_path=audio_file_path,
                language_hint=language_hint,
            )
            
            # Extract data from response
            text = response.text
            duration_seconds = int(response.duration) if response.duration else 0
            language = response.language
            
            # Log only metadata, never transcript content
            logger.info(
                f"Transcription complete: duration={duration_seconds}s, "
                f"language={language}, text_length={len(text)} chars"
            )
            
            return TranscriptionResult(
                text=text,
                duration_seconds=duration_seconds,
                message_type=message_type,
                language=language,
            )
            
        except FileNotFoundError:
            raise
        except Exception as e:
            # All retries exhausted or non-retryable error
            logger.error(
                f"Transcription failed after retries: {type(e).__name__}: {e}",
                exc_info=False  # Don't log full traceback with audio data
            )
            raise TranscriptionError(f"Transcription failed: {e}") from e
