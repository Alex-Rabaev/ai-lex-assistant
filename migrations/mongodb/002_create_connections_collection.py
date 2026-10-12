"""
Create connections collection and indexes for managing assistant channel integrations.

This migration creates the connections collection for storing
channel integration settings for assistants.
"""

import asyncio
import logging
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid, OperationFailure
from pymongo import ASCENDING
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def up(client: AsyncIOMotorClient, db_name: str):
    """Create connections collection with indexes."""
    db = client[db_name]
    
    # Create collection
    try:
        await db.create_collection("connections")
        logger.info("Created 'connections' collection")
    except CollectionInvalid:
        logger.info("Collection 'connections' already exists")
    
    collection = db["connections"]
    
    # Create indexes
    indexes_created = []
    
    # 1. Unique compound index: one channel per assistant
    try:
        await collection.create_index(
            [("assistant_id", ASCENDING), ("channel", ASCENDING)],
            unique=True,
            name="assistant_channel_unique",
            background=True
        )
        indexes_created.append("assistant_channel_unique")
    except OperationFailure as e:
        if "already exists" not in str(e):
            raise
        logger.info("Index 'assistant_channel_unique' already exists")
    
    # 2. Status index for monitoring
    try:
        await collection.create_index(
            [("status", ASCENDING)],
            name="status_idx",
            background=True
        )
        indexes_created.append("status_idx")
    except OperationFailure as e:
        if "already exists" not in str(e):
            raise
        logger.info("Index 'status_idx' already exists")
    
    # 3. Assistant ID index for fast lookups
    try:
        await collection.create_index(
            [("assistant_id", ASCENDING)],
            name="assistant_id_idx",
            background=True
        )
        indexes_created.append("assistant_id_idx")
    except OperationFailure as e:
        if "already exists" not in str(e):
            raise
        logger.info("Index 'assistant_id_idx' already exists")
    
    # 4. Compound index for health monitoring
    try:
        await collection.create_index(
            [("status", ASCENDING), ("last_checked_at", ASCENDING)],
            name="health_monitoring_idx",
            background=True
        )
        indexes_created.append("health_monitoring_idx")
    except OperationFailure as e:
        if "already exists" not in str(e):
            raise
        logger.info("Index 'health_monitoring_idx' already exists")
    
    if indexes_created:
        logger.info(f"Created indexes: {', '.join(indexes_created)}")
    
    # Record migration in history (use unified collection)
    await db["migration_history"].update_one(
        {"migration_id": "002_create_connections_collection"},
        {
            "$set": {
                "migration_id": "002_create_connections_collection",
                "description": "Create connections collection with indexes for assistant channel integrations",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed"
            }
        },
        upsert=True
    )
    
    logger.info("Migration 002_create_connections_collection completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop connections collection."""
    db = client[db_name]
    
    try:
        await db.drop_collection("connections")
        logger.info("Dropped 'connections' collection")
    except Exception as e:
        logger.error(f"Failed to drop 'connections' collection: {e}")
        raise
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": "002_create_connections_collection"
    })
    
    logger.info("Rollback of 002_create_connections_collection completed")


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
            "migration_id": "002_create_connections_collection",
            "status": "completed"
        })
        
        if existing:
            logger.info("Migration 002 already applied. Skipping...")
            client.close()
            return
        
        # Run migration
        await up(client, db_name)
        
        # Verify
        collections = await db.list_collection_names()
        if "connections" in collections:
            logger.info("✅ connections collection created successfully")
            indexes = await db["connections"].list_indexes().to_list(None)
            logger.info(f"Indexes created: {[idx['name'] for idx in indexes]}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())