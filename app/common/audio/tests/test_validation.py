"""Unit tests for audio validation functions.

Tests validate_audio_duration and validate_audio_format functions.
"""

import pytest

from app.common.audio.validation import (
    validate_audio_duration,
    validate_audio_format,
)
from app.common.audio.exceptions import (
    AudioTooLongError,
    UnsupportedFormatError,
)
from app.common.audio.constants import (
    MAX_AUDIO_DURATION_SECONDS,
    SUPPORTED_AUDIO_FORMATS,
)


class TestValidateAudioDuration:
    """Tests for validate_audio_duration function."""
    
    def test_duration_within_limit_passes(self):
        """Test validation passes for duration within limit."""
        # Should not raise any exception
        validate_audio_duration(100)
    
    def test_duration_exactly_at_limit_passes(self):
        """Test validation passes for duration exactly at limit (300s)."""
        # Exactly 300 seconds should pass
        validate_audio_duration(300)
    
    def test_duration_zero_passes(self):
        """Test validation passes for zero duration."""
        validate_audio_duration(0)
    
    def test_duration_one_second_passes(self):
        """Test validation passes for 1 second duration."""
        validate_audio_duration(1)
    
    def test_duration_exceeds_limit_raises_error(self):
        """Test validation raises AudioTooLongError for duration > 300s."""
        with pytest.raises(AudioTooLongError):
            validate_audio_duration(301)
    
    def test_duration_way_over_limit_raises_error(self):
        """Test validation raises error for duration way over limit."""
        with pytest.raises(AudioTooLongError):
            validate_audio_duration(600)
    
    def test_error_contains_duration_value(self):
        """Test error contains the actual duration value."""
        with pytest.raises(AudioTooLongError) as exc_info:
            validate_audio_duration(350)
        
        assert exc_info.value.duration == 350
    
    def test_error_contains_max_duration(self):
        """Test error contains the max duration value."""
        with pytest.raises(AudioTooLongError) as exc_info:
            validate_audio_duration(400)
        
        assert exc_info.value.max_duration == MAX_AUDIO_DURATION_SECONDS
    
    def test_boundary_299_passes(self):
        """Test 299 seconds (just under limit) passes."""
        validate_audio_duration(299)
    
    def test_boundary_301_fails(self):
        """Test 301 seconds (just over limit) fails."""
        with pytest.raises(AudioTooLongError):
            validate_audio_duration(301)


class TestValidateAudioFormat:
    """Tests for validate_audio_format function."""
    
    def test_ogg_format_passes(self):
        """Test audio/ogg format passes validation (Telegram voice)."""
        validate_audio_format("audio/ogg")
    
    def test_mpeg_format_passes(self):
        """Test audio/mpeg format passes validation (MP3)."""
        validate_audio_format("audio/mpeg")
    
    def test_mp4_format_passes(self):
        """Test audio/mp4 format passes validation (M4A)."""
        validate_audio_format("audio/mp4")
    
    def test_wav_format_passes(self):
        """Test audio/wav format passes validation."""
        validate_audio_format("audio/wav")
    
    def test_video_mp4_raises_error(self):
        """Test video/mp4 format raises UnsupportedFormatError."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("video/mp4")
    
    def test_video_webm_raises_error(self):
        """Test video/webm format raises error."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("video/webm")
    
    def test_text_plain_raises_error(self):
        """Test text/plain format raises error."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("text/plain")
    
    def test_application_pdf_raises_error(self):
        """Test application/pdf format raises error."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("application/pdf")
    
    def test_empty_string_raises_error(self):
        """Test empty string raises error."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("")
    
    def test_error_contains_mime_type(self):
        """Test error contains the rejected mime_type."""
        with pytest.raises(UnsupportedFormatError) as exc_info:
            validate_audio_format("video/mp4")
        
        assert exc_info.value.mime_type == "video/mp4"
    
    def test_case_sensitive(self):
        """Test validation is case-sensitive (AUDIO/OGG should fail)."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("AUDIO/OGG")
    
    def test_audio_webm_raises_error(self):
        """Test audio/webm format raises error (not in supported list)."""
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("audio/webm")
    
    def test_all_supported_formats_pass(self):
        """Test all formats in SUPPORTED_AUDIO_FORMATS pass."""
        for mime_type in SUPPORTED_AUDIO_FORMATS:
            # Should not raise
            validate_audio_format(mime_type)


class TestValidationIntegration:
    """Integration tests for validation functions."""
    
    def test_valid_audio_metadata(self):
        """Test both validations pass for valid audio."""
        # Typical Telegram voice message
        duration = 30  # 30 seconds
        mime_type = "audio/ogg"
        
        # Both should pass without exception
        validate_audio_duration(duration)
        validate_audio_format(mime_type)
    
    def test_invalid_duration_valid_format(self):
        """Test duration validation fails even if format is valid."""
        with pytest.raises(AudioTooLongError):
            validate_audio_duration(400)
        
        # Format validation would pass
        validate_audio_format("audio/ogg")
    
    def test_valid_duration_invalid_format(self):
        """Test format validation fails even if duration is valid."""
        validate_audio_duration(60)
        
        with pytest.raises(UnsupportedFormatError):
            validate_audio_format("video/mp4")
    
    def test_whatsapp_audio_typical(self):
        """Test typical WhatsApp audio message passes."""
        duration = 120  # 2 minutes
        mime_type = "audio/mp4"  # WhatsApp often uses M4A
        
        validate_audio_duration(duration)
        validate_audio_format(mime_type)
    
    def test_max_allowed_audio(self):
        """Test maximum allowed audio (5 minutes) passes."""
        duration = 300  # Exactly 5 minutes
        mime_type = "audio/ogg"
        
        validate_audio_duration(duration)
        validate_audio_format(mime_type)
