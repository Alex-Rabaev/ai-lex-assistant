"""Activity functions for SnapshotWorkflow.

Each Activity performs real I/O work (database, LLM, messaging).
Activities are retried independently by Temporal on failure.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import Client as LangSmithClient
from temporalio import activity

from app.config import config
from app.modules.analysis.schemas.config import parse_analysis_config
from app.modules.workflows.implementations.analysis_snapshot.prompts import (
    PROMPT_CONFIGS,
    PROMPT_NAMES,
)
from app.modules.workflows.models.params import (
    ConclusionsParams,
    NotifyParams,
    ProfileParams,
    SaveSnapshotParams,
)

logger = logging.getLogger(__name__)


def _get_langsmith_client() -> LangSmithClient:
    """Get LangSmith client for prompt loading."""
    return LangSmithClient(
        api_key=config.LANGSMITH_API_KEY,
        api_url=config.LANGSMITH_ENDPOINT,
    )


def _load_prompt_template(prompt_key: str) -> str:
    """Load prompt template from LangSmith by key.
    
    Args:
        prompt_key: Key in PROMPT_NAMES dict
        
    Returns:
        Prompt template string
    """
    client = _get_langsmith_client()
    prompt_name = PROMPT_NAMES[prompt_key]
    
    try:
        prompt = client.pull_prompt(prompt_name)
        if hasattr(prompt, "messages") and prompt.messages:
            first_msg = prompt.messages[0]
            if hasattr(first_msg, "prompt") and hasattr(first_msg.prompt, "template"):
                return first_msg.prompt.template
        return str(prompt)
    except Exception as e:
        logger.error(f"Failed to load prompt '{prompt_name}' from LangSmith: {e}")
        raise


def _get_llm(prompt_key: str) -> ChatOpenAI:
    """Create ChatOpenAI instance configured for a specific prompt.
    
    Args:
        prompt_key: Key in PROMPT_CONFIGS dict
        
    Returns:
        Configured ChatOpenAI instance
    """
    prompt_config = PROMPT_CONFIGS[prompt_key]
    
    kwargs: Dict[str, Any] = {
        "api_key": config.OPENAI_API_KEY,
        "model": prompt_config.model,
        "temperature": prompt_config.temperature,
        "max_tokens": prompt_config.max_tokens,
    }
    
    if prompt_config.response_format:
        kwargs["model_kwargs"] = {"response_format": {"type": prompt_config.response_format}}
    
    return ChatOpenAI(**kwargs)


@activity.defn(name="load_assistant")
async def load_assistant(assistant_id: str) -> Dict[str, Any]:
    """Load assistant data (goals, config, steps).
    
    Args:
        assistant_id: Assistant ID
        
    Returns:
        Dict with assistant data, analysis_config, survey_goal, steps
    """
    from app.modules.assistants.service import AssistantService
    
    service = AssistantService()
    assistant = await service.get_assistant_internal(assistant_id)
    
    steps = await service.get_steps_internal(assistant_id)
    
    survey_goal = ""
    survey_questions = ""
    analysis_config = None
    
    if assistant.metadata:
        survey_goal = assistant.metadata.get("survey_goal", "")
        raw_config = assistant.metadata.get("analysis_config")
        if raw_config:
            analysis_config = raw_config
    
    for step in steps:
        if step.step_key == "questionnaire" and step.metadata:
            survey_questions = step.metadata.get("specific_questions", "")
            if not survey_goal:
                survey_goal = step.metadata.get("survey_goal", "")
    
    analysis_language = "English"
    if analysis_config and isinstance(analysis_config, dict):
        analysis_language = analysis_config.get("analysis_language", "English") or "English"

    return {
        "assistant_id": assistant_id,
        "name": assistant.name,
        "survey_goal": survey_goal,
        "survey_questions": survey_questions,
        "analysis_config": analysis_config,
        "analysis_language": analysis_language,
    }


@activity.defn(name="load_conversations")
async def load_conversations(
    assistant_id: str,
    min_stage: str = "INTRO",
    include_mock: bool = False
) -> List[Dict[str, Any]]:
    """Load conversations for assistant.

    Args:
        assistant_id: Assistant ID
        min_stage: Minimum stage to include (reserved)
        include_mock: If True, include mock respondents; if False, only real.

    Returns:
        List of conversation dicts with id, state, analytic_meta, timestamps
    """
    from app.modules.conversations.service import ConversationsService

    service = ConversationsService()
    conversations = await service.get_conversations_by_assistant(
        assistant_id, include_mock=include_mock
    )

    result = []
    for conv in conversations:
        result.append({
            "id": str(conv.id),
            "state": conv.state,
            "analytic_meta": conv.analytic_meta,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        })

    logger.info(
        f"Loaded {len(result)} conversations for assistant {assistant_id} (include_mock={include_mock})"
    )
    return result


@activity.defn(name="compute_statistics")
async def compute_statistics(conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute basic statistics programmatically (no LLM).
    
    Args:
        conversations: List of conversation dicts
        
    Returns:
        OverallStatistics as dict
    """
    total = len(conversations)
    if total == 0:
        return {
            "total_respondents": 0,
            "completed_count": 0,
            "in_progress_count": 0,
            "abandoned_count": 0,
            "completion_rate": 0.0,
            "stage_distribution": [],
            "drop_off_analysis": [],
            "time_metrics": {},
        }
    
    # Count by status/stage
    stage_counts: Dict[str, int] = {}
    completed = 0
    in_progress = 0
    abandoned = 0
    
    for conv in conversations:
        state = conv.get("state", {})
        agent_meta = state.get("agent_metadata", {})
        current_stage = agent_meta.get("state", "unknown")
        
        stage_counts[current_stage] = stage_counts.get(current_stage, 0) + 1
        
        # Determine status from stage
        if current_stage in ("CLOSING", "COMPLETED", "closing", "completed"):
            completed += 1
        elif current_stage in ("ABANDONED", "abandoned"):
            abandoned += 1
        else:
            in_progress += 1
    
    completion_rate = completed / total if total > 0 else 0.0
    
    stage_distribution = [
        {"stage": stage, "count": count, "percentage": count / total}
        for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1])
    ]
    
    return {
        "total_respondents": total,
        "completed_count": completed,
        "in_progress_count": in_progress,
        "abandoned_count": abandoned,
        "completion_rate": round(completion_rate, 3),
        "stage_distribution": stage_distribution,
        "drop_off_analysis": [],
        "time_metrics": {},
    }


