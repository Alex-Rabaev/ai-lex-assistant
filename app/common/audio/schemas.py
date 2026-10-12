"""Pydantic schemas for audio transcription module.

Contains data models for transcription results and audio metadata.
"""

from pydantic import BaseModel, ConfigDict


class TranscriptionResult(BaseModel):
    """Result of audio transcription from Whisper API.
    
    Attributes:
        text: The transcribed text content.
        duration_seconds: Duration of the audio in seconds.
        message_type: Type of message ("voice" or "audio").
        language: Detected or specified language (optional).
    """
    
    model_config = ConfigDict(frozen=True)
    
    text: str
    duration_seconds: int
    message_type: str  # "voice" | "audio"
    language: str | None = None
