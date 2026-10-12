"""Service layer for processing conversations and generating responses."""

import logging
from typing import Optional, Dict, Any, List

from app.modules.conversations.schemas import IncomingMessage, ProcessingResult
from app.common.utils.logging_context import set_log_context
from app.modules.conversations.models.conversation import Conversation
from app.modules.conversations.models import ConversationMessage
from app.modules.conversations.models.interlocutor import Interlocutor
from app.modules.conversations.publisher import ConversationsPublisher
from app.modules.conversations.exceptions import ProcessingError
from app.modules.conversations.repositories.interlocutor_repository import InterlocutorRepository
from app.modules.conversations.repositories.conversation_repository import ConversationRepository
from app.modules.conversations.agents.factory import AgentFactory
from app.modules.assistants.models import Assistant, AssistantType
from app.modules.assistants.service import AssistantService, AssistantNotFoundError
from app.modules.webhooks.service import WebhookService
from app.modules.conversations.repositories.conversation_history_repository import ConversationHistoryRepository

logger = logging.getLogger(__name__)


class ConversationsService:
    """
    Service for processing incoming messages and generating responses.
    
    Full conversation logic:
    1. Get assistant
    2. Get or create interlocutor
    3. Get or create conversation
    4. Get agent by assistant type
    5. Agent processes message and updates state
    6. Publish response to outbound (if any)
    """
    
    def __init__(
        self,
        publisher: Optional[ConversationsPublisher] = None
    ):
        """
        Initialize conversations service.
        
        Args:
            publisher: Optional publisher instance
        """
        self.publisher = publisher or ConversationsPublisher()
        self._assistant_service = AssistantService()
        self._webhook_service = WebhookService()
    
    async def process_incoming_message(self, msg: IncomingMessage) -> ProcessingResult:
        """
        Process incoming message with full conversation logic.
        
        Args:
            msg: Incoming message from webhooks
            
        Returns:
            ProcessingResult with operation outcome
            
        Raises:
            ProcessingError: If processing fails
        """
        try:
            logger.info(f"Processing message: type={msg.type}")
            
            # Initialize repositories (they use _ensure_db internally)
            interlocutor_repo = InterlocutorRepository()
            conversation_repo = ConversationRepository()
            
            # Step 1: Get assistant using AssistantService
            try:
                assistant = await self._assistant_service.get_assistant_internal(msg.assistant_id)
            except AssistantNotFoundError:
                logger.error(f"Assistant not found: {msg.assistant_id}")
                return ProcessingResult(
                    success=False,
                    response_generated=False,
                    error=f"Assistant not found: {msg.assistant_id}"
                )
            
            logger.debug(f"Found assistant: {assistant.name} (type: {assistant.type})")

            # Check if assistant is active
            assistant_status = getattr(assistant.status, "value", str(assistant.status)) if hasattr(assistant, "status") else "active"
            if assistant_status != "active":
                logger.info(f"Assistant {assistant.name} is inactive, rejecting message")
                inactive_msg = "This assistant is currently inactive and not accepting messages."
                await self.publisher.publish_outgoing_message(
                    assistant_id=msg.assistant_id,
                    connection_id=msg.connection_id,
                    user_id=msg.user_id,
                    response_text=inactive_msg,
                    message_type=msg.type,
                    original_message_id=msg.message_id,
                    trace_id=msg.trace_id,
                    conversation_id="",
                )
                return ProcessingResult(
                    success=True,
                    response_generated=True,
                )

            # Step 2: Get user info from webhook_events
            user_info = await self._webhook_service.get_user_info_from_event(
                msg.user_id,
                msg.message_id
            )
            
            # Step 3: Get or create interlocutor
            interlocutor = await interlocutor_repo.get_or_create(
                user_id=msg.user_id,
                user_info=user_info
            )
            
            logger.debug(f"Interlocutor: {interlocutor.user_id} (id: {interlocutor.id})")
            
            # Step 4: Get or create conversation
            conversation = await conversation_repo.get_or_create(
                interlocutor_id=str(interlocutor.id),
                assistant_id=msg.assistant_id,
                connection_id=msg.connection_id
            )
            
            # Update logging context with IDs from database
            set_log_context(
                interlocutor_id=str(interlocutor.id),
                conversation_id=str(conversation.id)
            )
            
            logger.debug(f"Conversation state keys: {list(conversation.state.keys())}")
            
            # Step 5: Get agent by assistant type
            try:
                agent = AgentFactory.get_agent(assistant.type)
            except ValueError as e:
                logger.error(f"Failed to get agent: {e}")
                return ProcessingResult(
                    success=False,
                    response_generated=False,
                    error=str(e)
                )
            
            # Step 5.5: Send typing indicator before LLM processing
            # This shows "typing..." to the user while agent processes the message
            try:
                await self.publisher.publish_typing_indicator(
                    assistant_id=msg.assistant_id,
                    connection_id=msg.connection_id,
                    user_id=msg.user_id,
                    trace_id=msg.trace_id
                )
                logger.debug("Typing indicator published")
            except Exception as e:
                # Typing indicator is not critical - log warning and continue
                logger.warning(f"Failed to publish typing indicator: {e}")
            
            # Step 6: Agent processes message
            # Agent handles: metadata init, history saving, LLM invocation
            try:
                agent_response = await agent.process_message(
                    message=msg,
                    conversation=conversation,
                    interlocutor=interlocutor,
                    assistant=assistant
                )
            except Exception as e:
                logger.error(f"Agent processing failed: {e}", exc_info=True)
                
                return ProcessingResult(
                    success=False,
                    response_generated=False,
                    error=f"Agent error: {e}"
                )
            
            # Step 7: Publish response to outbound (if response exists)
            if agent_response.response_text:
                await self.publisher.publish_outgoing_message(
                    assistant_id=msg.assistant_id,
                    connection_id=msg.connection_id,
                    user_id=msg.user_id,
                    response_text=agent_response.response_text,
                    message_type=msg.type,
                    original_message_id=msg.message_id,
                    parse_mode="HTML",
                    trace_id=msg.trace_id,
                    conversation_id=str(conversation.id)  # For webchat
                )
                
                logger.info(
                    f"✅ Response published: length={len(agent_response.response_text)} chars"
                )
                
                return ProcessingResult(
                    success=True,
                    response_generated=True
                )
            else:
                logger.info(f"No response generated by agent (user={msg.user_id})")
                
                return ProcessingResult(
                    success=True,
                    response_generated=False
                )
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise ProcessingError(f"Failed to process message: {e}")
    
    # ============================================
    # Public API methods for other modules
    # ============================================
    
    async def update_agent_metadata(
        self,
        conversation_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Update agent_metadata in conversation state.
        
        Args:
            conversation_id: Conversation ID
            metadata: Metadata dict to update (will be merged with existing)
            
        Raises:
            ProcessingError: If update fails
        """
        try:
            conversation_repo = ConversationRepository()
            conversation = await conversation_repo.get_by_id(conversation_id)
            
            if not conversation:
                raise ProcessingError(f"Conversation not found: {conversation_id}")
            
            # Merge with existing agent_metadata
            current_metadata = conversation.get_agent_metadata()
            updated_metadata = {**current_metadata, **metadata}
            
            await conversation_repo.update_state(
                conversation_id,
                {"agent_metadata": updated_metadata}
            )
            
            logger.debug(f"Updated agent_metadata for conversation {conversation_id}: {list(metadata.keys())}")
        
        except Exception as e:
            logger.error(f"Failed to update agent_metadata: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update agent_metadata: {e}")
    
    async def get_conversation(self, conversation_id: str) -> Conversation:
        """
        Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation object
            
        Raises:
            ProcessingError: If retrieval fails
        """
        try:
            conversation_repo = ConversationRepository()
            conversation = await conversation_repo.get_by_id(conversation_id)
            
            if not conversation:
                raise ProcessingError(f"Conversation not found: {conversation_id}")
            
            return conversation
        
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get conversation: {e}")

    async def find_follow_up_candidates(
        self,
        assistant_id: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Conversation IDs for follow-up batching (not mock + caller-provided filter)."""
        try:
            conversation_repo = ConversationRepository()
            return await conversation_repo.find_follow_up_candidates(
                assistant_id, extra_filter=extra_filter
            )
        except Exception as e:
            logger.error(f"Failed to find follow-up candidates: {e}", exc_info=True)
            raise ProcessingError(f"Failed to find follow-up candidates: {e}")

    async def get_follow_up_candidate_ids(
        self,
        assistant_id: str,
        assistant_type: AssistantType,
    ) -> List[str]:
        """Candidate conversation IDs for follow-up for the given assistant type."""
        try:
            agent = AgentFactory.get_agent(assistant_type)
        except ValueError as e:
            logger.warning("No agent for assistant type %s: %s", assistant_type, e)
            return []
        return await agent.list_follow_up_candidate_conversation_ids(assistant_id)

    async def generate_follow_up_reminder(
        self,
        conversation: Conversation,
        interlocutor: Interlocutor,
        assistant: Assistant,
    ) -> Optional[str]:
        """Reminder text via the agent for assistant.type (no follow-up checks here)."""
        try:
            agent = AgentFactory.get_agent(assistant.type)
        except ValueError:
            logger.error("Unsupported assistant type for follow-up: %s", assistant.type)
            return None
        return await agent.generate_reminder(conversation, interlocutor, assistant)

    async def get_conversation_internal(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID without access control (for internal use by other modules).

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation if found, None otherwise
        """
        try:
            conversation_repo = ConversationRepository()
            return await conversation_repo.get_by_id(conversation_id)
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get conversation: {e}")
    
    async def create_mock_conversation(
        self,
        assistant_id: str,
        connection_id: str,
        stage: str,
        messages: List[tuple],
        mock_name: str,
        respondent_index: int,
    ) -> str:
        """Create a mock conversation with a real Interlocutor record.

        Creates a real Interlocutor (is_mock=True) so mock respondents are visible
        in the interlocutors list, then creates the conversation and its message history.

        Args:
            assistant_id: Assistant ID
            connection_id: Connection ID for the channel
            stage: Final agent state (e.g. 'completed', 'questionnaire')
            messages: List of (role, content, state) tuples for message history
            mock_name: Display name for the mock interlocutor
            respondent_index: 1-based index for unique user_id generation

        Returns:
            Created conversation ID (string)

        Raises:
            ProcessingError: If creation or save fails
        """
        try:
            from bson import ObjectId as _ObjectId
            interlocutor_repo = InterlocutorRepository()
            user_id = f"mock_{str(_ObjectId())}"
            interlocutor = await interlocutor_repo.create_mock(
                user_id=user_id,
                first_name=mock_name,
            )
            interlocutor_id = str(interlocutor.id)

            conversation_repo = ConversationRepository()
            conversation = await conversation_repo.create(
                interlocutor_id=interlocutor_id,
                assistant_id=assistant_id,
                connection_id=connection_id,
                is_mock=True
            )
            conversation_id = str(conversation.id)
            await conversation_repo.update_state(
                conversation_id,
                {"agent_metadata": {"state": stage}}
            )
            for role, content, msg_state in messages:
                await self.save_message(
                    conversation_id=conversation_id,
                    assistant_id=assistant_id,
                    interlocutor_id=interlocutor_id,
                    role=role,
                    content=content,
                    state=msg_state
                )
            logger.debug(
                f"Created mock conversation {conversation_id} "
                f"for interlocutor {interlocutor_id} ({mock_name})"
            )
            return conversation_id
        except Exception as e:
            logger.error(f"Failed to create mock conversation: {e}", exc_info=True)
            raise ProcessingError(f"Failed to create mock conversation: {e}")
    
    async def update_interlocutor_name(
        self,
        interlocutor_id: str,
        name: str
    ) -> None:
        """
        Update interlocutor's name.
        
        Args:
            interlocutor_id: Interlocutor ID
            name: User's name
            
        Raises:
            ProcessingError: If update fails
        """
        try:
            interlocutor_repo = InterlocutorRepository()
            interlocutor = await interlocutor_repo.get_by_id(interlocutor_id)
            
            if not interlocutor:
                raise ProcessingError(f"Interlocutor not found: {interlocutor_id}")
            
            await interlocutor_repo.update(
                interlocutor_id,
                {"first_name": name}
            )
            
            logger.info(f"Updated name for interlocutor {interlocutor_id}: {name}")
        
        except Exception as e:
            logger.error(f"Failed to update interlocutor name: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update interlocutor name: {e}")
    
    async def update_interlocutor_profile(
        self,
        interlocutor_id: str,
        profile_data: Dict[str, Any]
    ) -> None:
        """
        Update interlocutor's profile.
        
        Args:
            interlocutor_id: Interlocutor ID
            profile_data: Profile data to update (will be merged with existing)
            
        Raises:
            ProcessingError: If update fails
        """
        try:
            interlocutor_repo = InterlocutorRepository()
            interlocutor = await interlocutor_repo.get_by_id(interlocutor_id)
            
            if not interlocutor:
                raise ProcessingError(f"Interlocutor not found: {interlocutor_id}")
            
            # Merge with existing profile
            updated_profile = interlocutor.profile or {}
            updated_profile.update(profile_data)
            
            await interlocutor_repo.update(
                interlocutor_id,
                {"profile": updated_profile}
            )
            
            logger.info(f"Updated profile for interlocutor {interlocutor_id}: {list(profile_data.keys())}")
        
        except Exception as e:
            logger.error(f"Failed to update interlocutor profile: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update interlocutor profile: {e}")
    
    async def update_interlocutor_language(
        self,
        interlocutor_id: str,
        language: str
    ) -> None:
        """
        Update interlocutor's language.
        
        Args:
            interlocutor_id: Interlocutor ID
            language: Language name (e.g., "English", "Русский", "עברית")
            
        Raises:
            ProcessingError: If update fails
        """
        try:
            interlocutor_repo = InterlocutorRepository()
            interlocutor = await interlocutor_repo.get_by_id(interlocutor_id)
            
            if not interlocutor:
                raise ProcessingError(f"Interlocutor not found: {interlocutor_id}")
            
            await interlocutor_repo.update(
                interlocutor_id,
                {"language": language}
            )
            
            logger.info(f"Updated language for interlocutor {interlocutor_id}: {language}")
        
        except Exception as e:
            logger.error(f"Failed to update interlocutor language: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update interlocutor language: {e}")
    
    async def update_interlocutor_email(
        self,
        interlocutor_id: str,
        email: str
    ) -> None:
        """
        Update interlocutor's email address.
        
        Args:
            interlocutor_id: Interlocutor ID
            email: Email address
            
        Raises:
            ProcessingError: If update fails
        """
        try:
            interlocutor_repo = InterlocutorRepository()
            interlocutor = await interlocutor_repo.get_by_id(interlocutor_id)
            
            if not interlocutor:
                raise ProcessingError(f"Interlocutor not found: {interlocutor_id}")
            
            # Update profile with email
            updated_profile = interlocutor.profile or {}
            updated_profile["email"] = email
            
            await interlocutor_repo.update(
                interlocutor_id,
                {"profile": updated_profile}
            )
            
            logger.info(f"Updated email for interlocutor {interlocutor_id}")
        
        except Exception as e:
            logger.error(f"Failed to update interlocutor email: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update interlocutor email: {e}")
    
    async def get_history(
        self,
        conversation_id: str,
        state: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get conversation history formatted for agent use.
        
        This method returns history optimized for agent consumption:
        - Only necessary fields (role, content, state, created_at)
        - Already formatted as list of dicts
        - Filtered by state at DB level if provided
        
        Args:
            conversation_id: Conversation ID
            state: Optional state filter (step key)
            limit: Optional maximum number of messages to return (None = no limit)
            
        Returns:
            List of dicts with keys: role, content, state, created_at
            
        Raises:
            ProcessingError: If retrieval fails
        """
        try:
            history_repo = ConversationHistoryRepository()
            return await history_repo.get_formatted_history(
                conversation_id,
                state=state,
                limit=limit
            )
        
        except Exception as e:
            logger.error(f"Failed to get history: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get history: {e}")
    
    async def save_message(
        self,
        conversation_id: str,
        assistant_id: str,
        interlocutor_id: str,
        role: str,
        content: str,
        state: Optional[str] = None,
        message_type: str = "text",
        audio_duration_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationMessage:
        """
        Save message to conversation history.
        
        Args:
            conversation_id: Conversation ID
            assistant_id: Assistant ID
            interlocutor_id: Interlocutor ID
            role: Message role (user/assistant)
            content: Message text (or transcript for voice messages)
            state: Current step key
            message_type: Type of message ('text', 'voice', or 'audio')
            audio_duration_seconds: Duration of audio message (None for text)
            metadata: Optional metadata (e.g. follow_up, follow_up_attempt)
            
        Returns:
            Created ConversationMessage
            
        Raises:
            ProcessingError: If save fails
        """
        try:
            history_repo = ConversationHistoryRepository()
            saved = await history_repo.save_message(
                conversation_id=conversation_id,
                assistant_id=assistant_id,
                interlocutor_id=interlocutor_id,
                role=role,
                content=content,
                state=state,
                message_type=message_type,
                audio_duration_seconds=audio_duration_seconds,
                metadata=metadata,
            )
            if role == "user":
                conv_repo = ConversationRepository()
                await conv_repo.update_last_user_message_at(
                    conversation_id, saved.created_at
                )
            return saved

        except Exception as e:
            logger.error(f"Failed to save message: {e}", exc_info=True)
            raise ProcessingError(f"Failed to save message: {e}")
    
    async def reset_conversation(self, conversation_id: str) -> None:
        """
        Full reset: delete conversation, interlocutor, history, and follow-ups.

        After this, the next message from the same user will create
        a brand-new interlocutor and conversation with the current connection.

        Args:
            conversation_id: Conversation ID

        Raises:
            ProcessingError: If reset fails
        """
        try:
            conversation_repo = ConversationRepository()
            history_repo = ConversationHistoryRepository()
            interlocutor_repo = InterlocutorRepository()

            conversation = await conversation_repo.get_by_id(conversation_id)

            await history_repo.delete_all_by_conversation(conversation_id)

            from app.modules.follow_ups.repository import FollowUpRepository
            follow_up_repo = FollowUpRepository()
            await follow_up_repo.delete_by_conversation(conversation_id)

            if conversation:
                await interlocutor_repo.delete_by_id(str(conversation.interlocutor_id))

            await conversation_repo.delete_by_id(conversation_id)

            logger.info(
                f"Full reset: deleted conversation {conversation_id}, "
                f"interlocutor {conversation.interlocutor_id if conversation else 'N/A'}, "
                f"history, and follow-ups"
            )

        except Exception as e:
            logger.error(f"Failed to reset conversation: {e}", exc_info=True)
            raise ProcessingError(f"Failed to reset conversation: {e}")
    
    # ============================================
    # Analytics API methods
    # ============================================
    
    async def get_conversations_by_assistant(
        self,
        assistant_id: str,
        stage: Optional[str] = None,
        include_mock: Optional[bool] = None
    ) -> List[Conversation]:
        """
        Get all conversations for a given assistant.

        Used for bulk analysis of all respondents.

        Args:
            assistant_id: Assistant ID
            stage: Optional stage filter (filters by state.agent_metadata.state)
            include_mock: If False, only real conversations. If True or None, all.

        Returns:
            List of conversations for the assistant

        Raises:
            ProcessingError: If retrieval fails
        """
        try:
            conversation_repo = ConversationRepository()
            return await conversation_repo.get_by_assistant(
                assistant_id=assistant_id,
                stage=stage,
                include_mock=include_mock
            )
        except Exception as e:
            logger.error(f"Failed to get conversations by assistant: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get conversations by assistant: {e}")
    
    async def get_full_history(
        self,
        conversation_id: str,
        limit: int = 500
    ) -> List[ConversationMessage]:
        """
        Get complete message history for a conversation.
        
        Used for analyzing individual respondent.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return (default 500)
            
        Returns:
            List of ConversationMessage objects sorted by created_at (oldest first)
            
        Raises:
            ProcessingError: If retrieval fails
        """
        try:
            history_repo = ConversationHistoryRepository()
            return await history_repo.get_full_history(
                conversation_id=conversation_id,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get full history: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get full history: {e}")
    
    async def update_analytic_meta(
        self,
        conversation_id: str,
        analytic_meta: Dict[str, Any]
    ) -> Conversation:
        """
        Update analytic_meta field of a conversation.
        
        Saves analytics data (respondent profile, scores, tags) to Conversation.
        
        Args:
            conversation_id: Conversation ID
            analytic_meta: Analytics metadata dict (should conform to AnalyticMeta schema)
            
        Returns:
            Updated Conversation object
            
        Raises:
            ProcessingError: If update fails or conversation not found
        """
        try:
            conversation_repo = ConversationRepository()
            result = await conversation_repo.update_analytic_meta(
                conversation_id=conversation_id,
                analytic_meta=analytic_meta
            )
            
            if not result:
                raise ProcessingError(f"Conversation not found: {conversation_id}")
            
            logger.info(f"Updated analytic_meta for conversation {conversation_id}")
            return result
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to update analytic_meta: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update analytic_meta: {e}")

    async def get_conversation_by_interlocutor_and_assistant(
        self,
        interlocutor_id: str,
        assistant_id: str,
    ) -> Optional[Conversation]:
        """
        Get conversation for a specific interlocutor-assistant pair.

        Args:
            interlocutor_id: Interlocutor ID
            assistant_id: Assistant ID

        Returns:
            Conversation if found, None otherwise

        Raises:
            ProcessingError: If retrieval fails
        """
        try:
            conversation_repo = ConversationRepository()
            return await conversation_repo.get_by_interlocutor_and_assistant(
                interlocutor_id=interlocutor_id,
                assistant_id=assistant_id,
            )
        except Exception as e:
            logger.error(f"Failed to get conversation by interlocutor and assistant: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get conversation by interlocutor and assistant: {e}")

    async def get_interlocutor_by_id(
        self,
        interlocutor_id: str,
    ) -> Optional[Interlocutor]:
        """
        Get interlocutor by ID.

        Args:
            interlocutor_id: Interlocutor ObjectId as string

        Returns:
            Interlocutor if found, None otherwise

        Raises:
            ProcessingError: If retrieval fails
        """
        try:
            interlocutor_repo = InterlocutorRepository()
            return await interlocutor_repo.get_by_id(interlocutor_id)
        except Exception as e:
            logger.error(f"Failed to get interlocutor {interlocutor_id}: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get interlocutor: {e}")

    async def get_interlocutor_by_user_id(
        self,
        user_id: str,
    ) -> Optional[Interlocutor]:
        """Get interlocutor by external user_id (e.g. telegram_123)."""
        try:
            interlocutor_repo = InterlocutorRepository()
            return await interlocutor_repo.get_by_user_id(user_id)
        except Exception as e:
            logger.error(f"Failed to get interlocutor by user_id {user_id}: {e}", exc_info=True)
            raise ProcessingError(f"Failed to get interlocutor by user_id: {e}")

    async def update_interlocutor_blocked(
        self,
        interlocutor_id: str,
        blocked: bool,
    ) -> bool:
        """Set or clear the blocked flag on an interlocutor."""
        try:
            interlocutor_repo = InterlocutorRepository()
            return await interlocutor_repo.update_blocked(interlocutor_id, blocked=blocked)
        except Exception as e:
            logger.error(f"Failed to update interlocutor blocked: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update interlocutor blocked: {e}")

    async def delete_mock_conversations_for_assistant(self, assistant_id: str) -> int:
        """Delete all mock conversations, their message history, and mock interlocutors.

        Does not check access — caller must verify assistant ownership.

        Args:
            assistant_id: Assistant ID

        Returns:
            Number of conversations deleted
        """
        try:
            conversation_repo = ConversationRepository()
            history_repo = ConversationHistoryRepository()
            interlocutor_repo = InterlocutorRepository()

            # Load mock conversations to get their interlocutor IDs
            mock_convs = await conversation_repo.get_by_assistant(
                assistant_id, include_mock=True
            )
            mock_convs = [c for c in mock_convs if getattr(c, "is_mock", False)]
            if not mock_convs:
                return 0

            conv_ids = [str(c.id) for c in mock_convs]
            interlocutor_ids = list({str(c.interlocutor_id) for c in mock_convs})

            await history_repo.delete_by_conversation_ids(conv_ids)
            deleted = await conversation_repo.delete_many_by_ids(conv_ids)
            await interlocutor_repo.delete_many_by_ids(interlocutor_ids)

            logger.info(
                f"Deleted {deleted} mock conversations and "
                f"{len(interlocutor_ids)} mock interlocutors for assistant {assistant_id}"
            )
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete mock conversations: {e}", exc_info=True)
            raise ProcessingError(f"Failed to delete mock conversations: {e}")