@activity.defn(name="generate_profile")
async def generate_profile(params: ProfileParams) -> Optional[Dict[str, Any]]:
    """Generate respondent profile via LLM with smart recalculation.
    
    Skips if profile is up-to-date (unless force_recalculate).
    Saves result to Conversation.analytic_meta.
    
    Args:
        params: ProfileParams
        
    Returns:
        AnalyticMeta as dict, or None if skipped
    """
    from app.modules.conversations.service import ConversationsService
    
    conv_service = ConversationsService()
    
    # Load conversation with history
    conversation = await conv_service.get_conversation(params.conversation_id)
    if not conversation:
        logger.warning(f"Conversation not found: {params.conversation_id}")
        return None
    
    # Smart recalculation check
    if not params.force_recalculate and conversation.analytic_meta is not None:
        existing_meta = conversation.analytic_meta
        analyzed_at = existing_meta.get("analyzed_at")
        conv_updated = conversation.updated_at
        
        config_data = params.analysis_config
        config_updated = config_data.get("last_updated_at") if config_data else None
        
        if analyzed_at:
            skip = True
            if conv_updated and str(conv_updated) > str(analyzed_at):
                skip = False
            if config_updated and str(config_updated) > str(analyzed_at):
                skip = False
            if skip:
                logger.debug(f"Skipping profile for {params.conversation_id} — up to date")
                return None
    
    # Load conversation history
    history = await conv_service.get_full_history(params.conversation_id)
    history_text = "\n".join(
        f"{'User' if msg.role == 'user' else 'Assistant'}: {msg.content}"
        for msg in history
        if hasattr(msg, "role") and hasattr(msg, "content")
    )
    
    # Parse analysis config
    parsed_config = parse_analysis_config(params.analysis_config)
    
    # Format categories, tags, questions for prompt
    categories_text = ""
    tags_text = ""
    questions_text = ""
    summary_max_length = 500
    
    if parsed_config and parsed_config.framework:
        categories_text = "\n".join(
            f"- {c.name}: {c.description} (scoring: {c.scoring_type}, range: {c.min_score}-{c.max_score})"
            for c in parsed_config.framework.categories
        )
        tags_text = "\n".join(
            f"- {t.name}: {t.description or 'auto-extract'} (extraction: {t.extraction})"
            for t in parsed_config.framework.tags
        )
        questions_text = "\n".join(
            f"- {q}" for q in parsed_config.framework.custom_questions
        )
    
    if parsed_config and parsed_config.output:
        summary_max_length = parsed_config.output.summary_max_length
    
    # Get current stage
    agent_meta = conversation.state.get("agent_metadata", {})
    final_stage = agent_meta.get("state", "unknown")
    survey_status = "completed" if final_stage in ("CLOSING", "COMPLETED", "closing", "completed") else "in_progress"
    
    # Load prompt from LangSmith and call LLM
    template = _load_prompt_template("generate_profile")
    assistant_goal = "Not specified"
    if params.analysis_config:
        # Field is "assistant_goal" in AnalysisConfig schema
        assistant_goal = (
            params.analysis_config.get("assistant_goal")
            or params.analysis_config.get("survey_goal")
            or "Not specified"
        )

    logger.info(
        "generate_profile config | conv=%s | categories=%d | tags=%d | questions=%d | "
        "assistant_goal=%r | analysis_language=%r | parsed_config=%s",
        params.conversation_id,
        len(parsed_config.framework.categories) if parsed_config and parsed_config.framework else 0,
        len(parsed_config.framework.tags) if parsed_config and parsed_config.framework else 0,
        len(parsed_config.framework.custom_questions) if parsed_config and parsed_config.framework else 0,
        assistant_goal,
        params.analysis_language,
        "OK" if parsed_config else "NONE",
    )

    prompt_text = template.format(
        categories=categories_text or "No categories configured",
        tags=tags_text or "No tags configured",
        custom_questions=questions_text or "No custom questions",
        conversation_history=history_text or "No conversation history",
        assistant_goal=assistant_goal,
        final_stage=final_stage,
        survey_status=survey_status,
        summary_max_length=summary_max_length,
        analysis_language=params.analysis_language,
    )

    llm = _get_llm("generate_profile")
    response = await llm.ainvoke([SystemMessage(content=prompt_text)])

    profile_data = json.loads(response.content)

    logger.debug(
        "generate_profile LLM response | conv=%s | category_scores=%d | overall_score=%s | custom_answers=%d",
        params.conversation_id,
        len(profile_data.get("category_scores") or []),
        profile_data.get("overall_score"),
        len(profile_data.get("custom_answers") or []),
    )
    
    # Normalize and filter extracted_tags
    raw_tags = profile_data.get("extracted_tags", [])
    normalized_tags = []
    for tag in raw_tags:
        if isinstance(tag, str) and tag.strip():
            normalized_tags.append({"tag_name": tag, "value": tag, "source": "auto"})
        elif isinstance(tag, dict):
            tag_name = tag.get("tag_name") or tag.get("name")
            value = tag.get("value") or tag_name
            if tag_name and str(tag_name).strip():
                normalized_tags.append({
                    "tag_name": str(tag_name).strip(),
                    "value": str(value).strip() if value else str(tag_name).strip(),
                    "source": tag.get("source", "auto")
                })
    profile_data["extracted_tags"] = normalized_tags

    # Normalize recommendations: LLM may return a string instead of List[str]
    recs = profile_data.get("recommendations")
    if isinstance(recs, str) and recs.strip():
        # Split on ". " to try to get individual sentences as list items,
        # but only if multiple sentences — otherwise wrap as single-element list
        sentences = [s.strip() for s in recs.split(". ") if s.strip()]
        profile_data["recommendations"] = [s if s.endswith(".") else s + "." for s in sentences] if len(sentences) > 1 else [recs.strip()]
    elif not isinstance(recs, list):
        profile_data["recommendations"] = []

    # Extract numeric scores from category_scores (handles multiple LLM formats).
    raw_scores = profile_data.get("category_scores") or []
    numeric_scores = []
    if isinstance(raw_scores, dict):
        for val in raw_scores.values():
            score = val.get("score") if isinstance(val, dict) else val
            if score is None or score == "None":
                continue
            try:
                numeric_scores.append(float(score))
            except (TypeError, ValueError):
                pass
    elif isinstance(raw_scores, list):
        for cs in raw_scores:
            if isinstance(cs, dict):
                score = cs.get("score")
            elif isinstance(cs, (int, float, str)):
                score = cs
            else:
                continue
            if score is None or score == "None":
                continue
            try:
                numeric_scores.append(float(score))
            except (TypeError, ValueError):
                pass

    total_categories = len(raw_scores) if isinstance(raw_scores, (list, dict)) else 0

    # Compute overall_score: unscored categories count as 0.
    if not profile_data.get("overall_score") and total_categories > 0:
        profile_data["overall_score"] = round(
            sum(numeric_scores) / total_categories, 2
        )

    # Determine data quality.
    # Insufficient when: data_completeness < 0.4, analysis_confidence < 0.3,
    # or less than half of categories have a numeric score.
    dc = profile_data.get("data_completeness") or 0.0
    ac = profile_data.get("analysis_confidence") or 0.0
    try:
        dc = float(dc)
        ac = float(ac)
    except (TypeError, ValueError):
        dc = ac = 0.0
    low_coverage = total_categories > 0 and len(numeric_scores) < (total_categories / 2)
    profile_data["sufficient_data"] = not (dc < 0.4 or ac < 0.3 or low_coverage)

    # Add metadata
    profile_data["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    profile_data["survey_status"] = survey_status
    profile_data["final_stage"] = final_stage

    # Save to conversation
    await conv_service.update_analytic_meta(params.conversation_id, profile_data)
    
    logger.info(f"Generated profile for conversation {params.conversation_id}")
    return profile_data


def _aggregate_profiles(profiles: List[Dict[str, Any]]) -> Dict[str, str]:
    """Aggregate individual profile data into text summaries for conclusions prompt.

    Returns dict with keys: category_scores_summary, tags_summary,
    business_questions_summary, respondent_summaries, recommendations_summary.
    """
    from collections import Counter

    category_totals: Dict[str, List[float]] = {}
    tag_counter: Counter = Counter()
    bq_answers: Dict[str, List[str]] = {}
    summaries: List[str] = []
    rec_counter: Counter = Counter()

    for p in profiles:
        # Category scores
        raw_scores = p.get("category_scores") or []
        if isinstance(raw_scores, dict):
            for cat_name, val in raw_scores.items():
                score = val.get("score") if isinstance(val, dict) else val
                try:
                    category_totals.setdefault(cat_name, []).append(float(score))
                except (TypeError, ValueError):
                    pass
        elif isinstance(raw_scores, list):
            for cs in raw_scores:
                if not isinstance(cs, dict):
                    continue
                cat_name = cs.get("category_name") or cs.get("name") or "Unknown"
                score = cs.get("score")
                try:
                    category_totals.setdefault(cat_name, []).append(float(score))
                except (TypeError, ValueError):
                    pass

        # Tags
        for tag in p.get("extracted_tags") or []:
            if isinstance(tag, dict):
                tag_name = tag.get("tag_name") or tag.get("name", "")
                tag_value = tag.get("value", tag_name)
                if tag_name:
                    tag_counter[f"{tag_name}: {tag_value}"] += 1
            elif isinstance(tag, str):
                tag_counter[tag] += 1

        # Business question answers
        for qa in p.get("custom_answers") or []:
            if isinstance(qa, dict):
                q = qa.get("question", "")
                a = qa.get("answer", "")
                if q and a:
                    bq_answers.setdefault(q, []).append(a)

        # Summaries
        summary = p.get("summary")
        if summary and isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())

        # Recommendations
        for rec in p.get("recommendations") or []:
            if isinstance(rec, str) and rec.strip():
                rec_counter[rec.strip()] += 1

    # Format category scores
    cat_lines = []
    for cat, scores in sorted(category_totals.items()):
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        cat_lines.append(f"- {cat}: avg={avg:.2f} (n={len(scores)}, min={min(scores):.1f}, max={max(scores):.1f})")
    category_scores_text = "\n".join(cat_lines) if cat_lines else "No category scores available."

    # Format tags
    tag_lines = [f"- {tag}: {count} respondents" for tag, count in tag_counter.most_common(30)]
    tags_text = "\n".join(tag_lines) if tag_lines else "No tags extracted."

    # Format business questions — show top 3 representative answers per question
    bq_lines = []
    for question, answers in bq_answers.items():
        answer_counter: Counter = Counter(answers)
        top = answer_counter.most_common(3)
        top_str = "; ".join(f'"{a}" ({c}x)' for a, c in top)
        bq_lines.append(f"Q: {question}\n  Top answers (out of {len(answers)}): {top_str}")
    bq_text = "\n".join(bq_lines) if bq_lines else "No business question answers available."

    # Format respondent summaries (sample up to 15 for token budget)
    sample = summaries[:15]
    summaries_text = "\n".join(f"- {s}" for s in sample) if sample else "No respondent summaries available."
    if len(summaries) > 15:
        summaries_text += f"\n... and {len(summaries) - 15} more respondents."

    # Format top recommendations
    rec_lines = [f"- {rec} ({count}x)" for rec, count in rec_counter.most_common(10)]
    recs_text = "\n".join(rec_lines) if rec_lines else "No individual recommendations available."

    return {
        "category_scores_summary": category_scores_text,
        "tags_summary": tags_text,
        "business_questions_summary": bq_text,
        "respondent_summaries": summaries_text,
        "recommendations_summary": recs_text,
    }


