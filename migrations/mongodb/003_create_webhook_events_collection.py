"""
Create webhook_events collection with indexes.

This migration creates the webhook_events collection for storing
incoming webhook data from various channels (Telegram, WhatsApp).
"""

import asyncio
import logging
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid, OperationFailure
from pymongo import ASCENDING, DESCENDING
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def up(client: AsyncIOMotorClient, db_name: str):
    """Create webhook_events collection and indexes."""
    db = client[db_name]
    
    try:
        # Create collection
        await db.create_collection("webhook_events")
        logger.info("Created webhook_events collection")
    except CollectionInvalid:
        logger.info("webhook_events collection already exists")
    
    collection = db["webhook_events"]
    
    # Create indexes
    indexes = [
        # Compound index for finding events by assistant with sorting
        {
            "keys": [("assistant_id", ASCENDING), ("created_at", DESCENDING)],
            "name": "assistant_created_idx",
            "background": True
        },
        # Compound index for finding events by user with sorting
        {
            "keys": [("user_id", ASCENDING), ("created_at", DESCENDING)],
            "name": "user_created_idx",
            "background": True
        },
        # Unique index on update_id for deduplication (Telegram)
        {
            "keys": [("update_id", ASCENDING)],
            "name": "update_id_unique_idx",
            "unique": True,
            "sparse": True,  # Sparse because WhatsApp won't have update_id
            "background": True
        },
        # Index for finding unprocessed events
        {
            "keys": [("processed", ASCENDING)],
            "name": "processed_idx",
            "background": True
        },
        # Index for connection lookup
        {
            "keys": [("connection_id", ASCENDING)],
            "name": "connection_idx",
            "background": True
        },
        # Index for channel and user combination
        {
            "keys": [("channel", ASCENDING), ("user_id", ASCENDING)],
            "name": "channel_user_idx",
            "background": True
        },
        # TTL index for automatic cleanup of old events after 7 days
        {
            "keys": [("created_at", ASCENDING)],
            "name": "created_ttl_idx",
            "expireAfterSeconds": 604800  # 7 days (7 * 24 * 60 * 60)
        }
    ]
    
    for index_spec in indexes:
        try:
            keys = index_spec.pop("keys")
            await collection.create_index(keys, **index_spec)
            logger.info(f"Created index: {index_spec['name']}")
        except OperationFailure as e:
            if "already exists" in str(e):
                logger.info(f"Index {index_spec.get('name', 'unnamed')} already exists")
            else:
                logger.error(f"Failed to create index: {e}")
                raise
    
    # Record migration in history
    await db["migration_history"].update_one(
        {"migration_id": "003_create_webhook_events_collection"},
        {
            "$set": {
                "migration_id": "003_create_webhook_events_collection",
                "description": "Create webhook_events collection with indexes",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed"
            }
        },
        upsert=True
    )
    
    logger.info("webhook_events collection migration completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop webhook_events collection."""
    db = client[db_name]
    
    try:
        await db.drop_collection("webhook_events")
        logger.info("Dropped webhook_events collection")
    except Exception as e:
        logger.error(f"Failed to drop collection: {e}")
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": "003_create_webhook_events_collection"
    })


async def main():
    """Run migration with proper config."""
    try:
        # Import config after sys.path is set up
        from app.config import config
        
        # Connect to MongoDB using config
        client = AsyncIOMotorClient(config.MONGODB_URL)
        db_name = config.MONGODB_DB_NAME
        
        # Check if already applied
        db = client[db_name]
        existing = await db["migration_history"].find_one({
            "migration_id": "003_create_webhook_events_collection",
            "status": "completed"
        })
        
        if existing:
            logger.info("Migration 003 already applied. Skipping...")
            client.close()
            return
        
        # Run migration
        await up(client, db_name)
        
        # Verify
        collections = await db.list_collection_names()
        if "webhook_events" in collections:
            logger.info("✅ webhook_events collection created successfully")
            indexes = await db["webhook_events"].list_indexes().to_list(None)
            logger.info(f"Indexes created: {[idx['name'] for idx in indexes]}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
