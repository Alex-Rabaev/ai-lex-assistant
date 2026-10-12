"""Temporal Client connection manager.

Manages the connection to Temporal Service for starting and querying workflows.
Used by WorkflowService in the API process and by Temporal Worker.

Supports both local Temporal (no auth) and Temporal Cloud (API Key + TLS).
"""

import logging
from typing import Optional

from temporalio.client import Client

from app.config import config

logger = logging.getLogger(__name__)

_NOT_SET = object()


class TemporalClientManager:
    """Manages Temporal Client connection with lazy initialization.
    
    Automatically detects Temporal Cloud (when API key is set)
    and configures TLS + API Key authentication.
    
    Usage:
        manager = TemporalClientManager()
        client = await manager.get_client()
        handle = await client.start_workflow(...)
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        namespace: Optional[str] = None,
        api_key=_NOT_SET
    ):
        """Initialize Temporal Client manager.
        
        Args:
            host: Temporal gRPC endpoint (defaults to config.TEMPORAL_HOST)
            namespace: Temporal namespace (defaults to config.TEMPORAL_NAMESPACE)
            api_key: Temporal Cloud API key. Pass None to disable.
                     Defaults to config.TEMPORAL_API_KEY.
        """
        self.host = host or config.TEMPORAL_HOST
        self.namespace = namespace or config.TEMPORAL_NAMESPACE
        self.api_key = config.TEMPORAL_API_KEY if api_key is _NOT_SET else api_key
        self._client: Optional[Client] = None
    
    async def get_client(self) -> Client:
        """Get or create Temporal Client.
        
        Lazily connects on first call. Reuses existing connection.
        If API key is set, connects with TLS (Temporal Cloud).
        
        Returns:
            Connected Temporal Client
            
        Raises:
            RuntimeError: If connection to Temporal fails
        """
        if self._client is not None:
            return self._client
        
        try:
            connect_kwargs = {
                "target_host": self.host,
                "namespace": self.namespace,
            }
            
            # Temporal Cloud: API Key + TLS
            if self.api_key:
                connect_kwargs["api_key"] = self.api_key
                connect_kwargs["tls"] = True
                logger.info(f"Connecting to Temporal Cloud: host={self.host}")
            else:
                logger.info(f"Connecting to local Temporal: host={self.host}")
            
            self._client = await Client.connect(**connect_kwargs)
            
            logger.info(
                f"Connected to Temporal: "
                f"host={self.host}, namespace={self.namespace}, "
                f"cloud={'yes' if self.api_key else 'no'}"
            )
            return self._client
        except Exception as e:
            logger.error(
                f"Failed to connect to Temporal: "
                f"host={self.host}, error={e}"
            )
            raise RuntimeError(f"Failed to connect to Temporal: {e}") from e
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None
    
    async def close(self) -> None:
        """Close the Temporal Client connection."""
        if self._client is not None:
            self._client = None
            logger.info("Temporal Client connection closed")
