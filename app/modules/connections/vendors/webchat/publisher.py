"""Publisher for WebSocket messages."""

import json
import logging
from typing import Optional, Dict, Any

import aio_pika

from app.common.messaging.connection import RabbitMQConnection

logger = logging.getLogger(__name__)


class WebsocketPublisher:
    """
    Publishes messages to websocket_messages queue via topic exchange.
    
    Routing key format: {channel}.{user_id}.{message_type}
    Examples:
        - webchat.user123.chat_message
        - webchat.user123.typing
        - notifications.user123.alert
    
    This allows clients to subscribe to specific patterns:
        - webchat.user123.* - all webchat messages for user123
        - notifications.user123.* - all notifications for user123
    """
    
    EXCHANGE_NAME = "messages"
    ROUTING_KEY_PREFIX = "webchat"
    
    def __init__(self, connection: Optional[RabbitMQConnection] = None):
        """
        Initialize publisher.
        
        Args:
            connection: Optional RabbitMQ connection (creates new if not provided)
        """
        self.connection = connection or RabbitMQConnection()
        self.exchange: Optional[Any] = None
        self._setup_done = False
    
    async def setup(self) -> None:
        """Setup exchange for websocket messages."""
        if self._setup_done and self.exchange:
            return
        
        if not self.connection.is_connected:
            await self.connection.connect()
        
        # Declare exchange only - queue creation is consumer's responsibility
        self.exchange = await self.connection.declare_exchange(
            self.EXCHANGE_NAME,
            exchange_type="topic",
            durable=True
        )
        
        self._setup_done = True
        logger.info(f"WebsocketPublisher setup completed, exchange '{self.EXCHANGE_NAME}' ready")
    
    def _build_routing_key(self, user_id: str, message_type: str) -> str:
        """
        Build routing key for message.
        
        Format: {prefix}.{user_id}.{message_type}
        
        Args:
            user_id: User ID
            message_type: Message type (chat_message, typing, notification)
            
        Returns:
            Routing key string
        """
        return f"{self.ROUTING_KEY_PREFIX}.{user_id}.{message_type}"
    
    async def publish(
        self,
        message: Dict[str, Any],
        user_id: str,
        message_type: str = "chat_message"
    ) -> None:
        """
        Publish message to exchange with user-specific routing.
        
        Args:
            message: Message payload
            user_id: User ID for routing
            message_type: Message type for routing (chat_message, typing, notification)
        """
        await self.setup()
        
        routing_key = self._build_routing_key(user_id, message_type)
        
        # Publish to exchange
        body = json.dumps(message).encode()
        await self.exchange.publish(
            aio_pika.Message(body),
            routing_key=routing_key
        )
        
        logger.debug(
            f"Published websocket message: routing_key={routing_key}, "
            f"type={message_type}, user_id={user_id}"
        )
    
    async def publish_chat_message(
        self,
        assistant_id: str,
        user_id: str,
        message_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Publish chat message for WebSocket delivery.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID
            message_id: Message ID
            role: Message role (user/assistant)
            content: Message content
        """
        message = {
            "type": "chat_message",
            "assistant_id": assistant_id,
            "user_id": user_id,
            "payload": {
                "message_id": message_id,
                "role": role,
                "content": content
            }
        }
        
        await self.publish(message, user_id, "chat_message")
    
    async def publish_typing_indicator(
        self,
        assistant_id: str,
        user_id: str,
        is_typing: bool = True
    ) -> None:
        """
        Publish typing indicator for WebSocket delivery.
        
        Args:
            assistant_id: Assistant ID
            user_id: User ID
            is_typing: Whether assistant is typing
        """
        message = {
            "type": "typing",
            "assistant_id": assistant_id,
            "user_id": user_id,
            "payload": {
                "is_typing": is_typing
            }
        }
        
        await self.publish(message, user_id, "typing")
    
    async def publish_notification(
        self,
        user_id: str,
        title: str,
        message_text: str,
        action_url: Optional[str] = None
    ) -> None:
        """
        Publish notification for WebSocket delivery.
        
        Args:
            user_id: User ID
            title: Notification title
            message_text: Notification message
            action_url: Optional action URL
        """
        payload = {
            "title": title,
            "message": message_text
        }
        
        if action_url:
            payload["action_url"] = action_url
        
        message = {
            "type": "notification",
            "user_id": user_id,
            "payload": payload
        }
        
        await self.publish(message, user_id, "notification")
