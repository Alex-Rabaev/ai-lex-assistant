"""RabbitMQ message publisher."""

import json
import logging
from typing import Dict, Any, Optional
import aio_pika

from app.common.messaging.connection import RabbitMQConnection

logger = logging.getLogger(__name__)


class MessagePublisher:
    """Publishes messages to RabbitMQ."""
    
    def __init__(self, connection: RabbitMQConnection):
        """
        Initialize message publisher.
        
        Args:
            connection: RabbitMQ connection instance
        """
        self.connection = connection
        self.exchange: Optional[Any] = None
        self._setup_done = False
    
    async def setup(self) -> None:
        """Setup exchange and ensure connection."""
        if self._setup_done and self.exchange:
            return
        
        if not self.connection.is_connected:
            await self.connection.connect()
        
        # Declare exchange
        self.exchange = await self.connection.declare_exchange(
            "messages",
            exchange_type="topic",
            durable=True
        )
        
        # Declare and bind incoming_messages queue to exchange
        # This ensures messages published with routing_key "messages.*" reach the queue
        channel = await self.connection.get_channel()
        queue = await self.connection.declare_queue("incoming_messages", durable=True)
        await queue.bind(self.exchange, routing_key="messages.*")
        logger.info("Queue 'incoming_messages' bound to exchange 'messages' with routing_key 'messages.*'")
        
        self._setup_done = True
        logger.info(f"Publisher setup completed with exchange 'messages'")
    
    async def publish_incoming_message(
        self,
        message: Dict[str, Any],
        routing_key: str
    ) -> None:
        """
        Publish incoming message to RabbitMQ.
        
        Args:
            message: Message payload
            routing_key: Routing key (e.g., "telegram.message", "telegram.command.start")
        """
        await self.setup()
        
        # Convert to JSON
        body = json.dumps(message).encode()
        
        # Publish to exchange
        await self.exchange.publish(
            aio_pika.Message(body),
            routing_key=routing_key
        )
        
        logger.info(
            f"Published incoming message to queue: "
            f"user={message.get('user_id', 'unknown')}, "
            f"type={message.get('type', 'unknown')}, "
            f"routing_key={routing_key}"
        )

