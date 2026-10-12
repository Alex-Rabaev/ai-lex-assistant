"""Unit tests for WhatsApp Cloud API client."""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.modules.outbound.vendors.whatsapp.client import WhatsAppClient
from app.modules.outbound.exceptions import (
    InvalidTokenError,
    TemporaryError,
)
from app.common.audio.exceptions import AudioDownloadError


class TestWhatsAppClient:
    """Test suite for WhatsAppClient."""
    
    @pytest.fixture
    def client(self):
        """Create WhatsAppClient instance for testing."""
        return WhatsAppClient(
            phone_number_id="123456789",
            access_token="test_access_token"
        )
    
    @pytest.mark.asyncio
    async def test_send_text_message_success(self, client):
        """Test successful message sending."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "messaging_product": "whatsapp",
                "messages": [{"id": "wamid.test123"}]
            }
            mock_client.post.return_value = mock_response
            
            result = await client.send_text_message(
                to="15559876543",
                text="Test message"
            )
            
            assert result["messages"][0]["id"] == "wamid.test123"


class TestWhatsAppClientDownload:
    """Tests for download_file method."""
    
    @pytest.fixture
    def client(self):
        """Create WhatsAppClient instance for testing."""
        return WhatsAppClient(
            phone_number_id="123456789",
            access_token="test_access_token"
        )
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, client):
        """Test successful file download."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock getMediaURL response
            get_url_response = MagicMock()
            get_url_response.status_code = 200
            get_url_response.json.return_value = {
                "url": "https://lookaside.fbcdn.net/whatsapp/audio123",
                "mime_type": "audio/ogg; codecs=opus",
                "file_size": 12345
            }
            
            # Mock file download response
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.content = b"fake audio content for testing"
            
            mock_client.get.side_effect = [get_url_response, download_response]
            
            temp_path = await client.download_file("media_id_123")
            
            try:
                # Verify file was created
                assert os.path.exists(temp_path)
                assert temp_path.endswith(".ogg")
                
                # Verify content
                with open(temp_path, "rb") as f:
                    assert f.read() == b"fake audio content for testing"
            finally:
                # Cleanup
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_download_file_mp3_extension(self, client):
        """Test file download with MP3 mime type."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            get_url_response = MagicMock()
            get_url_response.status_code = 200
            get_url_response.json.return_value = {
                "url": "https://lookaside.fbcdn.net/whatsapp/audio456",
                "mime_type": "audio/mpeg"
            }
            
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.content = b"mp3 content"
            
            mock_client.get.side_effect = [get_url_response, download_response]
            
            temp_path = await client.download_file("media_id_456")
            
            try:
                assert temp_path.endswith(".mp3")
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_download_file_invalid_token(self, client):
        """Test handling of invalid token error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.get.return_value = mock_response
            
            with pytest.raises(InvalidTokenError):
                await client.download_file("test_media_id")
    
    @pytest.mark.asyncio
    async def test_download_file_get_url_fails(self, client):
        """Test handling of get media URL failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = '{"error": {"message": "Invalid media ID"}}'
            mock_response.json.return_value = {
                "error": {"message": "Invalid media ID"}
            }
            mock_client.get.return_value = mock_response
            
            with pytest.raises(AudioDownloadError) as exc_info:
                await client.download_file("invalid_media_id")
            
            assert "Invalid media ID" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_file_no_url_in_response(self, client):
        """Test handling of missing URL in response."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "mime_type": "audio/ogg"
                # No "url" field
            }
            mock_client.get.return_value = mock_response
            
            with pytest.raises(AudioDownloadError) as exc_info:
                await client.download_file("test_media_id")
            
            assert "No download URL" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_file_download_fails(self, client):
        """Test handling of file download failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Get URL succeeds
            get_url_response = MagicMock()
            get_url_response.status_code = 200
            get_url_response.json.return_value = {
                "url": "https://example.com/audio.ogg"
            }
            
            # Download fails
            download_response = MagicMock()
            download_response.status_code = 404
            
            mock_client.get.side_effect = [get_url_response, download_response]
            
            with pytest.raises(AudioDownloadError) as exc_info:
                await client.download_file("test_media_id")
            
            assert "download failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_download_file_server_error_retry(self, client):
        """Test retry on server error (5xx)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # First two attempts fail with 500
            error_response = MagicMock()
            error_response.status_code = 500
            
            # Third attempt succeeds
            get_url_response = MagicMock()
            get_url_response.status_code = 200
            get_url_response.json.return_value = {
                "url": "https://example.com/audio.ogg"
            }
            
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.content = b"audio content"
            
            mock_client.get.side_effect = [
                error_response,  # First getURL fails
                error_response,  # Second getURL fails
                get_url_response,  # Third getURL succeeds
                download_response,  # Download succeeds
            ]
            
            temp_path = await client.download_file("test_media_id")
            
            try:
                assert os.path.exists(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_download_file_timeout(self, client):
        """Test handling of timeout during download."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # All attempts timeout
            mock_client.get.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(AudioDownloadError):
                await client.download_file("test_media_id")
