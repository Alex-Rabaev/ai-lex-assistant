"""LLM integration for analysis module.

Provides callable functions for LLM-based operations
like config generation and mock respondent answer generation.
"""

import asyncio
import json
import logging
import math
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config import config

logger = logging.getLogger(__name__)


async def generate_config_llm(prompt: str) -> str:
    """Call LLM to generate analysis config.

    Args:
        prompt: Formatted prompt string

    Returns:
        LLM response text (expected to be JSON)
    """
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY,
        model="gpt-4o",
        temperature=0.0,
        max_tokens=4096,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])

    logger.info(f"LLM generate_config response: {len(response.content)} chars")
    return response.content


_MOCK_ANSWERS_PROMPT = """You are helping generate test data for a survey analytics system.

For each survey question below, generate exactly 5 short, varied, realistic answers that different respondents might give.
Answers should be concise (1–2 sentences max), plausible, and cover different perspectives or options.

Survey questions:
{questions_block}

Return a JSON object with key "answers" — a list of lists, one inner list per question (in the same order), each containing exactly 5 answer strings.
Example format:
{{
  "answers": [
    ["answer1a", "answer1b", "answer1c", "answer1d", "answer1e"],
    ["answer2a", ...]
  ]
}}"""


async def generate_mock_answers_llm(questions: List[str]) -> Dict[str, List[str]]:
    """Generate 5 varied realistic answers per question using LLM.

    Args:
        questions: List of survey questions (up to 10)

    Returns:
        Dict mapping question text -> list of answer variants.
        Falls back to empty dict on any LLM error.
    """
    if not questions:
        return {}

    questions_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    prompt = _MOCK_ANSWERS_PROMPT.format(questions_block=questions_block)

    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY,
        model="gpt-4o-mini",
        temperature=0.9,
        max_tokens=2048,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        data = json.loads(response.content)
        raw = data.get("answers", [])
        result: Dict[str, List[str]] = {}
        for i, q in enumerate(questions):
            if i < len(raw) and isinstance(raw[i], list) and raw[i]:
                result[q] = [str(a) for a in raw[i] if a]
        logger.info(f"LLM generated mock answers for {len(result)} questions")
        return result
    except Exception as e:
        logger.warning(f"Failed to generate mock answers via LLM: {e}")
        return {}


_MOCK_DIALOGUE_PROMPT = """You are generating realistic mock survey respondent conversations for testing purposes.

The assistant is a survey bot with the following steps (in order):
{steps_description}

Generate {count} distinct mock respondent conversations.
Each respondent should feel like a different real person with unique background, tone, and answers.

Rules:
- Follow the step order exactly. For each enabled step, generate the appropriate exchange.
- For "lang" step: the user states or implies their language (e.g. "English" or "Hi" triggers English).
- For "intro" step: assistant greets and asks the respondent's name; user replies with a realistic name.
- For "profile" step: assistant asks about background/profile; user provides a realistic profile description.
- For "questionnaire" step: assistant asks EACH question listed; user answers each one specifically and realistically.
- For "additional_info" step: assistant requests the specified info (e.g. email, company size); user provides it.
- For "closing" step: assistant sends a closing/farewell message; user acknowledges.
- CRITICAL: completed respondents MUST answer EVERY question in the questionnaire (no skipping). Partial/abandoned respondents stop mid-questionnaire (30-50% of questions answered).
- Aim for {completed_count} completed and {partial_count} partial respondents.
- Messages must alternate: assistant first in each step, then user.

Return a JSON object:
{{
  "dialogues": [
    {{
      "respondent_name": "<first name only>",
      "final_state": "completed" or "questionnaire",
      "messages": [
        {{"role": "assistant" or "user", "content": "<text>", "state": "<step_key>"}},
        ...
      ]
    }},
    ...
  ]
}}

Step keys for the "state" field: {step_keys}
"""

# gpt-4o output limit; stay below to leave room for JSON wrapper
_MOCK_DIALOGUE_MAX_OUTPUT_TOKENS = 16_384
# Conservative completion tokens per dialogue (verbose models exceed naive counts)
_MOCK_TOKENS_PER_QUESTION_ESTIMATE = 520
_MOCK_TOKENS_DIALOGUE_OVERHEAD = 800


