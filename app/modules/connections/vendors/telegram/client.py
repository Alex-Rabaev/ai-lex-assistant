"""Telegram Bot API client for managing bot connections."""

import logging
from typing import Optional, Dict, Any
import httpx

from app.modules.connections.schemas import BotInfo
from app.modules.connections.exceptions import (
    InvalidBotTokenError,
    TelegramAPIError,
    WebhookSetupError
)

logger = logging.getLogger(__name__)


class TelegramClient:
    """Client for interacting with Telegram Bot API."""
    
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    DEFAULT_TIMEOUT = 10.0
    
    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize Telegram client.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
    
    async def validate_token(self, bot_token: str) -> BotInfo:
        """
        Validate bot token by calling Telegram getMe API.
        
        Args:
            bot_token: Telegram bot token to validate
            
        Returns:
            BotInfo with bot details
            
        Raises:
            InvalidBotTokenError: If token is invalid or unauthorized
            TelegramAPIError: For other API errors
        """
        url = self.BASE_URL.format(token=bot_token, method="getMe")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                
                # Handle different response codes
                if response.status_code == 401:
                    raise InvalidBotTokenError("Invalid or expired bot token")
                elif response.status_code == 404:
                    raise InvalidBotTokenError("Bot not found")
                elif response.status_code != 200:
                    raise TelegramAPIError(
                        f"Telegram API error: {response.status_code}",
                        error_code=response.status_code
                    )
                
                data = response.json()
                
                if not data.get("ok"):
                    error_desc = data.get("description", "Unknown error")
                    error_code = data.get("error_code", 0)
                    
                    if error_code == 401 or "unauthorized" in error_desc.lower():
                        raise InvalidBotTokenError(error_desc)
                    else:
                        raise TelegramAPIError(error_desc, error_code=error_code)
                
                # Parse bot info from result
                result = data["result"]
                bot_info = BotInfo(
                    id=result["id"],
                    is_bot=result["is_bot"],
                    first_name=result["first_name"],
                    username=result["username"],
                    can_join_groups=result.get("can_join_groups"),
                    can_read_all_group_messages=result.get("can_read_all_group_messages"),
                    supports_inline_queries=result.get("supports_inline_queries")
                )
                
                logger.info(f"Validated bot token for @{bot_info.username} (ID: {bot_info.id})")
                return bot_info
                
            except httpx.TimeoutException:
                raise TelegramAPIError("Request timeout - Telegram API not responding")
            except httpx.NetworkError as e:
                raise TelegramAPIError(f"Network error: {e}")
            except httpx.RequestError as e:
                raise TelegramAPIError(f"Request error: {e}")
            except (KeyError, ValueError) as e:
                raise TelegramAPIError(f"Invalid response format: {e}")
    
    async def setup_webhook(
        self, 
        bot_token: str, 
        webhook_url: str,
        secret_token: Optional[str] = None,
        max_connections: int = 40,
        allowed_updates: Optional[list] = None
    ) -> bool:
        """
        Set up webhook for the bot.
        
        Args:
            bot_token: Telegram bot token
            webhook_url: URL to receive updates
            secret_token: Secret token for webhook verification (optional)
            max_connections: Maximum allowed concurrent connections (1-100)
            allowed_updates: List of update types to receive (optional)
            
        Returns:
            True if webhook was set successfully
            
        Raises:
            WebhookSetupError: If webhook setup fails
            TelegramAPIError: For other API errors
        """
        url = self.BASE_URL.format(token=bot_token, method="setWebhook")
        
        # Prepare parameters
        params = {
            "url": webhook_url,
            "max_connections": max_connections
        }
        
        if secret_token:
            params["secret_token"] = secret_token
            
        if allowed_updates:
            params["allowed_updates"] = allowed_updates
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=params)
                
                if response.status_code == 401:
                    raise InvalidBotTokenError("Invalid or expired bot token")
                elif response.status_code != 200:
                    raise WebhookSetupError(
                        f"Failed to set webhook: HTTP {response.status_code}"
                    )
                
                data = response.json()
                
                if not data.get("ok"):
                    error_desc = data.get("description", "Unknown error")
                    raise WebhookSetupError(f"Failed to set webhook: {error_desc}")
                
                logger.info(f"Webhook set successfully for {webhook_url}")
                return True
                
            except httpx.TimeoutException:
                raise WebhookSetupError("Request timeout - Telegram API not responding")
            except httpx.NetworkError as e:
                raise WebhookSetupError(f"Network error: {e}")
            except httpx.RequestError as e:
                raise WebhookSetupError(f"Request error: {e}")
    
    async def delete_webhook(self, bot_token: str) -> bool:
        """
        Delete webhook for the bot.
        
        Args:
            bot_token: Telegram bot token
            
        Returns:
            True if webhook was deleted successfully
            
        Raises:
            InvalidBotTokenError: If token is invalid
            TelegramAPIError: For other API errors
        """
        url = self.BASE_URL.format(token=bot_token, method="deleteWebhook")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url)
                
                if response.status_code == 401:
                    raise InvalidBotTokenError("Invalid or expired bot token")
                elif response.status_code != 200:
                    raise TelegramAPIError(
                        f"Failed to delete webhook: HTTP {response.status_code}",
                        error_code=response.status_code
                    )
                
                data = response.json()
                
                if not data.get("ok"):
                    error_desc = data.get("description", "Unknown error")
                    raise TelegramAPIError(f"Failed to delete webhook: {error_desc}")
                
                logger.info("Webhook deleted successfully")
                return True
                
            except httpx.TimeoutException:
                raise TelegramAPIError("Request timeout - Telegram API not responding")
            except httpx.NetworkError as e:
                raise TelegramAPIError(f"Network error: {e}")
            except httpx.RequestError as e:
                raise TelegramAPIError(f"Request error: {e}")
    
    async def get_webhook_info(self, bot_token: str) -> Dict[str, Any]:
        """
        Get current webhook configuration.
        
        Args:
            bot_token: Telegram bot token
            
        Returns:
            Dictionary with webhook info
            
        Raises:
            InvalidBotTokenError: If token is invalid
            TelegramAPIError: For other API errors
        """
        url = self.BASE_URL.format(token=bot_token, method="getWebhookInfo")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                
                if response.status_code == 401:
                    raise InvalidBotTokenError("Invalid or expired bot token")
                elif response.status_code != 200:
                    raise TelegramAPIError(
                        f"Failed to get webhook info: HTTP {response.status_code}",
                        error_code=response.status_code
                    )
                
                data = response.json()
                
                if not data.get("ok"):
                    error_desc = data.get("description", "Unknown error")
                    raise TelegramAPIError(f"Failed to get webhook info: {error_desc}")
                
                return data["result"]
                
            except httpx.TimeoutException:
                raise TelegramAPIError("Request timeout - Telegram API not responding")
            except httpx.NetworkError as e:
                raise TelegramAPIError(f"Network error: {e}")
            except httpx.RequestError as e:
                raise TelegramAPIError(f"Request error: {e}")
