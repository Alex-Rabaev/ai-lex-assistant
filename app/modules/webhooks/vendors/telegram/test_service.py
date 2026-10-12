"""Tests for Telegram webhook service."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from bson import ObjectId

from app.modules.webhooks.vendors.telegram.service import TelegramWebhookService
from app.modules.webhooks.models import WebhookEvent, WebhookResponse
from app.modules.connections.models import Connection, ConnectionStatus, ConnectionChannel


class TestTelegramWebhookService:
    """Tests for Telegram webhook service."""
    
    @pytest.fixture
    def mock_webhook_repo(self):
        """Create mock webhook repository."""
        repo = Mock()
        repo.save_event = AsyncMock()
        repo.get_by_update_id = AsyncMock(return_value=None)
        repo.mark_as_processed = AsyncMock()
        return repo
    
    @pytest.fixture
    def test_assistant_id(self):
        """Common assistant ID for tests."""
        return str(ObjectId())
    
    @pytest.fixture
    def mock_connection(self, test_assistant_id):
        """Create mock connection."""
        return Connection(
            id=ObjectId(),
            assistant_id=ObjectId(test_assistant_id),
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.CONNECTED,
            credentials={"token": "test_token"},
            config={},
            settings={"bot_token": "test_bot_token"}
        )
    
    @pytest.fixture
    def mock_assistant(self, test_assistant_id):
        """Create mock assistant."""
        assistant = Mock()
        assistant.id = ObjectId(test_assistant_id)
        assistant.name = "Test Assistant"
        return assistant
    
    @pytest.fixture
    def mock_webhook_publisher(self):
        """Create mock webhook publisher."""
        publisher = Mock()
        publisher.publish_message = AsyncMock()
        return publisher
    
    @pytest.fixture
    def service(self, mock_webhook_repo, mock_webhook_publisher, mock_connection, mock_assistant):
        """Create service with mocks."""
        svc = TelegramWebhookService(
            webhook_repository=mock_webhook_repo,
            webhook_publisher=mock_webhook_publisher
        )
        # Mock internal services
        svc._connection_service = Mock()
        svc._connection_service.get_connection_by_assistant_and_channel_internal = AsyncMock(return_value=mock_connection)
        svc._connection_service.update_connection_status_internal = AsyncMock()
        svc._connection_service.get_connection_internal = AsyncMock(return_value=mock_connection)
        
        svc._assistant_service = Mock()
        svc._assistant_service.get_assistant_internal = AsyncMock(return_value=mock_assistant)
        
        return svc
    
    @pytest.mark.asyncio
    async def test_process_update_text_message(self, service, mock_webhook_repo, test_assistant_id):
        """Test processing regular text message."""
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "text": "Hello bot",
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "username": "testuser",
                    "first_name": "Test"
                }
            }
        }
        
        # Mock saved event
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=str(ObjectId()),
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={"text": "Hello bot"},
            raw_data=update,
            update_id=12345,
            message_id="100"
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is True
        assert "saved" in response.message.lower()
        
        # Check webhook was saved
        mock_webhook_repo.save_event.assert_called_once()
        saved_call = mock_webhook_repo.save_event.call_args[0][0]
        assert saved_call.user_id == "telegram_123456"
        # content can be either dict or WebhookContent object
        if hasattr(saved_call.content, "text"):
            assert saved_call.content.text == "Hello bot"
        else:
            assert saved_call.content["text"] == "Hello bot"
    
    @pytest.mark.asyncio
    async def test_process_update_start_command(self, service, mock_webhook_repo, test_assistant_id):
        """Test processing /start command."""
        update = {
            "update_id": 12346,
            "message": {
                "message_id": 101,
                "text": "/start ref123",
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "is_bot": False, "first_name": "Test", "username": "testuser"}
            }
        }
        
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=str(ObjectId()),
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={"text": "/start ref123"},
            raw_data=update
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is True
        assert "saved" in response.message.lower()
        
        # Check webhook was saved
        mock_webhook_repo.save_event.assert_called_once()
        saved_call = mock_webhook_repo.save_event.call_args[0][0]
        assert saved_call.user_id == "telegram_123456"
        assert saved_call.type == "message"
    
    @pytest.mark.asyncio
    async def test_process_update_callback_query(self, service, mock_webhook_repo, test_assistant_id):
        """Test processing callback query."""
        update = {
            "update_id": 12347,
            "callback_query": {
                "id": "cb_123",
                "data": "action:approve",
                "from": {"id": 123456, "is_bot": False, "first_name": "Test", "username": "testuser"},
                "chat_instance": "chat_instance_123",
                "message": {
                    "message_id": 102,
                    "date": 1234567890,
                    "chat": {"id": 123456, "type": "private"}
                }
            }
        }
        
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=str(ObjectId()),
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="callback_query",
            content={
                "text": "action:approve",
                "callback_data": "action:approve",
                "callback_id": "cb_123"
            },
            raw_data=update
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is True
        assert "saved" in response.message.lower()
        
        # Check webhook was saved with correct callback data
        mock_webhook_repo.save_event.assert_called_once()
        saved_call = mock_webhook_repo.save_event.call_args[0][0]
        assert saved_call.user_id == "telegram_123456"
        assert saved_call.type == "callback_query"
    
    @pytest.mark.asyncio
    async def test_process_update_duplicate(self, service, mock_webhook_repo, test_assistant_id):
        """Test processing duplicate update."""
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "text": "Hello",
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "is_bot": False, "first_name": "Test"}
            }
        }
        
        # Mock existing event found
        existing_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=str(ObjectId()),
            update_id=12345,
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={},
            raw_data={}
        )
        mock_webhook_repo.get_by_update_id.return_value = existing_event
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is True
        assert "duplicate" in response.message.lower()
        
        # Should not save duplicate
        mock_webhook_repo.save_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_update_no_user_id(self, service, test_assistant_id):
        """Test processing update without user_id."""
        update = {
            "update_id": 12345,
            "unknown_field": {}
        }
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is False
        assert "no user_id" in response.message.lower()
    
    @pytest.mark.asyncio
    async def test_process_update_assistant_not_found(self, service, test_assistant_id):
        """Test processing with non-existent assistant."""
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "text": "Hello",
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "is_bot": False, "first_name": "Test"}
            }
        }
        
        # Mock assistant not found
        from app.modules.assistants.service import AssistantNotFoundError
        service._assistant_service.get_assistant_internal = AsyncMock(
            side_effect=AssistantNotFoundError("Not found")
        )
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is False
        assert "Assistant not found" in response.message
    
    @pytest.mark.asyncio
    async def test_process_update_no_connection(self, service, test_assistant_id):
        """Test processing with no active connection."""
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "text": "Hello",
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "is_bot": False, "first_name": "Test"}
            }
        }
        
        # Mock no connection found
        service._connection_service.get_connection_internal = AsyncMock(return_value=None)
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is False
        assert "Connection not found" in response.message
    
    @pytest.mark.asyncio
    async def test_process_update_error_handling(self, service, mock_webhook_repo, test_assistant_id):
        """Test error handling during processing."""
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "text": "Hello",
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "is_bot": False, "first_name": "Test"}
            }
        }
        
        # Mock save error
        mock_webhook_repo.save_event.side_effect = Exception("Database error")
        
        connection_id = str(ObjectId())
        response = await service.process_update(update, test_assistant_id, connection_id)
        
        assert response.success is False
        assert "Database error" in response.message


class TestTelegramWebhookServiceVoice:
    """Tests for voice message processing in Telegram webhook service."""
    
    @pytest.fixture
    def mock_webhook_repo(self):
        """Create mock webhook repository."""
        repo = Mock()
        repo.save_event = AsyncMock()
        repo.get_by_update_id = AsyncMock(return_value=None)
        return repo
    
    @pytest.fixture
    def test_assistant_id(self):
        """Common assistant ID for tests."""
        return str(ObjectId())
    
    @pytest.fixture
    def mock_connection(self, test_assistant_id):
        """Create mock connection."""
        return Connection(
            id=ObjectId(),
            assistant_id=ObjectId(test_assistant_id),
            channel=ConnectionChannel.TELEGRAM,
            status=ConnectionStatus.CONNECTED,
            credentials={"token": "test_token"},
            config={},
            settings={"bot_token": "test_bot_token"}
        )
    
    @pytest.fixture
    def mock_assistant(self, test_assistant_id):
        """Create mock assistant."""
        assistant = Mock()
        assistant.id = ObjectId(test_assistant_id)
        assistant.name = "Test Assistant"
        return assistant
    
    @pytest.fixture
    def mock_webhook_publisher(self):
        """Create mock webhook publisher."""
        publisher = Mock()
        publisher.publish_message = AsyncMock()
        return publisher
    
    @pytest.fixture
    def service_with_token(self, mock_webhook_repo, mock_webhook_publisher, mock_connection, mock_assistant):
        """Create service with bot_token for voice processing."""
        svc = TelegramWebhookService(
            webhook_repository=mock_webhook_repo,
            webhook_publisher=mock_webhook_publisher,
            bot_token="test_bot_token_123"
        )
        # Mock internal services
        svc._connection_service = Mock()
        svc._connection_service.get_connection_internal = AsyncMock(return_value=mock_connection)
        svc._connection_service.update_connection_status_internal = AsyncMock()
        
        svc._assistant_service = Mock()
        svc._assistant_service.get_assistant_internal = AsyncMock(return_value=mock_assistant)
        
        return svc
    
    @pytest.fixture
    def voice_message_update(self):
        """Sample Telegram update with voice message."""
        return {
            "update_id": 12350,
            "message": {
                "message_id": 105,
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "voice": {
                    "file_id": "AwACAgIAAxkBAAIBZ2X_test_voice_file",
                    "file_unique_id": "unique_voice_123",
                    "duration": 5,
                    "mime_type": "audio/ogg",
                    "file_size": 12345
                }
            }
        }
    
    @pytest.fixture
    def audio_message_update(self):
        """Sample Telegram update with audio file."""
        return {
            "update_id": 12351,
            "message": {
                "message_id": 106,
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Test"
                },
                "audio": {
                    "file_id": "CQACAgIAAxkBAAIBaGX_test_audio_file",
                    "file_unique_id": "unique_audio_123",
                    "duration": 180,
                    "mime_type": "audio/mpeg",
                    "file_size": 3456789
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_process_voice_message_success(
        self,
        service_with_token,
        mock_webhook_repo,
        mock_webhook_publisher,
        test_assistant_id,
        voice_message_update
    ):
        """Test successful voice message processing."""
        # Mock saved event
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=test_assistant_id,
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={"text": "Transcribed voice text"},
            raw_data=voice_message_update,
            update_id=12350,
            message_id="105"
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        # Mock the processor's handle_audio_message
        service_with_token.processor.handle_audio_message = AsyncMock(
            return_value=(
                "Hello, this is a transcribed voice message",
                {"message_type": "voice", "audio_duration_seconds": 5, "audio_language": "en"}
            )
        )
        
        connection_id = str(ObjectId())
        response = await service_with_token.process_update(
            voice_message_update, test_assistant_id, connection_id
        )
        
        assert response.success is True
        
        # Verify handle_audio_message was called
        service_with_token.processor.handle_audio_message.assert_called_once_with(
            file_id="AwACAgIAAxkBAAIBZ2X_test_voice_file",
            duration=5,
            mime_type="audio/ogg",
            message_type="voice"
        )
        
        # Verify published message contains audio metadata
        mock_webhook_publisher.publish_message.assert_called_once()
        call_kwargs = mock_webhook_publisher.publish_message.call_args[1]
        assert call_kwargs["message_data"]["text"] == "Hello, this is a transcribed voice message"
        assert call_kwargs["message_data"]["message_type"] == "voice"
        assert call_kwargs["message_data"]["audio_duration_seconds"] == 5
        assert call_kwargs["message_data"]["audio_language"] == "en"
    
    @pytest.mark.asyncio
    async def test_process_audio_file_message(
        self,
        service_with_token,
        mock_webhook_repo,
        mock_webhook_publisher,
        test_assistant_id,
        audio_message_update
    ):
        """Test audio file message processing."""
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=test_assistant_id,
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={},
            raw_data=audio_message_update,
            update_id=12351,
            message_id="106"
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        # Mock the processor's handle_audio_message
        service_with_token.processor.handle_audio_message = AsyncMock(
            return_value=(
                "Transcribed audio content",
                {"message_type": "audio", "audio_duration_seconds": 180}
            )
        )
        
        connection_id = str(ObjectId())
        response = await service_with_token.process_update(
            audio_message_update, test_assistant_id, connection_id
        )
        
        assert response.success is True
        
        # Verify handle_audio_message was called with audio type
        service_with_token.processor.handle_audio_message.assert_called_once()
        call_kwargs = service_with_token.processor.handle_audio_message.call_args[1]
        assert call_kwargs["message_type"] == "audio"
    
    @pytest.mark.asyncio
    async def test_process_voice_too_long(
        self,
        service_with_token,
        mock_webhook_repo,
        mock_webhook_publisher,
        test_assistant_id
    ):
        """Test voice message that exceeds duration limit."""
        long_voice_update = {
            "update_id": 12352,
            "message": {
                "message_id": 107,
                "date": 1234567890,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "is_bot": False, "first_name": "Test"},
                "voice": {
                    "file_id": "test_voice_file",
                    "file_unique_id": "unique_123",
                    "duration": 400,  # > 300 seconds (5 min)
                    "mime_type": "audio/ogg"
                }
            }
        }
        
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=test_assistant_id,
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={},
            raw_data=long_voice_update,
            update_id=12352
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        # Mock handle_audio_message returning error system message
        service_with_token.processor.handle_audio_message = AsyncMock(
            return_value=(
                "[SYSTEM: Audio too long (>5min)]",
                {"message_type": "voice", "audio_duration_seconds": 400}
            )
        )
        
        connection_id = str(ObjectId())
        response = await service_with_token.process_update(
            long_voice_update, test_assistant_id, connection_id
        )
        
        assert response.success is True
        
        # Verify system error message is published
        call_kwargs = mock_webhook_publisher.publish_message.call_args[1]
        assert "[SYSTEM:" in call_kwargs["message_data"]["text"]
    
    @pytest.mark.asyncio
    async def test_process_voice_transcription_failed(
        self,
        service_with_token,
        mock_webhook_repo,
        mock_webhook_publisher,
        test_assistant_id,
        voice_message_update
    ):
        """Test voice message when transcription fails."""
        saved_event = WebhookEvent(
            id=ObjectId(),
            assistant_id=test_assistant_id,
            connection_id=str(ObjectId()),
            user_id="telegram_123456",
            channel="telegram",
            type="message",
            content={},
            raw_data=voice_message_update,
            update_id=12350
        )
        mock_webhook_repo.save_event.return_value = saved_event
        
        # Mock handle_audio_message returning error
        service_with_token.processor.handle_audio_message = AsyncMock(
            return_value=(
                "[SYSTEM: Audio transcription failed]",
                {"message_type": "voice", "audio_duration_seconds": 5}
            )
        )
        
        connection_id = str(ObjectId())
        response = await service_with_token.process_update(
            voice_message_update, test_assistant_id, connection_id
        )
        
        assert response.success is True
        
        # Verify error message is published (agent will handle it)
        call_kwargs = mock_webhook_publisher.publish_message.call_args[1]
        assert "transcription failed" in call_kwargs["message_data"]["text"].lower()
