"""Tests for AudioAwareProcessor base class."""

import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from app.modules.webhooks.base.audio_processor import AudioAwareProcessor
from app.common.audio import (
    TranscriptionResult,
    AudioTooLongError,
    UnsupportedFormatError,
    TranscriptionError,
    AudioDownloadError,
    AUDIO_TOO_LONG,
    TRANSCRIPTION_FAILED,
    UNSUPPORTED_FORMAT,
)


class ConcreteAudioProcessor(AudioAwareProcessor):
    """Concrete implementation for testing."""
    
    def __init__(self, download_result: str | Exception = "/tmp/test.ogg"):
        super().__init__()
        self._download_result = download_result
    
    async def download_audio_file(self, file_id: str) -> str:
        """Mock download implementation."""
        if isinstance(self._download_result, Exception):
            raise self._download_result
        return self._download_result
    
    # Implement BaseProcessor abstract methods (not used in audio tests)
    def extract_text(self, update: Dict[str, Any]) -> Optional[str]:
        return None
    
    def get_user_id(self, update: Dict[str, Any]) -> Optional[str]:
        return None
    
    def get_user_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
    
    def get_chat_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
    
    def get_message_type(self, update: Dict[str, Any]) -> Optional[str]:
        return None
    
    def get_message_id(self, update: Dict[str, Any]) -> Optional[str]:
        return None


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(b"fake audio data")
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_transcription_service():
    """Create mock transcription service."""
    service = MagicMock()
    service.transcribe = AsyncMock(return_value=TranscriptionResult(
        text="Hello, world!",
        duration_seconds=10,
        message_type="voice",
        language="en",
    ))
    return service


@pytest.fixture
def processor(mock_transcription_service, temp_audio_file):
    """Create processor with mocked transcription service."""
    proc = ConcreteAudioProcessor(download_result=temp_audio_file)
    proc._transcription_service = mock_transcription_service
    return proc


class TestHandleAudioMessageSuccess:
    """Tests for successful audio message handling."""
    
    async def test_successful_transcription(self, processor, mock_transcription_service):
        """Test successful transcription returns content and metadata."""
        content, metadata = await processor.handle_audio_message(
            file_id="test_file_id",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert content == "Hello, world!"
        assert metadata["message_type"] == "voice"
        assert metadata["audio_duration_seconds"] == 10  # From transcription result
        assert metadata["audio_language"] == "en"
    
    async def test_transcription_called_with_correct_params(
        self, processor, mock_transcription_service, temp_audio_file
    ):
        """Test transcription service is called with correct parameters."""
        await processor.handle_audio_message(
            file_id="test_file",
            duration=60,
            mime_type="audio/mpeg",
            message_type="audio",
        )
        
        mock_transcription_service.transcribe.assert_called_once_with(
            audio_file_path=temp_audio_file,
            message_type="audio",
        )
    
    async def test_audio_message_type(self, processor, mock_transcription_service):
        """Test handling audio (not voice) message type."""
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=120,
            mime_type="audio/mp4",
            message_type="audio",
        )
        
        assert content == "Hello, world!"
        # Message type comes from input parameter (voice vs audio file)
        assert metadata["message_type"] == "audio"


class TestHandleAudioMessageDurationValidation:
    """Tests for duration validation."""
    
    async def test_duration_exceeds_limit_returns_error(
        self, mock_transcription_service, temp_audio_file
    ):
        """Test audio too long returns system message."""
        processor = ConcreteAudioProcessor(download_result=temp_audio_file)
        processor._transcription_service = mock_transcription_service
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=301,  # Exceeds 300s limit
            mime_type="audio/ogg",
        )
        
        assert content == AUDIO_TOO_LONG
        assert metadata["message_type"] == "voice"
        assert metadata["audio_duration_seconds"] == 301
        
        # Transcription should NOT be called
        mock_transcription_service.transcribe.assert_not_called()
    
    async def test_duration_exactly_at_limit_passes(
        self, processor, mock_transcription_service
    ):
        """Test audio exactly at 300s limit passes."""
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=300,
            mime_type="audio/ogg",
        )
        
        assert content == "Hello, world!"
        mock_transcription_service.transcribe.assert_called_once()


class TestHandleAudioMessageFormatValidation:
    """Tests for format validation."""
    
    async def test_unsupported_format_returns_error(
        self, mock_transcription_service, temp_audio_file
    ):
        """Test unsupported format returns system message."""
        processor = ConcreteAudioProcessor(download_result=temp_audio_file)
        processor._transcription_service = mock_transcription_service
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="video/mp4",  # Not in supported formats
        )
        
        assert content == UNSUPPORTED_FORMAT
        assert metadata["message_type"] == "voice"
        
        # Transcription should NOT be called
        mock_transcription_service.transcribe.assert_not_called()
    
    async def test_ogg_format_passes(self, processor, mock_transcription_service):
        """Test audio/ogg format is accepted."""
        content, _ = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert content == "Hello, world!"
    
    async def test_mpeg_format_passes(self, processor, mock_transcription_service):
        """Test audio/mpeg format is accepted."""
        content, _ = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/mpeg",
        )
        
        assert content == "Hello, world!"


