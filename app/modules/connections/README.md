# Connections Module

Module for managing assistant connections to communication channels (Telegram, WhatsApp).

**Current Status**: 100 tests passing ✅ | 6/6 tickets completed ✨

## ✅ Completed (Ticket #1: Models & Schemas)

### Files Created:
- `models.py` - Data models (Connection, ConnectionChannel, ConnectionStatus, ConnectionSettings)
- `schemas.py` - Request/Response schemas (CreateTelegramConnectionRequest, ConnectionResponse, etc.)
- `exceptions.py` - Custom exceptions for the module
- `__init__.py` - Module exports
- `test_models.py` - Unit tests for models (7 tests, all passing)
- `test_schemas.py` - Unit tests for schemas (9 tests, all passing)
- Migration: `migrations/mongodb/002_create_connections_collection.py` - MongoDB collection and indexes

### Key Features:
- **Connection Model**: Links assistant to communication channel with encrypted settings
- **Channel Types**: telegram, whatsapp (future)
- **Status Types**: pending, connected, error, degraded
- **Bot Token Validation**: Validates Telegram bot token format (bot_id:secret)
- **Encryption Ready**: ConnectionSettings stores encrypted bot tokens
- **MongoDB Indexes**: Unique constraint on (assistant_id, channel), status index

### MongoDB Collection Structure:
```javascript
{
  "_id": ObjectId,
  "assistant_id": ObjectId,
  "channel": "telegram",
  "status": "connected",
  "settings": {
    "bot_token": "encrypted",
    "bot_username": "@bot",
    "webhook_url": "https://...",
    // ...
  },
  "last_error": null,
  "last_checked_at": ISODate
}
```

## ✅ Completed (Ticket #2: Token Encryption Module)

### Files Created:
- `security/crypto.py` - Encryption/decryption utilities using Fernet
- `security/__init__.py` - Module exports
- `security/test_crypto.py` - Unit tests (19 tests, all passing)
- `env.example` - Example environment variables file

### Key Features:
- **Fernet Encryption**: Symmetric encryption for bot tokens
- **Functions**: `encrypt_token()`, `decrypt_token()`, `generate_encryption_key()`
- **TokenEncryptor Class**: Helper class with persistent key
- **Key Validation**: `is_valid_encryption_key()` function
- **Error Handling**: Proper exceptions for invalid keys/tokens

### Configuration Updated:
- Added `ENCRYPTION_KEY` to `app/core/config.py`
- Added `WEBHOOK_BASE_URL` to config for future webhook setup

### Usage:
```python
from app.modules.connections.security import encrypt_token, decrypt_token

# Encrypt a bot token
encrypted = encrypt_token("bot_token", encryption_key)

# Decrypt it back
original = decrypt_token(encrypted, encryption_key)
```

### Generate New Key:
```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(f'ENCRYPTION_KEY={Fernet.generate_key().decode()}')"
# Copy the output to your .env file
```

## ✅ Completed (Ticket #3: Telegram API Client)

### Files Created:
- `vendors/telegram/client.py` - Telegram Bot API client using httpx
- `vendors/telegram/__init__.py` - Module exports
- `vendors/telegram/test_client.py` - Unit tests (16 tests, all passing)

### Key Features:
- **TelegramClient Class**: Async client for Telegram Bot API
- **Methods**:
  - `validate_token()` - Validates bot token via getMe API
  - `setup_webhook()` - Registers webhook via setWebhook API
  - `delete_webhook()` - Removes webhook via deleteWebhook API
  - `get_webhook_info()` - Gets current webhook configuration
- **Error Handling**: Proper exceptions for 401, 404, timeouts, network errors
- **httpx**: Using async HTTP client for all API calls

### Usage:
```python
from app.modules.connections.vendors.telegram import TelegramClient

client = TelegramClient()

# Validate bot token
bot_info = await client.validate_token("bot_token")
print(f"Bot: @{bot_info.username}")

# Setup webhook
success = await client.setup_webhook(
    "bot_token",
    "https://example.com/webhook",
    secret_token="optional_secret"
)
```

## ✅ Completed (Ticket #4: Repository Layer)

### Files Created:
- `repository.py` - MongoDB operations for connections
- `test_repository.py` - Unit tests (16 tests, all passing)

### Key Features:
- **ConnectionRepository Class**: Complete CRUD operations
- **Methods**:
  - `create()` - Create connection with unique constraint (assistant_id + channel)
  - `get_by_id()` - Get connection by ID
  - `find_by_assistant()` - Find all connections for an assistant
  - `update()` - Update connection fields
  - `delete()` - Delete connection
  - `exists_by_assistant_and_channel()` - Check if connection exists
  - `update_status()` - Update connection status with health check
  - `get_by_assistant_and_channel()` - Get specific connection
- **Unique Constraint**: One channel per assistant (enforced by DB index)
- **Error Handling**: Proper handling of DuplicateKeyError

### MongoDB Operations:
- Uses Motor async driver
- Automatic ObjectId conversion
- Settings serialization/deserialization
- Timestamp management (created_at, updated_at)

## ✅ Completed (Ticket #5: Service Layer)

### Files Created:
- `service.py` - Business logic for managing connections
- `test_service.py` - Unit tests (16 tests, all passing)

### Key Features:
- **ConnectionService Class**: Complete business logic layer
- **Methods**:
  - `create_telegram_connection()` - Full flow: validate → encrypt → save → webhook
  - `get_connection()` - Get connection with user access control
  - `list_connections()` - List connections for assistant (with ownership check)
  - `delete_connection()` - Delete connection and cleanup webhook
  - `check_connection_health()` - Verify and update connection status
- **User Access Control**: All methods verify user has access to assistant
- **Integrations**:
  - AssistantRepository for ownership verification
  - ConnectionRepository for database operations
  - TelegramClient for API calls
  - TokenEncryptor for secure storage
- **Error Handling**: Graceful handling of webhook failures, invalid tokens

### Business Rules:
- One Telegram connection per assistant (enforced)
- User must own assistant to manage its connections
- Webhook failures don't prevent connection creation (ERROR status)
- Health checks update connection status dynamically

## ✅ Completed (Ticket #6: API Router)

### Files Created:
- `router.py` - FastAPI endpoints for managing connections
- `test_router.py` - Integration tests (11 tests, all passing)

### API Endpoints:
- `POST /api/v1/assistants/{assistant_id}/connections/telegram` - Create Telegram connection
- `GET /api/v1/assistants/{assistant_id}/connections` - List assistant connections
- `GET /api/v1/connections/{connection_id}` - Get connection details
- `DELETE /api/v1/connections/{connection_id}` - Delete connection
- `POST /api/v1/connections/{connection_id}/health-check` - Check connection health

### Key Features:
- Full API documentation in Swagger UI
- Authentication via Auth0 JWT
- Request/response validation with Pydantic
- Proper HTTP status codes (201, 200, 204, 400, 404, 409)
- Error handling with meaningful messages
- Integration with ConnectionService for business logic

## Testing
```bash
# Run tests
cd /home/...
source venv/bin/activate
PYTHONPATH=. pytest app/modules/connections/test_*.py -v
```

## Notes
- Following MVP principles: simple, readable, maintainable
- Following existing patterns from assistants module
- All models inherit from MongoBaseModel
- Pydantic v2 for validation
- Ready for encryption (token field accepts encrypted strings)
