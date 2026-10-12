"""
Migration 001: Create initial collections and indexes for assistants platform.

Run: python migrations/mongodb/001_initial_collections.py
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Migration001InitialCollections:
    """Create initial collections with indexes and validation."""
    
    def __init__(self):
        """Initialize migration with database connection."""
        # Use existing config from app
        from app.config import config
        
        self.db_url = config.MONGODB_URL
        self.db_name = config.MONGODB_DB_NAME
        self.client = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB."""
        logger.info(f"Connecting to MongoDB: {self.db_url}")
        self.client = AsyncIOMotorClient(self.db_url)
        self.db = self.client[self.db_name]
        
        # Test connection
        await self.client.server_info()
        logger.info(f"Connected to database: {self.db_name}")
    
    async def disconnect(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def create_assistants_collection(self):
        """Create assistants collection with indexes and validation."""
        logger.info("Creating 'assistants' collection...")
        
        # Collection validation schema
        validation_schema = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["org_id", "owner_user_id", "name", "type", "status"],
                "properties": {
                    "org_id": {
                        "bsonType": "string",
                        "description": "Organization ID is required"
                    },
                    "owner_user_id": {
                        "bsonType": "string",
                        "description": "Owner user ID is required"
                    },
                    "name": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 100,
                        "description": "Assistant name is required"
                    },
                    "type": {
                        "enum": ["survey", "faq", "support"],
                        "description": "Assistant type must be valid"
                    },
                    "status": {
                        "enum": ["draft", "inactive", "active", "paused", "archived"],
                        "description": "Status must be valid"
                    },
                    "settings": {
                        "bsonType": "object"
                    },
                    "created_at": {
                        "bsonType": "date"
                    },
                    "updated_at": {
                        "bsonType": "date"
                    }
                }
            }
        }
        
        # Create collection with validation
        try:
            await self.db.create_collection(
                "assistants",
                validator=validation_schema
            )
            logger.info("Collection 'assistants' created with validation schema")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Collection 'assistants' already exists")
                # Update validation on existing collection
                await self.db.command({
                    "collMod": "assistants",
                    "validator": validation_schema
                })
                logger.info("Updated validation schema for 'assistants'")
            else:
                raise
        
        # Create indexes
        collection = self.db["assistants"]
        
        # Index 1: org_id + status (for filtering assistants by org and status)
        await collection.create_index(
            [("org_id", 1), ("status", 1)],
            name="org_status_idx"
        )
        logger.info("Created index: org_id + status")
        
        # Index 2: org_id + name (unique within organization)
        await collection.create_index(
            [("org_id", 1), ("name", 1)],
            unique=True,
            name="org_name_unique_idx"
        )
        logger.info("Created unique index: org_id + name")
        
        # Index 3: created_at descending (for sorting)
        await collection.create_index(
            [("created_at", -1)],
            name="created_at_desc_idx"
        )
        logger.info("Created index: created_at DESC")
        
        # Index 4: owner_user_id (for finding user's assistants)
        await collection.create_index(
            [("owner_user_id", 1)],
            name="owner_user_idx"
        )
        logger.info("Created index: owner_user_id")
    
    async def create_assistant_steps_collection(self):
        """Create assistant_steps collection with indexes and validation."""
        logger.info("Creating 'assistant_steps' collection...")
        
        # Collection validation schema
        validation_schema = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["assistant_id", "step_key", "order_no", "prompt_template"],
                "properties": {
                    "assistant_id": {
                        "bsonType": "objectId",
                        "description": "Assistant ID is required"
                    },
                    "step_key": {
                        "bsonType": "string",
                        "pattern": "^[a-zA-Z0-9_]+$",
                        "description": "Step key must be alphanumeric with underscores"
                    },
                    "order_no": {
                        "bsonType": "int",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Order number must be between 1 and 100"
                    },
                    "prompt_template": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 2000,
                        "description": "Prompt template is required"
                    },
                    "step_config": {
                        "bsonType": "object"
                    },
                    "validators": {
                        "bsonType": "object"
                    },
                    "created_at": {
                        "bsonType": "date"
                    },
                    "updated_at": {
                        "bsonType": "date"
                    }
                }
            }
        }
        
        # Create collection with validation
        try:
            await self.db.create_collection(
                "assistant_steps",
                validator=validation_schema
            )
            logger.info("Collection 'assistant_steps' created with validation schema")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Collection 'assistant_steps' already exists")
                # Update validation on existing collection
                await self.db.command({
                    "collMod": "assistant_steps",
                    "validator": validation_schema
                })
                logger.info("Updated validation schema for 'assistant_steps'")
            else:
                raise
        
        # Create indexes
        collection = self.db["assistant_steps"]
        
        # Index 1: assistant_id + order_no (for sorting steps)
        await collection.create_index(
            [("assistant_id", 1), ("order_no", 1)],
            name="assistant_order_idx"
        )
        logger.info("Created index: assistant_id + order_no")
        
        # Index 2: assistant_id + step_key (unique)
        await collection.create_index(
            [("assistant_id", 1), ("step_key", 1)],
            unique=True,
            name="assistant_step_unique_idx"
        )
        logger.info("Created unique index: assistant_id + step_key")
        
        # Index 3: assistant_id alone (for finding all steps of an assistant)
        await collection.create_index(
            [("assistant_id", 1)],
            name="assistant_id_idx"
        )
        logger.info("Created index: assistant_id")
    
    async def create_migration_history(self):
        """Create migration history collection to track applied migrations."""
        logger.info("Creating 'migration_history' collection...")
        
        try:
            await self.db.create_collection("migration_history")
            logger.info("Collection 'migration_history' created")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Collection 'migration_history' already exists")
            else:
                raise
        
        # Record this migration
        await self.db.migration_history.insert_one({
            "migration_id": "001_initial_collections",
            "description": "Create assistants and assistant_steps collections with indexes",
            "applied_at": datetime.now(timezone.utc),
            "status": "completed"
        })
        logger.info("Migration recorded in history")
    
    async def verify_collections(self):
        """Verify that collections and indexes were created correctly."""
        logger.info("\nVerifying collections and indexes...")
        
        # Check assistants collection
        assistants_indexes = await self.db.assistants.list_indexes().to_list(None)
        logger.info(f"\nAssistants collection indexes:")
        for idx in assistants_indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
        
        # Check assistant_steps collection  
        steps_indexes = await self.db.assistant_steps.list_indexes().to_list(None)
        logger.info(f"\nAssistant_steps collection indexes:")
        for idx in steps_indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
        
        # Check collections list
        collections = await self.db.list_collection_names()
        logger.info(f"\nAll collections in database: {collections}")
        
        required_collections = ["assistants", "assistant_steps", "migration_history"]
        for coll in required_collections:
            if coll in collections:
                logger.info(f"✅ Collection '{coll}' exists")
            else:
                logger.error(f"❌ Collection '{coll}' NOT found")
    
    async def run(self):
        """Run the migration."""
        try:
            await self.connect()
            
            logger.info("\n" + "="*60)
            logger.info("Starting Migration 001: Initial Collections")
            logger.info("="*60 + "\n")
            
            # Check if migration already applied
            history = await self.db.migration_history.find_one({
                "migration_id": "001_initial_collections"
            })
            
            if history and history.get("status") == "completed":
                logger.info("⚠️  Migration 001 already applied. Skipping...")
                await self.verify_collections()
                return
            
            # Run migration steps
            await self.create_assistants_collection()
            await self.create_assistant_steps_collection()
            await self.create_migration_history()
            
            # Verify everything was created
            await self.verify_collections()
            
            logger.info("\n" + "="*60)
            logger.info("✅ Migration 001 completed successfully!")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
        finally:
            await self.disconnect()


async def main():
    """Main entry point for running migration."""
    migration = Migration001InitialCollections()
    await migration.run()


if __name__ == "__main__":
    asyncio.run(main())
