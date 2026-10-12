"""Export service for respondent data (CSV / JSON).

Collects data from conversations, messages, and interlocutors,
then formats it for CSV or JSON download.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.modules.assistants.service import AssistantService
from app.modules.conversations.service import ConversationsService
from app.modules.conversations.models.conversation import Conversation

logger = logging.getLogger(__name__)

CSV_BOM = "\ufeff"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

MAX_RESPONDENTS = 2000


class ExportService:
    """Collects and formats respondent data for export."""

    def __init__(
        self,
        assistant_service: Optional[AssistantService] = None,
        conversations_service: Optional[ConversationsService] = None,
    ):
        self.assistant_service = assistant_service or AssistantService()
        self._conversations = conversations_service or ConversationsService()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _verify_assistant(self, assistant_id: str, user_id: str):
        """Verify assistant exists and user has access (raises on failure)."""
        return await self.assistant_service.get_assistant(assistant_id, user_id)

    async def _get_filtered_conversations(
        self,
        assistant_id: str,
        include_mock: bool = False,
        conversation_ids: Optional[List[str]] = None,
        stages: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Conversation]:
        """Fetch conversations with filters applied."""
        mock_filter: Optional[bool] = None if include_mock else False
        conversations = await self._conversations.get_conversations_by_assistant(
            assistant_id, include_mock=mock_filter
        )

        if conversation_ids:
            id_set = set(conversation_ids)
            conversations = [c for c in conversations if str(c.id) in id_set]

        if stages:
            stage_set = set(stages)
            conversations = [
                c for c in conversations if c.get_current_stage() in stage_set
            ]

        if date_from:
            conversations = [c for c in conversations if c.created_at and c.created_at >= date_from]
        if date_to:
            conversations = [c for c in conversations if c.created_at and c.created_at <= date_to]

        return conversations[:limit]

    async def _get_interlocutor_map(
        self, interlocutor_ids: List[str]
    ) -> Dict[str, Any]:
        """Build {interlocutor_id_str: Interlocutor} map."""
        result: Dict[str, Any] = {}
        for iid in interlocutor_ids:
            interlocutor = await self._conversations.get_interlocutor_by_id(iid)
            if interlocutor:
                result[iid] = interlocutor
        return result

    # ------------------------------------------------------------------
    # Endpoint 1 — single respondent messages
    # ------------------------------------------------------------------

    async def get_single_messages(
        self,
        assistant_id: str,
        interlocutor_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Return list of message dicts for one respondent.

        Returns:
            List of dicts with keys: date, role, message, respondent, stage
        """
        await self._verify_assistant(assistant_id, user_id)

        conversation = await self._conversations.get_conversation_by_interlocutor_and_assistant(
            interlocutor_id, assistant_id
        )
        if not conversation:
            return []

        messages = await self._conversations.get_full_history(
            str(conversation.id), limit=10_000
        )

        return [
            {
                "date": msg.created_at.strftime(DATE_FORMAT) if msg.created_at else "",
                "role": msg.role,
                "message": msg.content,
                "respondent": interlocutor_id,
                "stage": msg.state,
            }
            for msg in messages
            if msg.role in ("user", "assistant")
        ]

    def single_messages_to_csv(self, rows: List[Dict[str, Any]]) -> str:
        """Serialize single-respondent messages to CSV string."""
        buf = io.StringIO()
        buf.write(CSV_BOM)
        writer = csv.DictWriter(
            buf,
            fieldnames=["date", "role", "message", "respondent", "stage"],
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Endpoint 2 — bulk messages
    # ------------------------------------------------------------------

    async def get_bulk_messages(
        self,
        assistant_id: str,
        user_id: str,
        include_mock: bool = False,
        conversation_ids: Optional[List[str]] = None,
        stages: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Return bulk messages export dict."""
        await self._verify_assistant(assistant_id, user_id)

        conversations = await self._get_filtered_conversations(
            assistant_id,
            include_mock=include_mock,
            conversation_ids=conversation_ids,
            stages=stages,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

        interlocutor_ids = list({str(c.interlocutor_id) for c in conversations})
        interlocutor_map = await self._get_interlocutor_map(interlocutor_ids)

        respondents = []
        total_messages = 0

        for conv in conversations:
            iid = str(conv.interlocutor_id)
            interlocutor = interlocutor_map.get(iid)
            name = interlocutor.first_name if interlocutor else None

            messages = await self._conversations.get_full_history(
                str(conv.id), limit=10_000
            )
            filtered = [m for m in messages if m.role in ("user", "assistant")]
            total_messages += len(filtered)

            respondents.append({
                "respondent_id": iid,
                "name": name,
                "messages": [
                    {
                        "date": m.created_at.strftime(DATE_FORMAT) if m.created_at else "",
                        "role": m.role,
                        "message": m.content,
                        "stage": m.state,
                    }
                    for m in filtered
                ],
            })

        return {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_respondents": len(respondents),
            "total_messages": total_messages,
            "respondents": respondents,
        }

    def bulk_messages_to_csv(self, data: Dict[str, Any]) -> str:
        """Serialize bulk messages to flat CSV string."""
        buf = io.StringIO()
        buf.write(CSV_BOM)
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["date", "role", "message", "respondent_id", "respondent_name", "stage"])

        for resp in data.get("respondents", []):
            rid = resp["respondent_id"]
            name = resp.get("name") or ""
            for msg in resp.get("messages", []):
                writer.writerow([
                    msg["date"],
                    msg["role"],
                    msg["message"],
                    rid,
                    name,
                    msg.get("stage") or "",
                ])
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Endpoint 3 — bulk respondents / survey
    # ------------------------------------------------------------------

    async def get_bulk_respondents(
        self,
        assistant_id: str,
        user_id: str,
        include_mock: bool = False,
        conversation_ids: Optional[List[str]] = None,
        stages: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Return bulk respondent/survey export dict."""
        await self._verify_assistant(assistant_id, user_id)

        conversations = await self._get_filtered_conversations(
            assistant_id,
            include_mock=include_mock,
            conversation_ids=conversation_ids,
            stages=stages,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

        interlocutor_ids = list({str(c.interlocutor_id) for c in conversations})
        interlocutor_map = await self._get_interlocutor_map(interlocutor_ids)

        respondents = []
        total_responses = 0

        for conv in conversations:
            iid = str(conv.interlocutor_id)
            interlocutor = interlocutor_map.get(iid)

            name = interlocutor.first_name if interlocutor else None
            email = (interlocutor.profile.get("email") if interlocutor and interlocutor.profile else None)
            profile_summary = (
                interlocutor.profile.get("profile_summary")
                if interlocutor and interlocutor.profile
                else None
            )

            survey_summary = conv.get_agent_metadata().get("survey_summary", [])
            survey = [
                {"question": item.get("question", ""), "answer": item.get("answer", "")}
                for item in survey_summary
                if isinstance(item, dict)
            ]
            total_responses += len(survey)

            respondents.append({
                "respondent_id": iid,
                "name": name,
                "email": email,
                "profile_summary": profile_summary,
                "survey": survey,
            })

        return {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_respondents": len(respondents),
            "total_responses": total_responses,
            "respondents": respondents,
        }

    def bulk_respondents_to_csv(self, data: Dict[str, Any]) -> str:
        """Serialize bulk respondent/survey data to flat CSV string.

        Each row = one question-answer pair.
        email and profile_summary are only written on the first row per respondent.
        """
        buf = io.StringIO()
        buf.write(CSV_BOM)
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["#", "respondent_id", "name", "email", "question", "answer", "profile_summary"])

        row_num = 1
        for resp in data.get("respondents", []):
            rid = resp["respondent_id"]
            name = resp.get("name") or ""
            email = resp.get("email") or ""
            profile_summary = resp.get("profile_summary") or ""
            survey = resp.get("survey", [])

            if not survey:
                writer.writerow([row_num, rid, name, email, "", "", profile_summary])
                row_num += 1
                continue

            for i, item in enumerate(survey):
                is_first = i == 0
                writer.writerow([
                    row_num,
                    rid,
                    name,
                    email if is_first else "",
                    item.get("question", ""),
                    item.get("answer", ""),
                    profile_summary if is_first else "",
                ])
                row_num += 1

        return buf.getvalue()
