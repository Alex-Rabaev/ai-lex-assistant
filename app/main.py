"""Main entry point for the Assistants Platform API."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import config
from app.common.db.database import get_motor_client, close_motor_client
from app.modules.assistants.router import router as assistants_router
from app.modules.connections.router import router as connections_router
from app.modules.conversations.router import router as conversations_router
from app.common.utils import setup_structured_logging
from app.modules.connections.vendors.webchat.router import router as webchat_api_router

# Setup logging
setup_structured_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    
    # Startup
    logger.info("Starting Assistants Platform...")
    
    # Initialize MongoDB connection
    try:
        client = get_motor_client()
        await client.admin.command('ping')
        logger.info(f"Connected to MongoDB database: {config.MONGODB_DB_NAME}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

    yield
    
    # Shutdown
    logger.info("Shutting down Assistants Platform...")
    await close_motor_client()


# Create FastAPI app
app = FastAPI(
    title="Assistants Platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    assistants_router,
    prefix=f"{config.API_V1_PREFIX}/assistants",
    tags=["assistants"]
)

# Connections module
app.include_router(
    connections_router,
    prefix=f"{config.API_V1_PREFIX}",
    tags=["connections"]
)

# Webhooks module with security validation
from app.modules.webhooks.router import router as webhook_router
app.include_router(
    webhook_router,
    prefix="",  # No prefix since the router already includes /webhook
    tags=["webhooks"]
)

# Conversations module - admin interface for managing interlocutors and messages
app.include_router(
    conversations_router,
    prefix=f"{config.API_V1_PREFIX}/conversations",
    tags=["conversations"]
)

# WebChat REST API for message history and management
app.include_router(
    webchat_api_router,
    prefix=f"{config.API_V1_PREFIX}",
    tags=["webchat"]
)

# Analysis module - config management and analytics
from app.modules.analysis.router import router as analysis_router
app.include_router(
    analysis_router,
    prefix=f"{config.API_V1_PREFIX}",
    tags=["analysis"]
)

# Follow-ups - manual reminder and config (config is under assistants)
from app.modules.follow_ups.router import router as follow_ups_router
app.include_router(
    follow_ups_router,
    prefix=f"{config.API_V1_PREFIX}/conversations",
    tags=["follow-ups"]
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "assistants-platform",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Assistants Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,  # Main platform port
        reload=True,
        log_level="info"
    )
