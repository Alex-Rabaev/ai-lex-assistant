"""Exceptions for webhooks module."""


class WebhookException(Exception):
    """Base exception for webhook module."""
    pass


class WebhookValidationError(WebhookException):
    """Raised when webhook validation fails."""
    pass


class WebhookSecretError(WebhookException):
    """Raised when webhook secret validation fails."""
    pass


class WebhookProcessingError(WebhookException):
    """Raised when webhook processing fails."""
    pass


class UnsupportedMessageTypeError(WebhookException):
    """Raised when message type is not supported."""
    pass


class AssistantNotFoundError(WebhookException):
    """Raised when assistant is not found."""
    pass


class ConnectionNotFoundError(WebhookException):
    """Raised when connection is not found."""
    pass


class DuplicateWebhookError(WebhookException):
    """Raised when duplicate webhook is received (e.g., same update_id)."""
    pass


class WebhookError(WebhookException):
    """Alias for WebhookException for backward compatibility."""
    pass


class WebhookEventError(WebhookException):
    """Error related to webhook event operations."""
    pass
