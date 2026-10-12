"""Unit tests for TelegramClient."""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.modules.outbound.vendors.telegram.client import TelegramClient
from app.modules.outbound.exceptions import (
    UserBlockedError,
    InvalidTokenError,
    RateLimitError,
    TemporaryError,
    SendError,
)
from app.common.audio.exceptions import AudioDownloadError


class TestTelegramClient:
    """Test suite for TelegramClient."""
    
    @pytest.fixture
    def client(self):
        """Create TelegramClient instance for testing."""
        return TelegramClient("test_token_123")
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, client):
        """Test successful message sending."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": True,
                "result": {"message_id": 123}
            }
            mock_client.post.return_value = mock_response
            
            result = await client.send_message(
                chat_id=284639219,
                text="Test message"
            )
            
            assert result["ok"] is True
            assert result["result"]["message_id"] == 123
            mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_with_parse_mode(self, client):
        """Test sending message with HTML parse mode."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": True,
                "result": {"message_id": 456}
            }
            mock_client.post.return_value = mock_response
            
            result = await client.send_message(
                chat_id=123456,
                text="<b>Bold text</b>",
                parse_mode="HTML"
            )
            
            assert result["ok"] is True
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["parse_mode"] == "HTML"
    
    @pytest.mark.asyncio
    async def test_send_message_user_blocked(self, client):
        """Test handling of user blocked error (403)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = '{"description": "Forbidden: bot was blocked by the user"}'
            mock_response.json.return_value = {
                "description": "Forbidden: bot was blocked by the user"
            }
            mock_client.post.return_value = mock_response
            
            with pytest.raises(UserBlockedError) as exc_info:
                await client.send_message(284639219, "Test")
            
            assert "blocked the bot" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_invalid_token(self, client):
        """Test handling of invalid token error (401)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.post.return_value = mock_response
            
            with pytest.raises(InvalidTokenError):
                await client.send_message(123456, "Test")
    
    @pytest.mark.asyncio
    async def test_send_message_rate_limit(self, client):
        """Test handling of rate limit error (429)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = '{"parameters": {"retry_after": 30}}'
            mock_response.json.return_value = {
                "parameters": {"retry_after": 30}
            }
            mock_client.post.return_value = mock_response
            
            with pytest.raises(RateLimitError) as exc_info:
                await client.send_message(123456, "Test")
            
            assert exc_info.value.retry_after == 30
    
    @pytest.mark.asyncio
    async def test_send_message_server_error(self, client):
        """Test handling of server error (5xx)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.post.return_value = mock_response
            
            with pytest.raises(TemporaryError):
                await client.send_message(123456, "Test")
    
    @pytest.mark.asyncio
    async def test_send_message_timeout(self, client):
        """Test handling of request timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(TemporaryError) as exc_info:
                await client.send_message(123456, "Test")
            
            assert "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_answer_callback_query_success(self, client):
        """Test successful callback query answer."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_client.post.return_value = mock_response
            
            result = await client.answer_callback_query(
                callback_query_id="callback_123",
                text="Button clicked!"
            )
            
            assert result["ok"] is True
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["callback_query_id"] == "callback_123"
            assert call_args[1]["json"]["text"] == "Button clicked!"
    
    @pytest.mark.asyncio
    async def test_answer_callback_query_with_alert(self, client):
        """Test callback query answer with alert."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_client.post.return_value = mock_response
            
            await client.answer_callback_query(
                callback_query_id="callback_456",
                text="Alert message",
                show_alert=True
            )
            
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["show_alert"] is True
    
    # ========================================
    # Tests for send_chat_action (typing indicator)
    # ========================================
    
    @pytest.mark.asyncio
    async def test_send_chat_action_success(self, client):
        """Test successful chat action (typing indicator) sending."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "result": True}
            mock_client.post.return_value = mock_response
            
            result = await client.send_chat_action(
                chat_id=284639219,
                action="typing"
            )
            
            assert result["ok"] is True
            call_args = mock_client.post.call_args
            assert "sendChatAction" in call_args[0][0]
            assert call_args[1]["json"]["chat_id"] == 284639219
            assert call_args[1]["json"]["action"] == "typing"
    
    @pytest.mark.asyncio
    async def test_send_chat_action_user_blocked(self, client):
        """Test handling of user blocked error for chat action."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = '{"description": "Forbidden: bot was blocked by the user"}'
            mock_response.json.return_value = {
                "description": "Forbidden: bot was blocked by the user"
            }
            mock_client.post.return_value = mock_response
            
            with pytest.raises(UserBlockedError):
                await client.send_chat_action(284639219, "typing")
    
    @pytest.mark.asyncio
    async def test_send_chat_action_invalid_token(self, client):
        """Test handling of invalid token error for chat action."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.post.return_value = mock_response
            
            with pytest.raises(InvalidTokenError):
                await client.send_chat_action(123456, "typing")
    
    @pytest.mark.asyncio
    async def test_send_chat_action_server_error(self, client):
        """Test handling of server error for chat action."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.post.return_value = mock_response
            
            with pytest.raises(TemporaryError):
                await client.send_chat_action(123456, "typing")
    
    @pytest.mark.asyncio
    async def test_send_chat_action_timeout(self, client):
        """Test handling of timeout for chat action."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(TemporaryError):
                await client.send_chat_action(123456, "typing")