class TestHandleAudioMessageDownloadErrors:
    """Tests for download error handling."""
    
    async def test_download_error_returns_transcription_failed(
        self, mock_transcription_service
    ):
        """Test download error returns transcription failed message."""
        processor = ConcreteAudioProcessor(
            download_result=AudioDownloadError("Network error")
        )
        processor._transcription_service = mock_transcription_service
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert content == TRANSCRIPTION_FAILED
        assert metadata["message_type"] == "voice"
        assert metadata["audio_duration_seconds"] == 30


class TestHandleAudioMessageTranscriptionErrors:
    """Tests for transcription error handling."""
    
    async def test_transcription_error_returns_system_message(
        self, temp_audio_file
    ):
        """Test transcription error returns system message."""
        processor = ConcreteAudioProcessor(download_result=temp_audio_file)
        processor._transcription_service = MagicMock()
        processor._transcription_service.transcribe = AsyncMock(
            side_effect=TranscriptionError("API error")
        )
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert content == TRANSCRIPTION_FAILED
        assert metadata["message_type"] == "voice"
    
    async def test_unexpected_error_returns_transcription_failed(
        self, temp_audio_file
    ):
        """Test unexpected error returns transcription failed message."""
        processor = ConcreteAudioProcessor(download_result=temp_audio_file)
        processor._transcription_service = MagicMock()
        processor._transcription_service.transcribe = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert content == TRANSCRIPTION_FAILED


class TestHandleAudioMessageCleanup:
    """Tests for temporary file cleanup."""
    
    async def test_temp_file_deleted_on_success(self, mock_transcription_service):
        """Test temp file is deleted after successful transcription."""
        # Create a real temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(b"test audio")
            temp_path = f.name
        
        processor = ConcreteAudioProcessor(download_result=temp_path)
        processor._transcription_service = mock_transcription_service
        
        await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        # File should be deleted
        assert not os.path.exists(temp_path)
    
    async def test_temp_file_deleted_on_transcription_error(self):
        """Test temp file is deleted even when transcription fails."""
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(b"test audio")
            temp_path = f.name
        
        processor = ConcreteAudioProcessor(download_result=temp_path)
        processor._transcription_service = MagicMock()
        processor._transcription_service.transcribe = AsyncMock(
            side_effect=TranscriptionError("API error")
        )
        
        await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        # File should be deleted
        assert not os.path.exists(temp_path)
    
    async def test_temp_file_deleted_on_download_error(self):
        """Test no cleanup needed when download fails."""
        processor = ConcreteAudioProcessor(
            download_result=AudioDownloadError("Failed")
        )
        processor._transcription_service = MagicMock()
        
        # Should not raise (cleanup handles non-existent files)
        content, _ = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert content == TRANSCRIPTION_FAILED


class TestHandleAudioMessageMetadata:
    """Tests for metadata handling."""
    
    async def test_metadata_includes_duration_from_transcription(
        self, processor, mock_transcription_service
    ):
        """Test metadata uses duration from transcription result."""
        mock_transcription_service.transcribe.return_value = TranscriptionResult(
            text="Test",
            duration_seconds=25,  # Different from input duration
            message_type="voice",
            language="ru",
        )
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,  # Input duration
            mime_type="audio/ogg",
        )
        
        # Should use transcription result duration
        assert metadata["audio_duration_seconds"] == 25
    
    async def test_metadata_includes_language_when_available(
        self, processor, mock_transcription_service
    ):
        """Test metadata includes detected language."""
        mock_transcription_service.transcribe.return_value = TranscriptionResult(
            text="Привет",
            duration_seconds=5,
            message_type="voice",
            language="ru",
        )
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert metadata["audio_language"] == "ru"
    
    async def test_metadata_excludes_language_when_none(
        self, processor, mock_transcription_service
    ):
        """Test metadata doesn't include language when None."""
        mock_transcription_service.transcribe.return_value = TranscriptionResult(
            text="Test",
            duration_seconds=5,
            message_type="voice",
            language=None,
        )
        
        content, metadata = await processor.handle_audio_message(
            file_id="test_file",
            duration=30,
            mime_type="audio/ogg",
        )
        
        assert "audio_language" not in metadata


class TestAbstractDownloadMethod:
    """Tests for abstract download_audio_file method."""
    
    def test_download_audio_file_is_abstract(self):
        """Test download_audio_file must be implemented by subclasses."""
        # AudioAwareProcessor cannot be instantiated directly
        with pytest.raises(TypeError):
            AudioAwareProcessor()
    
    async def test_download_called_with_file_id(
        self, temp_audio_file, mock_transcription_service
    ):
        """Test download_audio_file is called with correct file_id."""
        processor = ConcreteAudioProcessor(download_result=temp_audio_file)
        processor._transcription_service = mock_transcription_service
        processor.download_audio_file = AsyncMock(return_value=temp_audio_file)
        
        await processor.handle_audio_message(
            file_id="unique_file_id_123",
            duration=30,
            mime_type="audio/ogg",
        )
        
        processor.download_audio_file.assert_called_once_with("unique_file_id_123")