@activity.defn(name="generate_conclusions")
async def generate_conclusions(params: ConclusionsParams) -> Dict[str, Any]:
    """Generate conclusions from aggregated profile data via LLM.
    
    Args:
        params: ConclusionsParams
        
    Returns:
        SnapshotConclusions as dict
    """
    from app.modules.assistants.service import AssistantService
    from app.modules.conversations.service import ConversationsService

    assistant_service = AssistantService()
    assistant = await assistant_service.get_assistant_internal(params.assistant_id)

    # Read assistant_goal and analysis config
    assistant_goal = "Not specified"
    analysis_config_dict: Dict[str, Any] = {}
    if assistant.metadata:
        raw_config = assistant.metadata.get("analysis_config")
        if isinstance(raw_config, dict):
            analysis_config_dict = raw_config
            assistant_goal = raw_config.get("assistant_goal") or "Not specified"
        if assistant_goal == "Not specified":
            assistant_goal = assistant.metadata.get("survey_goal") or "Not specified"

    # Build scoring categories / tags / questions text from config
    parsed_config = parse_analysis_config(analysis_config_dict) if analysis_config_dict else None
    categories_text = ""
    tags_text = ""
    questions_text = ""
    if parsed_config and parsed_config.framework:
        categories_text = "\n".join(
            f"- {c.name}: {c.description}" for c in parsed_config.framework.categories
        )
        tags_text = "\n".join(
            f"- {t.name}: {t.description or 'auto-extract'}" for t in parsed_config.framework.tags
        )
        questions_text = "\n".join(
            f"- {q}" for q in parsed_config.framework.custom_questions
        )

    # Load actual profile data for sufficient-data respondents
    conv_service = ConversationsService()
    profiles: List[Dict[str, Any]] = []
    for conv_id in params.profile_ids:
        conv = await conv_service.get_conversation(conv_id)
        if conv and conv.analytic_meta:
            profiles.append(conv.analytic_meta)

    aggregated = _aggregate_profiles(profiles)

    # Data quality summary
    total_analyzed = params.statistics.get("total_respondents", 0)
    insufficient = params.statistics.get("insufficient_data_count", 0)
    sufficient_count = len(params.profile_ids)
    profiles_summary_text = (
        f"{sufficient_count} profiles with sufficient data out of {total_analyzed} total respondents. "
        f"{insufficient} respondents had insufficient data and were excluded from analysis."
    )

    # Load prompt and call LLM
    template = _load_prompt_template("generate_conclusions")
    prompt_text = template.format(
        assistant_goal=assistant_goal,
        statistics=json.dumps(params.statistics, indent=2, default=str),
        profiles_summary=profiles_summary_text,
        insufficient_data_count=insufficient,
        sufficient_data_count=sufficient_count,
        analysis_language=params.analysis_language,
        configured_categories=categories_text or "None configured",
        configured_tags=tags_text or "None configured",
        configured_questions=questions_text or "None configured",
        category_scores_summary=aggregated["category_scores_summary"],
        tags_summary=aggregated["tags_summary"],
        business_questions_summary=aggregated["business_questions_summary"],
        respondent_summaries=aggregated["respondent_summaries"],
        recommendations_summary=aggregated["recommendations_summary"],
    )
    
    llm = _get_llm("generate_conclusions")
    response = await llm.ainvoke([SystemMessage(content=prompt_text)])
    
    conclusions = json.loads(response.content)
    
    logger.info(
        "Generated conclusions for assistant %s (%d profiles aggregated)",
        params.assistant_id, len(profiles),
    )
    return conclusions


