"""Repository layer for connection database operations."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError

from app.modules.connections.models import (
    Connection,
    ConnectionChannel,
    ConnectionStatus,
    ConnectionSettings
)

logger = logging.getLogger(__name__)


class ConnectionRepository:
    """Repository for connection database operations."""
    
    def __init__(self):
        """Initialize repository without database dependency."""
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._collection: Optional[AsyncIOMotorCollection] = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["connections"]
    
    async def create(
        self,
        assistant_id: str,
        channel: ConnectionChannel,
        settings: ConnectionSettings,
        status: ConnectionStatus = ConnectionStatus.PENDING
    ) -> Connection:
        """
        Create new connection in database.
        
        Args:
            assistant_id: Assistant ID to connect to
            channel: Communication channel (telegram/whatsapp/webchat)
            settings: Channel-specific settings (encrypted tokens, etc)
            status: Initial connection status (default: PENDING)
            
        Returns:
            Created connection model
            
        Raises:
            DuplicateKeyError: If connection already exists for assistant+channel
        """
        await self._ensure_db()
        
        # Convert assistant_id to ObjectId
        assistant_oid = ObjectId(assistant_id)
        
        doc = {
            "assistant_id": assistant_oid,
            "channel": channel.value,
            "status": status.value,
            "settings": settings.model_dump(),
            "last_error": None,
            "last_checked_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        try:
            result = await self._collection.insert_one(doc)
            doc["_id"] = result.inserted_id
            
            logger.info(f"Created connection for assistant {assistant_id}, channel {channel.value}")
            return Connection(**doc)
            
        except DuplicateKeyError as e:
            logger.error(f"Duplicate connection: assistant {assistant_id} already has {channel.value}")
            raise DuplicateKeyError(
                f"Connection already exists for assistant {assistant_id} and channel {channel.value}"
            )
    
    async def get_by_id(self, connection_id: str) -> Optional[Connection]:
        """
        Get connection by ID.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Connection model or None if not found
        """
        await self._ensure_db()
        
        try:
            doc = await self._collection.find_one({
                "_id": ObjectId(connection_id)
            })
            
            if doc:
                # Convert settings dict to ConnectionSettings object
                if isinstance(doc.get("settings"), dict):
                    doc["settings"] = ConnectionSettings(**doc["settings"])
                return Connection(**doc)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting connection {connection_id}: {e}")
            return None
    
    async def find_by_assistant(
        self,
        assistant_id: str,
        status: Optional[ConnectionStatus] = None
    ) -> List[Connection]:
        """
        Find all connections for an assistant.
        
        Args:
            assistant_id: Assistant ID
            status: Optional status filter
            
        Returns:
            List of connections
        """
        await self._ensure_db()
        
        query = {"assistant_id": ObjectId(assistant_id)}
        
        if status:
            query["status"] = status.value
        
        cursor = self._collection.find(query)
        docs = await cursor.to_list(length=100)
        
        connections = []
        for doc in docs:
            # Convert settings dict to ConnectionSettings object
            if isinstance(doc.get("settings"), dict):
                doc["settings"] = ConnectionSettings(**doc["settings"])
            connections.append(Connection(**doc))
        
        return connections
    
    async def update(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> Optional[Connection]:
        """
        Update connection.
        
        Args:
            connection_id: Connection ID
            data: Fields to update
            
        Returns:
            Updated connection or None if not found
        """
        await self._ensure_db()
        
        # Add updated_at timestamp
        update_doc = {
            "updated_at": datetime.now(timezone.utc),
            **data
        }
        
        # Handle special fields
        if "status" in update_doc and isinstance(update_doc["status"], ConnectionStatus):
            update_doc["status"] = update_doc["status"].value
        
        if "channel" in update_doc and isinstance(update_doc["channel"], ConnectionChannel):
            update_doc["channel"] = update_doc["channel"].value
        
        if "settings" in update_doc and hasattr(update_doc["settings"], "model_dump"):
            update_doc["settings"] = update_doc["settings"].model_dump()
        
        result = await self._collection.find_one_and_update(
            {"_id": ObjectId(connection_id)},
            {"$set": update_doc},
            return_document=True
        )
        
        if result:
            # Convert settings dict to ConnectionSettings object
            if isinstance(result.get("settings"), dict):
                result["settings"] = ConnectionSettings(**result["settings"])
            
            logger.info(f"Updated connection {connection_id}")
            return Connection(**result)
        
        return None
    
    async def delete(self, connection_id: str) -> bool:
        """
        Delete connection.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            True if deleted, False if not found
        """
        await self._ensure_db()
        
        result = await self._collection.delete_one({
            "_id": ObjectId(connection_id)
        })
        
        if result.deleted_count > 0:
            logger.info(f"Deleted connection {connection_id}")
            return True
        
        return False
    
    async def exists_by_assistant_and_channel(
        self,
        assistant_id: str,
        channel: ConnectionChannel
    ) -> bool:
        """
        Check if connection exists for assistant and channel.
        
        Args:
            assistant_id: Assistant ID
            channel: Communication channel
            
        Returns:
            True if exists, False otherwise
        """
        await self._ensure_db()
        
        count = await self._collection.count_documents({
            "assistant_id": ObjectId(assistant_id),
            "channel": channel.value
        })
        
        return count > 0
    
    async def update_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        error: Optional[str] = None
    ) -> Optional[Connection]:
        """
        Update connection status and error.
        
        Args:
            connection_id: Connection ID
            status: New status
            error: Optional error message
            
        Returns:
            Updated connection or None if not found
        """
        update_data = {
            "status": status,
            "last_checked_at": datetime.now(timezone.utc)
        }
        
        if error:
            update_data["last_error"] = error
        elif status == ConnectionStatus.CONNECTED:
            # Clear error if status is connected
            update_data["last_error"] = None
        
        return await self.update(connection_id, update_data)
    
    async def get_by_assistant_and_channel(
        self,
        assistant_id: str,
        channel: ConnectionChannel
    ) -> Optional[Connection]:
        """
        Get connection by assistant ID and channel.
        
        Args:
            assistant_id: Assistant ID
            channel: Communication channel
            
        Returns:
            Connection or None if not found
        """
        await self._ensure_db()
        
        # Convert string ID to ObjectId for query
        try:
            query_id = ObjectId(assistant_id)
        except Exception as e:
            logger.warning(f"Failed to convert assistant_id to ObjectId: {assistant_id}, error: {e}")
            query_id = assistant_id  # Fallback if already ObjectId or invalid
            
        doc = await self._collection.find_one({
            "assistant_id": query_id,
            "channel": channel.value
        })
        
        if doc:
            # Convert settings dict to ConnectionSettings object
            if isinstance(doc.get("settings"), dict):
                doc["settings"] = ConnectionSettings(**doc["settings"])
            return Connection(**doc)
        
        return None
