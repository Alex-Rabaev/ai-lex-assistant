"""Audio transcription module.

Provides audio processing and transcription capabilities for voice messages
from Telegram and WhatsApp channels.

Exports:
    Constants:
        - MAX_AUDIO_DURATION_SECONDS: Maximum allowed audio duration (300s = 5min)
        - SUPPORTED_AUDIO_FORMATS: List of supported MIME types
        - AUDIO_TOO_LONG: System message for duration limit exceeded
        - TRANSCRIPTION_FAILED: System message for transcription failure
        - UNSUPPORTED_FORMAT: System message for unsupported format

    Exceptions:
        - AudioProcessingError: Base exception for audio errors
        - AudioTooLongError: Audio exceeds duration limit
        - TranscriptionError: Transcription failed after retries
        - UnsupportedFormatError: Audio format not supported
        - AudioDownloadError: File download failed

    Schemas:
        - TranscriptionResult: Result model for successful transcription

    Validation:
        - validate_audio_duration: Validate audio duration is within limit
        - validate_audio_format: Validate audio MIME type is supported

    Services:
        - AudioTranscriptionService: Transcribe audio using OpenAI Whisper API
"""

from app.common.audio.constants import (
    MAX_AUDIO_DURATION_SECONDS,
    SUPPORTED_AUDIO_FORMATS,
    AUDIO_TOO_LONG,
    TRANSCRIPTION_FAILED,
    UNSUPPORTED_FORMAT,
)

from app.common.audio.exceptions import (
    AudioProcessingError,
    AudioTooLongError,
    TranscriptionError,
    UnsupportedFormatError,
    AudioDownloadError,
)

from app.common.audio.schemas import TranscriptionResult

from app.common.audio.validation import (
    validate_audio_duration,
    validate_audio_format,
)

from app.common.audio.transcription import AudioTranscriptionService

__all__ = [
    # Constants
    "MAX_AUDIO_DURATION_SECONDS",
    "SUPPORTED_AUDIO_FORMATS",
    "AUDIO_TOO_LONG",
    "TRANSCRIPTION_FAILED",
    "UNSUPPORTED_FORMAT",
    # Exceptions
    "AudioProcessingError",
    "AudioTooLongError",
    "TranscriptionError",
    "UnsupportedFormatError",
    "AudioDownloadError",
    # Schemas
    "TranscriptionResult",
    # Validation
    "validate_audio_duration",
    "validate_audio_format",
    # Services
    "AudioTranscriptionService",
]
