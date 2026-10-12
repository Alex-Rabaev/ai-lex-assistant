"""Repository for managing interlocutors."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.modules.conversations.models.interlocutor import Interlocutor

logger = logging.getLogger(__name__)


class InterlocutorRepository:
    """Repository for interlocutor database operations."""
    
    def __init__(self):
        """Initialize repository."""
        self._db = None
        self._collection = None
    
    async def _ensure_db(self):
        """Ensure database connection is initialized."""
        if self._db is None:
            from app.common.db.database import get_database
            self._db = await get_database()
            self._collection = self._db["interlocutors"]
    
    async def get_by_id(self, interlocutor_id: str) -> Optional[Interlocutor]:
        """
        Get interlocutor by ID.
        
        Args:
            interlocutor_id: Interlocutor ObjectId as string
            
        Returns:
            Interlocutor if found, None otherwise
        """
        await self._ensure_db()
        doc = await self._collection.find_one({"_id": ObjectId(interlocutor_id)})
        
        if doc:
            return Interlocutor(**doc)
        return None
    
    async def get_by_user_id(self, user_id: str) -> Optional[Interlocutor]:
        """
        Get interlocutor by user_id.
        
        Args:
            user_id: User ID in format 'channel_chatid'
            
        Returns:
            Interlocutor if found, None otherwise
        """
        await self._ensure_db()
        doc = await self._collection.find_one({"user_id": user_id})
        
        if doc:
            return Interlocutor(**doc)
        return None
    
    async def create(
        self,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> Interlocutor:
        """
        Create new interlocutor.
        
        Args:
            user_id: User ID in format 'channel_chatid'
            first_name: User's first name
            last_name: User's last name
            username: User's username
            language_code: User's language code
            
        Returns:
            Created Interlocutor
        """
        await self._ensure_db()
        now = datetime.now(timezone.utc)
        
        interlocutor_data = {
            "user_id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "language": None,  # Will be set when user selects language
            "profile": {},
            "created_at": now,
            "updated_at": now
        }
        
        result = await self._collection.insert_one(interlocutor_data)
        interlocutor_data["_id"] = result.inserted_id
        
        logger.info(f"Created interlocutor: user_id={user_id}, id={result.inserted_id}")
        
        return Interlocutor(**interlocutor_data)
    
    async def get_or_create(
        self,
        user_id: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> Interlocutor:
        """
        Get existing interlocutor or create new one.
        
        Args:
            user_id: User ID in format 'channel_chatid'
            user_info: Optional user info from webhook (first_name, last_name, etc.)
            
        Returns:
            Interlocutor (existing or newly created)
        """
        await self._ensure_db()
        # Try to get existing
        interlocutor = await self.get_by_user_id(user_id)
        
        if interlocutor:
            logger.debug(f"Found existing interlocutor: {user_id}")
            return interlocutor
        
        # Create new with user_info
        user_info = user_info or {}
        
        interlocutor = await self.create(
            user_id=user_id,
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            username=user_info.get("username"),
            language_code=user_info.get("language_code")
        )
        
        return interlocutor
    
    async def update(
        self,
        interlocutor_id: str,
        update_data: Dict[str, Any]
    ) -> None:
        """
        Update interlocutor fields.
        
        Args:
            interlocutor_id: Interlocutor ObjectId as string
            update_data: Dictionary with fields to update
        """
        await self._ensure_db()
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        await self._collection.update_one(
            {"_id": ObjectId(interlocutor_id)},
            {"$set": update_data}
        )
        
        logger.debug(f"Updated interlocutor {interlocutor_id}: {list(update_data.keys())}")
    
    async def update_opted_out(self, interlocutor_id: str, opted_out: bool = True) -> bool:
        """
        Update opted_out flag (unsubscribed from follow-up reminders).

        Args:
            interlocutor_id: Interlocutor ObjectId as string
            opted_out: New value (default True)

        Returns:
            True if updated, False if not found
        """
        await self._ensure_db()
        result = await self._collection.update_one(
            {"_id": ObjectId(interlocutor_id)},
            {
                "$set": {
                    "opted_out": opted_out,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.modified_count > 0:
            logger.info(f"Updated opted_out={opted_out} for interlocutor {interlocutor_id}")
            return True
        return False

    async def update_blocked(self, interlocutor_id: str, blocked: bool = True) -> bool:
        """
        Update blocked flag (user blocked the bot, e.g. Telegram 403).

        Args:
            interlocutor_id: Interlocutor ObjectId as string
            blocked: New value (default True)

        Returns:
            True if updated, False if not found
        """
        await self._ensure_db()
        result = await self._collection.update_one(
            {"_id": ObjectId(interlocutor_id)},
            {
                "$set": {
                    "blocked": blocked,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.modified_count > 0:
            logger.info(f"Updated blocked={blocked} for interlocutor {interlocutor_id}")
            return True
        return False

    async def update_user_id(
        self,
        old_user_id: str,
        new_user_id: str
    ) -> bool:
        """
        Update user_id for an interlocutor (for claiming anonymous sessions).
        
        Args:
            old_user_id: Old user ID (anonymous ID)
            new_user_id: New user ID (authenticated email)
            
        Returns:
            True if updated, False if not found
        """
        await self._ensure_db()
        
        result = await self._collection.update_one(
            {"user_id": old_user_id},
            {
                "$set": {
                    "user_id": new_user_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated interlocutor user_id: {old_user_id} → {new_user_id}")
            return True

        return False

    async def create_mock(
        self,
        user_id: str,
        first_name: str,
    ) -> Interlocutor:
        """Create a mock interlocutor with is_mock=True.

        Args:
            user_id: Unique user ID in format 'mock_<uuid>'
            first_name: Generated fake name

        Returns:
            Created Interlocutor
        """
        await self._ensure_db()
        now = datetime.now(timezone.utc)
        data = {
            "user_id": user_id,
            "first_name": first_name,
            "last_name": None,
            "username": None,
            "language": None,
            "profile": {},
            "is_mock": True,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection.insert_one(data)
        data["_id"] = result.inserted_id
        logger.info(f"Created mock interlocutor: user_id={user_id}, id={result.inserted_id}")
        return Interlocutor(**data)

    async def delete_by_id(self, interlocutor_id: str) -> bool:
        """Delete a single interlocutor by ID."""
        await self._ensure_db()
        result = await self._collection.delete_one({"_id": ObjectId(interlocutor_id)})
        if result.deleted_count > 0:
            logger.info(f"Deleted interlocutor {interlocutor_id}")
            return True
        return False

    async def delete_many_by_ids(self, interlocutor_ids: List[str]) -> int:
        """Delete interlocutors by IDs.

        Args:
            interlocutor_ids: List of interlocutor ObjectId strings

        Returns:
            Number of deleted records
        """
        if not interlocutor_ids:
            return 0
        await self._ensure_db()
        ids = [ObjectId(iid) for iid in interlocutor_ids if iid]
        if not ids:
            return 0
        result = await self._collection.delete_many({"_id": {"$in": ids}})
        logger.info(f"Deleted {result.deleted_count} mock interlocutors")
        return result.deleted_count
