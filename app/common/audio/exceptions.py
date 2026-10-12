"""Custom exceptions for audio transcription module.

These exceptions are raised during audio processing and should be
caught by the AudioAwareProcessor to generate appropriate system messages.
"""


class AudioProcessingError(Exception):
    """Base exception for audio processing errors."""
    pass


class AudioTooLongError(AudioProcessingError):
    """Raised when audio duration exceeds MAX_AUDIO_DURATION_SECONDS."""
    
    def __init__(self, duration: int, max_duration: int = 300):
        self.duration = duration
        self.max_duration = max_duration
        super().__init__(
            f"Audio duration {duration}s exceeds maximum {max_duration}s"
        )


class TranscriptionError(AudioProcessingError):
    """Raised when audio transcription fails after all retries."""
    
    def __init__(self, message: str = "Transcription failed"):
        super().__init__(message)


class UnsupportedFormatError(AudioProcessingError):
    """Raised when audio format is not in SUPPORTED_AUDIO_FORMATS."""
    
    def __init__(self, mime_type: str):
        self.mime_type = mime_type
        super().__init__(f"Unsupported audio format: {mime_type}")


class AudioDownloadError(AudioProcessingError):
    """Raised when audio file download fails after all retries."""
    
    def __init__(self, message: str = "Audio download failed"):
        super().__init__(message)