class TestDownloadFile:
    """Tests for download_file method."""
    
    @pytest.fixture
    def client(self):
        """Create TelegramClient instance for testing."""
        return TelegramClient("test_token_123")
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, client):
        """Test successful file download."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock getFile response
            get_file_response = MagicMock()
            get_file_response.status_code = 200
            get_file_response.json.return_value = {
                "ok": True,
                "result": {
                    "file_id": "test_file_id",
                    "file_unique_id": "unique_123",
                    "file_size": 12345,
                    "file_path": "voice/file_0.ogg"
                }
            }
            
            # Mock file download response
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.content = b"fake audio content for testing"
            
            mock_client.get.side_effect = [get_file_response, download_response]
            
            temp_path = await client.download_file("test_file_id")
            
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
        """Test file download with MP3 extension."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            get_file_response = MagicMock()
            get_file_response.status_code = 200
            get_file_response.json.return_value = {
                "ok": True,
                "result": {
                    "file_id": "test_file_id",
                    "file_path": "music/song.mp3"
                }
            }
            
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.content = b"mp3 content"
            
            mock_client.get.side_effect = [get_file_response, download_response]
            
            temp_path = await client.download_file("test_file_id")
            
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
                await client.download_file("test_file_id")
    
    @pytest.mark.asyncio
    async def test_download_file_getfile_fails(self, client):
        """Test handling of getFile API failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = '{"ok": false, "description": "Bad Request: invalid file_id"}'
            mock_response.json.return_value = {
                "ok": False,
                "description": "Bad Request: invalid file_id"
            }
            mock_client.get.return_value = mock_response
            
            with pytest.raises(AudioDownloadError) as exc_info:
                await client.download_file("invalid_file_id")
            
            assert "getFile failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_file_no_file_path(self, client):
        """Test handling of missing file_path in response."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": True,
                "result": {
                    "file_id": "test_file_id"
                    # No file_path
                }
            }
            mock_client.get.return_value = mock_response
            
            with pytest.raises(AudioDownloadError) as exc_info:
                await client.download_file("test_file_id")
            
            assert "No file_path" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_file_download_fails(self, client):
        """Test handling of file download failure."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # getFile succeeds
            get_file_response = MagicMock()
            get_file_response.status_code = 200
            get_file_response.json.return_value = {
                "ok": True,
                "result": {"file_path": "voice/file.ogg"}
            }
            
            # Download fails
            download_response = MagicMock()
            download_response.status_code = 404
            
            mock_client.get.side_effect = [get_file_response, download_response]
            
            with pytest.raises(AudioDownloadError) as exc_info:
                await client.download_file("test_file_id")
            
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
            get_file_response = MagicMock()
            get_file_response.status_code = 200
            get_file_response.json.return_value = {
                "ok": True,
                "result": {"file_path": "voice/file.ogg"}
            }
            
            download_response = MagicMock()
            download_response.status_code = 200
            download_response.content = b"audio content"
            
            mock_client.get.side_effect = [
                error_response,  # First getFile fails
                error_response,  # Second getFile fails  
                get_file_response,  # Third getFile succeeds
                download_response,  # Download succeeds
            ]
            
            temp_path = await client.download_file("test_file_id")
            
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
                await client.download_file("test_file_id")
