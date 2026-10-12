"""Tests for Telegram webhook processor."""

import pytest
from app.modules.webhooks.vendors.telegram.processor import TelegramProcessor


class TestTelegramProcessor:
    """Tests for TelegramProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return TelegramProcessor()
    
    @pytest.fixture
    def text_message_update(self):
        """Sample Telegram update with text message."""
        return {
            "update_id": 123456789,
            "message": {
                "message_id": 1001,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe",
                    "language_code": "en"
                },
                "chat": {
                    "id": 987654321,
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe",
                    "type": "private"
                },
                "date": 1700000000,
                "text": "Hello, bot!"
            }
        }
    
    @pytest.fixture
    def start_command_update(self):
        """Sample Telegram update with /start command."""
        return {
            "update_id": 123456790,
            "message": {
                "message_id": 1002,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John",
                    "username": "johndoe"
                },
                "chat": {
                    "id": 987654321,
                    "first_name": "John",
                    "type": "private"
                },
                "date": 1700000001,
                "text": "/start ref123",
                "entities": [
                    {
                        "offset": 0,
                        "length": 6,
                        "type": "bot_command"
                    }
                ]
            }
        }
    
    @pytest.fixture
    def callback_query_update(self):
        """Sample Telegram update with callback query."""
        return {
            "update_id": 123456791,
            "callback_query": {
                "id": "callback123",
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John",
                    "username": "johndoe"
                },
                "message": {
                    "message_id": 1003,
                    "from": {
                        "id": 123456789,
                        "is_bot": True,
                        "first_name": "Test Bot",
                        "username": "testbot"
                    },
                    "chat": {
                        "id": 987654321,
                        "first_name": "John",
                        "type": "private"
                    },
                    "date": 1700000002,
                    "text": "Choose an option:"
                },
                "chat_instance": "chat_instance_123",
                "data": "button_clicked"
            }
        }
    
    @pytest.fixture
    def edited_message_update(self):
        """Sample Telegram update with edited message."""
        return {
            "update_id": 123456792,
            "edited_message": {
                "message_id": 1004,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John"
                },
                "chat": {
                    "id": 987654321,
                    "type": "private"
                },
                "date": 1700000003,
                "edit_date": 1700000004,
                "text": "Edited message text"
            }
        }
    
    @pytest.fixture
    def group_message_update(self):
        """Sample Telegram update from group chat."""
        return {
            "update_id": 123456793,
            "message": {
                "message_id": 1005,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John",
                    "username": "johndoe"
                },
                "chat": {
                    "id": -1001234567890,
                    "title": "Test Group",
                    "type": "supergroup"
                },
                "date": 1700000005,
                "text": "Message in group"
            }
        }
    
    @pytest.fixture
    def photo_message_update(self):
        """Sample Telegram update with photo and caption."""
        return {
            "update_id": 123456794,
            "message": {
                "message_id": 1006,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John"
                },
                "chat": {
                    "id": 987654321,
                    "type": "private"
                },
                "date": 1700000006,
                "photo": [
                    {
                        "file_id": "photo_file_id",
                        "file_unique_id": "unique_id",
                        "width": 320,
                        "height": 240,
                        "file_size": 12345
                    }
                ],
                "caption": "Check out this photo!"
            }
        }
    
    def test_extract_text_from_message(self, processor, text_message_update):
        """Test extracting text from regular message."""
        text = processor.extract_text(text_message_update)
        assert text == "Hello, bot!"
    
    def test_extract_text_from_command(self, processor, start_command_update):
        """Test extracting text from command message."""
        text = processor.extract_text(start_command_update)
        assert text == "/start ref123"
    
    def test_extract_text_from_callback(self, processor, callback_query_update):
        """Test extracting data from callback query."""
        text = processor.extract_text(callback_query_update)
        assert text == "button_clicked"
    
    def test_extract_text_from_photo_caption(self, processor, photo_message_update):
        """Test extracting caption from photo message."""
        text = processor.extract_text(photo_message_update)
        assert text == "Check out this photo!"
    
    def test_get_user_id(self, processor, text_message_update):
        """Test getting formatted user ID."""
        user_id = processor.get_user_id(text_message_update)
        assert user_id == "telegram_987654321"
    
    def test_get_user_id_from_group(self, processor, group_message_update):
        """Test getting user ID from group message."""
        user_id = processor.get_user_id(group_message_update)
        assert user_id == "telegram_-1001234567890"
    
    def test_get_user_info(self, processor, text_message_update):
        """Test extracting user information."""
        user_info = processor.get_user_info(text_message_update)
        assert user_info is not None
        assert user_info["id"] == 987654321
        assert user_info["first_name"] == "John"
        assert user_info["last_name"] == "Doe"
        assert user_info["username"] == "johndoe"
        assert user_info["language_code"] == "en"
        assert user_info["is_bot"] is False
    
    def test_get_chat_info(self, processor, text_message_update):
        """Test extracting chat information."""
        chat_info = processor.get_chat_info(text_message_update)
        assert chat_info is not None
        assert chat_info["id"] == 987654321
        assert chat_info["type"] == "private"
        assert chat_info["first_name"] == "John"
    
    def test_get_chat_info_group(self, processor, group_message_update):
        """Test extracting group chat information."""
        chat_info = processor.get_chat_info(group_message_update)
        assert chat_info is not None
        assert chat_info["id"] == -1001234567890
        assert chat_info["type"] == "supergroup"
        assert chat_info["title"] == "Test Group"
    
    def test_get_message_type_regular(self, processor, text_message_update):
        """Test determining regular message type."""
        msg_type = processor.get_message_type(text_message_update)
        assert msg_type == "message"
    
    def test_get_message_type_command(self, processor, start_command_update):
        """Test determining command message type - commands are treated as regular messages."""
        msg_type = processor.get_message_type(start_command_update)
        assert msg_type == "message"  # Commands are treated as regular messages
    
    def test_get_message_type_callback(self, processor, callback_query_update):
        """Test determining callback query type."""
        msg_type = processor.get_message_type(callback_query_update)
        assert msg_type == "callback_query"
    
    def test_get_message_type_edited(self, processor, edited_message_update):
        """Test determining edited message type."""
        msg_type = processor.get_message_type(edited_message_update)
        assert msg_type == "edited_message"
    
    def test_get_message_id(self, processor, text_message_update):
        """Test extracting message ID."""
        msg_id = processor.get_message_id(text_message_update)
        assert msg_id == "1001"
    
    def test_get_message_id_callback(self, processor, callback_query_update):
        """Test extracting callback query ID."""
        msg_id = processor.get_message_id(callback_query_update)
        assert msg_id == "callback123"
    
    def test_get_update_id(self, processor, text_message_update):
        """Test extracting update_id."""
        update_id = processor.get_update_id(text_message_update)
        assert update_id == 123456789
    
    def test_process_full(self, processor, text_message_update):
        """Test full processing of update."""
        result = processor.process(text_message_update)
        
        assert result["text"] == "Hello, bot!"
        assert result["user_id"] == "telegram_987654321"
        assert result["user_info"] is not None
        assert result["chat_info"] is not None
        assert result["message_type"] == "message"
        assert result["message_id"] == "1001"
        assert result["update_id"] == 123456789
        assert result["is_valid"] is True
        assert "parsed_update" in result
    
    def test_process_invalid_update(self, processor):
        """Test processing invalid update."""
        invalid_update = {"invalid": "data"}
        result = processor.process(invalid_update)
        
        assert result["text"] is None
        assert result["user_id"] is None
        assert result["is_valid"] is False
        assert "parse_error" in result
    
    def test_handle_empty_update(self, processor):
        """Test handling empty update."""
        result = processor.process({})
        assert result["is_valid"] is False
        assert result["text"] is None
        assert result["user_id"] is None
    
    def test_handle_minimal_update(self, processor):
        """Test handling minimal valid update."""
        minimal_update = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "chat": {"id": 456, "type": "private"},
                "date": 1700000000
            }
        }
        result = processor.process(minimal_update)
        
        assert result["is_valid"] is True
        assert result["user_id"] == "telegram_456"
        assert result["text"] is None  # No text in minimal update
        assert result["message_type"] == "message"


class TestVoiceAudioDetection:
    """Tests for voice and audio message detection."""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return TelegramProcessor()
    
    @pytest.fixture
    def voice_message_update(self):
        """Sample Telegram update with voice message."""
        return {
            "update_id": 123456795,
            "message": {
                "message_id": 1007,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John"
                },
                "chat": {
                    "id": 987654321,
                    "type": "private"
                },
                "date": 1700000007,
                "voice": {
                    "file_id": "AwACAgIAAxkBAAIBZ2X_voice_file_id",
                    "file_unique_id": "unique_voice_123",
                    "duration": 5,
                    "mime_type": "audio/ogg",
                    "file_size": 12345
                }
            }
        }
    
    @pytest.fixture
    def audio_message_update(self):
        """Sample Telegram update with audio file (music)."""
        return {
            "update_id": 123456796,
            "message": {
                "message_id": 1008,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John"
                },
                "chat": {
                    "id": 987654321,
                    "type": "private"
                },
                "date": 1700000008,
                "audio": {
                    "file_id": "CQACAgIAAxkBAAIBaGX_audio_file_id",
                    "file_unique_id": "unique_audio_123",
                    "duration": 180,
                    "mime_type": "audio/mpeg",
                    "file_size": 3456789,
                    "performer": "Artist Name",
                    "title": "Song Title"
                }
            }
        }
    
    @pytest.fixture
    def video_message_update(self):
        """Sample Telegram update with video."""
        return {
            "update_id": 123456797,
            "message": {
                "message_id": 1009,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John"
                },
                "chat": {
                    "id": 987654321,
                    "type": "private"
                },
                "date": 1700000009,
                "video": {
                    "file_id": "BAACAgIAAxkBAAIBaWX_video_file_id",
                    "file_unique_id": "unique_video_123",
                    "duration": 30,
                    "width": 1920,
                    "height": 1080,
                    "mime_type": "video/mp4",
                    "file_size": 5678901
                }
            }
        }
    
    @pytest.fixture
    def video_note_update(self):
        """Sample Telegram update with video note (round video)."""
        return {
            "update_id": 123456798,
            "message": {
                "message_id": 1010,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "John"
                },
                "chat": {
                    "id": 987654321,
                    "type": "private"
                },
                "date": 1700000010,
                "video_note": {
                    "file_id": "DQACAgIAAxkBAAIBamX_video_note_id",
                    "file_unique_id": "unique_video_note_123",
                    "duration": 10,
                    "length": 240,
                    "file_size": 234567
                }
            }
        }
    
    def test_get_voice_info(self, processor, voice_message_update):
        """Test extracting voice message info."""
        voice_info = processor.get_voice_info(voice_message_update)
        
        assert voice_info is not None
        assert voice_info["file_id"] == "AwACAgIAAxkBAAIBZ2X_voice_file_id"
        assert voice_info["duration"] == 5
        assert voice_info["mime_type"] == "audio/ogg"
        assert voice_info["file_size"] == 12345
    
    def test_get_voice_info_returns_none_for_text(self, processor):
        """Test get_voice_info returns None for text messages."""
        text_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1001,
                "from": {"id": 987654321, "is_bot": False, "first_name": "John"},
                "chat": {"id": 987654321, "type": "private"},
                "date": 1700000000,
                "text": "Hello, bot!"
            }
        }
        voice_info = processor.get_voice_info(text_update)
        assert voice_info is None
    
    def test_get_audio_info(self, processor, audio_message_update):
        """Test extracting audio file info."""
        audio_info = processor.get_audio_info(audio_message_update)
        
        assert audio_info is not None
        assert audio_info["file_id"] == "CQACAgIAAxkBAAIBaGX_audio_file_id"
        assert audio_info["duration"] == 180
        assert audio_info["mime_type"] == "audio/mpeg"
        assert audio_info["performer"] == "Artist Name"
        assert audio_info["title"] == "Song Title"
    
    def test_get_audio_info_returns_none_for_voice(
        self, processor, voice_message_update
    ):
        """Test get_audio_info returns None for voice messages."""
        audio_info = processor.get_audio_info(voice_message_update)
        assert audio_info is None
    
    def test_is_voice_message(self, processor, voice_message_update):
        """Test is_voice_message returns True for voice."""
        assert processor.is_voice_message(voice_message_update) is True
    
    def test_is_voice_message_false_for_audio(
        self, processor, audio_message_update
    ):
        """Test is_voice_message returns False for audio file."""
        assert processor.is_voice_message(audio_message_update) is False
    
    def test_is_audio_message(self, processor, audio_message_update):
        """Test is_audio_message returns True for audio."""
        assert processor.is_audio_message(audio_message_update) is True
    
    def test_is_audio_message_false_for_voice(
        self, processor, voice_message_update
    ):
        """Test is_audio_message returns False for voice."""
        assert processor.is_audio_message(voice_message_update) is False
    
    def test_is_video_message_for_video(self, processor, video_message_update):
        """Test is_video_message returns True for video."""
        assert processor.is_video_message(video_message_update) is True
    
    def test_is_video_message_for_video_note(self, processor, video_note_update):
        """Test is_video_message returns True for video note."""
        assert processor.is_video_message(video_note_update) is True
    
    def test_is_video_message_false_for_voice(
        self, processor, voice_message_update
    ):
        """Test is_video_message returns False for voice."""
        assert processor.is_video_message(voice_message_update) is False
    
    def test_is_video_message_false_for_audio(
        self, processor, audio_message_update
    ):
        """Test is_video_message returns False for audio."""
        assert processor.is_video_message(audio_message_update) is False
    
    def test_get_audio_or_voice_info_for_voice(
        self, processor, voice_message_update
    ):
        """Test get_audio_or_voice_info for voice message."""
        info, msg_type = processor.get_audio_or_voice_info(voice_message_update)
        
        assert info is not None
        assert msg_type == "voice"
        assert info["file_id"] == "AwACAgIAAxkBAAIBZ2X_voice_file_id"
    
    def test_get_audio_or_voice_info_for_audio(
        self, processor, audio_message_update
    ):
        """Test get_audio_or_voice_info for audio file."""
        info, msg_type = processor.get_audio_or_voice_info(audio_message_update)
        
        assert info is not None
        assert msg_type == "audio"
        assert info["file_id"] == "CQACAgIAAxkBAAIBaGX_audio_file_id"
    
    def test_get_audio_or_voice_info_for_text(self, processor):
        """Test get_audio_or_voice_info for text message."""
        text_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1001,
                "from": {"id": 987654321, "is_bot": False, "first_name": "John"},
                "chat": {"id": 987654321, "type": "private"},
                "date": 1700000000,
                "text": "Hello, bot!"
            }
        }
        info, msg_type = processor.get_audio_or_voice_info(text_update)
        
        assert info is None
        assert msg_type == "none"
    
    def test_voice_default_mime_type(self, processor):
        """Test voice message uses default mime_type if not provided."""
        update = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "chat": {"id": 456, "type": "private"},
                "date": 1700000000,
                "voice": {
                    "file_id": "test_file_id",
                    "file_unique_id": "unique_id",
                    "duration": 10
                    # No mime_type provided
                }
            }
        }
        
        voice_info = processor.get_voice_info(update)
        
        assert voice_info is not None
        assert voice_info["mime_type"] == "audio/ogg"  # Default
    
    def test_audio_default_mime_type(self, processor):
        """Test audio message uses default mime_type if not provided."""
        update = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "chat": {"id": 456, "type": "private"},
                "date": 1700000000,
                "audio": {
                    "file_id": "test_file_id",
                    "file_unique_id": "unique_id",
                    "duration": 180
                    # No mime_type provided
                }
            }
        }
        
        audio_info = processor.get_audio_info(update)
        
        assert audio_info is not None
        assert audio_info["mime_type"] == "audio/mpeg"  # Default


class TestTelegramProcessorAudioAware:
    """Tests for AudioAwareProcessor integration in TelegramProcessor."""
    
    def test_processor_without_token(self):
        """Test processor works without bot_token (audio disabled)."""
        processor = TelegramProcessor()
        
        assert processor._bot_token is None
        assert processor._telegram_client is None
    
    def test_processor_with_token(self):
        """Test processor initializes with bot_token."""
        processor = TelegramProcessor(bot_token="test_token_123")
        
        assert processor._bot_token == "test_token_123"
        assert processor._telegram_client is not None
    
    @pytest.mark.asyncio
    async def test_download_audio_file_no_client(self):
        """Test download_audio_file raises error without client."""
        from app.common.audio.exceptions import AudioDownloadError
        
        processor = TelegramProcessor()  # No bot_token
        
        with pytest.raises(AudioDownloadError) as exc_info:
            await processor.download_audio_file("test_file_id")
        
        assert "not configured" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_download_audio_file_with_client(self):
        """Test download_audio_file delegates to TelegramClient."""
        from unittest.mock import AsyncMock, patch
        
        processor = TelegramProcessor(bot_token="test_token")
        
        # Mock the client's download_file method
        processor._telegram_client.download_file = AsyncMock(
            return_value="/tmp/test_audio.ogg"
        )
        
        result = await processor.download_audio_file("test_file_id")
        
        assert result == "/tmp/test_audio.ogg"
        processor._telegram_client.download_file.assert_called_once_with("test_file_id")
    
    def test_processor_inherits_audio_aware(self):
        """Test TelegramProcessor inherits from AudioAwareProcessor."""
        from app.modules.webhooks.base.audio_processor import AudioAwareProcessor
        
        processor = TelegramProcessor()
        
        assert isinstance(processor, AudioAwareProcessor)
        assert hasattr(processor, 'handle_audio_message')
        assert hasattr(processor, '_transcription_service')
