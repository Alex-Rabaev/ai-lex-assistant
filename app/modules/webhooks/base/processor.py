"""Base processor for parsing channel-specific webhook data."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseProcessor(ABC):
    """
    Abstract base class for processing webhook data from different channels.
    Each channel (Telegram, WhatsApp, etc.) should implement its own processor.
    """
    
    @abstractmethod
    def extract_text(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract text message from the update.
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Extracted text or None if not a text message
        """
        pass
    
    @abstractmethod
    def get_user_id(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract and format user ID from the update.
        Format: {channel}_{id} (e.g., telegram_123456)
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Formatted user ID or None
        """
        pass
    
    @abstractmethod
    def get_user_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract user information from the update.
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Dictionary with user information (name, username, etc.) or None
        """
        pass
    
    @abstractmethod
    def get_chat_info(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract chat/conversation information from the update.
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Dictionary with chat information or None
        """
        pass
    
    @abstractmethod
    def get_message_type(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Determine the type of message from the update.
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Message type: 'message', 'callback_query', 'edited_message', 'command', etc.
        """
        pass
    
    @abstractmethod
    def get_message_id(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Extract message ID from the update.
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Message ID or None
        """
        pass
    
    def process(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the update and extract all relevant information.
        This method can be overridden for custom processing logic.
        
        Args:
            update: Raw webhook update from channel
            
        Returns:
            Dictionary with extracted information
        """
        # Default implementation using abstract methods
        result = {
            "text": self.extract_text(update),
            "user_id": self.get_user_id(update),
            "user_info": self.get_user_info(update),
            "chat_info": self.get_chat_info(update),
            "message_type": self.get_message_type(update),
            "message_id": self.get_message_id(update),
            "raw": update
        }
        
        return result
