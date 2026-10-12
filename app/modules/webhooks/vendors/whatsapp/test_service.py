"""Tests for WhatsApp webhook service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from bson import ObjectId

from app.modules.webhooks.vendors.whatsapp.service import WhatsAppWebhookService
from app.modules.webhooks.models import WebhookResponse


class TestWhatsAppWebhookService:
    """Tests for WhatsApp webhook service basic functionality."""
    
    @pytest.fixture
    def mock_webhook_repo(self):
        """Create mock webhook repository."""
        repo = Mock()
        repo.save_event = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_webhook_publisher(self):
        """Create mock webhook publisher."""
        publisher = Mock()
        publisher.publish_message = AsyncMock()
        return publisher
    
    @pytest.fixture
    def test_assistant_id(self):
        """Create valid assistant ID."""
        return str(ObjectId())
    
    @pytest.fixture
    def test_connection_id(self):
        """Create valid connection ID."""
        return str(ObjectId())
    
    @pytest.fixture
    def service(self, mock_webhook_repo, mock_webhook_publisher):
        """Create service without credentials."""
        return WhatsAppWebhookService(
            webhook_repository=mock_webhook_repo,
            webhook_publisher=mock_webhook_publisher
        )
    
    @pytest.fixture
    def text_message_update(self):
        """Sample WhatsApp webhook with text message."""
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [{
                            "wa_id": "15559876543",
                            "profile": {"name": "John Doe"}
                        }],
                        "messages": [{
                            "id": "wamid.test123",
                            "from": "15559876543",
                            "timestamp": "1700000000",
                            "type": "text",
                            "text": {"body": "Hello from WhatsApp"}
                        }]
                    }
                }]
            }]
        }
    
    @pytest.fixture
    def status_update(self):
        """Sample WhatsApp webhook with status update."""
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "statuses": [{
                            "id": "wamid.status123",
                            "status": "delivered",
                            "timestamp": "1700000000"
                        }]
                    }
                }]
            }]
        }
    
    @pytest.mark.asyncio
    async def test_process_text_message_success(
        self, service, mock_webhook_repo, mock_webhook_publisher, text_message_update,
        test_assistant_id, test_connection_id
    ):
        """Test processing text message successfully."""
        result = await service.process_update(
            update=text_message_update,
            assistant_id=test_assistant_id,
            connection_id=test_connection_id
        )
        
        assert result.success is True
        assert "published" in result.message.lower()
        
        # Verify event saved
        mock_webhook_repo.save_event.assert_called_once()
        
        # Verify message published
        mock_webhook_publisher.publish_message.assert_called_once()
        call_kwargs = mock_webhook_publisher.publish_message.call_args.kwargs
        assert call_kwargs["channel"] == "whatsapp"
        assert call_kwargs["user_id"] == "whatsapp_15559876543"
        assert call_kwargs["message_data"]["text"] == "Hello from WhatsApp"
    
    @pytest.mark.asyncio
    async def test_skip_status_update(self, service, status_update, test_assistant_id, test_connection_id):
        """Test that status updates are skipped."""
        result = await service.process_update(
            update=status_update,
            assistant_id=test_assistant_id,
            connection_id=test_connection_id
        )
        
        assert result.success is True
        assert "skipped" in result.message.lower()


class TestWhatsAppWebhookServiceVoice:
    """Tests for voice message processing in WhatsApp webhook service."""
    
    @pytest.fixture
    def mock_webhook_repo(self):
        """Create mock webhook repository."""
        repo = Mock()
        repo.save_event = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_webhook_publisher(self):
        """Create mock webhook publisher."""
        publisher = Mock()
        publisher.publish_message = AsyncMock()
        return publisher
    
    @pytest.fixture
    def test_assistant_id(self):
        """Create valid assistant ID."""
        return str(ObjectId())
    
    @pytest.fixture
    def test_connection_id(self):
        """Create valid connection ID."""
        return str(ObjectId())
    
    @pytest.fixture
    def service_with_credentials(self, mock_webhook_repo, mock_webhook_publisher):
        """Create service with WhatsApp credentials."""
        return WhatsAppWebhookService(
            webhook_repository=mock_webhook_repo,
            webhook_publisher=mock_webhook_publisher,
            phone_number_id="123456789",
            access_token="test_access_token"
        )
    
    @pytest.fixture
    def voice_message_update(self):
        """Sample WhatsApp webhook with voice message."""
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [{
                            "wa_id": "15559876543",
                            "profile": {"name": "John Doe"}
                        }],
                        "messages": [{
                            "id": "wamid.voice123",
                            "from": "15559876543",
                            "timestamp": "1700000000",
                            "type": "audio",
                            "audio": {
                                "id": "media_id_voice_123",
                                "mime_type": "audio/ogg; codecs=opus",
                                "sha256": "abc123sha256",
                                "voice": True
                            }
                        }]
                    }
                }]
            }]
        }
    
    @pytest.fixture
    def audio_file_update(self):
        """Sample WhatsApp webhook with audio file (not voice)."""
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [{
                            "wa_id": "15559876543",
                            "profile": {"name": "John Doe"}
                        }],
                        "messages": [{
                            "id": "wamid.audio456",
                            "from": "15559876543",
                            "timestamp": "1700000000",
                            "type": "audio",
                            "audio": {
                                "id": "media_id_audio_456",
                                "mime_type": "audio/mpeg",
                                "sha256": "def456sha256",
                                "voice": False
                            }
                        }]
                    }
                }]
            }]
        }
    
    @pytest.mark.asyncio
    async def test_process_voice_message_success(
        self, service_with_credentials, mock_webhook_repo, mock_webhook_publisher,
        voice_message_update, test_assistant_id, test_connection_id
    ):
        """Test successful voice message processing."""
        # Mock handle_audio_message
        with patch.object(
            service_with_credentials._processor,
            'handle_audio_message',
            new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = (
                "Transcribed voice text",
                {
                    "message_type": "voice",
                    "audio_duration_seconds": 5,
                    "audio_language": "english"
                }
            )
            
            result = await service_with_credentials.process_update(
                update=voice_message_update,
                assistant_id=test_assistant_id,
                connection_id=test_connection_id
            )
        
        assert result.success is True
        
        # Verify message published with audio metadata
        mock_webhook_publisher.publish_message.assert_called_once()
        call_kwargs = mock_webhook_publisher.publish_message.call_args.kwargs
        message_data = call_kwargs["message_data"]
        
        assert message_data["text"] == "Transcribed voice text"
        assert message_data["message_type"] == "voice"
        assert message_data["audio_duration_seconds"] == 5
        assert message_data["audio_language"] == "english"
    
    @pytest.mark.asyncio
    async def test_process_audio_file_message(
        self, service_with_credentials, mock_webhook_repo, mock_webhook_publisher,
        audio_file_update, test_assistant_id, test_connection_id
    ):
        """Test audio file (not voice) message processing."""
        with patch.object(
            service_with_credentials._processor,
            'handle_audio_message',
            new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = (
                "Transcribed audio text",
                {
                    "message_type": "audio",
                    "audio_duration_seconds": 120,
                    "audio_language": "russian"
                }
            )
            
            result = await service_with_credentials.process_update(
                update=audio_file_update,
                assistant_id=test_assistant_id,
                connection_id=test_connection_id
            )
        
        assert result.success is True
        
        # Verify message has correct audio type
        call_kwargs = mock_webhook_publisher.publish_message.call_args.kwargs
        message_data = call_kwargs["message_data"]
        
        assert message_data["message_type"] == "audio"
    
    @pytest.mark.asyncio
    async def test_process_voice_transcription_failed(
        self, service_with_credentials, mock_webhook_repo, mock_webhook_publisher,
        voice_message_update, test_assistant_id, test_connection_id
    ):
        """Test handling of transcription failure (returns error message)."""
        from app.common.audio.constants import TRANSCRIPTION_FAILED
        
        with patch.object(
            service_with_credentials._processor,
            'handle_audio_message',
            new_callable=AsyncMock
        ) as mock_handle:
            # handle_audio_message returns error message instead of raising
            mock_handle.return_value = (
                TRANSCRIPTION_FAILED,
                {
                    "message_type": "voice",
                    "audio_duration_seconds": 0,
                    "audio_language": None
                }
            )
            
            result = await service_with_credentials.process_update(
                update=voice_message_update,
                assistant_id=test_assistant_id,
                connection_id=test_connection_id
            )
        
        assert result.success is True
        
        # Even with error, message should be published (with error text)
        mock_webhook_publisher.publish_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_service_initializes_processor_with_credentials(self, mock_webhook_repo, mock_webhook_publisher):
        """Test that service passes credentials to processor."""
        service = WhatsAppWebhookService(
            webhook_repository=mock_webhook_repo,
            webhook_publisher=mock_webhook_publisher,
            phone_number_id="test_phone_id",
            access_token="test_token"
        )
        
        # Verify processor has credentials
        assert service._processor._phone_number_id == "test_phone_id"
        assert service._processor._access_token == "test_token"
        assert service._processor._whatsapp_client is not None
    
    @pytest.mark.asyncio
    async def test_service_without_credentials_disables_audio(self, mock_webhook_repo, mock_webhook_publisher):
        """Test that service without credentials has no WhatsApp client."""
        service = WhatsAppWebhookService(
            webhook_repository=mock_webhook_repo,
            webhook_publisher=mock_webhook_publisher
        )
        
        # Processor should not have a client
        assert service._processor._whatsapp_client is None


class TestWhatsAppWebhookServiceMessageTypes:
    """Tests for handling different message types."""
    
    @pytest.fixture
    def service(self):
        """Create service."""
        mock_repo = Mock()
        mock_repo.save_event = AsyncMock()
        mock_publisher = Mock()
        mock_publisher.publish_message = AsyncMock()
        
        return WhatsAppWebhookService(
            webhook_repository=mock_repo,
            webhook_publisher=mock_publisher
        )
    
    @pytest.fixture
    def test_assistant_id(self):
        """Create valid assistant ID."""
        return str(ObjectId())
    
    @pytest.fixture
    def test_connection_id(self):
        """Create valid connection ID."""
        return str(ObjectId())
    
    @pytest.fixture
    def image_message_update(self):
        """Sample WhatsApp webhook with image message."""
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "messages": [{
                            "id": "wamid.image123",
                            "from": "15559876543",
                            "timestamp": "1700000000",
                            "type": "image",
                            "image": {
                                "id": "media_id_image_123",
                                "mime_type": "image/jpeg"
                            }
                        }]
                    }
                }]
            }]
        }
    
    @pytest.mark.asyncio
    async def test_skip_image_message(self, service, image_message_update, test_assistant_id, test_connection_id):
        """Test that image messages are skipped."""
        result = await service.process_update(
            update=image_message_update,
            assistant_id=test_assistant_id,
            connection_id=test_connection_id
        )
        
        assert result.success is True
        assert "skipped" in result.message.lower() or "image" in result.message.lower()
