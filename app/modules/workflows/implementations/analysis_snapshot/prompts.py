"""Prompt configuration for SnapshotWorkflow.

Prompt templates are stored in LangSmith, not in code.
This file defines prompt NAMES (for LangSmith lookup) and
LLM configuration (model, temperature, max_tokens) for each prompt.

To pin a specific LangSmith commit per environment, set PROMPT_COMMITS below.
When a commit is set, the prompt is loaded as "prompt_name:commit_hash".
Set to None to always use the latest version.
"""

from app.modules.workflows.prompts import PromptConfig


# LangSmith prompt names
PROMPT_NAMES = {
    "generate_profile": "snapshot_generate_profile",
    "generate_conclusions": "snapshot_generate_conclusions",
    "analyze_dropoff": "snapshot_analyze_dropoff",
}

# Pinned LangSmith commit hashes per prompt (None = latest).
# Set specific commits here to lock production to a known-good prompt version.
PROMPT_COMMITS: dict = {
    "generate_profile": "6df53a1d",
    "generate_conclusions": "6bfeb7d8",
    "analyze_dropoff": "a5e8d2a0",
}

# LLM configuration per prompt
PROMPT_CONFIGS = {
    "generate_profile": PromptConfig(
        template="",  # Loaded from LangSmith at runtime
        model="gpt-4o",
        temperature=0.0,
        max_tokens=4096,
        response_format="json_object",
    ),
    "generate_conclusions": PromptConfig(
        template="",  # Loaded from LangSmith at runtime
        model="gpt-4o",
        temperature=0.1,
        max_tokens=4096,
        response_format="json_object",
    ),
    "analyze_dropoff": PromptConfig(
        template="",  # Loaded from LangSmith at runtime
        model="gpt-4o-mini",
        temperature=0.0,
        max_tokens=2048,
        response_format="json_object",
    ),
}
