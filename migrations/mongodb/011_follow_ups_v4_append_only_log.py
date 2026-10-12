"""
Migrate follow_ups collection to v4 append-only log schema.

Drops legacy per-conversation unique index and assistant/status index,
removes existing documents (cutover), and creates (conversation_id, created_at).
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

sys.path.append(str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_ID = "011_follow_ups_v4_append_only_log"

LEGACY_INDEXES = ("idx_conversation_id_unique", "idx_assistant_status")
NEW_INDEX_NAME = "idx_follow_ups_conversation_created"


async def up(client: AsyncIOMotorClient, db_name: str) -> None:
    db = client[db_name]
    if "follow_ups" not in await db.list_collection_names():
        await db.create_collection("follow_ups")
        logger.info("Created follow_ups collection")
    collection = db["follow_ups"]

    for name in LEGACY_INDEXES:
        try:
            await collection.drop_index(name)
            logger.info("Dropped legacy index %s", name)
        except Exception as e:
            if "index not found" in str(e).lower() or "ns not found" in str(e).lower():
                logger.info("Index %s not present, skip", name)
            else:
                raise

    del_result = await collection.delete_many({})
    logger.info(
        "follow_ups cutover: removed %s legacy document(s)",
        del_result.deleted_count,
    )

    try:
        await collection.create_index(
            [("conversation_id", ASCENDING), ("created_at", ASCENDING)],
            name=NEW_INDEX_NAME,
        )
        logger.info("Created index %s", NEW_INDEX_NAME)
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info("Index %s already exists", NEW_INDEX_NAME)
        else:
            raise

    await db["migration_history"].update_one(
        {"migration_id": MIGRATION_ID},
        {
            "$set": {
                "migration_id": MIGRATION_ID,
                "description": "follow_ups v4: append-only log, compound index",
                "applied_at": datetime.now(timezone.utc),
                "status": "completed",
            }
        },
        upsert=True,
    )


async def down(client: AsyncIOMotorClient, db_name: str) -> None:
    db = client[db_name]
    collection = db["follow_ups"]
    try:
        await collection.drop_index(NEW_INDEX_NAME)
    except Exception:
        pass
    await db["migration_history"].delete_one({"migration_id": MIGRATION_ID})


async def main() -> None:
    from app.config import config

    client = AsyncIOMotorClient(config.MONGODB_URL)
    db_name = config.MONGODB_DB_NAME
    db = client[db_name]

    existing = await db["migration_history"].find_one(
        {"migration_id": MIGRATION_ID, "status": "completed"}
    )
    if existing:
        logger.info("Migration %s already applied. Skipping.", MIGRATION_ID)
        client.close()
        return

    await up(client, db_name)
    client.close()
    logger.info("Migration %s completed", MIGRATION_ID)


if __name__ == "__main__":
    asyncio.run(main())
