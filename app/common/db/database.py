"""Database utilities for the platform."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import config

# Global motor client singleton
_motor_client: AsyncIOMotorClient | None = None


def get_motor_client() -> AsyncIOMotorClient:
    """Get or create motor client singleton.
    
    Returns:
        Async motor client instance
    """
    global _motor_client
    if _motor_client is None:
        _motor_client = AsyncIOMotorClient(config.MONGODB_URL)
    return _motor_client


async def get_database() -> AsyncIOMotorDatabase:
    """Get platform database instance.
    
    Returns:
        Async motor database
    """
    client = get_motor_client()
    return client[config.MONGODB_DB_NAME]


async def close_motor_client():
    """Close motor client connection."""
    global _motor_client
    if _motor_client:
        _motor_client.close()
        _motor_client = None

