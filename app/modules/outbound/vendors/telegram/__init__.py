"""Telegram-specific message sender implementation."""

from app.modules.outbound.vendors.telegram.client import TelegramClient
from app.modules.outbound.vendors.telegram.sender import TelegramSender

__all__ = ["TelegramClient", "TelegramSender"]

