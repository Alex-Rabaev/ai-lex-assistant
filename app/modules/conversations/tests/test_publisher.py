"""Unit tests for ConversationsPublisher."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.conversations.publisher import ConversationsPublisher


class TestConversationsPublisher:
    """Test suite for ConversationsPublisher."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock RabbitMQ connection."""
        connection = MagicMock()
        connection.is_connected = True
        connection.connect = AsyncMock()
        connection.declare_exchange = AsyncMock()
        connection.declare_queue = AsyncMock()
        return connection
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange."""
        exchange = MagicMock()
        exchange.publish = AsyncMock()
        return exchange
    
    @pytest.fixture
    def publisher(self, mock_connection, mock_exchange):
        """Create ConversationsPublisher instance."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        publisher = ConversationsPublisher(connection=mock_connection)
        return publisher
    
    @pytest.mark.asyncio
    async def test_publish_typing_indicator_success(
        self, publisher, mock_connection, mock_exchange
    ):
        """Test successful typing indicator publishing."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        await publisher.publish_typing_indicator(
            assistant_id="assistant_123",
            connection_id="connection_456",
            user_id="telegram_284639219"
        )
        
        # Verify exchange.publish was called
        mock_exchange.publish.assert_called_once()
        
        # Verify message content
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]  # First positional arg is the Message
        body = json.loads(message.body.decode())
        
        assert body["assistant_id"] == "assistant_123"
        assert body["connection_id"] == "connection_456"
        assert body["user_id"] == "telegram_284639219"
        assert body["type"] == "typing_indicator"
        
        # Verify routing key
        routing_key = call_args[1]["routing_key"]
        assert routing_key == "outbound.telegram"
    
    @pytest.mark.asyncio
    async def test_publish_typing_indicator_with_trace_id(
        self, publisher, mock_connection, mock_exchange
    ):
        """Test typing indicator includes trace_id when provided."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        await publisher.publish_typing_indicator(
            assistant_id="assistant_123",
            connection_id="connection_456",
            user_id="telegram_284639219",
            trace_id="trace_abc123"
        )
        
        # Verify message includes trace_id
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        body = json.loads(message.body.decode())
        
        assert body["trace_id"] == "trace_abc123"
    
    @pytest.mark.asyncio
    async def test_publish_typing_indicator_without_trace_id(
        self, publisher, mock_connection, mock_exchange
    ):
        """Test typing indicator works without trace_id."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        await publisher.publish_typing_indicator(
            assistant_id="assistant_123",
            connection_id="connection_456",
            user_id="telegram_284639219"
        )
        
        # Verify message doesn't include trace_id
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        body = json.loads(message.body.decode())
        
        assert "trace_id" not in body
    
    @pytest.mark.asyncio
    async def test_publish_typing_indicator_routing_key_whatsapp(
        self, publisher, mock_connection, mock_exchange
    ):
        """Test routing key is correct for WhatsApp users."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        await publisher.publish_typing_indicator(
            assistant_id="assistant_123",
            connection_id="connection_456",
            user_id="whatsapp_123456789"
        )
        
        # Verify routing key for WhatsApp
        call_args = mock_exchange.publish.call_args
        routing_key = call_args[1]["routing_key"]
        assert routing_key == "outbound.whatsapp"
    
    @pytest.mark.asyncio
    async def test_publish_typing_indicator_no_response_text(
        self, publisher, mock_connection, mock_exchange
    ):
        """Test typing indicator message has no response_text field."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        await publisher.publish_typing_indicator(
            assistant_id="assistant_123",
            connection_id="connection_456",
            user_id="telegram_284639219"
        )
        
        # Verify message doesn't include response_text
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        body = json.loads(message.body.decode())
        
        assert "response_text" not in body


class TestConversationsPublisherOutgoingMessage:
    """Test suite for publish_outgoing_message method."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock RabbitMQ connection."""
        connection = MagicMock()
        connection.is_connected = True
        connection.connect = AsyncMock()
        return connection
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange."""
        exchange = MagicMock()
        exchange.publish = AsyncMock()
        return exchange
    
    @pytest.mark.asyncio
    async def test_publish_outgoing_message_success(
        self, mock_connection, mock_exchange
    ):
        """Test successful outgoing message publishing."""
        mock_connection.declare_exchange = AsyncMock(return_value=mock_exchange)
        
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_connection.declare_queue = AsyncMock(return_value=mock_queue)
        
        publisher = ConversationsPublisher(connection=mock_connection)
        
        await publisher.publish_outgoing_message(
            assistant_id="assistant_123",
            connection_id="connection_456",
            user_id="telegram_284639219",
            response_text="Hello, world!"
        )
        
        # Verify exchange.publish was called
        mock_exchange.publish.assert_called_once()
        
        # Verify message content
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        body = json.loads(message.body.decode())
        
        assert body["type"] == "message"
        assert body["response_text"] == "Hello, world!"

