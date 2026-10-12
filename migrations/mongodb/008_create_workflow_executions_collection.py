"""
Create workflow_executions collection with indexes.

This migration creates the workflow_executions collection for tracking
all workflow execution states and results.

Indexes are optimized for:
- Filtering by workflow type and status
- Sorting by creation time
- Compound type + time queries

Note: Deduplication is handled natively by Temporal via Workflow IDs.
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

MIGRATION_ID = "008_create_workflow_executions_collection"
COLLECTION_NAME = "workflow_executions"


async def up(client: AsyncIOMotorClient, db_name: str):
    """Create workflow_executions collection and indexes."""
    db = client[db_name]
    
    # Create collection
    try:
        await db.create_collection(COLLECTION_NAME)
        logger.info(f"Created {COLLECTION_NAME} collection")
    except CollectionInvalid:
        logger.info(f"{COLLECTION_NAME} collection already exists")
    
    collection = db[COLLECTION_NAME]
    
    # Define indexes
    # Note: deduplication is handled natively by Temporal via Workflow IDs
    indexes = [
        # Index for filtering by type and status
        {
            "keys": [("workflow_type", ASCENDING), ("status", ASCENDING)],
            "name": "type_status_idx",
            "background": True
        },
        # Index for sorting by creation time (newest first)
        {
            "keys": [("created_at", DESCENDING)],
            "name": "created_at_idx",
            "background": True
        },
        # Compound index for type + time sorting
        {
            "keys": [("workflow_type", ASCENDING), ("created_at", DESCENDING)],
            "name": "type_created_idx",
            "background": True
        },
    ]
    
    # Create indexes
    indexes_created = []
    for index_spec in indexes:
        try:
            keys = index_spec.pop("keys")
            await collection.create_index(keys, **index_spec)
            indexes_created.append(index_spec["name"])
            logger.info(f"Created index: {index_spec['name']}")
        except OperationFailure as e:
            if "already exists" in str(e):
                logger.info(f"Index {index_spec.get('name', 'unnamed')} already exists")
            else:
                logger.error(f"Failed to create index: {e}")
                raise
    
    # Record migration in history
    await db["migration_history"].update_one(
        {"migration_id": MIGRATION_ID},
        {
            "$set": {
                "migration_id": MIGRATION_ID,
                "description": "Create workflow_executions collection with indexes",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed",
                "indexes_created": indexes_created
            }
        },
        upsert=True
    )
    
    logger.info(f"{COLLECTION_NAME} collection migration completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop workflow_executions collection."""
    db = client[db_name]
    
    try:
        await db.drop_collection(COLLECTION_NAME)
        logger.info(f"Dropped {COLLECTION_NAME} collection")
    except Exception as e:
        logger.error(f"Failed to drop {COLLECTION_NAME} collection: {e}")
        raise
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": MIGRATION_ID
    })
    
    logger.info(f"Rollback of {MIGRATION_ID} completed")


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
            "migration_id": MIGRATION_ID,
            "status": "completed"
        })
        
        if existing:
            logger.info(f"Migration {MIGRATION_ID} already applied. Skipping...")
            client.close()
            return
        
        # Run migration
        await up(client, db_name)
        
        # Verify
        collections = await db.list_collection_names()
        if COLLECTION_NAME in collections:
            logger.info(f"✅ {COLLECTION_NAME} collection created successfully")
            indexes = await db[COLLECTION_NAME].list_indexes().to_list(None)
            logger.info(f"Indexes created: {[idx['name'] for idx in indexes]}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
