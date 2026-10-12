"""
Migration 012: Backfill last_user_message_at on conversations.

For conversations that don't have last_user_message_at set,
derive it from the most recent user message in conversation_history.
Idempotent — skips conversations that already have the field.
"""

import asyncio
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import config

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def run_migration():
    client = AsyncIOMotorClient(config.MONGODB_URL)
    db = client[config.MONGODB_DB_NAME]
    conversations = db["conversations"]
    history = db["conversation_history"]

    cursor = conversations.find(
        {"last_user_message_at": {"$exists": False}},
        {"_id": 1},
    )
    conv_ids = [doc["_id"] async for doc in cursor]
    total = len(conv_ids)
    logger.info("Backfill: %d conversations without last_user_message_at", total)

    updated = 0
    for i in range(0, total, BATCH_SIZE):
        batch = conv_ids[i : i + BATCH_SIZE]
        for cid in batch:
            pipeline = [
                {"$match": {"conversation_id": cid, "role": "user"}},
                {"$sort": {"created_at": -1}},
                {"$limit": 1},
                {"$project": {"created_at": 1}},
            ]
            docs = await history.aggregate(pipeline).to_list(length=1)
            if docs:
                ts = docs[0]["created_at"]
            else:
                ts = None

            if ts is not None:
                await conversations.update_one(
                    {"_id": cid},
                    {"$set": {"last_user_message_at": ts, "updated_at": datetime.now(timezone.utc)}},
                )
                updated += 1

        logger.info("Backfill progress: %d / %d (updated %d)", min(i + BATCH_SIZE, total), total, updated)

    logger.info("Backfill complete: %d conversations updated out of %d", updated, total)

    await conversations.create_index(
        [("assistant_id", 1), ("last_user_message_at", 1)],
        name="idx_conversations_assistant_last_user_msg",
        sparse=True,
    )
    logger.info("Created index idx_conversations_assistant_last_user_msg")

    client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_migration())
