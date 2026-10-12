"""Unit tests for ConnectionManager with per-connection RabbitMQ queues."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestConnectionManager:
    """Test ConnectionManager methods."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.fixture
    def mock_queue(self):
        """Create mock RabbitMQ queue."""
        queue = MagicMock()
        queue.bind = AsyncMock()
        queue.unbind = AsyncMock()
        queue.iterator = MagicMock()
        return queue
    
    @pytest.fixture
    def mock_rabbitmq(self, mock_queue):
        """Create mock RabbitMQ connection."""
        rabbitmq = MagicMock()
        rabbitmq.is_connected = True
        rabbitmq.connect = AsyncMock()
        rabbitmq.close = AsyncMock()
        rabbitmq.declare_exchange = AsyncMock()
        rabbitmq.declare_queue = AsyncMock(return_value=mock_queue)
        rabbitmq.get_channel = AsyncMock()
        return rabbitmq
    
    @pytest.fixture
    def manager(self, mock_rabbitmq):
        """Create ConnectionManager with mocked RabbitMQ."""
        from app.modules.websocket_worker.manager import ConnectionManager
        
        mgr = ConnectionManager()
        mgr._rabbitmq = mock_rabbitmq
        mgr._exchange = MagicMock()
        mgr._channel = MagicMock()
        
        return mgr
    
    # === Subscription Validation Tests ===
    
    def test_validate_subscription_own_user(self, manager):
        """Test user can subscribe to own patterns."""
        # User ID is email, pattern contains email
        assert manager._validate_subscription(
            "user@example.com", 
            "webchat.user@example.com.*"
        ) is True
        
        # Notifications pattern
        assert manager._validate_subscription(
            "user@example.com", 
            "notifications.user@example.com.*"
        ) is True
    
    def test_validate_subscription_other_user(self, manager):
        """Test user cannot subscribe to other user's patterns."""
        assert manager._validate_subscription(
            "user@example.com", 
            "webchat.other@example.com.*"
        ) is False
    
    def test_validate_subscription_invalid_pattern(self, manager):
        """Test invalid patterns are rejected."""
        assert manager._validate_subscription(
            "user@example.com", 
            "invalid"
        ) is False
        
        assert manager._validate_subscription(
            "user@example.com", 
            ""
        ) is False
    
    # === Connect/Disconnect Tests ===
    
    @pytest.mark.asyncio
    async def test_connect_creates_queue(self, manager, mock_websocket, mock_rabbitmq):
        """Test connect creates unique queue for user."""
        connection_id = await manager.connect(mock_websocket, "user@example.com")
        
        assert connection_id is not None
        assert "user@example.com" in connection_id
        assert manager.is_connected(connection_id)
        mock_rabbitmq.declare_queue.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, manager, mock_websocket, mock_rabbitmq):
        """Test disconnect cleans up resources."""
        connection_id = await manager.connect(mock_websocket, "user@example.com")
        
        await manager.disconnect(connection_id)
        
        assert not manager.is_connected(connection_id)
        assert manager.get_connection_count() == 0
    
    # === Subscribe/Unsubscribe Tests ===
    
    @pytest.mark.asyncio
    async def test_subscribe_valid_pattern(self, manager, mock_websocket, mock_queue):
        """Test subscribing to valid pattern binds queue."""
        connection_id = await manager.connect(mock_websocket, "user@example.com")
        
        success = await manager.subscribe(connection_id, "webchat.user@example.com.*")
        
        assert success is True
        mock_queue.bind.assert_called_once()
        
        conn = manager.get_connection(connection_id)
        assert "webchat.user@example.com.*" in conn.subscriptions
    
    @pytest.mark.asyncio
    async def test_subscribe_invalid_pattern(self, manager, mock_websocket, mock_queue):
        """Test subscribing to other user's pattern fails."""
        connection_id = await manager.connect(mock_websocket, "user@example.com")
        
        success = await manager.subscribe(connection_id, "webchat.other@example.com.*")
        
        assert success is False
        mock_queue.bind.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, manager, mock_websocket, mock_queue):
        """Test unsubscribing removes binding."""
        connection_id = await manager.connect(mock_websocket, "user@example.com")
        await manager.subscribe(connection_id, "webchat.user@example.com.*")
        
        success = await manager.unsubscribe(connection_id, "webchat.user@example.com.*")
        
        assert success is True
        mock_queue.unbind.assert_called_once()
        
        conn = manager.get_connection(connection_id)
        assert "webchat.user@example.com.*" not in conn.subscriptions
    
    # === Utility Method Tests ===
    
    @pytest.mark.asyncio
    async def test_get_connection(self, manager, mock_websocket):
        """Test getting connection by ID."""
        connection_id = await manager.connect(mock_websocket, "user@example.com")
        
        conn = manager.get_connection(connection_id)
        
        assert conn is not None
        assert conn.user_id == "user@example.com"
    
    @pytest.mark.asyncio
    async def test_get_connection_count(self, manager, mock_websocket):
        """Test connection count."""
        assert manager.get_connection_count() == 0
        
        conn1 = await manager.connect(mock_websocket, "user1@example.com")
        assert manager.get_connection_count() == 1
        
        conn2 = await manager.connect(mock_websocket, "user2@example.com")
        assert manager.get_connection_count() == 2
    
    @pytest.mark.asyncio
    async def test_close_all(self, manager, mock_websocket, mock_rabbitmq):
        """Test closing all connections."""
        await manager.connect(mock_websocket, "user1@example.com")
        await manager.connect(mock_websocket, "user2@example.com")
        
        await manager.close()
        
        assert manager.get_connection_count() == 0
        mock_rabbitmq.close.assert_called_once()