def _questionnaire_question_count(steps: List[Dict[str, Any]]) -> int:
    """How many fixed questionnaire questions are in assistant steps (for batch sizing)."""
    for step in steps:
        if step.get("step_key") != "questionnaire":
            continue
        meta = step.get("metadata") or {}
        ql = meta.get("questions_list")
        if ql and isinstance(ql, list):
            return len([q for q in ql if isinstance(q, str) and q.strip()])
        raw = meta.get("specific_questions") or ""
        return len([q for q in raw.splitlines() if q.strip()])
    return 0


def _mock_dialogue_batch_size(num_questions: int, total_count: int) -> int:
    """Smaller batches when surveys are long so each completion stays under token limit."""
    if total_count <= 1:
        return total_count
    per_dialogue = _MOCK_TOKENS_DIALOGUE_OVERHEAD + max(0, num_questions) * _MOCK_TOKENS_PER_QUESTION_ESTIMATE
    # Target max output per request (leave margin below model max)
    budget = _MOCK_DIALOGUE_MAX_OUTPUT_TOKENS - 2500
    per_batch = max(1, budget // max(per_dialogue, 1))
    return max(1, min(total_count, per_batch))


def _mock_llm_retryable_oversize_or_parse_error(exc: BaseException) -> bool:
    """True if failure may be fixed by smaller batches or a retry (truncated JSON, etc.)."""
    if isinstance(exc, json.JSONDecodeError):
        return True
    msg = str(exc).lower()
    if "length limit" in msg or "length_limit" in msg:
        return True
    if "token" in msg and ("limit" in msg or "maximum" in msg):
        return True
    if "could not parse" in msg and "json" in msg:
        return True
    if "unexpected end" in msg or "unterminated string" in msg:
        return True
    return False


def _batch_sizes(total: int, chunk: int) -> List[int]:
    """Split total into chunks of at most `chunk` (last may be smaller)."""
    if total <= 0:
        return []
    sizes: List[int] = []
    remaining = total
    while remaining > 0:
        n = min(chunk, remaining)
        sizes.append(n)
        remaining -= n
    return sizes


def _allocate_partials_across_batches(batch_sizes: List[int], total_partial: int) -> List[int]:
    """Hamilton: distribute total_partial across batches; each partial count <= batch size."""
    if not batch_sizes or total_partial <= 0:
        return [0] * len(batch_sizes)
    total = sum(batch_sizes)
    p = min(total_partial, total)
    exact = [p * n / total for n in batch_sizes]
    floors = [int(x) for x in exact]
    rem = p - sum(floors)
    order = sorted(range(len(batch_sizes)), key=lambda i: exact[i] - floors[i], reverse=True)
    for j in range(rem):
        floors[order[j]] += 1
    return [min(floors[i], batch_sizes[i]) for i in range(len(batch_sizes))]


async def _generate_mock_dialogues_llm_single_request(
    *,
    steps_description: str,
    step_keys_str: str,
    count: int,
    completed_count: int,
    partial_count: int,
) -> List[Dict[str, Any]]:
    """One Chat completion; returns dialogue dicts or raises."""
    prompt = _MOCK_DIALOGUE_PROMPT.format(
        steps_description=steps_description,
        count=count,
        completed_count=completed_count,
        partial_count=partial_count,
        step_keys=step_keys_str,
    )
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY,
        model="gpt-4o",
        temperature=0.9,
        max_tokens=_MOCK_DIALOGUE_MAX_OUTPUT_TOKENS,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    data = json.loads(response.content)
    return data.get("dialogues", [])


async def generate_full_mock_dialogues_llm(
    steps: List[Dict[str, Any]],
    count: int,
    include_partial: bool = True,
) -> List[Dict[str, Any]]:
    """Generate full mock respondent dialogues using LLM based on assistant step configuration.

    Each dialogue follows the actual enabled steps of the assistant in order.
    Completed respondents finish all steps; partial respondents stop mid-questionnaire.

    Args:
        steps: List of dicts with step_key, enabled, metadata (ordered by order_no).
        count: Total number of mock respondents to generate.
        include_partial: If True, ~30% of respondents will be partial (stopped mid-questionnaire).

    Returns:
        List of dialogue dicts: {respondent_name, final_state, messages: [{role, content, state}]}
        Returns empty list on any LLM error (caller falls back to template generation).
    """
    if not steps:
        return []

    partial_total = math.floor(count * 0.3) if include_partial else 0

    # Build human-readable steps description for the prompt
    step_lines = []
    step_keys = []
    for step in steps:
        step_key = step["step_key"]
        step_keys.append(step_key)
        meta = step.get("metadata") or {}
        if step_key == "lang":
            step_lines.append(f"- lang: detect/set user language")
        elif step_key == "intro":
            intro = meta.get("intro_prompt", "Ask for the respondent's name")
            step_lines.append(f"- intro: {intro[:200]}")
        elif step_key == "profile":
            profile = meta.get("intro_prompt", "Ask about the respondent's background/profile")
            step_lines.append(f"- profile: {profile[:200]}")
        elif step_key == "questionnaire":
            questions_list = meta.get("questions_list")
            if questions_list and isinstance(questions_list, list):
                questions = [q.strip() for q in questions_list if isinstance(q, str) and q.strip()]
            else:
                questions = [q.strip() for q in meta.get("specific_questions", "").splitlines() if q.strip()]
            if not questions:
                goal = meta.get("survey_goal", "")
                if goal and goal.strip():
                    step_lines.append(f"- questionnaire: Generate and ask questions to achieve this goal: {goal.strip()[:500]}")
                else:
                    step_lines.append(f"- questionnaire: Ask relevant survey questions")
            else:
                qs = "\n    ".join(f"{i+1}. {q}" for i, q in enumerate(questions))
                step_lines.append(f"- questionnaire: Ask ALL of the following questions in order:\n    {qs}")
        elif step_key == "additional_info":
            info = meta.get("info_to_collect", "Ask for additional contact information")
            step_lines.append(f"- additional_info: {info[:200]}")
        elif step_key == "closing":
            closing = meta.get("closing_generation_prompt", "Send a personalized farewell message")
            step_lines.append(f"- closing: {closing[:200]}")
        else:
            step_lines.append(f"- {step_key}: {str(meta)[:100]}")

    steps_description = "\n".join(step_lines)
    step_keys_str = ", ".join(step_keys)

    nq = _questionnaire_question_count(steps)
    chunk = _mock_dialogue_batch_size(nq, count)
    last_error: BaseException | None = None

    while chunk >= 1:
        sizes = _batch_sizes(count, chunk)
        partials = _allocate_partials_across_batches(sizes, partial_total)
        try:
            coros = [
                _generate_mock_dialogues_llm_single_request(
                    steps_description=steps_description,
                    step_keys_str=step_keys_str,
                    count=bc,
                    completed_count=bc - bp,
                    partial_count=bp,
                )
                for bc, bp in zip(sizes, partials)
            ]
            batch_results = await asyncio.gather(*coros)
            all_dialogues: List[Dict[str, Any]] = []
            for batch_dialogues in batch_results:
                all_dialogues.extend(batch_dialogues)
            logger.info(
                f"LLM generated {len(all_dialogues)} mock dialogues in {len(sizes)} request(s) "
                f"(batch_size={chunk}, questions={nq})"
            )
            return all_dialogues
        except Exception as e:
            last_error = e
            if chunk == 1 or not _mock_llm_retryable_oversize_or_parse_error(e):
                logger.warning(f"Failed to generate mock dialogues via LLM: {e}")
                return []
            new_chunk = max(1, chunk // 2)
            logger.warning(
                f"Mock dialogue LLM batch failed ({e!s}); retrying with batch chunk {chunk} -> {new_chunk}"
            )
            chunk = new_chunk

    if last_error:
        logger.warning(f"Failed to generate mock dialogues via LLM: {last_error}")
    return []
