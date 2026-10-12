"""Unit tests for mock respondent generator."""

import pytest
from app.modules.analysis.mock_generator import (
    STAGE_COMPLETED,
    STAGE_QUESTIONNAIRE,
    generate_mock_dialogues,
)


class TestGenerateMockDialogues:
    """Tests for generate_mock_dialogues."""

    def test_returns_requested_count(self):
        result = generate_mock_dialogues(count=5, language="en", include_abandoned=False)
        assert len(result) == 5

    def test_each_item_is_stage_and_messages(self):
        result = generate_mock_dialogues(count=3, language="en", include_abandoned=True)
        for stage, messages in result:
            assert stage in (STAGE_COMPLETED, STAGE_QUESTIONNAIRE)
            assert isinstance(messages, list)
            assert len(messages) >= 1
            for role, content, msg_state in messages:
                assert role in ("user", "assistant")
                assert isinstance(content, str)
                assert len(content) > 0
                assert isinstance(msg_state, str)

    def test_only_real_stages_used(self):
        """No uppercase or invented stages — only 'completed' and 'questionnaire'."""
        result = generate_mock_dialogues(count=20, include_abandoned=True)
        for stage, _ in result:
            assert stage in (STAGE_COMPLETED, STAGE_QUESTIONNAIRE), f"Unexpected stage: {stage}"

    def test_messages_have_user_and_assistant(self):
        result = generate_mock_dialogues(count=2, include_abandoned=False)
        for _, messages in result:
            roles = [m[0] for m in messages]
            assert "user" in roles
            assert "assistant" in roles

    def test_language_accepted(self):
        result = generate_mock_dialogues(count=2, language="ru", include_abandoned=False)
        assert len(result) == 2

    def test_completed_has_completed_stage_messages(self):
        result = generate_mock_dialogues(count=15, include_abandoned=False)
        completed = [r for r in result if r[0] == STAGE_COMPLETED]
        if completed:
            _, messages = completed[0]
            assert STAGE_COMPLETED in [m[2] for m in messages]

    def test_question_answers_used_in_dialogues(self):
        q1 = "How would you rate from 1 to 5?"
        q2 = "What is your main challenge?"
        result = generate_mock_dialogues(
            count=5,
            include_abandoned=False,
            assistant_context={
                "questions": [q1, q2],
                "question_answers": {
                    q1: ["Definitely 5", "I'd say 4", "About 3", "Top score", "Good enough"],
                    q2: ["Pricing", "Integration", "Support speed", "Onboarding", "Documentation"],
                },
            },
        )
        assert len(result) == 5
        user_answers = [
            content
            for _, messages in result
            for role, content, state in messages
            if role == "user" and state == STAGE_QUESTIONNAIRE
        ]
        combined = {"Definitely 5", "I'd say 4", "About 3", "Top score", "Good enough",
                    "Pricing", "Integration", "Support speed", "Onboarding", "Documentation"}
        assert any(a in combined for a in user_answers)

    def test_fallback_when_no_question_answers(self):
        result = generate_mock_dialogues(
            count=3,
            include_abandoned=False,
            assistant_context={"questions": ["What is your budget?", "When do you need it?"]},
        )
        assert len(result) == 3

    def test_completed_respondents_answer_all_questions(self):
        """Completed mocks must include all questions from the list."""
        questions = ["Q1", "Q2", "Q3", "Q4", "Q5"]
        result = generate_mock_dialogues(
            count=5,
            include_abandoned=False,
            assistant_context={"questions": questions},
        )
        for stage, messages in result:
            assert stage == STAGE_COMPLETED
            assistant_questions = [m[1] for m in messages if m[0] == "assistant" and m[2] == STAGE_QUESTIONNAIRE]
            assert len(assistant_questions) == len(questions), (
                f"Expected {len(questions)} questions, got {len(assistant_questions)}"
            )
            assert set(assistant_questions) == set(questions)
