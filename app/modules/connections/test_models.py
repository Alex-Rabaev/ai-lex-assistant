"""Tests for connection models."""

import pytest
from datetime import datetime, timezone
from bson import ObjectId

from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)


class TestConnectionModels:
    """Test connection models."""
    
    def test_connection_channel_enum(self):
        """Test ConnectionChannel enum values."""
        assert ConnectionChannel.TELEGRAM == "telegram"
        assert ConnectionChannel.WHATSAPP == "whatsapp"
        
    def test_connection_status_enum(self):
        """Test ConnectionStatus enum values."""
        assert ConnectionStatus.PENDING == "pending"
        assert ConnectionStatus.CONNECTED == "connected"
        assert ConnectionStatus.ERROR == "error"
        assert ConnectionStatus.DEGRADED == "degraded"
        
    def test_connection_settings_creation(self):
        """Test creating ConnectionSettings."""
        settings = ConnectionSettings(
            bot_token="encrypted_token_here",
            bot_username="@test_bot",
            bot_id=123456789,
            bot_first_name="Test Bot",
            webhook_url="https://example.com/webhook",
            bot_info={"id": 123456789, "is_bot": True}
        )
        
        assert settings.bot_token == "encrypted_token_here"
        assert settings.bot_username == "@test_bot"
        assert settings.bot_id == 123456789
        assert settings.bot_first_name == "Test Bot"
        assert settings.webhook_url == "https://example.com/webhook"
        assert settings.bot_info["is_bot"] is True
        
    def test_connection_creation(self):
        """Test creating Connection model."""
        assistant_id = ObjectId()
        settings = ConnectionSettings(bot_token="encrypted_token")
        
        connection = Connection(
            assistant_id=assistant_id,
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.PENDING,
            settings=settings,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        assert connection.assistant_id == assistant_id
        assert connection.channel == ConnectionChannel.TELEGRAM
        assert connection.status == ConnectionStatus.PENDING
        assert connection.settings.bot_token == "encrypted_token"
        assert connection.last_error is None
        assert connection.last_checked_at is None
        
    def test_connection_with_error(self):
        """Test connection with error state."""
        assistant_id = ObjectId()
        settings = ConnectionSettings(bot_token="encrypted_token")
        
        connection = Connection(
            assistant_id=assistant_id,
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.ERROR,
            settings=settings,
            last_error="Invalid bot token",
            last_checked_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        assert connection.status == ConnectionStatus.ERROR
        assert connection.last_error == "Invalid bot token"
        assert connection.last_checked_at is not None
        
    def test_connection_validation_invalid_channel(self):
        """Test validation for invalid channel."""
        assistant_id = ObjectId()
        settings = ConnectionSettings(bot_token="encrypted_token")
        
        # This should not raise because we use Enum which validates automatically
        with pytest.raises(ValueError):
            Connection(
                assistant_id=assistant_id,
                channel="invalid_channel",  # This will fail Enum validation
                status=ConnectionStatus.PENDING,
                settings=settings,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
    
    def test_connection_validation_missing_assistant_id(self):
        """Test validation for missing assistant_id."""
        settings = ConnectionSettings(bot_token="encrypted_token")
        
        with pytest.raises(ValueError):
            Connection(
                assistant_id=None,  # Missing assistant_id
                channel=ConnectionChannel.TELEGRAM,
                status=ConnectionStatus.PENDING,
                settings=settings,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
