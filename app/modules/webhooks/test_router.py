"""
Tests for webhook router with security validation.
"""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.modules.webhooks.router import (
    router,
    validate_webhook_secret,
    telegram_webhook
)
from app.modules.webhooks.models import WebhookResponse
from app.modules.webhooks.exceptions import WebhookValidationError
from app.modules.connections.models import Connection, ConnectionSettings, ConnectionChannel, ConnectionStatus


class TestWebhookSecurity:
    """Test webhook security functions."""
    
    def test_validate_webhook_secret_success(self):
        """Test successful secret validation."""
        result = validate_webhook_secret(
            "test_secret_123",
            "test_secret_123",
            "telegram"
        )
        assert result is True
    
    def test_validate_webhook_secret_mismatch(self):
        """Test secret mismatch."""
        result = validate_webhook_secret(
            "wrong_secret",
            "correct_secret",
            "telegram"
        )
        assert result is False
    
    def test_validate_webhook_secret_no_expected(self):
        """Test when no expected secret configured."""
        result = validate_webhook_secret(
            "some_secret",
            None,
            "telegram"
        )
        assert result is False
    
    def test_validate_webhook_secret_no_header(self):
        """Test when no secret in header."""
        result = validate_webhook_secret(
            None,
            "expected_secret",
            "telegram"
        )
        assert result is False
    
    def test_validate_webhook_secret_timing_safe(self):
        """Test that validation is timing-attack safe."""
        # This test verifies we use secrets.compare_digest
        # which is constant-time comparison
        import secrets as secrets_module
        
        with patch.object(secrets_module, 'compare_digest', return_value=True) as mock_compare:
            result = validate_webhook_secret(
                "secret1",
                "secret2",
                "telegram"
            )
            
            # Verify secrets.compare_digest was called
            mock_compare.assert_called_once_with("secret1", "secret2")


