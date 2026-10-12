"""Unit tests for TemporalClientManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.workflows.temporal_client import TemporalClientManager


class TestTemporalClientManagerInit:
    """Tests for TemporalClientManager initialization."""
    
    def test_default_config(self):
        """Test that manager uses config values by default."""
        manager = TemporalClientManager()
        
        assert manager.host is not None
        assert manager.namespace is not None
        assert manager._client is None
    
    def test_custom_host_and_namespace(self):
        """Test that manager accepts custom host and namespace."""
        manager = TemporalClientManager(
            host="localhost:7233",
            namespace="test-ns"
        )
        
        assert manager.host == "localhost:7233"
        assert manager.namespace == "test-ns"
    
    def test_is_connected_false_initially(self):
        """Test that is_connected is False before connecting."""
        manager = TemporalClientManager()
        
        assert manager.is_connected is False


class TestTemporalClientManagerGetClient:
    """Tests for TemporalClientManager.get_client method."""
    
    @pytest.mark.asyncio
    async def test_get_client_connects_on_first_call(self):
        """Test that get_client connects to Temporal on first call."""
        mock_client = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ) as mock_connect:
            manager = TemporalClientManager(
                host="localhost:7233",
                namespace="default",
                api_key=None
            )
            
            client = await manager.get_client()
            
            assert client == mock_client
            mock_connect.assert_called_once_with(
                target_host="localhost:7233",
                namespace="default"
            )
    
    @pytest.mark.asyncio
    async def test_get_client_reuses_connection(self):
        """Test that get_client reuses existing connection."""
        mock_client = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ) as mock_connect:
            manager = TemporalClientManager(
                host="localhost:7233",
                namespace="default",
                api_key=None
            )
            
            client1 = await manager.get_client()
            client2 = await manager.get_client()
            
            assert client1 is client2
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_client_sets_is_connected(self):
        """Test that is_connected is True after connecting."""
        mock_client = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ):
            manager = TemporalClientManager(
                host="localhost:7233",
                namespace="default",
                api_key=None
            )
            
            await manager.get_client()
            
            assert manager.is_connected is True
    
    @pytest.mark.asyncio
    async def test_get_client_raises_runtime_error_on_failure(self):
        """Test that get_client raises RuntimeError on connection failure."""
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused")
        ):
            manager = TemporalClientManager(
                host="bad-host:7233",
                namespace="default",
                api_key=None
            )
            
            with pytest.raises(RuntimeError, match="Failed to connect to Temporal"):
                await manager.get_client()
    
    @pytest.mark.asyncio
    async def test_get_client_not_connected_after_failure(self):
        """Test that is_connected remains False after failed connection."""
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused")
        ):
            manager = TemporalClientManager(
                host="bad-host:7233",
                namespace="default",
                api_key=None
            )
            
            try:
                await manager.get_client()
            except RuntimeError:
                pass
            
            assert manager.is_connected is False


class TestTemporalClientManagerClose:
    """Tests for TemporalClientManager.close method."""
    
    @pytest.mark.asyncio
    async def test_close_resets_client(self):
        """Test that close resets the client reference."""
        mock_client = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ):
            manager = TemporalClientManager(
                host="localhost:7233",
                namespace="default",
                api_key=None
            )
            
            await manager.get_client()
            assert manager.is_connected is True
            
            await manager.close()
            assert manager.is_connected is False
            assert manager._client is None
    
    @pytest.mark.asyncio
    async def test_close_when_not_connected(self):
        """Test that close is safe when not connected."""
        manager = TemporalClientManager()
        
        # Should not raise
        await manager.close()
        assert manager.is_connected is False
    
    @pytest.mark.asyncio
    async def test_reconnect_after_close(self):
        """Test that client can reconnect after close."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            side_effect=[mock_client1, mock_client2]
        ) as mock_connect:
            manager = TemporalClientManager(
                host="localhost:7233",
                namespace="default",
                api_key=None
            )
            
            client1 = await manager.get_client()
            await manager.close()
            client2 = await manager.get_client()
            
            assert client1 is not client2
            assert mock_connect.call_count == 2


class TestTemporalClientManagerCloud:
    """Tests for Temporal Cloud connection (API Key + TLS)."""
    
    @pytest.mark.asyncio
    async def test_cloud_connection_uses_api_key_and_tls(self):
        """Test that API key triggers TLS connection."""
        mock_client = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ) as mock_connect:
            manager = TemporalClientManager(
                host="ns.account.tmprl.cloud:7233",
                namespace="my-ns",
                api_key="test-api-key"
            )
            
            await manager.get_client()
            
            mock_connect.assert_called_once_with(
                target_host="ns.account.tmprl.cloud:7233",
                namespace="my-ns",
                api_key="test-api-key",
                tls=True
            )
    
    @pytest.mark.asyncio
    async def test_local_connection_no_tls(self):
        """Test that no API key means no TLS."""
        mock_client = MagicMock()
        
        with patch(
            "app.modules.workflows.temporal_client.Client.connect",
            new_callable=AsyncMock,
            return_value=mock_client
        ) as mock_connect:
            manager = TemporalClientManager(
                host="localhost:7233",
                namespace="default",
                api_key=None
            )
            
            await manager.get_client()
            
            mock_connect.assert_called_once_with(
                target_host="localhost:7233",
                namespace="default"
            )
