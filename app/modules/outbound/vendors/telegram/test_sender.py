"""Unit tests for TelegramSender."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.modules.outbound.vendors.telegram.sender import TelegramSender
from app.modules.outbound.schemas import SendResult
from app.modules.outbound.exceptions import TemporaryError, UserBlockedError
from app.modules.connections.models import Connection, ConnectionChannel, ConnectionStatus, ConnectionSettings


class TestTelegramSender:
    """Test suite for TelegramSender."""
    
    @pytest.fixture
    def mock_connection_repo(self):
        """Create mock connection repository."""
        repo = MagicMock()
        repo.update_status = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock connection."""
        connection = MagicMock(spec=Connection)
        connection.id = ObjectId()
        connection.channel = ConnectionChannel.TELEGRAM
        connection.status = ConnectionStatus.CONNECTED
        connection.settings = MagicMock()
        connection.settings.bot_token = "encrypted_token"
        connection.settings.bot_username = "@test_bot"
        connection.get_decrypted_token = MagicMock(return_value="test_token_123")
        connection.set_connected = AsyncMock()
        connection.set_degraded = AsyncMock()
        connection.set_error_status = AsyncMock()
        return connection
    
    @pytest.fixture
    def sender(self, mock_connection, mock_connection_repo):
        """Create TelegramSender instance for testing."""
        return TelegramSender(
            connection=mock_connection,
            connection_repo=mock_connection_repo
        )
    
    def test_extract_chat_id_valid(self, sender):
        """Test extracting chat_id from valid user_id."""
        chat_id = sender._extract_chat_id("telegram_284639219")
        assert chat_id == 284639219
        assert isinstance(chat_id, int)
    
    def test_extract_chat_id_invalid_format(self, sender):
        """Test extracting chat_id from invalid user_id format."""
        with pytest.raises(ValueError) as exc_info:
            sender._extract_chat_id("whatsapp_123456")
        
        assert "Invalid user_id format" in str(exc_info.value)
    
    def test_extract_chat_id_invalid_number(self, sender):
        """Test extracting chat_id with non-numeric value."""
        with pytest.raises(ValueError) as exc_info:
            sender._extract_chat_id("telegram_abc123")
        
        assert "Invalid chat_id" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, sender):
        """Test successful message sending."""
        sender.client.send_message = AsyncMock(return_value={
            "ok": True,
            "result": {"message_id": 456}
        })
        
        result = await sender.send_message(
            user_id="telegram_123456",
            text="Hello, world!"
        )
        
        assert result.success is True
        assert result.message_id == "456"
        assert result.retry_count == 0
        
        sender.client.send_message.assert_called_once_with(
            chat_id=123456,
            text="Hello, world!",
            parse_mode="HTML",
            reply_markup=None
        )
    
    @pytest.mark.asyncio
    async def test_send_message_with_markdown(self, sender):
        """Test sending message with Markdown parse mode."""
        sender.client.send_message = AsyncMock(return_value={
            "ok": True,
            "result": {"message_id": 789}
        })
        
        result = await sender.send_message(
            user_id="telegram_999888",
            text="*Bold* text",
            parse_mode="Markdown"
        )
        
        assert result.success is True
        call_args = sender.client.send_message.call_args
        assert call_args[1]["parse_mode"] == "Markdown"
    
    @pytest.mark.asyncio
    async def test_send_message_user_blocked(self, sender):
        """Test handling of user blocked error."""
        sender.client.send_message = AsyncMock(
            side_effect=UserBlockedError("User blocked the bot")
        )
        
        result = await sender.send_message(
            user_id="telegram_123456",
            text="Test"
        )
        
        assert result.success is False
        assert "blocked" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_send_message_temporary_error_retry(self, sender):
        """Test retry on temporary error."""
        # First two calls fail with TemporaryError, third succeeds
        sender.client.send_message = AsyncMock(
            side_effect=[
                TemporaryError("Server error"),
                TemporaryError("Server error"),
                {"ok": True, "result": {"message_id": 123}}
            ]
        )
        
        result = await sender.send_message(
            user_id="telegram_123456",
            text="Test"
        )
        
        assert result.success is True
        assert result.message_id == "123"
        # Should have been called 3 times (2 failures + 1 success)
        assert sender.client.send_message.call_count == 3
    
    @pytest.mark.asyncio
    async def test_send_callback_response_success(self, sender):
        """Test successful callback query response (private method)."""
        sender.client.answer_callback_query = AsyncMock(return_value={"ok": True})
        
        result = await sender._send_callback_response(
            user_id="telegram_123456",
            callback_id="callback_xyz",
            text="Button clicked!"
        )
        
        assert result.success is True
        sender.client.answer_callback_query.assert_called_once_with(
            callback_query_id="callback_xyz",
            text="Button clicked!",
            show_alert=False
        )
    
    @pytest.mark.asyncio
    async def test_send_callback_response_long_text(self, sender):
        """Test callback response with text longer than 200 chars (private method)."""
        long_text = "A" * 250  # Longer than Telegram's 200 char limit
        
        sender.client.answer_callback_query = AsyncMock(return_value={"ok": True})
        sender.client.send_message = AsyncMock(return_value={
            "ok": True,
            "result": {"message_id": 999}
        })
        
        result = await sender._send_callback_response(
            user_id="telegram_123456",
            callback_id="callback_abc",
            text=long_text
        )
        
        assert result.success is True
        # Should answer callback without text
        sender.client.answer_callback_query.assert_called_once()
        # Should send full text as message
        sender.client.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_callback_response_with_alert(self, sender):
        """Test callback response with alert (private method)."""
        sender.client.answer_callback_query = AsyncMock(return_value={"ok": True})
        
        result = await sender._send_callback_response(
            user_id="telegram_123456",
            callback_id="callback_def",
            text="Alert!",
            show_alert=True
        )
        
        assert result.success is True
        call_args = sender.client.answer_callback_query.call_args
        assert call_args[1]["show_alert"] is True
    
    @pytest.mark.asyncio
    async def test_send_callback_response_no_text(self, sender):
        """Test callback response without text (private method)."""
        sender.client.answer_callback_query = AsyncMock(return_value={"ok": True})
        
        result = await sender._send_callback_response(
            user_id="telegram_123456",
            callback_id="callback_ghi"
        )
        
        assert result.success is True
        call_args = sender.client.answer_callback_query.call_args
        assert call_args[1]["text"] is None
    
    # ========================================
    # Tests for send_typing_indicator
    # ========================================
    
    @pytest.mark.asyncio
    async def test_send_typing_indicator_success(self, sender):
        """Test successful typing indicator sending."""
        sender.client.send_chat_action = AsyncMock(return_value={
            "ok": True,
            "result": True
        })
        
        result = await sender.send_typing_indicator(
            user_id="telegram_123456"
        )
        
        assert result.success is True
        assert result.error is None
        
        sender.client.send_chat_action.assert_called_once_with(
            chat_id=123456,
            action="typing"
        )
    
    @pytest.mark.asyncio
    async def test_send_typing_indicator_user_blocked(self, sender):
        """Test typing indicator when user has blocked the bot."""
        sender.client.send_chat_action = AsyncMock(
            side_effect=UserBlockedError("User blocked the bot")
        )
        
        result = await sender.send_typing_indicator(
            user_id="telegram_123456"
        )
        
        # Should return failure but not raise exception
        assert result.success is False
        assert "blocked" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_send_typing_indicator_error_returns_result(self, sender):
        """Test that typing indicator errors return SendResult, not raise."""
        sender.client.send_chat_action = AsyncMock(
            side_effect=Exception("Network error")
        )
        
        # Should NOT raise exception, just return failed SendResult
        result = await sender.send_typing_indicator(
            user_id="telegram_123456"
        )
        
        assert result.success is False
        assert "Network error" in result.error
    
    @pytest.mark.asyncio
    async def test_send_typing_indicator_invalid_user_id(self, sender):
        """Test typing indicator with invalid user_id format."""
        result = await sender.send_typing_indicator(
            user_id="whatsapp_123456"  # Invalid format for Telegram
        )
        
        assert result.success is False
        assert "Invalid user_id format" in result.error
