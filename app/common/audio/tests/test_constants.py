"""Unit tests for audio constants.

Tests that all constants are defined with correct values.
"""

import pytest

from app.common.audio.constants import (
    MAX_AUDIO_DURATION_SECONDS,
    SUPPORTED_AUDIO_FORMATS,
    AUDIO_TOO_LONG,
    TRANSCRIPTION_FAILED,
    UNSUPPORTED_FORMAT,
)


class TestMaxAudioDuration:
    """Tests for MAX_AUDIO_DURATION_SECONDS constant."""
    
    def test_value_is_300_seconds(self):
        """Test max duration is 5 minutes (300 seconds)."""
        assert MAX_AUDIO_DURATION_SECONDS == 300
    
    def test_value_is_integer(self):
        """Test max duration is an integer."""
        assert isinstance(MAX_AUDIO_DURATION_SECONDS, int)


class TestSupportedAudioFormats:
    """Tests for SUPPORTED_AUDIO_FORMATS constant."""
    
    def test_contains_ogg(self):
        """Test OGG format is supported (Telegram voice messages)."""
        assert "audio/ogg" in SUPPORTED_AUDIO_FORMATS
    
    def test_contains_mpeg(self):
        """Test MPEG/MP3 format is supported."""
        assert "audio/mpeg" in SUPPORTED_AUDIO_FORMATS
    
    def test_contains_mp4(self):
        """Test M4A format is supported (audio/mp4)."""
        assert "audio/mp4" in SUPPORTED_AUDIO_FORMATS
    
    def test_contains_wav(self):
        """Test WAV format is supported."""
        assert "audio/wav" in SUPPORTED_AUDIO_FORMATS
    
    def test_is_list(self):
        """Test formats is a list."""
        assert isinstance(SUPPORTED_AUDIO_FORMATS, list)
    
    def test_has_four_formats(self):
        """Test exactly 4 formats are supported."""
        assert len(SUPPORTED_AUDIO_FORMATS) == 4


class TestSystemMessages:
    """Tests for system error messages."""
    
    def test_audio_too_long_format(self):
        """Test AUDIO_TOO_LONG has correct format."""
        assert AUDIO_TOO_LONG == "[SYSTEM: Audio too long (>5min)]"
    
    def test_audio_too_long_is_bracketed(self):
        """Test AUDIO_TOO_LONG starts with [SYSTEM:."""
        assert AUDIO_TOO_LONG.startswith("[SYSTEM:")
        assert AUDIO_TOO_LONG.endswith("]")
    
    def test_transcription_failed_format(self):
        """Test TRANSCRIPTION_FAILED has correct format."""
        assert TRANSCRIPTION_FAILED == "[SYSTEM: Audio transcription failed]"
    
    def test_transcription_failed_is_bracketed(self):
        """Test TRANSCRIPTION_FAILED starts with [SYSTEM:."""
        assert TRANSCRIPTION_FAILED.startswith("[SYSTEM:")
        assert TRANSCRIPTION_FAILED.endswith("]")
    
    def test_unsupported_format_format(self):
        """Test UNSUPPORTED_FORMAT has correct format."""
        assert UNSUPPORTED_FORMAT == "[SYSTEM: Unsupported audio format]"
    
    def test_unsupported_format_is_bracketed(self):
        """Test UNSUPPORTED_FORMAT starts with [SYSTEM:."""
        assert UNSUPPORTED_FORMAT.startswith("[SYSTEM:")
        assert UNSUPPORTED_FORMAT.endswith("]")
    
    def test_all_messages_are_strings(self):
        """Test all system messages are strings."""
        assert isinstance(AUDIO_TOO_LONG, str)
        assert isinstance(TRANSCRIPTION_FAILED, str)
        assert isinstance(UNSUPPORTED_FORMAT, str)
