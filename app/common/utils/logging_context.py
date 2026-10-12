"""
Logging context management using contextvars.

Provides trace_id and context fields propagation for structured logging.
Context is automatically included in all log entries via StructuredFormatter.
"""

import contextvars
import uuid
from typing import Optional, Dict, Any

# Context variables for logging
trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('trace_id', default=None)
assistant_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('assistant_id', default=None)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('user_id', default=None)
interlocutor_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('interlocutor_id', default=None)
conversation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('conversation_id', default=None)


def generate_trace_id() -> str:
    """Generate a new trace_id (short UUID for readability)."""
    return uuid.uuid4().hex[:12]


def set_log_context(
    trace_id: Optional[str] = None,
    assistant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    interlocutor_id: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> None:
    """
    Set logging context fields.
    
    Once set, these fields are automatically included in all log entries
    within the current async context.
    
    Args:
        trace_id: Unique ID for tracing request through the pipeline
        assistant_id: Assistant ID handling the request
        user_id: User ID (e.g., telegram_123456)
        interlocutor_id: Interlocutor ID from database
        conversation_id: Conversation ID from database
    """
    if trace_id is not None:
        trace_id_var.set(trace_id)
    if assistant_id is not None:
        assistant_id_var.set(assistant_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if interlocutor_id is not None:
        interlocutor_id_var.set(interlocutor_id)
    if conversation_id is not None:
        conversation_id_var.set(conversation_id)


def clear_log_context() -> None:
    """Clear all logging context fields."""
    trace_id_var.set(None)
    assistant_id_var.set(None)
    user_id_var.set(None)
    interlocutor_id_var.set(None)
    conversation_id_var.set(None)


def get_log_context() -> Dict[str, Any]:
    """
    Get current logging context as dict.
    
    Returns only non-None values for cleaner log output.
    
    Returns:
        Dict with current context fields
    """
    context = {}
    
    if trace_id_var.get():
        context["trace_id"] = trace_id_var.get()
    if assistant_id_var.get():
        context["assistant_id"] = assistant_id_var.get()
    if user_id_var.get():
        context["user_id"] = user_id_var.get()
    if interlocutor_id_var.get():
        context["interlocutor_id"] = interlocutor_id_var.get()
    if conversation_id_var.get():
        context["conversation_id"] = conversation_id_var.get()
    
    return context

