"""Publisher for outgoing messages to outbound module."""

import json
import logging
from typing import Optional, Dict, Any

import aio_pika

from app.common.messaging.connection import RabbitMQConnection

logger = logging.getLogger(__name__)


class ConversationsPublisher:
    """
    Publishes outgoing messages to outbound_messages queue.
    
    This publisher sends generated responses to the outbound module
    for delivery to users via communication channels.
    """
    
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
        """Setup exchange and queue for outgoing messages."""
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
        
        # Declare and bind outbound_messages queue
        queue = await self.connection.declare_queue("outbound_messages", durable=True)
        await queue.bind(self.exchange, routing_key="outbound.*")
        logger.info("Queue 'outbound_messages' bound to exchange 'messages' with routing_key 'outbound.*'")
        
        self._setup_done = True
        logger.info("Publisher setup completed for outbound_messages queue")
    
    async def publish_outgoing_message(
        self,
        assistant_id: str,
        connection_id: str,
        user_id: str,
        response_text: str,
        message_type: str = "message",
        original_message_id: Optional[str] = None,
        parse_mode: str = "HTML",
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> None:
        """
        Publish outgoing message to outbound_messages queue.
        
        Args:
            assistant_id: Assistant ID
            connection_id: Connection ID
            user_id: User ID in format 'channel_id'
            response_text: Response text to send
            message_type: Message type (message or callback_query)
            original_message_id: Original message ID
            parse_mode: Parse mode (HTML or Markdown)
            metadata: Additional metadata
            trace_id: Trace ID for request tracking through pipeline
            conversation_id: Conversation ID (for webchat)
        """
        await self.setup()
        
        # Build message payload
        message = {
            "assistant_id": assistant_id,
            "connection_id": connection_id,
            "user_id": user_id,
            "type": message_type,
            "response_text": response_text,
            "parse_mode": parse_mode,
        }
        
        if trace_id:
            message["trace_id"] = trace_id
        
        if original_message_id:
            message["original_message_id"] = original_message_id
        
        if metadata:
            message["metadata"] = metadata
        
        if conversation_id:
            message["conversation_id"] = conversation_id
        
        # Extract channel from user_id for routing key
        channel = user_id.split("_", 1)[0] if "_" in user_id else "unknown"
        routing_key = f"outbound.{channel}"
        
        # Publish to exchange
        body = json.dumps(message).encode()
        await self.exchange.publish(
            aio_pika.Message(body),
            routing_key=routing_key
        )
        
        logger.info(
            f"Published outgoing message: routing_key={routing_key}"
        )
    
    async def publish_typing_indicator(
        self,
        assistant_id: str,
        connection_id: str,
        user_id: str,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Publish typing indicator to outbound_messages queue.
        
        This sends a typing indicator message that will be processed
        by the outbound worker to show "typing..." status to the user.
        
        Args:
            assistant_id: Assistant ID
            connection_id: Connection ID
            user_id: User ID in format 'channel_id'
            trace_id: Trace ID for request tracking through pipeline
        """
        await self.setup()
        
        # Build typing indicator message payload
        message = {
            "assistant_id": assistant_id,
            "connection_id": connection_id,
            "user_id": user_id,
            "type": "typing_indicator",
        }
        
        if trace_id:
            message["trace_id"] = trace_id
        
        # Extract channel from user_id for routing key
        channel = user_id.split("_", 1)[0] if "_" in user_id else "unknown"
        routing_key = f"outbound.{channel}"
        
        # Publish to exchange
        body = json.dumps(message).encode()
        await self.exchange.publish(
            aio_pika.Message(body),
            routing_key=routing_key
        )
        
        logger.debug(
            f"Published typing indicator: routing_key={routing_key}, user_id={user_id}"
        )

