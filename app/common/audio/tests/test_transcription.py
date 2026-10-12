"""Unit tests for AudioTranscriptionService.

Tests transcription functionality with mocked OpenAI Whisper API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from app.common.audio.transcription import AudioTranscriptionService
from app.common.audio.schemas import TranscriptionResult
from app.common.audio.exceptions import TranscriptionError


class MockWhisperResponse:
    """Mock response from Whisper API."""
    
    def __init__(
        self,
        text: str = "Hello, world!",
        duration: float = 5.0,
        language: str = "en"
    ):
        self.text = text
        self.duration = duration
        self.language = language


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    client = MagicMock()
    client.audio = MagicMock()
    client.audio.transcriptions = MagicMock()
    client.audio.transcriptions.create = AsyncMock(
        return_value=MockWhisperResponse()
    )
    return client


@pytest.fixture
def service(mock_openai_client):
    """Create AudioTranscriptionService with mocked client."""
    return AudioTranscriptionService(client=mock_openai_client)


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing."""
    with tempfile.NamedTemporaryFile(
        suffix=".ogg",
        delete=False
    ) as f:
        # Write some dummy data
        f.write(b"fake audio data for testing")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestAudioTranscriptionServiceInit:
    """Tests for AudioTranscriptionService initialization."""
    
    def test_init_with_client(self, mock_openai_client):
        """Test initialization with provided client."""
        service = AudioTranscriptionService(client=mock_openai_client)
        assert service._client is mock_openai_client
    
    @patch('app.common.audio.transcription.AsyncOpenAI')
    def test_init_without_client_uses_config(self, mock_async_openai):
        """Test initialization creates client from config."""
        service = AudioTranscriptionService()
        mock_async_openai.assert_called_once()


