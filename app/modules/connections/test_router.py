"""Integration tests for connections API router."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime, timezone
from bson import ObjectId
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.main import app
from app.common.auth import get_current_admin_auth0, AdminUser
from app.common.db.database import get_database
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)
from app.modules.connections.service import AssistantNotFoundError
from app.modules.connections.exceptions import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    InvalidBotTokenError
)


@pytest.fixture
def mock_admin_user():
    """Create mock admin user."""
    return AdminUser(
        email="admin@example.com",
        role="admin",
        username="admin"
    )


@pytest.fixture
def mock_db():
    """Create mock database."""
    db = MagicMock(spec=AsyncIOMotorDatabase)
    return db


@pytest.fixture
def test_client(mock_admin_user, mock_db):
    """Create test client with mocked dependencies."""
    app.dependency_overrides[get_current_admin_auth0] = lambda: mock_admin_user
    app.dependency_overrides[get_database] = lambda: mock_db

    mock_motor = MagicMock()
    mock_motor.admin.command = AsyncMock(return_value={"ok": 1})

    with patch("app.main.get_motor_client", return_value=mock_motor), \
         patch("app.main.close_motor_client", new_callable=AsyncMock):
        client = TestClient(app)
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_connection():
    """Create mock connection."""
    settings = ConnectionSettings(
        bot_token="encrypted_token",
        bot_username="@test_bot",
        bot_id=123456789,
        bot_first_name="Test Bot",
        webhook_url="https://example.com/webhook"
    )
    
    return Connection(
        _id=ObjectId("507f1f77bcf86cd799439012"),
        assistant_id=ObjectId("507f1f77bcf86cd799439011"),
        channel=ConnectionChannel.TELEGRAM,
        status=ConnectionStatus.CONNECTED,
        settings=settings,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestConnectionRouter:
    """Test connection API endpoints."""
    
    def test_create_telegram_connection_success(
        self, test_client, mock_connection
    ):
        """Test successful Telegram connection creation."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            # Mock async method
            future = AsyncMock()
            future.return_value = mock_connection
            mock_service.create_telegram_connection = future
            
            response = test_client.post(
                "/api/v1/assistants/507f1f77bcf86cd799439011/connections/telegram",
                json={"bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["channel"] == "telegram"
            assert data["status"] == "connected"
            assert data["bot_username"] == "@test_bot"
    
    def test_create_telegram_connection_assistant_not_found(self, test_client):
        """Test connection creation when assistant not found."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            # Mock async method that raises exception
            future = AsyncMock()
            future.side_effect = AssistantNotFoundError("Assistant not found")
            mock_service.create_telegram_connection = future
            
            response = test_client.post(
                "/api/v1/assistants/invalid_id/connections/telegram",
                json={"bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"}
            )
            
            assert response.status_code == 404
    
    def test_create_telegram_connection_invalid_token(self, test_client):
        """Test connection creation with invalid bot token."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.side_effect = InvalidBotTokenError("Invalid token")
            mock_service.create_telegram_connection = future
            
            response = test_client.post(
                "/api/v1/assistants/507f1f77bcf86cd799439011/connections/telegram",
                json={"bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"}
            )
            
            assert response.status_code == 400
    
    def test_create_telegram_connection_duplicate(self, test_client):
        """Test connection creation when already exists."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.side_effect = DuplicateConnectionError("Connection already exists")
            mock_service.create_telegram_connection = future
            
            response = test_client.post(
                "/api/v1/assistants/507f1f77bcf86cd799439011/connections/telegram",
                json={"bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"}
            )
            
            assert response.status_code == 409
    
    def test_list_assistant_connections_success(
        self, test_client, mock_connection
    ):
        """Test listing connections for assistant."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.return_value = [mock_connection]
            mock_service.list_connections = future
            
            response = test_client.get(
                "/api/v1/assistants/507f1f77bcf86cd799439011/connections"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["channel"] == "telegram"
    
    def test_get_connection_success(
        self, test_client, mock_connection
    ):
        """Test getting connection details."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.return_value = mock_connection
            mock_service.get_connection = future
            
            response = test_client.get(
                "/api/v1/connections/507f1f77bcf86cd799439012"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["channel"] == "telegram"
            assert data["status"] == "connected"
    
    def test_get_connection_not_found(self, test_client):
        """Test getting non-existent connection."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.side_effect = ConnectionNotFoundError("Connection not found")
            mock_service.get_connection = future
            
            response = test_client.get("/api/v1/connections/invalid_id")
            
            assert response.status_code == 404
    
    def test_delete_connection_success(self, test_client):
        """Test successful connection deletion."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.return_value = True
            mock_service.delete_connection = future
            
            response = test_client.delete(
                "/api/v1/connections/507f1f77bcf86cd799439012"
            )
            
            assert response.status_code == 204
    
    def test_delete_connection_not_found(self, test_client):
        """Test deleting non-existent connection."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future = AsyncMock()
            future.side_effect = ConnectionNotFoundError("Connection not found")
            mock_service.delete_connection = future
            
            response = test_client.delete("/api/v1/connections/invalid_id")
            
            assert response.status_code == 404
    
    def test_check_connection_health_success(
        self, test_client, mock_connection
    ):
        """Test successful health check."""
        with patch('app.modules.connections.router.ConnectionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service
            
            future_get = AsyncMock()
            future_get.return_value = mock_connection
            mock_service.get_connection = future_get
            
            future_check = AsyncMock()
            future_check.return_value = mock_connection
            mock_service.check_connection_health = future_check
            
            response = test_client.post(
                "/api/v1/connections/507f1f77bcf86cd799439012/health-check"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "connected"
            assert data["is_healthy"] is True
    
    def test_unauthorized_request(self):
        """Test request without authentication."""
        mock_motor = MagicMock()
        mock_motor.admin.command = AsyncMock(return_value={"ok": 1})

        with patch("app.main.get_motor_client", return_value=mock_motor), \
             patch("app.main.close_motor_client", new_callable=AsyncMock):
            client = TestClient(app)
            response = client.get("/api/v1/connections/some_id")

        assert response.status_code in [401, 403, 422]