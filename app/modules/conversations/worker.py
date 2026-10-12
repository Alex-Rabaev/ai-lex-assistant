"""RabbitMQ worker for processing incoming messages and generating responses."""

import logging
import json
import signal
import asyncio
from typing import Optional

from app.common.messaging.connection import RabbitMQConnection
from app.modules.conversations.schemas import IncomingMessage
from app.modules.conversations.service import ConversationsService
from app.modules.conversations.exceptions import ProcessingError
from app.common.utils.logging_context import set_log_context, clear_log_context

logger = logging.getLogger(__name__)


class ConversationsWorker:
    """
    Worker for processing incoming messages from webhooks.
    
    Consumes messages from 'incoming_messages' queue, processes them
    via ConversationsService, and publishes responses to outbound module.
    """
    
    def __init__(self):
        """Initialize conversations worker."""
        self.rabbitmq_connection: Optional[RabbitMQConnection] = None
        self.service: Optional[ConversationsService] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self):
        """
        Start the worker and begin processing messages.
        
        This is the main entry point that:
        1. Sets up signal handlers for graceful shutdown
        2. Connects to RabbitMQ
        3. Begins consuming messages from incoming_messages queue
        4. Processes each message via ConversationsService
        """
        logger.info("🚀 Starting Conversations Worker...")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            # Initialize service
            self.service = ConversationsService()
            
            # Connect to RabbitMQ
            self.rabbitmq_connection = RabbitMQConnection()
            await self.rabbitmq_connection.connect()
            
            # Declare queue (idempotent operation)
            queue = await self.rabbitmq_connection.declare_queue(
                "incoming_messages",
                durable=True
            )
            
            # Set QoS to process one message at a time
            channel = await self.rabbitmq_connection.get_channel()
            await channel.set_qos(prefetch_count=1)
            
            logger.info("✅ Worker connected to RabbitMQ, waiting for messages...")
            self.running = True
            
            # Start consuming messages
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.running:
                        logger.info("Worker shutting down, stopping message consumption")
                        break
                    
                    async with message.process(ignore_processed=True):
                        try:
                            # Parse message body
                            body = json.loads(message.body.decode())
                            incoming_msg = IncomingMessage(**body)
                            
                            # Set logging context for tracing
                            set_log_context(
                                trace_id=incoming_msg.trace_id,
                                assistant_id=incoming_msg.assistant_id,
                                user_id=incoming_msg.user_id
                            )
                            
                            logger.info(
                                f"📨 Received message: type={incoming_msg.type}"
                            )
                            
                            # Process message via service
                            result = await self.service.process_incoming_message(incoming_msg)
                            
                            if result.success:
                                # Acknowledge successful processing
                                await message.ack()
                                logger.info("✅ Message processed and acknowledged")
                            else:
                                logger.error(f"Processing failed: {result.error}")
                                await message.nack(requeue=False)
                            
                        except ProcessingError as e:
                            logger.error(f"❌ Processing error: {e}", exc_info=True)
                            # Reject and requeue for retry
                            await message.nack(requeue=True)
                            
                        except Exception as e:
                            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
                            # Reject without requeue (bad message)
                            await message.nack(requeue=False)
                        
                        finally:
                            # Clear context after processing
                            clear_log_context()
            
        except Exception as e:
            logger.error(f"Fatal error in worker: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals (SIGTERM, SIGINT).
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        self._shutdown_event.set()
    
    async def shutdown(self):
        """Perform graceful shutdown of the worker."""
        logger.info("🛑 Shutting down Conversations Worker...")
        self.running = False
        
        if self.rabbitmq_connection:
            try:
                await self.rabbitmq_connection.close()
                logger.info("RabbitMQ connection closed")
            except Exception as e:
                logger.error(f"Error closing RabbitMQ connection: {e}")
        
        logger.info("✅ Conversations Worker stopped")


async def main():
    """Main entry point for running the worker."""
    worker = ConversationsWorker()
    await worker.start()


if __name__ == "__main__":
    # Configure structured JSON logging
    from app.common.utils import setup_structured_logging
    setup_structured_logging()
    
    # Run worker
    asyncio.run(main())

