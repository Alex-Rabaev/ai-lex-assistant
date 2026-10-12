"""
Add follow_up_config field to assistants collection.

This migration adds the follow_up_config field with default values
to existing assistants that don't have it.

Default: enabled=True, idle_threshold_hours=23, max_attempts=1
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

MIGRATION_ID = "009_add_follow_up_config_to_assistants"

DEFAULT_FOLLOW_UP_CONFIG = {
    "enabled": True,
    "idle_threshold_hours": 23,
    "max_attempts": 1,
}


async def up(client: AsyncIOMotorClient, db_name: str):
    """
    Add follow_up_config with defaults to assistants that don't have it.
    """
    db = client[db_name]

    collections = await db.list_collection_names()
    if "assistants" not in collections:
        logger.warning("assistants collection does not exist - skipping migration")
        return

    result = await db["assistants"].update_many(
        {"$or": [{"follow_up_config": {"$exists": False}}, {"follow_up_config": None}]},
        {"$set": {"follow_up_config": DEFAULT_FOLLOW_UP_CONFIG, "updated_at": datetime.now(timezone.utc)}}
    )

    logger.info(f"Updated {result.modified_count} assistants with default follow_up_config")

    await db["migration_history"].update_one(
        {"migration_id": MIGRATION_ID},
        {
            "$set": {
                "migration_id": MIGRATION_ID,
                "description": "Add follow_up_config field to assistants with defaults",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed",
                "notes": f"Updated {result.modified_count} documents"
            }
        },
        upsert=True
    )


async def down(client: AsyncIOMotorClient, db_name: str):
    """Remove follow_up_config from all assistants."""
    db = client[db_name]

    result = await db["assistants"].update_many(
        {"follow_up_config": {"$exists": True}},
        {"$unset": {"follow_up_config": ""}}
    )

    logger.info(f"Removed follow_up_config from {result.modified_count} assistants")
    await db["migration_history"].delete_one({"migration_id": MIGRATION_ID})


async def main():
    """Run migration."""
    try:
        from app.config import config

        client = AsyncIOMotorClient(config.MONGODB_URL)
        db_name = config.MONGODB_DB_NAME

        existing = await client[db_name]["migration_history"].find_one({
            "migration_id": MIGRATION_ID,
            "status": "completed"
        })

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
