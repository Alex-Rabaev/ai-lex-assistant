"""Tests for WhatsApp webhook processor."""

import pytest
from unittest.mock import AsyncMock

from app.modules.webhooks.vendors.whatsapp.processor import WhatsAppProcessor


class TestWhatsAppProcessor:
    """Tests for basic WhatsApp processor functionality."""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return WhatsAppProcessor()
    
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
    
    def test_extract_text(self, processor, text_message_update):
        """Test extracting text from WhatsApp message."""
        text = processor.extract_text(text_message_update)
        assert text == "Hello from WhatsApp"
    
    def test_get_user_id(self, processor, text_message_update):
        """Test getting user ID."""
        user_id = processor.get_user_id(text_message_update)
        assert user_id == "whatsapp_15559876543"
    
    def test_get_user_info(self, processor, text_message_update):
        """Test getting user info."""
        user_info = processor.get_user_info(text_message_update)
        
        assert user_info is not None
        assert user_info["wa_id"] == "15559876543"
        assert user_info["name"] == "John Doe"
    
    def test_get_message_type(self, processor, text_message_update):
        """Test getting message type."""
        msg_type = processor.get_message_type(text_message_update)
        assert msg_type == "text"
    
    def test_get_message_id(self, processor, text_message_update):
        """Test getting message ID."""
        msg_id = processor.get_message_id(text_message_update)
        assert msg_id == "wamid.test123"


class TestWhatsAppAudioDetection:
    """Tests for audio detection in WhatsApp processor."""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return WhatsAppProcessor()
    
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
                        "messages": [{
                            "id": "wamid.text789",
                            "from": "15559876543",
                            "timestamp": "1700000000",
                            "type": "text",
                            "text": {"body": "Hello"}
                        }]
                    }
                }]
            }]
        }
    
    def test_get_audio_info_voice(self, processor, voice_message_update):
        """Test extracting voice message info."""
        audio_info = processor.get_audio_info(voice_message_update)
        
        assert audio_info is not None
        assert audio_info["id"] == "media_id_voice_123"
        assert "audio/ogg" in audio_info["mime_type"]
        assert audio_info["voice"] is True
    
    def test_get_audio_info_audio_file(self, processor, audio_file_update):
        """Test extracting audio file info."""
        audio_info = processor.get_audio_info(audio_file_update)
        
        assert audio_info is not None
        assert audio_info["id"] == "media_id_audio_456"
        assert audio_info["mime_type"] == "audio/mpeg"
        assert audio_info["voice"] is False
    
    def test_get_audio_info_text(self, processor, text_message_update):
        """Test get_audio_info returns None for text."""
        audio_info = processor.get_audio_info(text_message_update)
        assert audio_info is None
    
    def test_is_audio_message_voice(self, processor, voice_message_update):
        """Test is_audio_message for voice."""
        assert processor.is_audio_message(voice_message_update) is True
    
    def test_is_audio_message_audio_file(self, processor, audio_file_update):
        """Test is_audio_message for audio file."""
        assert processor.is_audio_message(audio_file_update) is True
    
    def test_is_audio_message_text(self, processor, text_message_update):
        """Test is_audio_message for text."""
        assert processor.is_audio_message(text_message_update) is False
    
    def test_is_voice_message_voice(self, processor, voice_message_update):
        """Test is_voice_message for voice."""
        assert processor.is_voice_message(voice_message_update) is True
    
    def test_is_voice_message_audio_file(self, processor, audio_file_update):
        """Test is_voice_message for audio file (should be False)."""
        assert processor.is_voice_message(audio_file_update) is False
    
    def test_is_voice_message_text(self, processor, text_message_update):
        """Test is_voice_message for text."""
        assert processor.is_voice_message(text_message_update) is False
    
    def test_get_audio_or_voice_info_voice(self, processor, voice_message_update):
        """Test get_audio_or_voice_info for voice message."""
        info, msg_type = processor.get_audio_or_voice_info(voice_message_update)
        
        assert info is not None
        assert msg_type == "voice"
        assert info["id"] == "media_id_voice_123"
    
    def test_get_audio_or_voice_info_audio_file(self, processor, audio_file_update):
        """Test get_audio_or_voice_info for audio file."""
        info, msg_type = processor.get_audio_or_voice_info(audio_file_update)
        
        assert info is not None
        assert msg_type == "audio"
        assert info["id"] == "media_id_audio_456"
    
    def test_get_audio_or_voice_info_text(self, processor, text_message_update):
        """Test get_audio_or_voice_info for text message."""
        info, msg_type = processor.get_audio_or_voice_info(text_message_update)
        
        assert info is None
        assert msg_type == "none"


class TestWhatsAppProcessorAudioAware:
    """Tests for AudioAwareProcessor integration."""
    
    def test_processor_without_credentials(self):
        """Test processor works without credentials (audio disabled)."""
        processor = WhatsAppProcessor()
        
        assert processor._phone_number_id is None
        assert processor._access_token is None
        assert processor._whatsapp_client is None
    
    def test_processor_with_credentials(self):
        """Test processor initializes with credentials."""
        processor = WhatsAppProcessor(
            phone_number_id="123456789",
            access_token="test_token"
        )
        
        assert processor._phone_number_id == "123456789"
        assert processor._access_token == "test_token"
        assert processor._whatsapp_client is not None
    
    @pytest.mark.asyncio
    async def test_download_audio_file_no_client(self):
        """Test download_audio_file raises error without client."""
        from app.common.audio.exceptions import AudioDownloadError
        
        processor = WhatsAppProcessor()  # No credentials
        
        with pytest.raises(AudioDownloadError) as exc_info:
            await processor.download_audio_file("test_media_id")
        
        assert "not configured" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_download_audio_file_with_client(self):
        """Test download_audio_file delegates to WhatsAppClient."""
        processor = WhatsAppProcessor(
            phone_number_id="123456789",
            access_token="test_token"
        )
        
        # Mock the client's download_file method
        processor._whatsapp_client.download_file = AsyncMock(
            return_value="/tmp/test_audio.ogg"
        )
        
        result = await processor.download_audio_file("test_media_id")
        
        assert result == "/tmp/test_audio.ogg"
        processor._whatsapp_client.download_file.assert_called_once_with("test_media_id")
    
    def test_processor_inherits_audio_aware(self):
        """Test WhatsAppProcessor inherits from AudioAwareProcessor."""
        from app.modules.webhooks.base.audio_processor import AudioAwareProcessor
        
        processor = WhatsAppProcessor()
        
        assert isinstance(processor, AudioAwareProcessor)
        assert hasattr(processor, 'handle_audio_message')
        assert hasattr(processor, '_transcription_service')
