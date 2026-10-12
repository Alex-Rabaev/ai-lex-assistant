"""Unit tests for WebchatChannelService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from bson import ObjectId

from app.modules.connections.vendors.webchat.service import (
    WebchatChannelService,
    WebchatValidationError,
    WebchatMessageNotFoundError
)
from app.modules.connections.vendors.webchat.models import WebchatMessage
from app.modules.connections.models import ConnectionChannel, ConnectionStatus
from app.modules.assistants.service import AssistantNotFoundError


class TestWebchatChannelService:
    """Test WebchatChannelService methods."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock webchat message repository."""
        repo = MagicMock()
        repo.create = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.get_messages = AsyncMock(return_value=[])
        repo.count_messages = AsyncMock(return_value=0)
        repo.update_content = AsyncMock()
        repo.soft_delete = AsyncMock(return_value=True)
        return repo
    
    @pytest.fixture
    def mock_assistant_service(self):
        """Create mock assistant service."""
        svc = MagicMock()
        svc.get_assistant_internal = AsyncMock()
        return svc
    
    @pytest.fixture
    def mock_connection_repository(self):
        """Create mock connection repository."""
        repo = MagicMock()
        repo.get_by_assistant_and_channel = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_websocket_publisher(self):
        """Create mock websocket publisher."""
        pub = MagicMock()
        pub.publish_chat_message = AsyncMock()
        pub.publish_typing_indicator = AsyncMock()
        return pub
    
    @pytest.fixture
    def service(self, mock_repository, mock_assistant_service, mock_connection_repository, mock_websocket_publisher):
        """Create service instance with mocked dependencies."""
        svc = WebchatChannelService()
        svc._repository = mock_repository
        svc._assistant_service = mock_assistant_service
        svc._connection_repository = mock_connection_repository
        svc._websocket_publisher = mock_websocket_publisher
        return svc
    
    @pytest.fixture
    def mock_webchat_message(self):
        """Create mock webchat message."""
        return WebchatMessage(
            id=ObjectId("507f1f77bcf86cd799439011"),
            conversation_id=ObjectId("507f1f77bcf86cd799439012"),
            assistant_id=ObjectId("507f1f77bcf86cd799439013"),
            user_id="webchat_user123",
            role="user",
            content="Hello!",
            is_deleted=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock webchat connection."""
        conn = MagicMock()
        conn.id = ObjectId("507f1f77bcf86cd799439014")
        conn.channel = ConnectionChannel.WEBCHAT
        conn.status = ConnectionStatus.CONNECTED
        return conn
    
    # === Validation Tests ===
    
    @pytest.mark.asyncio
    async def test_validate_message_success(self, service, mock_assistant_service, mock_connection_repository, mock_connection):
        """Test successful message validation."""
        mock_assistant_service.get_assistant_internal.return_value = MagicMock()
        mock_connection_repository.get_by_assistant_and_channel.return_value = mock_connection
        
        # Should not raise
        await service.validate_message(
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            content="Hello!"
        )
        
        mock_assistant_service.get_assistant_internal.assert_called_once()
        mock_connection_repository.get_by_assistant_and_channel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_message_empty_content(self, service):
        """Test validation fails for empty content."""
        with pytest.raises(WebchatValidationError) as exc_info:
            await service.validate_message(
                assistant_id="507f1f77bcf86cd799439013",
                user_id="webchat_user123",
                content=""
            )
        
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_message_assistant_not_found(self, service, mock_assistant_service):
        """Test validation fails when assistant not found."""
        mock_assistant_service.get_assistant_internal.side_effect = AssistantNotFoundError("Not found")
        
        with pytest.raises(WebchatValidationError) as exc_info:
            await service.validate_message(
                assistant_id="nonexistent",
                user_id="webchat_user123",
                content="Hello!"
            )
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_message_webchat_not_enabled(self, service, mock_assistant_service, mock_connection_repository):
        """Test validation fails when webchat not enabled."""
        mock_assistant_service.get_assistant_internal.return_value = MagicMock()
        mock_connection_repository.get_by_assistant_and_channel.return_value = None
        
        with pytest.raises(WebchatValidationError) as exc_info:
            await service.validate_message(
                assistant_id="507f1f77bcf86cd799439013",
                user_id="webchat_user123",
                content="Hello!"
            )
        
        assert "not enabled" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_message_connection_error_status(self, service, mock_assistant_service, mock_connection_repository):
        """Test validation fails when connection is in error state."""
        mock_assistant_service.get_assistant_internal.return_value = MagicMock()
        
        error_connection = MagicMock()
        error_connection.status = ConnectionStatus.ERROR
        mock_connection_repository.get_by_assistant_and_channel.return_value = error_connection
        
        with pytest.raises(WebchatValidationError) as exc_info:
            await service.validate_message(
                assistant_id="507f1f77bcf86cd799439013",
                user_id="webchat_user123",
                content="Hello!"
            )
        
        assert "error state" in str(exc_info.value).lower()
    
    # === Save Messages Tests ===
    
    @pytest.mark.asyncio
    async def test_save_user_message(self, service, mock_repository, mock_webchat_message):
        """Test saving user message."""
        mock_repository.create.return_value = mock_webchat_message
        
        result = await service.save_user_message(
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            content="Hello!",
            conversation_id="507f1f77bcf86cd799439012"
        )
        
        assert result.id == mock_webchat_message.id
        mock_repository.create.assert_called_once_with(
            conversation_id="507f1f77bcf86cd799439012",
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            role="user",
            content="Hello!"
        )
    
    @pytest.mark.asyncio
    async def test_save_assistant_message(self, service, mock_repository, mock_websocket_publisher, mock_webchat_message):
        """Test saving assistant message and publishing to websocket."""
        mock_webchat_message.role = "assistant"
        mock_repository.create.return_value = mock_webchat_message
        
        result = await service.save_assistant_message(
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            content="Hi there!",
            conversation_id="507f1f77bcf86cd799439012"
        )
        
        assert result.id == mock_webchat_message.id
        mock_repository.create.assert_called_once()
        mock_websocket_publisher.publish_chat_message.assert_called_once()
    
    # === Get Messages Tests ===
    
    @pytest.mark.asyncio
    async def test_get_messages(self, service, mock_repository, mock_webchat_message):
        """Test getting message history."""
        mock_repository.get_messages.return_value = [mock_webchat_message]
        mock_repository.count_messages.return_value = 1
        
        messages, total = await service.get_messages(
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            limit=50,
            skip=0
        )
        
        assert len(messages) == 1
        assert total == 1
        mock_repository.get_messages.assert_called_once()
        mock_repository.count_messages.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_message_success(self, service, mock_repository, mock_webchat_message):
        """Test getting single message."""
        mock_repository.get_by_id.return_value = mock_webchat_message
        
        result = await service.get_message(
            message_id="507f1f77bcf86cd799439011",
            user_id="webchat_user123"
        )
        
        assert result.id == mock_webchat_message.id
    
    @pytest.mark.asyncio
    async def test_get_message_not_found(self, service, mock_repository):
        """Test getting non-existent message."""
        mock_repository.get_by_id.return_value = None
        
        with pytest.raises(WebchatMessageNotFoundError):
            await service.get_message(
                message_id="nonexistent",
                user_id="webchat_user123"
            )
    
    @pytest.mark.asyncio
    async def test_get_message_wrong_user(self, service, mock_repository, mock_webchat_message):
        """Test getting message from another user fails."""
        mock_repository.get_by_id.return_value = mock_webchat_message
        
        with pytest.raises(WebchatMessageNotFoundError):
            await service.get_message(
                message_id="507f1f77bcf86cd799439011",
                user_id="webchat_other_user"
            )
    
    @pytest.mark.asyncio
    async def test_get_message_deleted(self, service, mock_repository, mock_webchat_message):
        """Test getting deleted message fails."""
        mock_webchat_message.is_deleted = True
        mock_repository.get_by_id.return_value = mock_webchat_message
        
        with pytest.raises(WebchatMessageNotFoundError):
            await service.get_message(
                message_id="507f1f77bcf86cd799439011",
                user_id="webchat_user123"
            )
    
    # === Update/Delete Tests ===
    
    @pytest.mark.asyncio
    async def test_update_message_success(self, service, mock_repository, mock_webchat_message):
        """Test updating message content."""
        mock_repository.get_by_id.return_value = mock_webchat_message
        mock_webchat_message.content = "Updated content"
        mock_repository.update_content.return_value = mock_webchat_message
        
        result = await service.update_message(
            message_id="507f1f77bcf86cd799439011",
            user_id="webchat_user123",
            content="Updated content"
        )
        
        assert result.content == "Updated content"
        mock_repository.update_content.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_message_cannot_edit_assistant(self, service, mock_repository, mock_webchat_message):
        """Test cannot edit assistant messages."""
        mock_webchat_message.role = "assistant"
        mock_repository.get_by_id.return_value = mock_webchat_message
        
        with pytest.raises(WebchatValidationError) as exc_info:
            await service.update_message(
                message_id="507f1f77bcf86cd799439011",
                user_id="webchat_user123",
                content="Try to edit"
            )
        
        assert "cannot edit" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_update_message_empty_content(self, service, mock_repository, mock_webchat_message):
        """Test cannot update with empty content."""
        mock_repository.get_by_id.return_value = mock_webchat_message
        
        with pytest.raises(WebchatValidationError) as exc_info:
            await service.update_message(
                message_id="507f1f77bcf86cd799439011",
                user_id="webchat_user123",
                content=""
            )
        
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_delete_message_success(self, service, mock_repository, mock_webchat_message):
        """Test soft deleting message."""
        mock_repository.get_by_id.return_value = mock_webchat_message
        mock_repository.soft_delete.return_value = True
        
        result = await service.delete_message(
            message_id="507f1f77bcf86cd799439011",
            user_id="webchat_user123"
        )
        
        assert result is True
        mock_repository.soft_delete.assert_called_once_with("507f1f77bcf86cd799439011")
    
    # === Typing Indicator Test ===
    
    @pytest.mark.asyncio
    async def test_publish_typing_indicator(self, service, mock_websocket_publisher):
        """Test publishing typing indicator."""
        await service.publish_typing_indicator(
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            is_typing=True
        )
        
        mock_websocket_publisher.publish_typing_indicator.assert_called_once_with(
            assistant_id="507f1f77bcf86cd799439013",
            user_id="webchat_user123",
            is_typing=True
        )
    
    # === Helper Method Test ===
    
    def test_to_response(self, service, mock_webchat_message):
        """Test converting message to response schema."""
        response = service.to_response(mock_webchat_message)
        
        assert response.id == str(mock_webchat_message.id)
        assert response.user_id == mock_webchat_message.user_id
        assert response.content == mock_webchat_message.content
        assert response.role == mock_webchat_message.role

