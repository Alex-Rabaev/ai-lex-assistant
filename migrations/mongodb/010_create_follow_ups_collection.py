"""
Create follow_ups collection with indexes.

This migration creates the follow_ups collection for tracking
follow-up reminders sent to respondents who abandoned surveys.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_ID = "010_create_follow_ups_collection"


async def up(client: AsyncIOMotorClient, db_name: str):
    """
    Create follow_ups collection and indexes.

    Collection tracks reminder attempts per conversation.
    """
    db = client[db_name]

    # Create collection (MongoDB creates on first insert; we create explicitly)
    if "follow_ups" not in await db.list_collection_names():
        await db.create_collection("follow_ups")
        logger.info("Created follow_ups collection")
    else:
        logger.info("follow_ups collection already exists")

    collection = db["follow_ups"]

    # Create indexes
    indexes = [
        {"keys": [("conversation_id", ASCENDING)], "unique": True, "name": "idx_conversation_id_unique"},
        {"keys": [("assistant_id", ASCENDING), ("status", ASCENDING)], "name": "idx_assistant_status"},
    ]

    for spec in indexes:
        unique = spec.pop("unique", False)
        try:
            await collection.create_index(spec["keys"], unique=unique, name=spec["name"])
            logger.info(f"Created index: {spec['name']}")
        except Exception as e:
            if "already exists" in str(e):
                logger.info(f"Index {spec['name']} already exists")
            else:
                raise

    await db["migration_history"].update_one(
        {"migration_id": MIGRATION_ID},
        {
            "$set": {
                "migration_id": MIGRATION_ID,
                "description": "Create follow_ups collection for reminder tracking",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed",
            }
        },
        upsert=True,
    )
    logger.info("Migration 010 completed successfully")


async def down(client: AsyncIOMotorClient, db_name: str):
    """Drop follow_ups collection."""
    db = client[db_name]
    await db["follow_ups"].drop()
    await db["migration_history"].delete_one({"migration_id": MIGRATION_ID})
    logger.info("Rollback of 010 completed")


async def main():
    """Run migration."""
    try:
        from app.config import config

        client = AsyncIOMotorClient(config.MONGODB_URL)
        db_name = config.MONGODB_DB_NAME
        db = client[db_name]

        existing = await db["migration_history"].find_one(
            {"migration_id": MIGRATION_ID, "status": "completed"}
        )
        if existing:
            logger.info(f"Migration {MIGRATION_ID} already applied. Skipping...")
            client.close()
            return

        await up(client, db_name)
        client.close()
        logger.info(f"✅ Migration {MIGRATION_ID} completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
