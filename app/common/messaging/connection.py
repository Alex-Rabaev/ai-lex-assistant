"""RabbitMQ connection manager."""

import logging
from typing import Optional
import aio_pika
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange, AbstractQueue

from app.config import config

logger = logging.getLogger(__name__)


class RabbitMQConnection:
    """Manages RabbitMQ connection and channel."""
    
    def __init__(self, url: Optional[str] = None):
        """
        Initialize RabbitMQ connection.
        
        Args:
            url: RabbitMQ connection URL (defaults to config.RABBITMQ_URL)
        """
        self.url = url or config.RABBITMQ_URL
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
    
    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if self._connection and not self._connection.is_closed:
            logger.debug("RabbitMQ connection already established")
            return
        
        logger.info(f"🔌 Connecting to RabbitMQ: {self.url}")
        self._connection = await aio_pika.connect_robust(self.url)
        self._channel = await self._connection.channel()
        logger.info("✅ RabbitMQ connection established successfully")
        logger.info("RabbitMQ channel created")
    
    async def get_channel(self) -> AbstractChannel:
        """
        Get or create RabbitMQ channel.
        
        Returns:
            RabbitMQ channel
            
        Raises:
            RuntimeError: If not connected
        """
        if not self._channel or self._channel.is_closed:
            if not self._connection or self._connection.is_closed:
                raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")
            self._channel = await self._connection.channel()
        return self._channel
    
    async def declare_exchange(
        self,
        name: str,
        exchange_type: str = "topic",
        durable: bool = True
    ) -> AbstractExchange:
        """
        Declare exchange.
        
        Args:
            name: Exchange name
            exchange_type: Exchange type (default: topic)
            durable: Whether exchange should survive broker restart
            
        Returns:
            Declared exchange
        """
        channel = await self.get_channel()
        exchange = await channel.declare_exchange(
            name,
            type=aio_pika.ExchangeType.TOPIC if exchange_type == "topic" else aio_pika.ExchangeType.DIRECT,
            durable=durable
        )
        logger.info(f"Exchange '{name}' declared")
        return exchange
    
    async def declare_queue(
        self,
        name: str,
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
        arguments: Optional[dict] = None
    ) -> AbstractQueue:
        """
        Declare queue.
        
        Args:
            name: Queue name
            durable: Whether queue should survive broker restart
            exclusive: Only allow access by the current connection
            auto_delete: Delete queue when all consumers disconnect
            arguments: Additional queue arguments
            
        Returns:
            Declared queue
        """
        channel = await self.get_channel()
        queue = await channel.declare_queue(
            name,
            durable=durable,
            exclusive=exclusive,
            auto_delete=auto_delete,
            arguments=arguments or {}
        )
        logger.info(f"Queue '{name}' declared (exclusive={exclusive}, auto_delete={auto_delete})")
        return queue
    
    async def close(self) -> None:
        """Close connection and channel."""
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
            logger.info("RabbitMQ channel closed")
        
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return (
            self._connection is not None
            and not self._connection.is_closed
            and self._channel is not None
            and not self._channel.is_closed
        )

