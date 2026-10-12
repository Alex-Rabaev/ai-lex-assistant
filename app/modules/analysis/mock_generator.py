"""Mock respondent dialogue generator.

Primary path: LLM generates full realistic dialogues following the assistant's actual
step configuration (all enabled steps in order, all questions answered).

Fallback path (when no steps config or LLM fails): template-based dialogue using
only questionnaire questions with pre-defined answer pool.
"""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

STAGE_COMPLETED = "completed"
STAGE_QUESTIONNAIRE = "questionnaire"

MAX_QUESTIONS = 100  # upper cap for question list (completed mocks use ALL questions)

# Fallback templates
_FALLBACK_QUESTIONS = [
    "How would you rate your experience from 1 to 5?",
    "What is your main goal?",
    "Any additional comments?",
]
_FALLBACK_ANSWERS = [
    "I'd say 4 out of 5",
    "Quality is the most important factor for me",
    "We are a team of about 15 people",
    "I've been using it for two years and I'm mostly satisfied",
    "The onboarding was smooth, support is good",
]
_GREETINGS = ["Hi", "Hello", "Good day"]
_INTROS = [
    "Welcome! I'll ask you a few questions.",
    "Thanks for your time. Let's start.",
]
_CLOSING = [
    "Thank you for completing the survey!",
    "We have received your answers. Goodbye!",
]
_MOCK_NAMES = [
    "Alex", "Jordan", "Morgan", "Casey", "Riley", "Taylor", "Sam", "Quinn",
    "Blake", "Drew", "Avery", "Cameron", "Logan", "Dylan", "Peyton",
    "Sage", "River", "Skyler", "Finley", "Rowan",
]


def _pick(items: List[str]) -> str:
    return random.choice(items)


def _answer_for(question: str, question_answers: Dict[str, List[str]]) -> str:
    pool = question_answers.get(question)
    if pool:
        return _pick(pool)
    return _pick(_FALLBACK_ANSWERS)


def _build_fallback_completed(
    questions: List[str],
    num_questions: int,
    question_answers: Dict[str, List[str]],
) -> List[Tuple[str, str, str]]:
    messages: List[Tuple[str, str, str]] = []
    messages.append(("user", _pick(_GREETINGS), "intro"))
    messages.append(("assistant", _pick(_INTROS), "intro"))
    for q in questions[:num_questions]:
        messages.append(("assistant", q, STAGE_QUESTIONNAIRE))
        messages.append(("user", _answer_for(q, question_answers), STAGE_QUESTIONNAIRE))
    messages.append(("assistant", _pick(_CLOSING), STAGE_COMPLETED))
    messages.append(("user", "Thanks, bye!", STAGE_COMPLETED))
    return messages


def _build_fallback_partial(
    questions: List[str],
    num_questions: int,
    question_answers: Dict[str, List[str]],
) -> List[Tuple[str, str, str]]:
    messages: List[Tuple[str, str, str]] = []
    messages.append(("user", _pick(_GREETINGS), "intro"))
    messages.append(("assistant", _pick(_INTROS), "intro"))
    for q in questions[:num_questions]:
        messages.append(("assistant", q, STAGE_QUESTIONNAIRE))
        messages.append(("user", _answer_for(q, question_answers), STAGE_QUESTIONNAIRE))
    return messages


def _fallback_generate(
    count: int,
    include_partial: bool,
    question_answers: Dict[str, List[str]],
    questions: List[str],
) -> List[Dict[str, Any]]:
    """Template-based fallback when no step config or LLM fails."""
    result = []
    num_partial = random.randint(max(0, count // 4), max(1, count // 3)) if include_partial else 0
    num_completed = count - num_partial
    q_max = len(questions)
    names = random.sample(_MOCK_NAMES * ((count // len(_MOCK_NAMES)) + 2), count)

    for i in range(num_completed):
        # Completed respondents answer ALL questions from the list
        n = q_max
        result.append({
            "respondent_name": names[i],
            "final_state": STAGE_COMPLETED,
            "messages": [
                {"role": r, "content": c, "state": s}
                for r, c, s in _build_fallback_completed(questions, n, question_answers)
            ],
        })
    for i in range(num_partial):
        n = 1 if (include_partial and random.random() < 0.3) else random.randint(1, max(1, min(3, q_max)))
        result.append({
            "respondent_name": names[num_completed + i],
            "final_state": STAGE_QUESTIONNAIRE,
            "messages": [
                {"role": r, "content": c, "state": s}
                for r, c, s in _build_fallback_partial(questions, n, question_answers)
            ],
        })
    random.shuffle(result)
    return result


def dialogues_to_tuples(
    dialogues: List[Dict[str, Any]],
) -> List[Tuple[str, str, List[Tuple[str, str, str]]]]:
    """Convert LLM dialogue dicts to (name, stage, messages) tuples.

    Args:
        dialogues: Output from generate_full_mock_dialogues_llm or _fallback_generate.

    Returns:
        List of (respondent_name, final_state, [(role, content, state), ...])
    """
    result = []
    for d in dialogues:
        name = d.get("respondent_name", "Mock User")
        stage = d.get("final_state", STAGE_QUESTIONNAIRE)
        messages = [
            (m["role"], m["content"], m.get("state", STAGE_QUESTIONNAIRE))
            for m in d.get("messages", [])
            if m.get("role") and m.get("content")
        ]
        if messages:
            result.append((name, stage, messages))
    return result


def generate_mock_dialogues(
    count: int,
    language: str = "en",
    include_abandoned: bool = True,
    assistant_context: Optional[dict] = None,
) -> List[Tuple[str, List[Tuple[str, str, str]]]]:
    """Fallback-compatible entry point (no async, template-based only).

    Used when no LLM is available or no steps config is provided.
    For full step-aware LLM generation use generate_mock_dialogues_async.

    Returns:
        List of (stage, messages) tuples — legacy format without respondent name.
    """
    question_answers: Dict[str, List[str]] = {}
    questions = _FALLBACK_QUESTIONS

    if assistant_context:
        qs = [q for q in (assistant_context.get("questions") or []) if q and q.strip()]
        if qs:
            questions = qs[:MAX_QUESTIONS]
        question_answers = assistant_context.get("question_answers") or {}

    dialogues = _fallback_generate(
        count=count,
        include_partial=include_abandoned,
        question_answers=question_answers,
        questions=questions,
    )
    return [
        (d["final_state"], [(m["role"], m["content"], m["state"]) for m in d["messages"]])
        for d in dialogues
    ]
