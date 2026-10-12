"""HTTP client for Telegram Bot API."""

import logging
import tempfile
from typing import Optional, Dict, Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.modules.outbound.exceptions import (
    UserBlockedError,
    InvalidTokenError,
    RateLimitError,
    TemporaryError,
    SendError,
)
from app.common.audio.exceptions import AudioDownloadError

logger = logging.getLogger(__name__)


class TelegramClient:
    """
    Low-level HTTP client for Telegram Bot API.
    
    Handles direct API calls to Telegram and maps HTTP errors
    to appropriate custom exceptions.
    """
    
    def __init__(self, bot_token: str):
        """
        Initialize Telegram client.
        
        Args:
            bot_token: Telegram bot token
        """
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send text message via Telegram Bot API.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Optional parse mode (HTML or Markdown)
            reply_markup: Optional inline keyboard markup
            
        Returns:
            Response from Telegram API
            
        Raises:
            UserBlockedError: User has blocked the bot (403)
            InvalidTokenError: Bot token is invalid (401)
            RateLimitError: Rate limit exceeded (429)
            TemporaryError: Temporary server error (5xx)
            SendError: Other HTTP errors
        """
        url = f"{self.base_url}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                
                # Handle specific HTTP errors
                if response.status_code == 403:
                    error_data = response.json() if response.text else {}
                    error_desc = error_data.get("description", "Forbidden")
                    logger.warning(f"User {chat_id} blocked the bot: {error_desc}")
                    raise UserBlockedError(f"User {chat_id} blocked the bot")
                
                elif response.status_code == 401:
                    logger.error("Invalid bot token")
                    raise InvalidTokenError("Invalid bot token")
                
                elif response.status_code == 429:
                    error_data = response.json() if response.text else {}
                    retry_after = error_data.get("parameters", {}).get("retry_after", 60)
                    logger.warning(f"Rate limit exceeded, retry after {retry_after}s")
                    raise RateLimitError(
                        f"Rate limit exceeded, retry after {retry_after}s",
                        retry_after=retry_after
                    )
                
                elif response.status_code >= 500:
                    logger.error(f"Telegram API error: {response.status_code}")
                    raise TemporaryError(f"Telegram API error: {response.status_code}")
                
                # Raise for other 4xx errors
                response.raise_for_status()
                
                result = response.json()
                message_id = result.get("result", {}).get("message_id")
                logger.info(f"Message sent to chat_id={chat_id}, message_id={message_id}")
                
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout sending message to {chat_id}: {e}")
            raise TemporaryError(f"Request timeout: {e}")
        
        except httpx.HTTPError as e:
            if not isinstance(e, (httpx.HTTPStatusError,)):
                logger.error(f"HTTP error sending message to {chat_id}: {e}")
                raise SendError(f"HTTP error: {e}")
            raise
    
    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """
        Answer callback query (button press).
        
        Args:
            callback_query_id: Callback query ID from Telegram
            text: Optional notification text to show to user
            show_alert: Show as alert instead of notification
            
        Returns:
            Response from Telegram API
            
        Raises:
            SendError: If request fails
        """
        url = f"{self.base_url}/answerCallbackQuery"
        payload: Dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert
        }
        
        if text:
            payload["text"] = text
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Answered callback query: {callback_query_id}")
                
                return result
                
        except httpx.HTTPError as e:
            logger.error(f"Error answering callback query {callback_query_id}: {e}")
            raise SendError(f"HTTP error: {e}")
    
    async def send_chat_action(
        self,
        chat_id: int,
        action: str = "typing"
    ) -> Dict[str, Any]:
        """
        Send chat action (typing indicator) via Telegram Bot API.
        
        This tells the user that something is happening on the bot's side.
        The status is set for 5 seconds or until next message is sent.
        
        Args:
            chat_id: Telegram chat ID
            action: Type of action to broadcast (typing, upload_photo, etc.)
            
        Returns:
            Response from Telegram API
            
        Raises:
            UserBlockedError: User has blocked the bot (403)
            InvalidTokenError: Bot token is invalid (401)
            TemporaryError: Temporary server error (5xx)
            SendError: Other HTTP errors
        """
        url = f"{self.base_url}/sendChatAction"
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "action": action
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                
                # Handle specific HTTP errors
                if response.status_code == 403:
                    error_data = response.json() if response.text else {}
                    error_desc = error_data.get("description", "Forbidden")
                    logger.warning(f"User {chat_id} blocked the bot: {error_desc}")
                    raise UserBlockedError(f"User {chat_id} blocked the bot")
                
                elif response.status_code == 401:
                    logger.error("Invalid bot token")
                    raise InvalidTokenError("Invalid bot token")
                
                elif response.status_code >= 500:
                    logger.warning(f"Telegram API error for chat action: {response.status_code}")
                    raise TemporaryError(f"Telegram API error: {response.status_code}")
                
                # Raise for other 4xx errors
                response.raise_for_status()
                
                result = response.json()
                logger.debug(f"Chat action '{action}' sent to chat_id={chat_id}")
                
                return result
                
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout sending chat action to {chat_id}: {e}")
            raise TemporaryError(f"Request timeout: {e}")
        
        except httpx.HTTPError as e:
            if not isinstance(e, (httpx.HTTPStatusError,)):
                logger.warning(f"HTTP error sending chat action to {chat_id}: {e}")
                raise SendError(f"HTTP error: {e}")
            raise
    
    async def download_file(self, file_id: str) -> str:
        """
        Download file from Telegram servers to temporary file.
        
        Uses Telegram Bot API:
        1. getFile - get file_path from file_id
        2. Download file from https://api.telegram.org/file/bot<token>/<file_path>
        
        Includes automatic retry with exponential backoff (3 attempts).
        
        Args:
            file_id: Telegram file identifier
            
        Returns:
            Path to downloaded temporary file
            
        Raises:
            AudioDownloadError: If download fails after retries
            InvalidTokenError: If bot token is invalid
        """
        try:
            return await self._download_file_with_retry(file_id)
        except TemporaryError as e:
            # Convert TemporaryError to AudioDownloadError after all retries
            raise AudioDownloadError(f"Download failed after retries: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(TemporaryError),
        reraise=True,
    )
    async def _download_file_with_retry(self, file_id: str) -> str:
        """Internal method with retry logic for file download."""
        try:
            # Step 1: Get file info from Telegram
            get_file_url = f"{self.base_url}/getFile"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    get_file_url,
                    params={"file_id": file_id}
                )
                
                if response.status_code == 401:
                    raise InvalidTokenError("Invalid bot token")
                
                if response.status_code >= 500:
                    raise TemporaryError(f"Telegram API error: {response.status_code}")
                
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    error_desc = error_data.get("description", "Unknown error")
                    raise AudioDownloadError(f"getFile failed: {error_desc}")
                
                data = response.json()
                
                if not data.get("ok"):
                    error_desc = data.get("description", "Unknown error")
                    raise AudioDownloadError(f"getFile failed: {error_desc}")
                
                file_path = data["result"].get("file_path")
                if not file_path:
                    raise AudioDownloadError("No file_path in getFile response")
                
                # Step 2: Download the file
                # URL format: https://api.telegram.org/file/bot<token>/<file_path>
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                
                download_response = await client.get(download_url)
                
                if download_response.status_code >= 500:
                    raise TemporaryError(
                        f"File download error: {download_response.status_code}"
                    )
                
                if download_response.status_code != 200:
                    raise AudioDownloadError(
                        f"File download failed: HTTP {download_response.status_code}"
                    )
                
                # Step 3: Save to temporary file
                # Determine file extension from file_path
                extension = ".ogg"  # Default for voice messages
                if "." in file_path:
                    extension = "." + file_path.rsplit(".", 1)[-1]
                
                with tempfile.NamedTemporaryFile(
                    suffix=extension,
                    delete=False
                ) as temp_file:
                    temp_file.write(download_response.content)
                    temp_path = temp_file.name
                
                file_size = len(download_response.content)
                logger.info(
                    f"Downloaded file: file_id={file_id}, "
                    f"size={file_size} bytes, path={temp_path}"
                )
                
                return temp_path
                
        except (InvalidTokenError, AudioDownloadError):
            raise
        except TemporaryError:
            logger.warning(f"Temporary error downloading file {file_id}, will retry")
            raise
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout downloading file {file_id}: {e}")
            raise TemporaryError(f"Request timeout: {e}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading file {file_id}: {e}")
            raise AudioDownloadError(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error downloading file {file_id}: {e}")
            raise AudioDownloadError(f"Download failed: {e}")

