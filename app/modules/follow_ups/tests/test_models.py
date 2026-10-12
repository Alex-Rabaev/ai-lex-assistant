"""Tests for follow_ups v4 models."""

from datetime import datetime, timezone
from bson import ObjectId

from app.modules.follow_ups.models import (
    FollowUpLogEntry,
    FollowUpReasonCode,
    SendReminderResponse,
    SendReminderResult,
)
from app.modules.follow_ups import service as fu_service


class TestSendReminderResult:
    def test_sent_true(self):
        r = SendReminderResult(sent=True)
        assert r.sent is True
        assert r.reason is None

    def test_sent_false_with_reason(self):
        r = SendReminderResult(sent=False, reason="opted_out")
        assert r.sent is False
        assert r.reason == "opted_out"


class TestFollowUpReasonCode:
    def test_all_service_constants_in_enum(self):
        """Every REASON_* constant in the service module must be a valid enum member."""
        service_reasons = {
            v
            for k, v in vars(fu_service).items()
            if k.startswith("REASON_") and isinstance(v, str)
        }
        enum_values = {e.value for e in FollowUpReasonCode}
        assert service_reasons == enum_values

    def test_enum_count(self):
        assert len(FollowUpReasonCode) == 10


class TestSendReminderResponse:
    def test_sent_true_omits_reason_when_excluded(self):
        r = SendReminderResponse(sent=True, conversation_id="abc")
        dump = r.model_dump(exclude_none=True)
        assert "reason" not in dump

    def test_sent_false_includes_reason(self):
        r = SendReminderResponse(
            sent=False, conversation_id="abc", reason="blocked"
        )
        dump = r.model_dump()
        assert dump["reason"] == "blocked"

    def test_reason_accepts_string_matching_enum(self):
        r = SendReminderResponse(
            sent=False, conversation_id="x", reason="whatsapp_24h_passed"
        )
        assert r.reason == FollowUpReasonCode.whatsapp_24h_passed


class TestFollowUpLogEntry:
    def test_from_mongo_doc(self):
        conv_id = ObjectId()
        asst_id = ObjectId()
        inter_id = ObjectId()
        now = datetime.now(timezone.utc)
        doc = {
            "_id": ObjectId(),
            "conversation_id": conv_id,
            "assistant_id": asst_id,
            "interlocutor_id": inter_id,
            "created_at": now,
            "updated_at": now,
        }
        entry = FollowUpLogEntry(**doc)
        assert str(entry.conversation_id) == str(conv_id)
        assert str(entry.assistant_id) == str(asst_id)
        assert str(entry.interlocutor_id) == str(inter_id)
