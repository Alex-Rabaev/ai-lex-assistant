"""Unit tests for audio schemas.

Tests Pydantic models for transcription results.
"""

import pytest
from pydantic import ValidationError

from app.common.audio.schemas import TranscriptionResult


class TestTranscriptionResult:
    """Tests for TranscriptionResult schema."""
    
    def test_create_with_required_fields(self):
        """Test creating result with required fields only."""
        result = TranscriptionResult(
            text="Hello, world!",
            duration_seconds=10,
            message_type="voice"
        )
        
        assert result.text == "Hello, world!"
        assert result.duration_seconds == 10
        assert result.message_type == "voice"
        assert result.language is None
    
    def test_create_with_all_fields(self):
        """Test creating result with all fields including language."""
        result = TranscriptionResult(
            text="Привет, мир!",
            duration_seconds=15,
            message_type="audio",
            language="Russian"
        )
        
        assert result.text == "Привет, мир!"
        assert result.duration_seconds == 15
        assert result.message_type == "audio"
        assert result.language == "Russian"
    
    def test_voice_message_type(self):
        """Test creating result with voice message type."""
        result = TranscriptionResult(
            text="Test",
            duration_seconds=5,
            message_type="voice"
        )
        
        assert result.message_type == "voice"
    
    def test_audio_message_type(self):
        """Test creating result with audio message type."""
        result = TranscriptionResult(
            text="Test",
            duration_seconds=5,
            message_type="audio"
        )
        
        assert result.message_type == "audio"
    
    def test_empty_text_allowed(self):
        """Test creating result with empty text (edge case)."""
        result = TranscriptionResult(
            text="",
            duration_seconds=1,
            message_type="voice"
        )
        
        assert result.text == ""
    
    def test_zero_duration_allowed(self):
        """Test creating result with zero duration (edge case)."""
        result = TranscriptionResult(
            text="Test",
            duration_seconds=0,
            message_type="voice"
        )
        
        assert result.duration_seconds == 0
    
    def test_missing_text_raises_error(self):
        """Test missing text field raises validation error."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                duration_seconds=10,
                message_type="voice"
            )
    
    def test_missing_duration_raises_error(self):
        """Test missing duration_seconds field raises validation error."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                text="Test",
                message_type="voice"
            )
    
    def test_missing_message_type_raises_error(self):
        """Test missing message_type field raises validation error."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                text="Test",
                duration_seconds=10
            )
    
    def test_model_is_frozen(self):
        """Test model is immutable (frozen)."""
        result = TranscriptionResult(
            text="Test",
            duration_seconds=10,
            message_type="voice"
        )
        
        with pytest.raises(ValidationError):
            result.text = "Modified"
    
    def test_model_dump(self):
        """Test model can be converted to dict."""
        result = TranscriptionResult(
            text="Hello",
            duration_seconds=20,
            message_type="voice",
            language="English"
        )
        
        data = result.model_dump()
        
        assert data["text"] == "Hello"
        assert data["duration_seconds"] == 20
        assert data["message_type"] == "voice"
        assert data["language"] == "English"
    
    def test_model_dump_without_language(self):
        """Test model dump includes None for optional language."""
        result = TranscriptionResult(
            text="Test",
            duration_seconds=5,
            message_type="voice"
        )
        
        data = result.model_dump()
        
        assert data["language"] is None
    
    def test_long_text(self):
        """Test creating result with long text (transcription of 5 min audio)."""
        long_text = "Word " * 1000  # Approximately 1000 words
        result = TranscriptionResult(
            text=long_text,
            duration_seconds=300,
            message_type="voice"
        )
        
        assert len(result.text) > 4000
        assert result.duration_seconds == 300


class TestTranscriptionResultFromDict:
    """Tests for creating TranscriptionResult from dict (deserialization)."""
    
    def test_create_from_dict(self):
        """Test creating result from dictionary."""
        data = {
            "text": "Hello from dict",
            "duration_seconds": 30,
            "message_type": "audio",
            "language": "Spanish"
        }
        
        result = TranscriptionResult(**data)
        
        assert result.text == "Hello from dict"
        assert result.duration_seconds == 30
        assert result.message_type == "audio"
        assert result.language == "Spanish"
    
    def test_create_from_minimal_dict(self):
        """Test creating result from dict with only required fields."""
        data = {
            "text": "Minimal",
            "duration_seconds": 5,
            "message_type": "voice"
        }
        
        result = TranscriptionResult(**data)
        
        assert result.text == "Minimal"
        assert result.language is None
