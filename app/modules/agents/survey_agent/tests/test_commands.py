"""Tests for CommandHandler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.agents.survey_agent.commands import CommandHandler


class TestCommandHandler:
    """Test CommandHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create command handler."""
        return CommandHandler()
    
    @pytest.fixture
    def mock_service(self):
        """Mock ConversationsService."""
        service = MagicMock()
        service.reset_conversation = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_handle_reset(self, handler, mock_service):
        """Test /reset command."""
        conversation_id = "abc123"
        
        with patch('app.modules.conversations.service.ConversationsService', return_value=mock_service):
            # Act
            result = await handler.handle_command("/reset", conversation_id)
            
            # Assert
            assert result is not None
            assert "deleted" in result.lower()
            mock_service.reset_conversation.assert_called_once_with(conversation_id)
    
    @pytest.mark.asyncio
    async def test_handle_error(self, handler):
        """Test /error command."""
        conversation_id = "abc123"
        
        # Act
        result = await handler.handle_command("/error", conversation_id)
        
        # Assert
        assert result is not None
        assert "oops" in result.lower() or "wrong" in result.lower()
    
    @pytest.mark.asyncio
    async def test_unknown_command(self, handler):
        """Test unknown command."""
        conversation_id = "abc123"
        
        # Act
        result = await handler.handle_command("/unknown", conversation_id)
        
        # Assert
        assert result is None
