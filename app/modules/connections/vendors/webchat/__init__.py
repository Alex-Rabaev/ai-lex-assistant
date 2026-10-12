"""WebChat vendor module for webchat channel connections."""

from app.modules.connections.vendors.webchat.service import (
    WebchatChannelService,
    WebchatValidationError,
    WebchatMessageNotFoundError
)
from app.modules.connections.vendors.webchat.connection_service import WebchatConnectionService
from app.modules.connections.vendors.webchat.models import WebchatMessage
from app.modules.connections.vendors.webchat.repository import WebchatMessageRepository
from app.modules.connections.vendors.webchat.publisher import WebsocketPublisher
from app.modules.connections.vendors.webchat.router import router as webchat_router
from app.modules.connections.vendors.webchat.schemas import (
    EnableWebchatRequest,
    UpdateWebchatSettingsRequest,
    WebchatConnectionResponse,
    SendMessageRequest,
    UpdateMessageRequest,
    WebchatMessageResponse,
    MessageListResponse,
    SendMessageResponse,
    AssistantInfoResponse
)

__all__ = [
    # Services
    "WebchatChannelService",
    "WebchatConnectionService",
    # Exceptions
    "WebchatValidationError",
    "WebchatMessageNotFoundError",
    # Models
    "WebchatMessage",
    # Repository & Publisher
    "WebchatMessageRepository",
    "WebsocketPublisher",
    # Router
    "webchat_router",
    # Schemas
    "EnableWebchatRequest",
    "UpdateWebchatSettingsRequest",
    "WebchatConnectionResponse",
    "SendMessageRequest",
    "UpdateMessageRequest",
    "WebchatMessageResponse",
    "MessageListResponse",
    "SendMessageResponse",
    "AssistantInfoResponse",
]

