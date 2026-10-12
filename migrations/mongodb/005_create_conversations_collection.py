"""
Create conversations collection with indexes.

This migration creates the conversations collection for storing
dialogue state between interlocutors and assistants.
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
    """Create conversations collection and indexes."""
    db = client[db_name]
    
    try:
        # Create collection
        await db.create_collection("conversations")
        logger.info("Created conversations collection")
    except CollectionInvalid:
        logger.info("conversations collection already exists")
    
    collection = db["conversations"]
    
    # Create indexes
    indexes = [
        # Unique compound index on (interlocutor_id, assistant_id)
        {
            "keys": [("interlocutor_id", ASCENDING), ("assistant_id", ASCENDING)],
            "name": "interlocutor_assistant_unique_idx",
            "unique": True,
            "background": True
        },
        # Index on assistant_id for finding all conversations of an assistant
        {
            "keys": [("assistant_id", ASCENDING)],
            "name": "assistant_idx",
            "background": True
        },
        # Index on interlocutor_id for finding all conversations of an interlocutor
        {
            "keys": [("interlocutor_id", ASCENDING)],
            "name": "interlocutor_idx",
            "background": True
        },
        # Index on connection_id
        {
            "keys": [("connection_id", ASCENDING)],
            "name": "connection_idx",
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
        {"migration_id": "005_create_conversations_collection"},
        {
            "$set": {
                "migration_id": "005_create_conversations_collection",
                "description": "Create conversations collection with indexes",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed"
            }
        },
        upsert=True
    )
    
    logger.info("conversations collection migration completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop conversations collection."""
    db = client[db_name]
    
    try:
        await db.drop_collection("conversations")
        logger.info("Dropped conversations collection")
    except Exception as e:
        logger.error(f"Failed to drop collection: {e}")
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": "005_create_conversations_collection"
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
            "migration_id": "005_create_conversations_collection",
            "status": "completed"
        })
        
        if existing:
            logger.info("Migration 005 already applied. Skipping...")
            client.close()
            return
        
        # Run migration
        await up(client, db_name)
        
        # Verify
        collections = await db.list_collection_names()
        if "conversations" in collections:
            logger.info("✅ conversations collection created successfully")
            indexes = await db["conversations"].list_indexes().to_list(None)
            logger.info(f"Indexes created: {[idx['name'] for idx in indexes]}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