@activity.defn(name="save_snapshot")
async def save_snapshot(params: SaveSnapshotParams) -> str:
    """Save snapshot result to WorkflowExecution in MongoDB.
    
    Args:
        params: SaveSnapshotParams
        
    Returns:
        Execution ID
    """
    from app.modules.workflows.service import WorkflowService
    
    service = WorkflowService()
    
    result = {
        "statistics": params.statistics,
        "conclusions": params.conclusions,
        "conversations_analyzed": params.conversations_analyzed,
        "conversations_skipped": params.conversations_skipped,
        "failed_conversations": params.failed_conversations,
        "include_partial": params.include_partial,
    }
    
    await service.complete_execution(params.execution_id, result, duration_ms=0)
    
    logger.info(f"Saved snapshot result for execution {params.execution_id}")
    return params.execution_id


@activity.defn(name="notify_websocket")
async def notify_websocket(params: NotifyParams) -> None:
    """Send progress/completion notification via RabbitMQ -> WebSocket.
    
    Args:
        params: NotifyParams
    """
    # WebSocket notification via RabbitMQ will be connected
    # when WebSocket infrastructure is ready (Story 3.8)
    logger.info(
        f"Notification: execution={params.execution_id}, "
        f"status={params.status}, progress={params.progress}"
    )
