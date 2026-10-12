"""Tests for connection service layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.connections.service import ConnectionService
from app.modules.assistants.service import AssistantNotFoundError
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)
from app.modules.connections.schemas import BotInfo
from app.modules.connections.exceptions import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    InvalidBotTokenError,
    WebhookSetupError
)


class TestConnectionService:
    """Test ConnectionService methods."""
    
    @pytest.fixture
    def mock_connection_repo(self):
        """Create mock connection repository."""
        repo = MagicMock()
        repo.exists_by_assistant_and_channel = AsyncMock(return_value=False)
        repo.create = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.find_by_assistant = AsyncMock(return_value=[])
        repo.update = AsyncMock()
        repo.update_status = AsyncMock()
        repo.delete = AsyncMock(return_value=True)
        repo.get_by_assistant_and_channel = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_assistant_service(self):
        """Create mock assistant service."""
        svc = MagicMock()
        svc.get_assistant = AsyncMock()
        return svc
    
    @pytest.fixture
    def mock_telegram_service(self):
        """Create mock telegram connection service."""
        svc = MagicMock()
        svc.create_connection = AsyncMock()
        svc.delete_webhook = AsyncMock(return_value=True)
        svc.check_health = AsyncMock(return_value=(True, None))
        return svc
    
    @pytest.fixture
    def service(self, mock_connection_repo, mock_assistant_service, mock_telegram_service):
        """Create service instance with mocked dependencies."""
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            with patch('app.modules.connections.service.AssistantService', return_value=mock_assistant_service):
                with patch('app.modules.connections.service.TelegramConnectionService', return_value=mock_telegram_service):
                    svc = ConnectionService()
                    svc._assistant_service = mock_assistant_service
                    svc._telegram_service = mock_telegram_service
                    return svc
    
    @pytest.fixture
    def mock_assistant(self):
        """Create mock assistant."""
        assistant = MagicMock()
        assistant.id = ObjectId("507f1f77bcf86cd799439011")
        assistant.owner_user_id = "user@example.com"
        assistant.name = "Test Assistant"
        return assistant
    
    @pytest.fixture
    def mock_bot_info(self):
        """Create mock bot info."""
        return BotInfo(
            id=123456789,
            is_bot=True,
            first_name="Test Bot",
            username="test_bot",
            can_join_groups=True,
            can_read_all_group_messages=False,
            supports_inline_queries=False
        )
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock connection."""
        settings = ConnectionSettings(
            bot_token="encrypted_token",
            bot_username="@test_bot",
            bot_id=123456789,
            bot_first_name="Test Bot",
            webhook_url="https://example.com/webhook"
        )
        
        connection = Connection(
            _id=ObjectId("507f1f77bcf86cd799439012"),
            assistant_id=ObjectId("507f1f77bcf86cd799439011"),
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.CONNECTED,
            settings=settings,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        return connection
    
    # ===== Test create_telegram_connection =====
    
    @pytest.mark.asyncio
    async def test_create_telegram_connection_success(
        self, service, mock_assistant, mock_connection,
        mock_assistant_service, mock_telegram_service
    ):
        """Test successful Telegram connection creation."""
        assistant_id = "507f1f77bcf86cd799439011"
        user_id = "user@example.com"
        bot_token = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
        
        # Mock assistant exists
        mock_assistant_service.get_assistant.return_value = mock_assistant
        
        # Mock telegram service create_connection
        mock_telegram_service.create_connection.return_value = mock_connection
        
        # Create connection
        result = await service.create_telegram_connection(
            assistant_id,
            user_id,
            bot_token
        )
        
        assert result is not None
        assert result.channel == ConnectionChannel.TELEGRAM
        assert result.status == ConnectionStatus.CONNECTED
        
        # Verify calls
        mock_assistant_service.get_assistant.assert_called_once_with(assistant_id, user_id)
        mock_telegram_service.create_connection.assert_called_once_with(assistant_id, bot_token)
    
    @pytest.mark.asyncio
    async def test_create_telegram_connection_assistant_not_found(
        self, service, mock_assistant_service
    ):
        """Test connection creation when assistant not found."""
        mock_assistant_service.get_assistant.side_effect = AssistantNotFoundError("Not found")
        
        with pytest.raises(AssistantNotFoundError):
            await service.create_telegram_connection(
                "507f1f77bcf86cd799439011",
                "user@example.com",
                "bot_token"
            )
    
    @pytest.mark.asyncio
    async def test_create_telegram_connection_already_exists(
        self, service, mock_assistant, mock_assistant_service, mock_telegram_service
    ):
        """Test connection creation when already exists."""
        mock_assistant_service.get_assistant.return_value = mock_assistant
        mock_telegram_service.create_connection.side_effect = DuplicateConnectionError("Already exists")
        
        with pytest.raises(DuplicateConnectionError):
            await service.create_telegram_connection(
                "507f1f77bcf86cd799439011",
                "user@example.com",
                "bot_token"
            )
    
    @pytest.mark.asyncio
    async def test_create_telegram_connection_invalid_token(
        self, service, mock_assistant, mock_assistant_service, mock_telegram_service
    ):
        """Test connection creation with invalid bot token."""
        mock_assistant_service.get_assistant.return_value = mock_assistant
        mock_telegram_service.create_connection.side_effect = InvalidBotTokenError("Invalid token")
        
        with pytest.raises(InvalidBotTokenError):
            await service.create_telegram_connection(
                "507f1f77bcf86cd799439011",
                "user@example.com",
                "invalid_token"
            )
    
    @pytest.mark.asyncio
    async def test_create_telegram_connection_webhook_fails(
        self, service, mock_assistant, mock_connection,
        mock_assistant_service, mock_telegram_service
    ):
        """Test connection creation when webhook setup fails."""
        assistant_id = "507f1f77bcf86cd799439011"
        user_id = "user@example.com"
        bot_token = "valid_token"
        
        mock_assistant_service.get_assistant.return_value = mock_assistant
        
        # Return connection with ERROR status (webhook failed)
        error_connection = Connection(
            _id=mock_connection.id,
            assistant_id=mock_connection.assistant_id,
            channel=mock_connection.channel,
            status=ConnectionStatus.ERROR,
            settings=mock_connection.settings,
            last_error="Webhook setup failed",
            created_at=mock_connection.created_at,
            updated_at=mock_connection.updated_at
        )
        mock_telegram_service.create_connection.return_value = error_connection
        
        result = await service.create_telegram_connection(
            assistant_id,
            user_id,
            bot_token
        )
        
        assert result.status == ConnectionStatus.ERROR
    
    # ===== Test get_connection =====
    
    @pytest.mark.asyncio
    async def test_get_connection_success(
        self, service, mock_assistant, mock_connection,
        mock_connection_repo, mock_assistant_service
    ):
        """Test successful connection retrieval."""
        connection_id = "507f1f77bcf86cd799439012"
        user_id = "user@example.com"
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_assistant_service.get_assistant.return_value = mock_assistant
            
            result = await service.get_connection(connection_id, user_id)
            
            assert result == mock_connection
            mock_connection_repo.get_by_id.assert_called_once_with(connection_id)
    
    @pytest.mark.asyncio
    async def test_get_connection_not_found(self, service, mock_connection_repo):
        """Test get connection when not found."""
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = None
            
            with pytest.raises(ConnectionNotFoundError):
                await service.get_connection("nonexistent", "user@example.com")
    
    @pytest.mark.asyncio
    async def test_get_connection_no_access(
        self, service, mock_connection, mock_connection_repo, mock_assistant_service
    ):
        """Test get connection when user has no access."""
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_assistant_service.get_assistant.side_effect = AssistantNotFoundError("No access")
            
            with pytest.raises(ConnectionNotFoundError):
                await service.get_connection("507f1f77bcf86cd799439012", "other@example.com")
    
    # ===== Test list_connections =====
    
    @pytest.mark.asyncio
    async def test_list_connections_success(
        self, service, mock_assistant, mock_connection,
        mock_connection_repo, mock_assistant_service
    ):
        """Test listing connections for assistant."""
        assistant_id = "507f1f77bcf86cd799439011"
        user_id = "user@example.com"
        
        mock_assistant_service.get_assistant.return_value = mock_assistant
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.find_by_assistant.return_value = [mock_connection]
            
            result = await service.list_connections(assistant_id, user_id)
            
            assert len(result) == 1
            assert result[0] == mock_connection
    
    @pytest.mark.asyncio
    async def test_list_connections_no_access(self, service, mock_assistant_service):
        """Test listing connections when no access."""
        mock_assistant_service.get_assistant.side_effect = AssistantNotFoundError("No access")
        
        with pytest.raises(AssistantNotFoundError):
            await service.list_connections(
                "507f1f77bcf86cd799439011",
                "other@example.com"
            )
    
    # ===== Test delete_connection =====
    
    @pytest.mark.asyncio
    async def test_delete_connection_success(
        self, service, mock_assistant, mock_connection,
        mock_connection_repo, mock_assistant_service, mock_telegram_service
    ):
        """Test successful connection deletion."""
        connection_id = "507f1f77bcf86cd799439012"
        user_id = "user@example.com"
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_assistant_service.get_assistant.return_value = mock_assistant
            mock_telegram_service.delete_webhook.return_value = True
            mock_connection_repo.delete.return_value = True
            
            result = await service.delete_connection(connection_id, user_id)
            
            assert result is True
            mock_telegram_service.delete_webhook.assert_called_once_with(mock_connection)
            mock_connection_repo.delete.assert_called_once_with(connection_id)
    
    @pytest.mark.asyncio
    async def test_delete_connection_webhook_fails(
        self, service, mock_assistant, mock_connection,
        mock_connection_repo, mock_assistant_service, mock_telegram_service
    ):
        """Test deletion continues even if webhook deletion fails."""
        connection_id = "507f1f77bcf86cd799439012"
        user_id = "user@example.com"
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_assistant_service.get_assistant.return_value = mock_assistant
            
            # Webhook deletion fails
            mock_telegram_service.delete_webhook.return_value = False
            mock_connection_repo.delete.return_value = True
            
            # Should still delete from DB
            result = await service.delete_connection(connection_id, user_id)
            
            assert result is True
            mock_connection_repo.delete.assert_called_once_with(connection_id)
    
    # ===== Test check_connection_health =====
    
    @pytest.mark.asyncio
    async def test_check_connection_health_healthy(
        self, service, mock_connection, mock_connection_repo, mock_telegram_service
    ):
        """Test health check for healthy connection."""
        connection_id = "507f1f77bcf86cd799439012"
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_telegram_service.check_health.return_value = (True, None)
            mock_connection_repo.update_status.return_value = mock_connection
            
            result = await service.check_connection_health(connection_id)
            
            assert result.status == ConnectionStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_check_connection_health_degraded(
        self, service, mock_connection, mock_connection_repo, mock_telegram_service
    ):
        """Test health check for degraded connection."""
        connection_id = "507f1f77bcf86cd799439012"
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_telegram_service.check_health.return_value = (False, "Too many pending updates")
            
            degraded_connection = Connection(
                _id=mock_connection.id,
                assistant_id=mock_connection.assistant_id,
                channel=mock_connection.channel,
                status=ConnectionStatus.DEGRADED,
                settings=mock_connection.settings,
                last_error="Too many pending updates",
                created_at=mock_connection.created_at,
                updated_at=mock_connection.updated_at
            )
            mock_connection_repo.update_status.return_value = degraded_connection
            
            result = await service.check_connection_health(connection_id)
            
            assert result.status == ConnectionStatus.DEGRADED
    
    @pytest.mark.asyncio
    async def test_check_connection_health_invalid_token(
        self, service, mock_connection, mock_connection_repo, mock_telegram_service
    ):
        """Test health check with invalid token."""
        connection_id = "507f1f77bcf86cd799439012"
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = mock_connection
            mock_telegram_service.check_health.side_effect = InvalidBotTokenError("Invalid")
            
            error_connection = Connection(
                _id=mock_connection.id,
                assistant_id=mock_connection.assistant_id,
                channel=mock_connection.channel,
                status=ConnectionStatus.ERROR,
                settings=mock_connection.settings,
                last_error="Invalid bot token",
                created_at=mock_connection.created_at,
                updated_at=mock_connection.updated_at
            )
            mock_connection_repo.update_status.return_value = error_connection
            
            result = await service.check_connection_health(connection_id)
            
            assert result.status == ConnectionStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_check_connection_health_skip_error_status(
        self, service, mock_connection_repo, mock_telegram_service
    ):
        """Test health check skips connections in ERROR status."""
        connection_id = "507f1f77bcf86cd799439012"
        
        # Connection already in ERROR status
        error_connection = Connection(
            _id=ObjectId(connection_id),
            assistant_id=ObjectId("507f1f77bcf86cd799439011"),
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.ERROR,
            settings=ConnectionSettings(bot_token="encrypted"),
            last_error="Previous error",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        with patch('app.modules.connections.service.ConnectionRepository', return_value=mock_connection_repo):
            mock_connection_repo.get_by_id.return_value = error_connection
            
            # Should not call telegram_service
            result = await service.check_connection_health(connection_id)
            
            assert result.status == ConnectionStatus.ERROR
            mock_telegram_service.check_health.assert_not_called()
