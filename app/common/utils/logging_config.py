"""
Structured JSON logging with secret masking for Gateway project
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import config
from app.common.utils.logging_context import get_log_context


class SecretMasker:
    """Utility class for masking sensitive information in logs"""
    
    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        (re.compile(r'(token|key|secret|password|auth)', re.IGNORECASE), 'MASKED'),
        (re.compile(r'(\d{4,})', re.IGNORECASE), lambda m: '*' * (len(m.group(1)) - 4) + m.group(1)[-4:]),
        (re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.IGNORECASE), 
         lambda m: m.group(1)[:2] + '*' * (len(m.group(1)) - 6) + m.group(1)[-4:]),
    ]
    
    @classmethod
    def mask_secrets(cls, data: Any) -> Any:
        """Recursively mask sensitive data in any data structure"""
        if isinstance(data, dict):
            return {key: cls.mask_secrets(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [cls.mask_secrets(item) for item in data]
        elif isinstance(data, str):
            return cls._mask_string(data)
        else:
            return data
    
    @classmethod
    def _mask_string(cls, text: str) -> str:
        """Mask sensitive patterns in a string"""
        masked_text = text
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            if callable(replacement):
                masked_text = pattern.sub(replacement, masked_text)
            else:
                masked_text = pattern.sub(replacement, masked_text)
        return masked_text


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add context fields from contextvars (trace_id, assistant_id, etc.)
        log_entry.update(get_log_context())
        
        # Add extra fields if present (can override context)
        if hasattr(record, 'trace_id'):
            log_entry["trace_id"] = record.trace_id
        if hasattr(record, 'assistant_id'):
            log_entry["assistant_id"] = record.assistant_id
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'interlocutor_id'):
            log_entry["interlocutor_id"] = record.interlocutor_id
        if hasattr(record, 'conversation_id'):
            log_entry["conversation_id"] = record.conversation_id
        if hasattr(record, 'channel'):
            log_entry["channel"] = record.channel
        if hasattr(record, 'stage'):
            log_entry["stage"] = record.stage
        if hasattr(record, 'request_path'):
            log_entry["request_path"] = record.request_path
        if hasattr(record, 'response_code'):
            log_entry["response_code"] = record.response_code
        if hasattr(record, 'processing_time'):
            log_entry["processing_time_ms"] = record.processing_time
        if hasattr(record, 'message_length'):
            log_entry["message_length"] = record.message_length
        if hasattr(record, 'response_length'):
            log_entry["response_length"] = record.response_length
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Mask sensitive data
        log_entry = SecretMasker.mask_secrets(log_entry)
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_structured_logging():
    """Setup structured JSON logging with secret masking"""
    
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set specific loggers to appropriate levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    
    return root_logger


class StructuredLogger:
    """Helper class for structured logging with context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_request(self, 
                   path: str, 
                   method: str = "POST",
                   user_id: Optional[str] = None,
                   channel: Optional[str] = None,
                   stage: Optional[str] = None):
        """Log incoming request"""
        self.logger.info(
            f"Request received: {method} {path}",
            extra={
                "request_path": path,
                "user_id": user_id,
                "channel": channel,
                "stage": stage
            }
        )
    
    def log_response(self, 
                    path: str,
                    status_code: int,
                    processing_time_ms: float,
                    user_id: Optional[str] = None,
                    channel: Optional[str] = None,
                    message_length: Optional[int] = None,
                    response_length: Optional[int] = None):
        """Log response with metrics"""
        self.logger.info(
            f"Response sent: {status_code} for {path}",
            extra={
                "request_path": path,
                "response_code": status_code,
                "processing_time": processing_time_ms,
                "user_id": user_id,
                "channel": channel,
                "message_length": message_length,
                "response_length": response_length
            }
        )
    
    def log_agent_processing(self,
                           user_id: str,
                           stage: str,
                           channel: str,
                           input_length: int,
                           output_length: int,
                           processing_time_ms: float):
        """Log agent processing metrics"""
        self.logger.info(
            f"Agent processed message for user {user_id[:8]}... in stage {stage}",
            extra={
                "user_id": user_id,
                "stage": stage,
                "channel": channel,
                "message_length": input_length,
                "response_length": output_length,
                "processing_time": processing_time_ms
            }
        )
    
    def log_error(self, 
                 message: str, 
                 error: Exception,
                 user_id: Optional[str] = None,
                 channel: Optional[str] = None,
                 stage: Optional[str] = None):
        """Log error with context"""
        self.logger.error(
            message,
            extra={
                "user_id": user_id,
                "channel": channel,
                "stage": stage
            },
            exc_info=error
        )
    
    def info(self, message: str, **kwargs):
        """Log info with extra context"""
        self.logger.info(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error with extra context"""
        self.logger.error(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning with extra context"""
        self.logger.warning(message, extra=kwargs)
