"""Custom exceptions for conversations module."""


class ConversationsError(Exception):
    """Base exception for conversations module."""
    pass


class ProcessingError(ConversationsError):
    """Error occurred while processing message."""
    pass


class PublishError(ConversationsError):
    """Error occurred while publishing outgoing message."""
    pass

