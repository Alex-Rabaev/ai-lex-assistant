"""Tests for connection schemas."""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import ValidationError

from app.modules.connections.schemas import (
    CreateTelegramConnectionRequest,
    ConnectionResponse,
    ConnectionListResponse,
    ConnectionHealthCheckResponse,
    BotInfo
)
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)


class TestConnectionSchemas:
    """Test connection schemas."""
    
    def test_create_telegram_connection_request_valid(self):
        """Test valid Telegram connection request."""
        request = CreateTelegramConnectionRequest(
            bot_token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
        )
        assert request.bot_token == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
        
    def test_create_telegram_connection_request_invalid_format(self):
        """Test invalid bot token format."""
        # Too short
        with pytest.raises(ValidationError):
            CreateTelegramConnectionRequest(
                bot_token="invalid_token"
            )
        
        # Wrong format - missing proper separator
        with pytest.raises(ValidationError):
            CreateTelegramConnectionRequest(
                bot_token="12345:tooshort"
            )
        
        # Invalid bot ID part (not numeric)
        with pytest.raises(ValidationError):
            CreateTelegramConnectionRequest(
                bot_token="notanumber:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
            )
    
    def test_create_telegram_connection_request_too_short(self):
        """Test bot token too short."""
        with pytest.raises(ValidationError):
            CreateTelegramConnectionRequest(
                bot_token="123:abc"
            )
    
    def test_connection_response_from_model(self):
        """Test converting Connection model to response."""
        assistant_id = ObjectId()
        settings = ConnectionSettings(
            bot_token="encrypted_token",
            bot_username="@test_bot",
            bot_first_name="Test Bot",
            webhook_url="https://example.com/webhook/telegram/123"
        )
        
        connection = Connection(
            _id=ObjectId(),
            assistant_id=assistant_id,
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.CONNECTED,
            settings=settings,
            last_error=None,
            last_checked_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        response = ConnectionResponse.from_model(connection)
        
        assert response.id == str(connection.id)
        assert response.assistant_id == str(connection.assistant_id)
        assert response.channel == ConnectionChannel.TELEGRAM
        assert response.status == ConnectionStatus.CONNECTED
        assert response.bot_username == "@test_bot"
        assert response.bot_first_name == "Test Bot"
        assert response.webhook_url == "https://example.com/webhook/telegram/123"
        assert response.last_error is None
        
    def test_connection_response_with_error(self):
        """Test ConnectionResponse with error state."""
        assistant_id = ObjectId()
        settings = ConnectionSettings(
            bot_token="encrypted_token",
            bot_username=None,
            bot_first_name=None,
            webhook_url=None
        )
        
        connection = Connection(
            _id=ObjectId(),
            assistant_id=assistant_id,
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.ERROR,
            settings=settings,
            last_error="Invalid bot token",
            last_checked_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        response = ConnectionResponse.from_model(connection)
        
        assert response.status == ConnectionStatus.ERROR
        assert response.last_error == "Invalid bot token"
        assert response.bot_username is None
        assert response.webhook_url is None
    
    def test_connection_list_response(self):
        """Test ConnectionListResponse."""
        assistant_id = ObjectId()
        
        # Create sample connections
        connections = []
        for i in range(2):
            settings = ConnectionSettings(
                bot_token=f"encrypted_token_{i}",
                bot_username=f"@bot_{i}",
                bot_first_name=f"Bot {i}"
            )
            
            connection = Connection(
                _id=ObjectId(),
                assistant_id=assistant_id,
                channel=ConnectionChannel.TELEGRAM,
                status=ConnectionStatus.CONNECTED,
                settings=settings,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            connections.append(connection)
        
        # Convert to response items
        items = [ConnectionResponse.from_model(conn) for conn in connections]
        
        list_response = ConnectionListResponse(
            items=items,
            total=2,
            skip=0,
            limit=20,
            assistant_id=str(assistant_id)
        )
        
        assert len(list_response.items) == 2
        assert list_response.total == 2
        assert list_response.skip == 0
        assert list_response.limit == 20
        assert list_response.assistant_id == str(assistant_id)
    
    def test_health_check_response(self):
        """Test ConnectionHealthCheckResponse."""
        response = ConnectionHealthCheckResponse(
            id="507f1f77bcf86cd799439011",
            status=ConnectionStatus.CONNECTED,
            is_healthy=True,
            checked_at=datetime.now(timezone.utc),
            last_error=None
        )
        
        assert response.id == "507f1f77bcf86cd799439011"
        assert response.status == ConnectionStatus.CONNECTED
        assert response.is_healthy is True
        assert response.last_error is None
    
    def test_health_check_response_unhealthy(self):
        """Test unhealthy ConnectionHealthCheckResponse."""
        response = ConnectionHealthCheckResponse(
            id="507f1f77bcf86cd799439011",
            status=ConnectionStatus.ERROR,
            is_healthy=False,
            checked_at=datetime.now(timezone.utc),
            last_error="Bot token is invalid or expired"
        )
        
        assert response.status == ConnectionStatus.ERROR
        assert response.is_healthy is False
        assert response.last_error == "Bot token is invalid or expired"
    
    def test_bot_info(self):
        """Test BotInfo schema."""
        bot_info = BotInfo(
            id=123456789,
            is_bot=True,
            first_name="Test Bot",
            username="test_bot",
            can_join_groups=True,
            can_read_all_group_messages=False,
            supports_inline_queries=False
        )
        
        assert bot_info.id == 123456789
        assert bot_info.is_bot is True
        assert bot_info.first_name == "Test Bot"
        assert bot_info.username == "test_bot"
        assert bot_info.can_join_groups is True
        assert bot_info.can_read_all_group_messages is False
        assert bot_info.supports_inline_queries is False
