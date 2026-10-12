"""Custom exceptions for outbound message delivery."""


class OutboundError(Exception):
    """Base exception for outbound module."""
    pass


class SendError(OutboundError):
    """Error occurred while sending message."""
    pass


class DeliveryError(SendError):
    """Message could not be delivered."""
    pass


class UserBlockedError(SendError):
    """User has blocked the bot (HTTP 403)."""
    pass


class InvalidTokenError(SendError):
    """Bot token is invalid or expired (HTTP 401)."""
    pass


class RateLimitError(SendError):
    """Rate limit exceeded (HTTP 429)."""
    
    def __init__(self, message: str, retry_after: int = 60):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retry
        """
        super().__init__(message)
        self.retry_after = retry_after


class TemporaryError(SendError):
    """Temporary error that can be retried (HTTP 5xx)."""
    pass