class TestTranscribe:
    """Tests for transcribe method."""
    
    async def test_successful_transcription(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test successful transcription returns TranscriptionResult."""
        result = await service.transcribe(temp_audio_file)
        
        assert isinstance(result, TranscriptionResult)
        assert result.text == "Hello, world!"
        assert result.duration_seconds == 5
        assert result.language == "en"
        assert result.message_type == "voice"
    
    async def test_transcription_with_audio_message_type(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test transcription with audio message type."""
        result = await service.transcribe(
            temp_audio_file,
            message_type="audio"
        )
        
        assert result.message_type == "audio"
    
    async def test_transcription_with_language_hint(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test transcription passes language hint to API."""
        await service.transcribe(
            temp_audio_file,
            language_hint="ru"
        )
        
        # Verify language was passed to API
        call_kwargs = mock_openai_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["language"] == "ru"
    
    async def test_transcription_without_language_hint(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test transcription without language hint."""
        await service.transcribe(temp_audio_file)
        
        # Verify language was not passed to API
        call_kwargs = mock_openai_client.audio.transcriptions.create.call_args.kwargs
        assert "language" not in call_kwargs
    
    async def test_file_not_found_raises_error(self, service):
        """Test transcription raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            await service.transcribe("/nonexistent/path/audio.ogg")
    
    async def test_api_error_raises_transcription_error(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test API error raises TranscriptionError after retries."""
        mock_openai_client.audio.transcriptions.create.side_effect = Exception(
            "API error"
        )
        
        with pytest.raises(TranscriptionError) as exc_info:
            await service.transcribe(temp_audio_file)
        
        assert "Transcription failed" in str(exc_info.value)
    
    async def test_response_with_zero_duration(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test handling of response with zero duration."""
        mock_openai_client.audio.transcriptions.create.return_value = (
            MockWhisperResponse(duration=0)
        )
        
        result = await service.transcribe(temp_audio_file)
        
        assert result.duration_seconds == 0
    
    async def test_response_with_none_duration(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test handling of response with None duration."""
        response = MockWhisperResponse()
        response.duration = None
        mock_openai_client.audio.transcriptions.create.return_value = response
        
        result = await service.transcribe(temp_audio_file)
        
        assert result.duration_seconds == 0
    
    async def test_long_transcription(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test handling of long transcription text."""
        long_text = "Word " * 1000
        mock_openai_client.audio.transcriptions.create.return_value = (
            MockWhisperResponse(text=long_text, duration=300)
        )
        
        result = await service.transcribe(temp_audio_file)
        
        assert len(result.text) > 4000
        assert result.duration_seconds == 300


class TestRetryLogic:
    """Tests for retry logic."""
    
    async def test_retries_on_first_failure(
        self, mock_openai_client, temp_audio_file
    ):
        """Test service retries on first failure."""
        # Fail twice, succeed on third attempt
        mock_openai_client.audio.transcriptions.create.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            MockWhisperResponse(),
        ]
        
        service = AudioTranscriptionService(client=mock_openai_client)
        result = await service.transcribe(temp_audio_file)
        
        assert result.text == "Hello, world!"
        assert mock_openai_client.audio.transcriptions.create.call_count == 3
    
    async def test_fails_after_three_retries(
        self, mock_openai_client, temp_audio_file
    ):
        """Test service fails after 3 retries."""
        mock_openai_client.audio.transcriptions.create.side_effect = Exception(
            "Persistent failure"
        )
        
        service = AudioTranscriptionService(client=mock_openai_client)
        
        with pytest.raises(TranscriptionError):
            await service.transcribe(temp_audio_file)
        
        # Should have tried 3 times
        assert mock_openai_client.audio.transcriptions.create.call_count == 3
    
    async def test_retry_succeeds_on_second_attempt(
        self, mock_openai_client, temp_audio_file
    ):
        """Test service succeeds on second attempt."""
        mock_openai_client.audio.transcriptions.create.side_effect = [
            Exception("First failure"),
            MockWhisperResponse(text="Success after retry"),
        ]
        
        service = AudioTranscriptionService(client=mock_openai_client)
        result = await service.transcribe(temp_audio_file)
        
        assert result.text == "Success after retry"
        assert mock_openai_client.audio.transcriptions.create.call_count == 2


class TestAPICallParameters:
    """Tests for Whisper API call parameters."""
    
    async def test_uses_whisper_model(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test service uses whisper-1 model."""
        await service.transcribe(temp_audio_file)
        
        call_kwargs = mock_openai_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["model"] == "whisper-1"
    
    async def test_uses_verbose_json_format(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test service requests verbose_json response format."""
        await service.transcribe(temp_audio_file)
        
        call_kwargs = mock_openai_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["response_format"] == "verbose_json"
    
    async def test_passes_file_object(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test service passes file object to API."""
        await service.transcribe(temp_audio_file)
        
        call_kwargs = mock_openai_client.audio.transcriptions.create.call_args.kwargs
        assert "file" in call_kwargs


class TestTranscriptionResultData:
    """Tests for TranscriptionResult data integrity."""
    
    async def test_preserves_transcript_text(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test transcript text is preserved exactly."""
        expected_text = "Привет, мир! 你好世界 🎤"
        mock_openai_client.audio.transcriptions.create.return_value = (
            MockWhisperResponse(text=expected_text)
        )
        
        result = await service.transcribe(temp_audio_file)
        
        assert result.text == expected_text
    
    async def test_preserves_language(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test detected language is preserved."""
        mock_openai_client.audio.transcriptions.create.return_value = (
            MockWhisperResponse(language="ru")
        )
        
        result = await service.transcribe(temp_audio_file)
        
        assert result.language == "ru"
    
    async def test_converts_duration_to_int(
        self, service, mock_openai_client, temp_audio_file
    ):
        """Test duration is converted to integer."""
        mock_openai_client.audio.transcriptions.create.return_value = (
            MockWhisperResponse(duration=15.7)
        )
        
        result = await service.transcribe(temp_audio_file)
        
        assert result.duration_seconds == 15
        assert isinstance(result.duration_seconds, int)
