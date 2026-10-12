"""
Create interlocutors collection with indexes.

This migration creates the interlocutors collection for storing
user profiles across different communication channels.
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
    """Create interlocutors collection and indexes."""
    db = client[db_name]
    
    try:
        # Create collection
        await db.create_collection("interlocutors")
        logger.info("Created interlocutors collection")
    except CollectionInvalid:
        logger.info("interlocutors collection already exists")
    
    collection = db["interlocutors"]
    
    # Create indexes
    indexes = [
        # Unique index on user_id
        {
            "keys": [("user_id", ASCENDING)],
            "name": "user_id_unique_idx",
            "unique": True,
            "background": True
        },
        # Index on created_at for sorting
        {
            "keys": [("created_at", ASCENDING)],
            "name": "created_at_idx",
            "background": True
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
        {"migration_id": "004_create_interlocutors_collection"},
        {
            "$set": {
                "migration_id": "004_create_interlocutors_collection",
                "description": "Create interlocutors collection with indexes",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed"
            }
        },
        upsert=True
    )
    
    logger.info("interlocutors collection migration completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop interlocutors collection."""
    db = client[db_name]
    
    try:
        await db.drop_collection("interlocutors")
        logger.info("Dropped interlocutors collection")
    except Exception as e:
        logger.error(f"Failed to drop collection: {e}")
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": "004_create_interlocutors_collection"
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
            "migration_id": "004_create_interlocutors_collection",
            "status": "completed"
        })
        
        if existing:
            logger.info("Migration 004 already applied. Skipping...")
            client.close()
            return
        
        # Run migration
        await up(client, db_name)
        
        # Verify
        collections = await db.list_collection_names()
        if "interlocutors" in collections:
            logger.info("✅ interlocutors collection created successfully")
            indexes = await db["interlocutors"].list_indexes().to_list(None)
            logger.info(f"Indexes created: {[idx['name'] for idx in indexes]}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

