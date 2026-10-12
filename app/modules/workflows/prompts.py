"""Prompt configuration for LLM-based workflows.

Each prompt can have its own LLM settings (model, temperature, etc.)
allowing fine-tuned control over generation behavior.
"""

from typing import Optional

from pydantic import BaseModel, Field


class PromptConfig(BaseModel):
    """Configuration for a single LLM prompt.
    
    Allows per-prompt configuration of LLM parameters.
    Different prompts in the same workflow can use different models
    or temperature settings.
    
    Example:
        PROMPTS = {
            "generate_profile": PromptConfig(
                template="Analyze this conversation...",
                model="gpt-4o",
                temperature=0.0,
            ),
            "generate_summary": PromptConfig(
                template="Summarize the following...",
                model="gpt-4o-mini",
                temperature=0.3,
            ),
        }
    """
    
    template: str = Field(..., description="Prompt text template")
    model: str = Field(
        default="gpt-4o",
        description="LLM model identifier"
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperature for generation (0.0 = deterministic)"
    )
    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens in response"
    )
    response_format: Optional[str] = Field(
        default=None,
        description="Response format: None or 'json_object' for structured output"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "template": "Analyze the following conversation and extract key insights...",
                "model": "gpt-4o",
                "temperature": 0.0,
                "max_tokens": 4096,
                "response_format": "json_object"
            }
        }
    }
