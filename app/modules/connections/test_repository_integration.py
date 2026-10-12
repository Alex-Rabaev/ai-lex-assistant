"""Integration test for repository with real MongoDB (optional, requires DB)."""

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
import os
from unittest.mock import patch, AsyncMock

from app.modules.connections.repository import ConnectionRepository
from app.modules.connections.models import (
    ConnectionChannel,
    ConnectionSettings,
    ConnectionStatus
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "true").lower() == "true",
    reason="Integration tests skipped (set SKIP_INTEGRATION_TESTS=false to run)"
)
async def test_unique_constraint_integration():
    """
    Integration test to verify unique constraint works with real MongoDB.
    
    This test requires MongoDB to be running and accessible.
    It will create and clean up test data.
    """
    # Get MongoDB URL from environment or use default
    mongo_url = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = "test_assistants_platform"
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Patch get_database to return our test db
    async def mock_get_database():
        return db
    
    with patch('app.modules.connections.repository.get_database', new=mock_get_database):
        # Create repository (will use patched get_database)
        repository = ConnectionRepository()
        
        # Ensure indexes exist
        await db["connections"].create_index(
            [("assistant_id", 1), ("channel", 1)],
            unique=True,
            name="assistant_channel_unique"
        )
        
        try:
            # Test data
            assistant_id = "507f1f77bcf86cd799439999"
            settings = ConnectionSettings(
                bot_token="encrypted_test_token",
                bot_username="@test_bot"
            )
            
            # Create first connection - should succeed
            connection1 = await repository.create(
                assistant_id,
                ConnectionChannel.TELEGRAM,
                settings
            )
            assert connection1 is not None
            
            # Try to create duplicate - should fail
            with pytest.raises(DuplicateKeyError):
                await repository.create(
                    assistant_id,
                    ConnectionChannel.TELEGRAM,  # Same channel!
                    settings
                )
            
            # Creating with different channel should succeed
            connection2 = await repository.create(
                assistant_id,
                ConnectionChannel.WHATSAPP,  # Different channel
                settings
            )
            assert connection2 is not None
            
            # Verify both exist
            connections = await repository.find_by_assistant(assistant_id)
            assert len(connections) == 2
            
        finally:
            # Clean up test data
            await db["connections"].delete_many({
                "assistant_id": {"$regex": "507f1f77bcf86cd799439999"}
            })
            
            # Close connection
            client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "true").lower() == "true",
    reason="Integration tests skipped"
)
async def test_repository_crud_integration():
    """
    Full CRUD integration test with real MongoDB.
    """
    mongo_url = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = "test_assistants_platform"
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Patch get_database to return our test db
    async def mock_get_database():
        return db
    
    with patch('app.modules.connections.repository.get_database', new=mock_get_database):
        repository = ConnectionRepository()
        
        try:
            assistant_id = "507f1f77bcf86cd799439888"
            settings = ConnectionSettings(
                bot_token="encrypted_token_123",
                bot_username="@crud_test_bot",
                bot_id=987654321,
                bot_first_name="CRUD Test Bot"
            )
            
            # CREATE
            connection = await repository.create(
                assistant_id,
                ConnectionChannel.TELEGRAM,
                settings
            )
            connection_id = str(connection.id)
            
            # READ
            fetched = await repository.get_by_id(connection_id)
            assert fetched is not None
            assert fetched.settings.bot_username == "@crud_test_bot"
            
            # UPDATE
            updated = await repository.update_status(
                connection_id,
                ConnectionStatus.CONNECTED,
                None
            )
            assert updated.status == ConnectionStatus.CONNECTED
            assert updated.last_error is None
            
            # EXISTS
            exists = await repository.exists_by_assistant_and_channel(
                assistant_id,
                ConnectionChannel.TELEGRAM
            )
            assert exists is True
            
            # DELETE
            deleted = await repository.delete(connection_id)
            assert deleted is True
            
            # Verify deleted
            fetched_after_delete = await repository.get_by_id(connection_id)
            assert fetched_after_delete is None
            
        finally:
            # Clean up any remaining test data
            await db["connections"].delete_many({
                "assistant_id": {"$regex": "507f1f77bcf86cd799439888"}
            })
            client.close()
