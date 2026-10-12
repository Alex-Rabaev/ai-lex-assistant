"""Unit tests for audio exceptions.

Tests custom exception classes and their behavior.
"""

import pytest

from app.common.audio.exceptions import (
    AudioProcessingError,
    AudioTooLongError,
    TranscriptionError,
    UnsupportedFormatError,
    AudioDownloadError,
)


class TestAudioProcessingError:
    """Tests for AudioProcessingError base exception."""
    
    def test_is_exception(self):
        """Test AudioProcessingError is an Exception."""
        assert issubclass(AudioProcessingError, Exception)
    
    def test_can_be_raised(self):
        """Test AudioProcessingError can be raised."""
        with pytest.raises(AudioProcessingError):
            raise AudioProcessingError("Test error")
    
    def test_message(self):
        """Test exception message is preserved."""
        error = AudioProcessingError("Custom message")
        assert str(error) == "Custom message"


class TestAudioTooLongError:
    """Tests for AudioTooLongError exception."""
    
    def test_inherits_from_base(self):
        """Test AudioTooLongError inherits from AudioProcessingError."""
        assert issubclass(AudioTooLongError, AudioProcessingError)
    
    def test_stores_duration(self):
        """Test exception stores duration value."""
        error = AudioTooLongError(duration=350)
        assert error.duration == 350
    
    def test_stores_max_duration(self):
        """Test exception stores max_duration value."""
        error = AudioTooLongError(duration=350)
        assert error.max_duration == 300  # default
    
    def test_custom_max_duration(self):
        """Test exception accepts custom max_duration."""
        error = AudioTooLongError(duration=500, max_duration=400)
        assert error.duration == 500
        assert error.max_duration == 400
    
    def test_message_format(self):
        """Test exception message contains duration info."""
        error = AudioTooLongError(duration=350, max_duration=300)
        assert "350" in str(error)
        assert "300" in str(error)
    
    def test_can_be_caught_as_base(self):
        """Test can be caught as AudioProcessingError."""
        with pytest.raises(AudioProcessingError):
            raise AudioTooLongError(duration=400)


class TestTranscriptionError:
    """Tests for TranscriptionError exception."""
    
    def test_inherits_from_base(self):
        """Test TranscriptionError inherits from AudioProcessingError."""
        assert issubclass(TranscriptionError, AudioProcessingError)
    
    def test_default_message(self):
        """Test default error message."""
        error = TranscriptionError()
        assert str(error) == "Transcription failed"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = TranscriptionError("API timeout")
        assert str(error) == "API timeout"
    
    def test_can_be_caught_as_base(self):
        """Test can be caught as AudioProcessingError."""
        with pytest.raises(AudioProcessingError):
            raise TranscriptionError()


class TestUnsupportedFormatError:
    """Tests for UnsupportedFormatError exception."""
    
    def test_inherits_from_base(self):
        """Test UnsupportedFormatError inherits from AudioProcessingError."""
        assert issubclass(UnsupportedFormatError, AudioProcessingError)
    
    def test_stores_mime_type(self):
        """Test exception stores mime_type value."""
        error = UnsupportedFormatError(mime_type="video/mp4")
        assert error.mime_type == "video/mp4"
    
    def test_message_contains_mime_type(self):
        """Test exception message contains mime_type."""
        error = UnsupportedFormatError(mime_type="application/pdf")
        assert "application/pdf" in str(error)
    
    def test_can_be_caught_as_base(self):
        """Test can be caught as AudioProcessingError."""
        with pytest.raises(AudioProcessingError):
            raise UnsupportedFormatError(mime_type="text/plain")


class TestAudioDownloadError:
    """Tests for AudioDownloadError exception."""
    
    def test_inherits_from_base(self):
        """Test AudioDownloadError inherits from AudioProcessingError."""
        assert issubclass(AudioDownloadError, AudioProcessingError)
    
    def test_default_message(self):
        """Test default error message."""
        error = AudioDownloadError()
        assert str(error) == "Audio download failed"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = AudioDownloadError("Network timeout")
        assert str(error) == "Network timeout"
    
    def test_can_be_caught_as_base(self):
        """Test can be caught as AudioProcessingError."""
        with pytest.raises(AudioProcessingError):
            raise AudioDownloadError()


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""
    
    def test_all_inherit_from_base(self):
        """Test all exceptions inherit from AudioProcessingError."""
        exceptions = [
            AudioTooLongError,
            TranscriptionError,
            UnsupportedFormatError,
            AudioDownloadError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, AudioProcessingError)
    
    def test_base_inherits_from_exception(self):
        """Test base class inherits from Exception."""
        assert issubclass(AudioProcessingError, Exception)
    
    def test_catch_all_with_base(self):
        """Test all exceptions can be caught with base class."""
        errors = [
            AudioTooLongError(duration=400),
            TranscriptionError(),
            UnsupportedFormatError(mime_type="video/mp4"),
            AudioDownloadError(),
        ]
        
        for error in errors:
            try:
                raise error
            except AudioProcessingError as e:
                # Successfully caught
                assert isinstance(e, AudioProcessingError)
