"""
Add analytic_meta field to conversations collection.

This migration adds the analytic_meta field (nullable) to the conversations
collection for storing respondent analytics data.

The field is Optional and defaults to None, so existing documents
don't need to be updated - MongoDB handles missing fields gracefully.
"""

import asyncio
import logging
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_ID = "007_add_analytic_meta_to_conversations"


async def up(client: AsyncIOMotorClient, db_name: str):
    """
    Add analytic_meta field to conversations.
    
    Since the field is nullable and MongoDB is schemaless,
    we don't need to update existing documents.
    The Pydantic model handles None/missing values gracefully.
    
    This migration primarily:
    1. Records that the schema has been extended
    2. Verifies the conversations collection exists
    """
    db = client[db_name]
    
    # Verify conversations collection exists
    collections = await db.list_collection_names()
    if "conversations" not in collections:
        logger.warning("conversations collection does not exist - skipping migration")
        return
    
    logger.info("conversations collection found")
    
    # Note: We don't need to update existing documents because:
    # 1. analytic_meta is Optional[Dict[str, Any]] with default=None
    # 2. MongoDB returns None for missing fields
    # 3. Pydantic model handles None gracefully
    
    # Count existing conversations for logging
    count = await db["conversations"].count_documents({})
    logger.info(f"Found {count} existing conversations - they will have analytic_meta=null")
    
    # Record migration in history
    await db["migration_history"].update_one(
        {"migration_id": MIGRATION_ID},
        {
            "$set": {
                "migration_id": MIGRATION_ID,
                "description": "Add analytic_meta field to conversations collection",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed",
                "notes": f"Schema extended, {count} existing documents unmodified"
            }
        },
        upsert=True
    )
    
    logger.info("Migration completed successfully - analytic_meta field added to schema")


async def down(client: AsyncIOMotorClient, db_name: str):
    """
    Remove analytic_meta field from all conversations.
    
    This removes the field from all documents that have it.
    """
    db = client[db_name]
    
    # Remove analytic_meta from all documents that have it
    result = await db["conversations"].update_many(
        {"analytic_meta": {"$exists": True}},
        {"$unset": {"analytic_meta": ""}}
    )
    
    logger.info(f"Removed analytic_meta from {result.modified_count} conversations")
    
    # Remove migration from history
    await db["migration_history"].delete_one({
        "migration_id": MIGRATION_ID
    })
    
    logger.info("Migration rollback completed")


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
        migration_record = await db["migration_history"].find_one({
            "migration_id": MIGRATION_ID
        })
        if migration_record and migration_record.get("status") == "completed":
            logger.info(f"✅ Migration {MIGRATION_ID} completed successfully")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
