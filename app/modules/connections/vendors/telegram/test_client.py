"""Tests for Telegram Bot API client."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from app.modules.connections.vendors.telegram.client import TelegramClient
from app.modules.connections.schemas import BotInfo
from app.modules.connections.exceptions import (
    InvalidBotTokenError,
    TelegramAPIError,
    WebhookSetupError
)


class TestTelegramClient:
    """Test TelegramClient methods."""
    
    @pytest.fixture
    def client(self):
        """Create TelegramClient instance."""
        return TelegramClient(timeout=5.0)
    
    @pytest.fixture
    def mock_bot_response(self):
        """Mock successful getMe response."""
        return {
            "ok": True,
            "result": {
                "id": 123456789,
                "is_bot": True,
                "first_name": "Test Bot",
                "username": "test_bot",
                "can_join_groups": True,
                "can_read_all_group_messages": False,
                "supports_inline_queries": False
            }
        }
    
    # ===== Test validate_token =====
    
    @pytest.mark.asyncio
    async def test_validate_token_success(self, client, mock_bot_response):
        """Test successful token validation."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value=mock_bot_response)
            mock_get.return_value = mock_response
            
            bot_info = await client.validate_token("valid_token")
            
            assert isinstance(bot_info, BotInfo)
            assert bot_info.id == 123456789
            assert bot_info.is_bot is True
            assert bot_info.first_name == "Test Bot"
            assert bot_info.username == "test_bot"
            assert bot_info.can_join_groups is True
    
    @pytest.mark.asyncio
    async def test_validate_token_invalid_401(self, client):
        """Test token validation with 401 Unauthorized."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response
            
            with pytest.raises(InvalidBotTokenError, match="Invalid or expired bot token"):
                await client.validate_token("invalid_token")
    
    @pytest.mark.asyncio
    async def test_validate_token_bot_not_found_404(self, client):
        """Test token validation with 404 Not Found."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            with pytest.raises(InvalidBotTokenError, match="Bot not found"):
                await client.validate_token("nonexistent_token")
    
    @pytest.mark.asyncio
    async def test_validate_token_api_error(self, client):
        """Test token validation with API error response."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: invalid token"
            })
            mock_get.return_value = mock_response
            
            with pytest.raises(TelegramAPIError, match="Bad Request: invalid token"):
                await client.validate_token("bad_token")
    
    @pytest.mark.asyncio
    async def test_validate_token_timeout(self, client):
        """Test token validation with timeout."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timed out")
            
            with pytest.raises(TelegramAPIError, match="Request timeout"):
                await client.validate_token("test_token")
    
    @pytest.mark.asyncio
    async def test_validate_token_network_error(self, client):
        """Test token validation with network error."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.NetworkError("Connection failed")
            
            with pytest.raises(TelegramAPIError, match="Network error"):
                await client.validate_token("test_token")
    
    # ===== Test setup_webhook =====
    
    @pytest.mark.asyncio
    async def test_setup_webhook_success(self, client):
        """Test successful webhook setup."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "ok": True,
                "result": True,
                "description": "Webhook was set"
            })
            mock_post.return_value = mock_response
            
            result = await client.setup_webhook(
                "valid_token",
                "https://example.com/webhook"
            )
            
            assert result is True
            
            # Check that correct parameters were sent
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["url"] == "https://example.com/webhook"
            assert call_args[1]["json"]["max_connections"] == 40
    
    @pytest.mark.asyncio
    async def test_setup_webhook_with_secret(self, client):
        """Test webhook setup with secret token."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={"ok": True, "result": True})
            mock_post.return_value = mock_response
            
            result = await client.setup_webhook(
                "valid_token",
                "https://example.com/webhook",
                secret_token="my_secret",
                allowed_updates=["message", "callback_query"]
            )
            
            assert result is True
            
            # Check parameters
            call_args = mock_post.call_args
            json_data = call_args[1]["json"]
            assert json_data["secret_token"] == "my_secret"
            assert json_data["allowed_updates"] == ["message", "callback_query"]
    
    @pytest.mark.asyncio
    async def test_setup_webhook_invalid_token(self, client):
        """Test webhook setup with invalid token."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response
            
            with pytest.raises(InvalidBotTokenError):
                await client.setup_webhook("invalid_token", "https://example.com")
    
    @pytest.mark.asyncio
    async def test_setup_webhook_api_error(self, client):
        """Test webhook setup with API error."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "ok": False,
                "description": "Bad webhook URL"
            })
            mock_post.return_value = mock_response
            
            with pytest.raises(WebhookSetupError, match="Bad webhook URL"):
                await client.setup_webhook("token", "bad_url")
    
    @pytest.mark.asyncio
    async def test_setup_webhook_timeout(self, client):
        """Test webhook setup with timeout."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")
            
            with pytest.raises(WebhookSetupError, match="Request timeout"):
                await client.setup_webhook("token", "https://example.com")
    
    # ===== Test delete_webhook =====
    
    @pytest.mark.asyncio
    async def test_delete_webhook_success(self, client):
        """Test successful webhook deletion."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "ok": True,
                "result": True,
                "description": "Webhook was deleted"
            })
            mock_post.return_value = mock_response
            
            result = await client.delete_webhook("valid_token")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_webhook_invalid_token(self, client):
        """Test webhook deletion with invalid token."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response
            
            with pytest.raises(InvalidBotTokenError):
                await client.delete_webhook("invalid_token")
    
    @pytest.mark.asyncio
    async def test_delete_webhook_api_error(self, client):
        """Test webhook deletion with API error."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "ok": False,
                "description": "Some error occurred"
            })
            mock_post.return_value = mock_response
            
            with pytest.raises(TelegramAPIError, match="Some error occurred"):
                await client.delete_webhook("token")
    
    # ===== Test get_webhook_info =====
    
    @pytest.mark.asyncio
    async def test_get_webhook_info_success(self, client):
        """Test getting webhook info."""
        webhook_info = {
            "url": "https://example.com/webhook",
            "has_custom_certificate": False,
            "pending_update_count": 0,
            "max_connections": 40
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "ok": True,
                "result": webhook_info
            })
            mock_get.return_value = mock_response
            
            result = await client.get_webhook_info("valid_token")
            
            assert result == webhook_info
            assert result["url"] == "https://example.com/webhook"
            assert result["max_connections"] == 40
    
    @pytest.mark.asyncio
    async def test_get_webhook_info_invalid_token(self, client):
        """Test getting webhook info with invalid token."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_get.return_value = mock_response
            
            with pytest.raises(InvalidBotTokenError):
                await client.get_webhook_info("invalid_token")
