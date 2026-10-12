"""WhatsApp Cloud API client for sending messages."""

import logging
import tempfile
from typing import Dict, Any, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.modules.outbound.exceptions import (
    SendError,
    TemporaryError,
    InvalidTokenError
)
from app.common.audio.exceptions import AudioDownloadError

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Client for sending WhatsApp messages via Meta Cloud API."""
    
    BASE_URL = "https://graph.facebook.com/v18.0"
    DEFAULT_TIMEOUT = 30.0
    
    def __init__(self, phone_number_id: str, access_token: str):
        """
        Initialize WhatsApp client.
        
        Args:
            phone_number_id: WhatsApp Phone Number ID
            access_token: Meta Graph API access token
        """
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.timeout = self.DEFAULT_TIMEOUT
    
    async def send_text_message(
        self,
        to: str,
        text: str,
        preview_url: bool = False
    ) -> Dict[str, Any]:
        """
        Send text message to WhatsApp user.
        
        Args:
            to: Recipient phone number (without + prefix)
            text: Message text
            preview_url: Whether to show link previews
            
        Returns:
            API response with message ID
            
        Raises:
            SendError: If message cannot be sent
            InvalidTokenError: If token is invalid
            TemporaryError: For temporary errors (retry)
        """
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 401:
                    raise InvalidTokenError("Invalid or expired access token")
                
                if response.status_code == 429:
                    raise TemporaryError("Rate limit exceeded")
                
                if response.status_code >= 500:
                    raise TemporaryError(f"WhatsApp API error: {response.status_code}")
                
                data = response.json()
                
                if "error" in data:
                    error = data["error"]
                    code = error.get("code", 0)
                    message = error.get("message", "Unknown error")
                    
                    # Token errors
                    if code in [190, 463]:
                        raise InvalidTokenError(message)
                    
                    # Rate limits
                    if code == 80007:
                        raise TemporaryError(message)
                    
                    raise SendError(message)
                
                logger.info(f"Message sent: {data.get('messages', [{}])[0].get('id')}")
                return data
                
            except httpx.TimeoutException:
                raise TemporaryError("Request timeout")
            except httpx.NetworkError as e:
                raise TemporaryError(f"Network error: {e}")
    
    async def mark_as_read_with_typing(self, message_id: str) -> bool:
        """
        Mark message as read and show typing indicator.
        
        Combines two actions in one API call:
        - status: "read" - shows blue checkmarks
        - typing_indicator: {"type": "text"} - shows typing bubble with dots
        """
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"}
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    logger.debug(f"Marked as read with typing: {message_id}")
                    return True
                return False
        except Exception as e:
            logger.warning(f"Failed to mark as read with typing: {e}")
            return False
    
    async def download_file(self, media_id: str) -> str:
        """
        Download media file from WhatsApp Cloud API.
        
        WhatsApp media download is a two-step process:
        1. GET /{media-id} to get the download URL
        2. GET the download URL with Authorization header
        
        Args:
            media_id: WhatsApp media ID
            
        Returns:
            Path to downloaded temporary file
            
        Raises:
            AudioDownloadError: If download fails after retries
            InvalidTokenError: If access token is invalid
        """
        try:
            return await self._download_file_with_retry(media_id)
        except TemporaryError as e:
            raise AudioDownloadError(f"Download failed after retries: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(TemporaryError),
        reraise=True,
    )
    async def _download_file_with_retry(self, media_id: str) -> str:
        """Internal method with retry logic for file download."""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Step 1: Get media URL from WhatsApp API
                media_url_endpoint = f"{self.BASE_URL}/{media_id}"
                
                response = await client.get(media_url_endpoint, headers=headers)
                
                if response.status_code == 401:
                    raise InvalidTokenError("Invalid or expired access token")
                
                if response.status_code >= 500:
                    raise TemporaryError(f"WhatsApp API error: {response.status_code}")
                
                if response.status_code != 200:
                    data = response.json() if response.text else {}
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    raise AudioDownloadError(f"Failed to get media URL: {error_msg}")
                
                data = response.json()
                download_url = data.get("url")
                mime_type = data.get("mime_type", "audio/ogg")
                
                if not download_url:
                    raise AudioDownloadError("No download URL in response")
                
                # Step 2: Download the actual file
                download_response = await client.get(
                    download_url,
                    headers=headers  # WhatsApp requires auth for download too
                )
                
                if download_response.status_code >= 500:
                    raise TemporaryError(
                        f"File download error: {download_response.status_code}"
                    )
                
                if download_response.status_code != 200:
                    raise AudioDownloadError(
                        f"File download failed: HTTP {download_response.status_code}"
                    )
                
                # Step 3: Save to temporary file
                # Determine extension from mime_type
                extension = ".ogg"  # Default for WhatsApp voice
                if "mpeg" in mime_type or "mp3" in mime_type:
                    extension = ".mp3"
                elif "mp4" in mime_type or "m4a" in mime_type:
                    extension = ".m4a"
                elif "wav" in mime_type:
                    extension = ".wav"
                
                with tempfile.NamedTemporaryFile(
                    suffix=extension,
                    delete=False
                ) as temp_file:
                    temp_file.write(download_response.content)
                    temp_path = temp_file.name
                
                file_size = len(download_response.content)
                logger.info(
                    f"Downloaded WhatsApp media: media_id={media_id}, "
                    f"size={file_size} bytes, path={temp_path}"
                )
                
                return temp_path
                
        except (InvalidTokenError, AudioDownloadError):
            raise
        except TemporaryError:
            logger.warning(f"Temporary error downloading media {media_id}, will retry")
            raise
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout downloading media {media_id}: {e}")
            raise TemporaryError(f"Request timeout: {e}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading media {media_id}: {e}")
            raise AudioDownloadError(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error downloading media {media_id}: {e}")
            raise AudioDownloadError(f"Download failed: {e}")

