"""
WebSocket Worker - standalone FastAPI service for WebSocket connections.

Each WebSocket connection creates its own RabbitMQ queue.
The message forwarding is handled by ConnectionManager.

Run standalone:
    python -m app.modules.websocket_worker.worker

Or use make:
    make run-websocket-worker
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.modules.websocket_worker.router import router as websocket_router, get_connection_manager
from app.config import config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("🚀 WebSocket Worker starting...")
    yield
    # Shutdown
    logger.info("🛑 WebSocket Worker shutting down...")
    manager = get_connection_manager()
    await manager.close()
    logger.info("✅ WebSocket Worker stopped")


def create_websocket_app() -> FastAPI:
    """Create FastAPI app for WebSocket service."""
    app = FastAPI(
        title="WebSocket Worker",
        description="Real-time message delivery via WebSocket",
        version="1.0.0",
        lifespan=lifespan
    )
    
    app.include_router(websocket_router, prefix="/websockets/v1")
    
    @app.get("/health")
    async def health():
        manager = get_connection_manager()
        return {
            "status": "healthy",
            "service": "websocket-worker",
            "connections": manager.get_connection_count()
        }
    
    return app


def run_standalone():
    """
    Run WebSocket worker as a standalone service.
    
    Host and port are read from config (env vars).
    """
    app = create_websocket_app()
    
    uvicorn.run(
        app,
        host=config.WEBSOCKET_WORKER_HOST,
        port=config.WEBSOCKET_WORKER_PORT,
        log_level="info"
    )


async def main():
    """Async main for testing."""
    app = create_websocket_app()
    
    server_config = uvicorn.Config(
        app,
        host=config.WEBSOCKET_WORKER_HOST,
        port=config.WEBSOCKET_WORKER_PORT,
        log_level="info"
    )
    server = uvicorn.Server(server_config)
    
    await server.serve()


# Export app for uvicorn
# Usage: uvicorn app.modules.websocket_worker.worker:app --host 0.0.0.0 --port 8000
from app.common.utils import setup_structured_logging
setup_structured_logging()
app = create_websocket_app()

if __name__ == "__main__":
    run_standalone()
