"""WhatsApp Business Cloud API client for managing connections."""

import logging
from typing import Dict, Any
import httpx

from app.modules.connections.exceptions import (
    InvalidAccessTokenError,
    WhatsAppAPIError
)

logger = logging.getLogger(__name__)


class WhatsAppBusinessInfo:
    """WhatsApp Business phone number info."""
    
    def __init__(
        self,
        phone_number_id: str,
        display_phone_number: str,
        verified_name: str = None,
        quality_rating: str = None
    ):
        self.phone_number_id = phone_number_id
        self.display_phone_number = display_phone_number
        self.verified_name = verified_name
        self.quality_rating = quality_rating


class WhatsAppClient:
    """Client for Meta WhatsApp Business Cloud API."""
    
    BASE_URL = "https://graph.facebook.com/v18.0"
    DEFAULT_TIMEOUT = 10.0
    
    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize WhatsApp client."""
        self.timeout = timeout
    
    async def validate_credentials(
        self,
        phone_number_id: str,
        access_token: str
    ) -> WhatsAppBusinessInfo:
        """
        Validate credentials by getting phone number info.
        
        Args:
            phone_number_id: WhatsApp Phone Number ID
            access_token: Meta Graph API access token
            
        Returns:
            WhatsAppBusinessInfo with phone details
            
        Raises:
            InvalidAccessTokenError: If token is invalid
            WhatsAppAPIError: For other API errors
        """
        url = f"{self.BASE_URL}/{phone_number_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"fields": "display_phone_number,verified_name,quality_rating"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 401:
                    raise InvalidAccessTokenError("Invalid or expired access token")
                elif response.status_code == 400:
                    data = response.json()
                    error = data.get("error", {})
                    if error.get("code") == 100:
                        raise InvalidAccessTokenError("Invalid phone number ID")
                    raise WhatsAppAPIError(
                        error.get("message", "Bad request"),
                        error_code=error.get("code")
                    )
                elif response.status_code != 200:
                    raise WhatsAppAPIError(
                        f"WhatsApp API error: {response.status_code}",
                        error_code=response.status_code
                    )
                
                data = response.json()
                
                if "error" in data:
                    error = data["error"]
                    if error.get("code") in [190, 463]:
                        raise InvalidAccessTokenError(error.get("message", "Token error"))
                    raise WhatsAppAPIError(
                        error.get("message", "Unknown error"),
                        error_code=error.get("code")
                    )
                
                info = WhatsAppBusinessInfo(
                    phone_number_id=phone_number_id,
                    display_phone_number=data.get("display_phone_number", ""),
                    verified_name=data.get("verified_name"),
                    quality_rating=data.get("quality_rating")
                )
                
                logger.info(
                    f"Validated WhatsApp credentials: {info.display_phone_number} "
                    f"({info.verified_name or 'unverified'})"
                )
                return info
                
            except httpx.TimeoutException:
                raise WhatsAppAPIError("Request timeout - WhatsApp API not responding")
            except httpx.NetworkError as e:
                raise WhatsAppAPIError(f"Network error: {e}")
            except httpx.RequestError as e:
                raise WhatsAppAPIError(f"Request error: {e}")

