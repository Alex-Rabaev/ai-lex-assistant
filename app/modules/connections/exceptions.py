"""Custom exceptions for connections module."""


class ConnectionError(Exception):
    """Base exception for connection-related errors."""
    pass


class InvalidBotTokenError(ConnectionError):
    """Raised when bot token is invalid or unauthorized."""
    pass


class WebhookSetupError(ConnectionError):
    """Raised when webhook setup fails."""
    pass


class ConnectionNotFoundError(ConnectionError):
    """Raised when connection is not found."""
    pass


class DuplicateConnectionError(ConnectionError):
    """Raised when trying to create duplicate connection."""
    pass


class TelegramAPIError(ConnectionError):
    """Raised when Telegram API returns an error."""
    def __init__(self, message: str, error_code: int = None):
        super().__init__(message)
        self.error_code = error_code


class WhatsAppAPIError(ConnectionError):
    """Raised when WhatsApp API returns an error."""
    def __init__(self, message: str, error_code: int = None):
        super().__init__(message)
        self.error_code = error_code


class InvalidAccessTokenError(ConnectionError):
    """Raised when WhatsApp access token is invalid."""
    pass
