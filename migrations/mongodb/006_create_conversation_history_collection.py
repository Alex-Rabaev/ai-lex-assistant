"""
Create conversation_history collection with indexes.

This migration creates the conversation_history collection for storing
message history between interlocutors and assistants.
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
    """Create conversation_history collection and indexes."""
    db = client[db_name]
    
    try:
        # Create collection
        await db.create_collection("conversation_history")
        logger.info("Created conversation_history collection")
    except CollectionInvalid:
        logger.info("conversation_history collection already exists")
    
    collection = db["conversation_history"]
    
    # Create indexes
    indexes = [
        # Compound index for getting conversation history with sorting
        {
            "keys": [("conversation_id", ASCENDING), ("created_at", ASCENDING)],
            "name": "conversation_created_idx",
            "background": True
        },
        # Index on conversation_id for finding all messages
        {
            "keys": [("conversation_id", ASCENDING)],
            "name": "conversation_idx",
            "background": True
        },
        # Index on created_at for sorting
        {
            "keys": [("created_at", ASCENDING)],
            "name": "created_at_idx",
            "background": True
        },
        # Index on assistant_id
        {
            "keys": [("assistant_id", ASCENDING)],
            "name": "assistant_idx",
            "background": True
        },
        # Index on interlocutor_id
        {
            "keys": [("interlocutor_id", ASCENDING)],
            "name": "interlocutor_idx",
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
        {"migration_id": "006_create_conversation_history_collection"},
        {
            "$set": {
                "migration_id": "006_create_conversation_history_collection",
                "description": "Create conversation_history collection with indexes",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed"
            }
        },
        upsert=True
    )
    
    logger.info("conversation_history collection migration completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop conversation_history collection."""
    db = client[db_name]
    
    try:
        await db.drop_collection("conversation_history")
        logger.info("Dropped conversation_history collection")
    except Exception as e:
        logger.error(f"Failed to drop collection: {e}")
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": "006_create_conversation_history_collection"
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
            "migration_id": "006_create_conversation_history_collection",
            "status": "completed"
        })
        
        if existing:
            logger.info("Migration 006 already applied. Skipping...")
            client.close()
            return
        
        # Run migration
        await up(client, db_name)
        
        # Verify
        collections = await db.list_collection_names()
        if "conversation_history" in collections:
            logger.info("✅ conversation_history collection created successfully")
            indexes = await db["conversation_history"].list_indexes().to_list(None)
            logger.info(f"Indexes created: {[idx['name'] for idx in indexes]}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

