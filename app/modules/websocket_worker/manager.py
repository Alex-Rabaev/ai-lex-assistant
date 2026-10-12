"""WebSocket connection manager with per-connection RabbitMQ queues."""

import logging
import json
import uuid
import asyncio
from typing import Dict, Optional, Set, Any
from dataclasses import dataclass, field

from fastapi import WebSocket
import aio_pika

from app.common.messaging.connection import RabbitMQConnection
from app.config import config

logger = logging.getLogger(__name__)


@dataclass
class UserConnection:
    """Represents a single WebSocket connection with its RabbitMQ queue."""
    
    user_id: str
    websocket: WebSocket
    queue_name: str
    queue: Optional[Any] = None
    subscriptions: Set[str] = field(default_factory=set)
    consumer_task: Optional[asyncio.Task] = None


class ConnectionManager:
    """
    Manages WebSocket connections with per-user RabbitMQ queues.
    
    Each WebSocket connection gets its own exclusive, auto-delete queue.
    RabbitMQ handles message routing, worker just forwards messages.
    
    This architecture scales horizontally - multiple workers can run,
    each handling different connections, and RabbitMQ routes messages
    to the correct queue.
    """
    
    def __init__(self):
        """Initialize connection manager."""
        # Map: connection_id -> UserConnection
        self._connections: Dict[str, UserConnection] = {}
        
        # RabbitMQ connection (shared for all user connections)
        self._rabbitmq: Optional[RabbitMQConnection] = None
        self._exchange: Optional[Any] = None
        self._channel: Optional[Any] = None
        
        logger.info("ConnectionManager initialized")
    
    async def _ensure_rabbitmq(self) -> None:
        """Ensure RabbitMQ connection is established."""
        if self._rabbitmq is None or not self._rabbitmq.is_connected:
            self._rabbitmq = RabbitMQConnection()
            await self._rabbitmq.connect()
            
            self._exchange = await self._rabbitmq.declare_exchange(
                config.RABBITMQ_EXCHANGE_NAME,
                exchange_type="topic",
                durable=True
            )
            
            self._channel = await self._rabbitmq.get_channel()
            logger.info("RabbitMQ connection established for ConnectionManager")
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str
    ) -> str:
        """
        Register WebSocket connection and create RabbitMQ queue for user.
        
        Note: WebSocket should already be accepted before calling this method.
        
        Args:
            websocket: WebSocket connection (already accepted)
            user_id: Authenticated user ID
            
        Returns:
            Connection ID
        """
        # Note: websocket.accept() is called in router before authentication
        # Do not call accept() here to avoid duplicate accept error
        
        # Generate unique connection ID
        connection_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        
        # Ensure RabbitMQ is connected
        await self._ensure_rabbitmq()
        
        # Create exclusive auto-delete queue for this connection
        queue_name = f"ws.{connection_id}"
        queue = await self._rabbitmq.declare_queue(
            queue_name,
            durable=False,
            exclusive=True,  # Only this connection can use it
            auto_delete=True  # Delete when connection closes
        )
        
        # Create user connection
        user_conn = UserConnection(
            user_id=user_id,
            websocket=websocket,
            queue_name=queue_name,
            queue=queue,
            subscriptions=set()
        )
        
        self._connections[connection_id] = user_conn
        
        # Start consuming from queue
        user_conn.consumer_task = asyncio.create_task(
            self._consume_messages(connection_id)
        )
        
        logger.info(
            f"WebSocket connected: connection_id={connection_id}, "
            f"user_id={user_id}, queue={queue_name}"
        )
        
        return connection_id
    
    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect WebSocket and cleanup RabbitMQ queue.
        
        Args:
            connection_id: Connection ID to disconnect
        """
        user_conn = self._connections.pop(connection_id, None)
        
        if not user_conn:
            return
        
        # Cancel consumer task
        if user_conn.consumer_task:
            user_conn.consumer_task.cancel()
            try:
                await user_conn.consumer_task
            except asyncio.CancelledError:
                pass
        
        # Queue will be auto-deleted by RabbitMQ when connection closes
        
        logger.info(
            f"WebSocket disconnected: connection_id={connection_id}, "
            f"user_id={user_conn.user_id}"
        )
    
    async def subscribe(
        self,
        connection_id: str,
        routing_pattern: str
    ) -> bool:
        """
        Subscribe connection to a routing pattern.
        
        Args:
            connection_id: Connection ID
            routing_pattern: RabbitMQ routing pattern (e.g., "webchat.user123.*")
            
        Returns:
            True if subscribed successfully
        """
        user_conn = self._connections.get(connection_id)
        
        if not user_conn:
            logger.warning(f"Connection {connection_id} not found for subscribe")
            return False
        
        # Validate user can only subscribe to their own messages
        if not self._validate_subscription(user_conn.user_id, routing_pattern):
            logger.warning(
                f"User {user_conn.user_id} tried to subscribe to unauthorized pattern: {routing_pattern}"
            )
            return False
        
        # Bind queue to exchange with this pattern
        await user_conn.queue.bind(self._exchange, routing_key=routing_pattern)
        user_conn.subscriptions.add(routing_pattern)
        
        logger.info(
            f"Subscribed: connection_id={connection_id}, pattern={routing_pattern}"
        )
        
        return True
    
    async def unsubscribe(
        self,
        connection_id: str,
        routing_pattern: str
    ) -> bool:
        """
        Unsubscribe connection from a routing pattern.
        
        Args:
            connection_id: Connection ID
            routing_pattern: RabbitMQ routing pattern to unsubscribe from
            
        Returns:
            True if unsubscribed successfully
        """
        user_conn = self._connections.get(connection_id)
        
        if not user_conn:
            return False
        
        if routing_pattern in user_conn.subscriptions:
            await user_conn.queue.unbind(self._exchange, routing_key=routing_pattern)
            user_conn.subscriptions.discard(routing_pattern)
            
            logger.info(
                f"Unsubscribed: connection_id={connection_id}, pattern={routing_pattern}"
            )
            return True
        
        return False
    
    def _validate_subscription(self, user_id: str, routing_pattern: str) -> bool:
        """
        Validate user can subscribe to the pattern.
        
        Security: User can only subscribe to patterns containing their user_id.
        
        Pattern format: "{prefix}.{user_id}.*" or "{prefix}.{user_id}.{suffix}"
        
        Args:
            user_id: User ID (email, e.g., "user@email.com")
            routing_pattern: Routing pattern to validate (e.g., "webchat.user@email.com.*")
            
        Returns:
            True if subscription is allowed
        """
        # Pattern must have at least prefix.user_id
        first_dot = routing_pattern.find(".")
        if first_dot == -1:
            return False
        
        # Find the last segment (e.g., "*" or "chat_message")
        last_dot = routing_pattern.rfind(".")
        if last_dot == first_dot:
            # Only one dot: "prefix.user_id"
            pattern_user_id = routing_pattern[first_dot + 1:]
        else:
            # Multiple dots: "prefix.user_id.suffix" -> extract middle part
            pattern_user_id = routing_pattern[first_dot + 1:last_dot]
        
        # User can only subscribe to their own messages
        return pattern_user_id == user_id
    
    async def _consume_messages(self, connection_id: str) -> None:
        """
        Consume messages from user's queue and forward to WebSocket.
        
        This is the core message forwarding loop. It doesn't parse
        or understand messages - just forwards them.
        
        Args:
            connection_id: Connection ID
        """
        user_conn = self._connections.get(connection_id)
        
        if not user_conn:
            return
        
        try:
            async with user_conn.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            # Decode message
                            body = json.loads(message.body.decode())
                            
                            # Forward to WebSocket as-is
                            await user_conn.websocket.send_json(body)
                            
                            logger.debug(
                                f"Forwarded message: connection_id={connection_id}, "
                                f"type={body.get('type')}"
                            )
                            
                        except Exception as e:
                            logger.error(
                                f"Error forwarding message to {connection_id}: {e}"
                            )
                            # Continue processing other messages
                            
        except asyncio.CancelledError:
            logger.debug(f"Consumer task cancelled for {connection_id}")
            raise
        except Exception as e:
            logger.error(f"Consumer error for {connection_id}: {e}", exc_info=True)
    
    def get_connection(self, connection_id: str) -> Optional[UserConnection]:
        """Get connection by ID."""
        return self._connections.get(connection_id)
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self._connections)
    
    def is_connected(self, connection_id: str) -> bool:
        """Check if connection exists."""
        return connection_id in self._connections
    
    async def close(self) -> None:
        """Close all connections and cleanup."""
        # Disconnect all users
        for connection_id in list(self._connections.keys()):
            await self.disconnect(connection_id)
        
        # Close RabbitMQ connection
        if self._rabbitmq:
            await self._rabbitmq.close()
            self._rabbitmq = None
        
        logger.info("ConnectionManager closed")
