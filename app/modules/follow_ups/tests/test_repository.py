"""Tests for FollowUpRepository (v4 append-only)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

import pytest

from app.modules.follow_ups.models import FollowUpLogEntry
from app.modules.follow_ups.repository import FollowUpRepository


class TestFollowUpRepository:
    @pytest.fixture
    def repository(self):
        repo = FollowUpRepository()
        repo._db = MagicMock()
        repo._collection = MagicMock()
        return repo

    @pytest.mark.asyncio
    async def test_append_log_entry(self, repository):
        conv_id = str(ObjectId())
        asst_id = str(ObjectId())
        inter_id = str(ObjectId())
        inserted_id = ObjectId()
        repository._collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )

        result = await repository.append_log_entry(conv_id, asst_id, inter_id)

        assert isinstance(result, FollowUpLogEntry)
        repository._collection.insert_one.assert_called_once()
        call_doc = repository._collection.insert_one.call_args[0][0]
        assert call_doc["conversation_id"] == ObjectId(conv_id)
        assert call_doc["assistant_id"] == ObjectId(asst_id)
        assert call_doc["interlocutor_id"] == ObjectId(inter_id)

    @pytest.mark.asyncio
    async def test_count_since(self, repository):
        repository._collection.count_documents = AsyncMock(return_value=3)
        after = datetime(2025, 1, 1, tzinfo=timezone.utc)
        cid = str(ObjectId())

        n = await repository.count_since(cid, after)

        assert n == 3
        repository._collection.count_documents.assert_called_once()
        q = repository._collection.count_documents.call_args[0][0]
        assert q["conversation_id"] == ObjectId(cid)
        assert q["created_at"] == {"$gt": after}

    @pytest.mark.asyncio
    async def test_last_sent_at_since_found(self, repository):
        ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=[{"created_at": ts}])
        repository._collection.find = MagicMock(return_value=cursor)
        after = datetime(2025, 1, 1, tzinfo=timezone.utc)
        cid = str(ObjectId())

        out = await repository.last_sent_at_since(cid, after)

        assert out == ts

    @pytest.mark.asyncio
    async def test_last_sent_at_since_empty(self, repository):
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=[])
        repository._collection.find = MagicMock(return_value=cursor)

        out = await repository.last_sent_at_since(str(ObjectId()), datetime.now(timezone.utc))

        assert out is None

    @pytest.mark.asyncio
    async def test_delete_by_conversation(self, repository):
        repository._collection.delete_many = AsyncMock(
            return_value=MagicMock(deleted_count=2)
        )
        cid = str(ObjectId())

        n = await repository.delete_by_conversation(cid)

        assert n == 2