class TestTelegramWebhook:
    """Test Telegram webhook endpoint."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock connection with webhook secret."""
        settings = ConnectionSettings(
            bot_token="test_bot_token",
            webhook_secret="test_webhook_secret"
        )
        connection = Connection(
            id=ObjectId(),
            assistant_id=ObjectId(),
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.CONNECTED,
            credentials={"token": "bot_token"},
            config={},
            settings=settings
        )
        return connection
    
    @pytest.fixture
    def mock_webhook_repo(self):
        """Create mock webhook repository."""
        webhook_repo = Mock()
        webhook_repo.save_event = AsyncMock()
        webhook_repo.get_by_update_id = AsyncMock(return_value=None)
        webhook_repo.mark_as_processed = AsyncMock()
        return webhook_repo
    
    @pytest.fixture
    def mock_webhook_publisher(self):
        """Create mock webhook publisher."""
        publisher = Mock()
        publisher.publish_message = AsyncMock()
        return publisher
    
    @pytest.mark.asyncio
    async def test_telegram_webhook_success(self, mock_connection, mock_webhook_repo, mock_webhook_publisher):
        """Test successful webhook processing."""
        from fastapi import Request
        
        # Create mock request
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test"
                },
                "chat": {
                    "id": 123456,
                    "type": "private"
                },
                "date": 1234567890,
                "text": "Hello bot!"
            }
        })
        
        # Mock ConnectionService
        with patch('app.modules.webhooks.router.ConnectionService') as MockConnectionService:
            mock_conn_service = MockConnectionService.return_value
            mock_conn_service.get_connection_by_assistant_and_channel_internal = AsyncMock(
                return_value=mock_connection
            )
            
            # Mock TelegramWebhookService
            with patch('app.modules.webhooks.router.TelegramWebhookService') as MockService:
                mock_service = MockService.return_value
                mock_service.process_update = AsyncMock(
                    return_value=WebhookResponse(
                        success=True,
                        message="Message queued for processing"
                    )
                )
                
                # Call endpoint
                response = await telegram_webhook(
                    assistant_id="test_assistant",
                    request=request,
                    x_telegram_bot_api_secret_token="test_webhook_secret",
                    webhook_repo=mock_webhook_repo,
                    webhook_publisher=mock_webhook_publisher
                )
                
                # Check response
                assert response.status_code == 200
                content = json.loads(response.body)
                assert content["ok"] is True
                
                # Verify service was called
                mock_service.process_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_telegram_webhook_invalid_secret(self, mock_connection, mock_webhook_repo, mock_webhook_publisher):
        """Test webhook with invalid secret."""
        from fastapi import Request
        
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={"update_id": 12345})
        
        # Mock ConnectionService
        with patch('app.modules.webhooks.router.ConnectionService') as MockConnectionService:
            mock_conn_service = MockConnectionService.return_value
            mock_conn_service.get_connection_by_assistant_and_channel_internal = AsyncMock(
                return_value=mock_connection
            )
            
            # Call with wrong secret
            with pytest.raises(HTTPException) as exc_info:
                await telegram_webhook(
                    assistant_id="test_assistant",
                    request=request,
                    x_telegram_bot_api_secret_token="wrong_secret",
                    webhook_repo=mock_webhook_repo,
                    webhook_publisher=mock_webhook_publisher
                )
            
            # Check it's a 403 Forbidden
            assert exc_info.value.status_code == 403
            assert "Invalid webhook secret" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_telegram_webhook_no_connection(self, mock_webhook_repo, mock_webhook_publisher):
        """Test webhook when connection not found."""
        from fastapi import Request
        
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={"update_id": 12345})
        
        # Mock ConnectionService - no connection found
        with patch('app.modules.webhooks.router.ConnectionService') as MockConnectionService:
            mock_conn_service = MockConnectionService.return_value
            mock_conn_service.get_connection_by_assistant_and_channel_internal = AsyncMock(
                return_value=None
            )
            
            # Call endpoint
            response = await telegram_webhook(
                assistant_id="test_assistant",
                request=request,
                x_telegram_bot_api_secret_token=None,
                webhook_repo=mock_webhook_repo,
                webhook_publisher=mock_webhook_publisher
            )
            
            # Should still return 200 to prevent retries
            assert response.status_code == 200
            content = json.loads(response.body)
            assert content["ok"] is True
    
    @pytest.mark.asyncio
    async def test_telegram_webhook_processing_error(self, mock_connection, mock_webhook_repo, mock_webhook_publisher):
        """Test webhook when processing fails."""
        from fastapi import Request
        
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test"
                },
                "chat": {
                    "id": 123456,
                    "type": "private"
                },
                "date": 1234567890,
                "text": "Hello bot!"
            }
        })
        
        # Mock ConnectionService
        with patch('app.modules.webhooks.router.ConnectionService') as MockConnectionService:
            mock_conn_service = MockConnectionService.return_value
            mock_conn_service.get_connection_by_assistant_and_channel_internal = AsyncMock(
                return_value=mock_connection
            )
            
            # Mock processing failure
            with patch('app.modules.webhooks.router.TelegramWebhookService') as MockService:
                mock_service = MockService.return_value
                mock_service.process_update = AsyncMock(
                    return_value=WebhookResponse(
                        success=False,
                        message="Processing failed"
                    )
                )
                
                # Call endpoint
                response = await telegram_webhook(
                    assistant_id="test_assistant",
                    request=request,
                    x_telegram_bot_api_secret_token="test_webhook_secret",
                    webhook_repo=mock_webhook_repo,
                    webhook_publisher=mock_webhook_publisher
                )
                
                # Should still return 200 to prevent retries
                assert response.status_code == 200
                content = json.loads(response.body)
                assert content["ok"] is True
    
    @pytest.mark.asyncio
    async def test_telegram_webhook_exception(self, mock_connection, mock_webhook_repo, mock_webhook_publisher):
        """Test webhook when exception occurs."""
        from fastapi import Request
        
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "update_id": 12345
        })
        
        # Mock ConnectionService
        with patch('app.modules.webhooks.router.ConnectionService') as MockConnectionService:
            mock_conn_service = MockConnectionService.return_value
            mock_conn_service.get_connection_by_assistant_and_channel_internal = AsyncMock(
                return_value=mock_connection
            )
            
            # Mock exception during processing
            with patch('app.modules.webhooks.router.TelegramWebhookService') as MockService:
                mock_service = MockService.return_value
                mock_service.process_update = AsyncMock(
                    side_effect=Exception("Unexpected error")
                )
                
                # Call endpoint
                response = await telegram_webhook(
                    assistant_id="test_assistant",
                    request=request,
                    x_telegram_bot_api_secret_token="test_webhook_secret",
                    webhook_repo=mock_webhook_repo,
                    webhook_publisher=mock_webhook_publisher
                )
                
                # Should still return 200 to prevent retries
                assert response.status_code == 200
                content = json.loads(response.body)
                assert content["ok"] is True
                assert "error" in content


class TestWebhookHealth:
    """Test webhook health endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        from app.modules.webhooks.router import webhook_health, get_webhook_publisher
        
        webhook_publisher = await get_webhook_publisher()
        result = await webhook_health(webhook_publisher=webhook_publisher)
        
        assert result["service"] == "webhooks"
        assert result["status"] == "healthy"
        assert "telegram" in result["channels"]
        assert "secret_validation" in result["features"]
        assert "event_storage" in result["features"]
        assert "ttl_cleanup" in result["features"]
        assert "rabbitmq_publishing" in result["features"]
        assert "rabbitmq" in result
        assert "status" in result["rabbitmq"]
        assert "url" in result["rabbitmq"]
