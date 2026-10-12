"""WhatsApp-specific connection service."""

import logging
from typing import Optional, Tuple
from pymongo.errors import DuplicateKeyError

from app.modules.connections.vendors.whatsapp.client import WhatsAppClient
from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.security import encrypt_token
from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)
from app.modules.connections.exceptions import (
    DuplicateConnectionError,
    InvalidAccessTokenError
)
from app.config import config

logger = logging.getLogger(__name__)


class WhatsAppConnectionService:
    """Service for WhatsApp-specific connection operations."""
    
    def __init__(self):
        """Initialize service with client and repository."""
        self._client = WhatsAppClient()
        self._repository = ConnectionRepository()
    
    async def create_connection(
        self,
        assistant_id: str,
        phone_number_id: str,
        access_token: str,
        app_secret: str,
        verify_token: str
    ) -> Connection:
        """
        Create WhatsApp connection:
        1. Check uniqueness
        2. Validate credentials with Meta API
        3. Encrypt tokens
        4. Save to database (webhook setup is manual via Meta Portal)
        
        Args:
            assistant_id: Assistant ID to connect
            phone_number_id: WhatsApp Phone Number ID
            access_token: Meta Graph API access token
            app_secret: App secret for webhook signature verification
            verify_token: Token for webhook verification challenge
            
        Returns:
            Created connection
            
        Raises:
            DuplicateConnectionError: If WhatsApp already connected
            InvalidAccessTokenError: If credentials validation fails
        """
        logger.info(f"Creating WhatsApp connection for assistant {assistant_id}")
        
        # 1. Check if WhatsApp connection already exists
        existing = await self._repository.exists_by_assistant_and_channel(
            assistant_id,
            ConnectionChannel.WHATSAPP
        )
        if existing:
            raise DuplicateConnectionError(
                f"Assistant {assistant_id} already has a WhatsApp connection"
            )
        
        # 2. Validate credentials with Meta API
        try:
            business_info = await self._client.validate_credentials(
                phone_number_id,
                access_token
            )
            logger.info(f"Validated WhatsApp: {business_info.display_phone_number}")
        except InvalidAccessTokenError:
            raise
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            raise InvalidAccessTokenError(f"Failed to validate credentials: {e}")
        
        # 3. Encrypt sensitive tokens
        try:
            encrypted_access_token = encrypt_token(access_token, config.ENCRYPTION_KEY)
            encrypted_app_secret = encrypt_token(app_secret, config.ENCRYPTION_KEY)
        except Exception as e:
            logger.error(f"Failed to encrypt tokens: {e}")
            raise ValueError(f"Token encryption failed: {e}")
        
        # 4. Prepare connection settings
        webhook_url = f"{config.WEBHOOK_BASE_URL}/webhook/whatsapp/{assistant_id}"
        
        settings = ConnectionSettings(
            bot_token=encrypted_access_token,  # Reuse field for access_token
            bot_username=business_info.display_phone_number,
            bot_first_name=business_info.verified_name,
            webhook_url=webhook_url,
            webhook_secret=verify_token,
            bot_info={
                "phone_number_id": phone_number_id,
                "display_phone_number": business_info.display_phone_number,
                "verified_name": business_info.verified_name,
                "quality_rating": business_info.quality_rating,
                "app_secret_encrypted": encrypted_app_secret
            }
        )
        
        # 5. Save to database (status = PENDING until webhook verified)
        try:
            connection = await self._repository.create(
                assistant_id,
                ConnectionChannel.WHATSAPP,
                settings
            )
            logger.info(f"Created WhatsApp connection {connection.id}")
        except DuplicateKeyError:
            raise DuplicateConnectionError(
                f"Assistant {assistant_id} already has a WhatsApp connection"
            )
        
        return connection
    
    async def check_health(
        self,
        connection: Connection
    ) -> Tuple[bool, Optional[str]]:
        """
        Check WhatsApp connection health by validating credentials.
        
        Args:
            connection: Connection to check
            
        Returns:
            Tuple of (is_healthy, error_message)
        """
        if not connection.settings or not connection.settings.bot_token:
            return False, "No access token configured"
        
        try:
            from app.modules.connections.security import decrypt_token
            
            access_token = decrypt_token(
                connection.settings.bot_token,
                config.ENCRYPTION_KEY
            )
            phone_number_id = connection.settings.bot_info.get("phone_number_id")
            
            if not phone_number_id:
                return False, "No phone number ID configured"
            
            await self._client.validate_credentials(phone_number_id, access_token)
            return True, None
            
        except InvalidAccessTokenError as e:
            return False, str(e)
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False, str(e)

