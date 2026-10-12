"""Repository for follow_ups append-only log (v4)."""

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.modules.follow_ups.models import FollowUpLogEntry

logger = logging.getLogger(__name__)


class FollowUpRepository:
    """Append-only log in `follow_ups` collection."""

    def __init__(self):
        self._db = None
        self._collection: Optional[AsyncIOMotorCollection] = None

    async def _ensure_db(self) -> None:
        if self._db is None:
            from app.common.db.database import get_database

            self._db = await get_database()
            self._collection = self._db["follow_ups"]
            await self._collection.create_index(
                [("conversation_id", 1), ("created_at", 1)],
                name="idx_follow_ups_conversation_created",
            )

    async def append_log_entry(
        self,
        conversation_id: str,
        assistant_id: str,
        interlocutor_id: str,
        created_at: Optional[datetime] = None,
    ) -> FollowUpLogEntry:
        """Insert one log row (call only after successful delivery)."""
        await self._ensure_db()
        now = created_at or datetime.now(timezone.utc)
        doc = {
            "conversation_id": ObjectId(conversation_id),
            "assistant_id": ObjectId(assistant_id),
            "interlocutor_id": ObjectId(interlocutor_id),
            "created_at": now,
        }
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(
            "Follow-up log append: conversation=%s assistant=%s id=%s",
            conversation_id,
            assistant_id,
            result.inserted_id,
        )
        return FollowUpLogEntry(**doc)

    async def count_since(self, conversation_id: str, after: datetime) -> int:
        """Number of log entries with created_at strictly after `after`."""
        await self._ensure_db()
        return await self._collection.count_documents(
            {
                "conversation_id": ObjectId(conversation_id),
                "created_at": {"$gt": after},
            }
        )

    async def last_sent_at_since(
        self, conversation_id: str, after: datetime
    ) -> Optional[datetime]:
        """Max created_at among entries after `after`, or None."""
        await self._ensure_db()
        cursor = (
            self._collection.find(
                {
                    "conversation_id": ObjectId(conversation_id),
                    "created_at": {"$gt": after},
                },
                projection={"created_at": 1},
            )
            .sort("created_at", -1)
            .limit(1)
        )
        docs = await cursor.to_list(length=1)
        if not docs:
            return None
        ts = docs[0]["created_at"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts

    async def delete_by_conversation(self, conversation_id: str) -> int:
        """Remove all log rows for a conversation (e.g. full reset)."""
        await self._ensure_db()
        result = await self._collection.delete_many(
            {"conversation_id": ObjectId(conversation_id)}
        )
        if result.deleted_count:
            logger.info(
                "Deleted %s follow_up log rows for conversation %s",
                result.deleted_count,
                conversation_id,
            )
        return result.deleted_count
