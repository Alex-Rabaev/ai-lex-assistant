"""Webhook publisher wrapper for RabbitMQ."""

import logging
from typing import Dict, Any, Optional

from app.common.messaging.connection import RabbitMQConnection
from app.common.messaging.publisher import MessagePublisher
from app.common.utils.logging_context import get_log_context, generate_trace_id

logger = logging.getLogger(__name__)


class WebhookPublisher:
    """Publishes webhook events to RabbitMQ."""
    
    def __init__(self, connection: Optional[RabbitMQConnection] = None):
        """
        Initialize webhook publisher.
        
        Args:
            connection: Optional RabbitMQ connection (creates new if not provided)
        """
        self.connection = connection or RabbitMQConnection()
        self.publisher: Optional[MessagePublisher] = None
    
    async def _ensure_publisher(self) -> None:
        """Ensure publisher is initialized."""
        if not self.publisher:
            if not self.connection.is_connected:
                await self.connection.connect()
            self.publisher = MessagePublisher(self.connection)
    
    async def publish_message(
        self,
        assistant_id: str,
        connection_id: str,
        user_id: str,
        channel: str,
        message_data: Dict[str, Any]
    ) -> str:
        """
        Publish message to RabbitMQ.
        
        Args:
            assistant_id: Assistant ID
            connection_id: Connection ID
            user_id: User ID (e.g., telegram_123456)
            channel: Channel type (e.g., "telegram", "whatsapp")
            message_data: Message data dictionary (type, text, callback_data, etc.)
            
        Returns:
            trace_id used for this message
        """
        await self._ensure_publisher()
        
        # Get trace_id from context (set by router) or generate if missing
        context = get_log_context()
        trace_id = context.get("trace_id") or generate_trace_id()
        
        message = {
            "trace_id": trace_id,
            "assistant_id": assistant_id,
            "connection_id": connection_id,
            "user_id": user_id,
            **message_data
        }
        
        # Dynamic routing key: messages.{channel}
        routing_key = f"messages.{channel}"
        await self.publisher.publish_incoming_message(message, routing_key)
        
        logger.info(
            f"Published message: channel={channel}, type={message_data.get('type', 'unknown')}"
        )
        
        return trace_id

