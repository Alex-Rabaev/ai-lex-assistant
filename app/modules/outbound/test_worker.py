"""Unit tests for OutboundWorker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.modules.outbound.worker import OutboundWorker
from app.modules.outbound.schemas import OutgoingMessage
from app.modules.connections.models import Connection, ConnectionChannel, ConnectionStatus


class TestOutboundWorkerProcessMessage:
    """Test suite for OutboundWorker.process_message method."""
    
    @pytest.fixture
    def worker(self):
        """Create OutboundWorker instance for testing."""
        worker = OutboundWorker()
        worker.connection_repo = MagicMock()
        return worker
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock connection."""
        connection = MagicMock(spec=Connection)
        connection.id = ObjectId()
        connection.channel = ConnectionChannel.TELEGRAM
        connection.status = ConnectionStatus.CONNECTED
        connection.get_decrypted_token = MagicMock(return_value="test_token_123")
        connection.set_connected = AsyncMock()
        connection.set_degraded = AsyncMock()
        connection.set_error_status = AsyncMock()
        return connection
    
    @pytest.mark.asyncio
    async def test_process_typing_indicator_success(self, worker, mock_connection):
        """Test successful processing of typing indicator message."""
        worker.connection_repo.get_by_id = AsyncMock(return_value=mock_connection)
        
        msg = OutgoingMessage(
            assistant_id="assistant_123",
            connection_id=str(mock_connection.id),
            user_id="telegram_284639219",
            type="typing_indicator"
        )
        
        with patch(
            "app.modules.outbound.worker.TelegramSender"
        ) as mock_sender_class:
            mock_sender = MagicMock()
            mock_sender.send_typing_indicator = AsyncMock(
                return_value=MagicMock(success=True, error=None)
            )
            mock_sender_class.return_value = mock_sender
            
            await worker.process_message(msg)
            
            # Verify typing indicator was sent with unified interface
            mock_sender.send_typing_indicator.assert_called_once_with(
                user_id="telegram_284639219",
                assistant_id="assistant_123"
            )
            # Verify send_message was NOT called
            mock_sender.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_typing_indicator_failure_logs_warning(
        self, worker, mock_connection
    ):
        """Test that typing indicator failure is logged but doesn't fail."""
        worker.connection_repo.get_by_id = AsyncMock(return_value=mock_connection)
        
        msg = OutgoingMessage(
            assistant_id="assistant_123",
            connection_id=str(mock_connection.id),
            user_id="telegram_284639219",
            type="typing_indicator"
        )
        
        with patch(
            "app.modules.outbound.worker.TelegramSender"
        ) as mock_sender_class:
            mock_sender = MagicMock()
            mock_sender.send_typing_indicator = AsyncMock(
                return_value=MagicMock(success=False, error="User blocked")
            )
            mock_sender_class.return_value = mock_sender
            
            # Should not raise exception
            await worker.process_message(msg)
            
            mock_sender.send_typing_indicator.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_regular_message_success(self, worker, mock_connection):
        """Test successful processing of regular message."""
        worker.connection_repo.get_by_id = AsyncMock(return_value=mock_connection)
        
        msg = OutgoingMessage(
            assistant_id="assistant_123",
            connection_id=str(mock_connection.id),
            user_id="telegram_284639219",
            type="message",
            response_text="Hello, world!"
        )
        
        with patch(
            "app.modules.outbound.worker.TelegramSender"
        ) as mock_sender_class:
            mock_sender = MagicMock()
            mock_sender.send_message = AsyncMock(
                return_value=MagicMock(success=True, message_id="123", error=None)
            )
            mock_sender_class.return_value = mock_sender
            
            await worker.process_message(msg)
            
            # Verify message was sent with unified interface
            mock_sender.send_message.assert_called_once_with(
                user_id="telegram_284639219",
                text="Hello, world!",
                assistant_id="assistant_123",
                conversation_id=None,
                parse_mode="HTML"
            )
            # Verify connection status was updated
            mock_connection.set_connected.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_connection_not_found(self, worker):
        """Test handling when connection is not found."""
        worker.connection_repo.get_by_id = AsyncMock(return_value=None)
        
        msg = OutgoingMessage(
            assistant_id="assistant_123",
            connection_id="nonexistent_connection",
            user_id="telegram_284639219",
            type="message",
            response_text="Test"
        )
        
        # Should not raise exception
        await worker.process_message(msg)
        
        # Connection lookup should have been attempted
        worker.connection_repo.get_by_id.assert_called_once_with("nonexistent_connection")
    
    @pytest.mark.asyncio
    async def test_process_typing_indicator_before_regular_message_flow(
        self, worker, mock_connection
    ):
        """Test that typing indicator is handled separately from regular messages."""
        worker.connection_repo.get_by_id = AsyncMock(return_value=mock_connection)
        
        # First message: typing indicator
        typing_msg = OutgoingMessage(
            assistant_id="assistant_123",
            connection_id=str(mock_connection.id),
            user_id="telegram_284639219",
            type="typing_indicator"
        )
        
        # Second message: regular message
        regular_msg = OutgoingMessage(
            assistant_id="assistant_123",
            connection_id=str(mock_connection.id),
            user_id="telegram_284639219",
            type="message",
            response_text="Hello!"
        )
        
        with patch(
            "app.modules.outbound.worker.TelegramSender"
        ) as mock_sender_class:
            mock_sender = MagicMock()
            mock_sender.send_typing_indicator = AsyncMock(
                return_value=MagicMock(success=True)
            )
            mock_sender.send_message = AsyncMock(
                return_value=MagicMock(success=True, message_id="456")
            )
            mock_sender_class.return_value = mock_sender
            
            # Process both messages
            await worker.process_message(typing_msg)
            await worker.process_message(regular_msg)
            
            # Verify both methods were called
            mock_sender.send_typing_indicator.assert_called_once()
            mock_sender.send_message.assert_called_once()

