"""Configuration for the Assistants Platform."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional


class Config(BaseSettings):
    """Platform configuration."""
    
    # MongoDB (using existing connection)
    MONGODB_URL: str = Field(..., alias="MONGO_URI", description="MongoDB connection string")
    MONGODB_DB_NAME: str = Field("assistants-platform", description="Database name for the platform")
    
    # Organization (temporary - single org for MVP)
    DEFAULT_ORG_ID: str = Field(..., description="Default organization ID for MVP")
    
    # API
    API_V1_PREFIX: str = Field("/api/v1", description="API version 1 prefix")
    
    # CORS - список разрешенных источников для запросов с фронтенда
    BACKEND_CORS_ORIGINS: List[str] = Field(
        ["http://localhost:3000", "http://localhost:8000", "http://localhost:5173"],
        description="Allowed CORS origins (frontend URLs)"
    )
    
    # Auth0
    AUTH0_DOMAIN: str = Field(..., description="Auth0 domain")
    AUTH0_API_AUDIENCE: str = Field(..., description="Auth0 API audience")
    AUTH0_ALGORITHMS: List[str] = Field(["RS256"], description="JWT algorithms")
    
    # OpenAI (для будущей интеграции с LLM)
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    
    # LangSmith (для промптов и трейсинга)
    LANGSMITH_API_KEY: str = Field(..., description="LangSmith API key")
    LANGSMITH_TRACING: bool = Field(True, description="Enable LangSmith tracing")
    LANGSMITH_ENDPOINT: str = Field("https://api.smith.langchain.com", description="LangSmith API endpoint")
    LANGSMITH_PROJECT: str = Field("assistants-platform", description="LangSmith project name")
    
    # Security
    ENCRYPTION_KEY: str = Field(..., description="Fernet encryption key for securing bot tokens")
    WEBHOOK_BASE_URL: str = Field(..., description="Base URL for webhook endpoints")
    
    # RabbitMQ
    RABBITMQ_URL: str = Field(
        ...,
        description="RabbitMQ connection URL"
    )
    RABBITMQ_EXCHANGE_NAME: str = Field("messages", description="RabbitMQ exchange name")
    
    # WebSocket Worker
    WEBSOCKET_WORKER_HOST: str = Field("0.0.0.0", description="WebSocket worker host")
    WEBSOCKET_WORKER_PORT: int = Field(8001, description="WebSocket worker port")
    
    # Temporal
    TEMPORAL_HOST: str = Field("temporal:7233", description="Temporal gRPC endpoint")
    TEMPORAL_NAMESPACE: str = Field("default", description="Temporal namespace")
    TEMPORAL_TASK_QUEUE: str = Field("analysis-workflows", description="Temporal task queue name")
    TEMPORAL_MAX_CONCURRENT_ACTIVITIES: int = Field(5, description="Max concurrent Temporal activities")
    TEMPORAL_MAX_CONCURRENT_WORKFLOWS: int = Field(10, description="Max concurrent Temporal workflows")
    TEMPORAL_API_KEY: Optional[str] = Field(None, description="Temporal Cloud API key (None for local dev)")
    
    # Logging
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra fields from .env
        "populate_by_name": True  # V2 naming
    }


# Create global config instance
config = Config()
