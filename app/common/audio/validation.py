"""Validation functions for audio processing.

Validates audio metadata before processing to reject invalid audio early
and save API costs.
"""

from app.common.audio.constants import (
    MAX_AUDIO_DURATION_SECONDS,
    SUPPORTED_AUDIO_FORMATS,
)
from app.common.audio.exceptions import (
    AudioTooLongError,
    UnsupportedFormatError,
)


def validate_audio_duration(duration: int) -> None:
    """Validate audio duration is within allowed limit.
    
    Args:
        duration: Audio duration in seconds.
        
    Raises:
        AudioTooLongError: If duration exceeds MAX_AUDIO_DURATION_SECONDS (300s).
    """
    if duration > MAX_AUDIO_DURATION_SECONDS:
        raise AudioTooLongError(
            duration=duration,
            max_duration=MAX_AUDIO_DURATION_SECONDS
        )


def validate_audio_format(mime_type: str) -> None:
    """Validate audio format is supported.
    
    Args:
        mime_type: MIME type of the audio file (e.g., "audio/ogg").
        
    Raises:
        UnsupportedFormatError: If mime_type is not in SUPPORTED_AUDIO_FORMATS.
    """
    if mime_type not in SUPPORTED_AUDIO_FORMATS:
        raise UnsupportedFormatError(mime_type=mime_type)
