"""Telegram-specific webhook schemas."""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    """Telegram user information."""
    
    id: int = Field(..., description="Unique identifier for this user")
    is_bot: bool = Field(..., description="True if this user is a bot")
    first_name: str = Field(..., description="User's or bot's first name")
    last_name: Optional[str] = Field(None, description="User's or bot's last name")
    username: Optional[str] = Field(None, description="User's or bot's username")
    language_code: Optional[str] = Field(None, description="IETF language tag of the user's language")
    is_premium: Optional[bool] = Field(None, description="True if this user is a Telegram Premium user")
    added_to_attachment_menu: Optional[bool] = Field(None, description="True if this user added the bot to the attachment menu")


class TelegramChat(BaseModel):
    """Telegram chat information."""
    
    id: int = Field(..., description="Unique identifier for this chat")
    type: Literal["private", "group", "supergroup", "channel"] = Field(..., description="Type of chat")
    title: Optional[str] = Field(None, description="Title, for supergroups, channels and group chats")
    username: Optional[str] = Field(None, description="Username, for private chats, supergroups and channels if available")
    first_name: Optional[str] = Field(None, description="First name of the other party in a private chat")
    last_name: Optional[str] = Field(None, description="Last name of the other party in a private chat")
    is_forum: Optional[bool] = Field(None, description="True if the supergroup chat is a forum")


class TelegramMessageEntity(BaseModel):
    """Entity in a text message (e.g., mention, hashtag, URL)."""
    
    type: str = Field(..., description="Type of the entity")
    offset: int = Field(..., description="Offset in UTF-16 code units to the start of the entity")
    length: int = Field(..., description="Length of the entity in UTF-16 code units")
    url: Optional[str] = Field(None, description="For 'text_link' only, URL that will be opened")
    user: Optional[TelegramUser] = Field(None, description="For 'text_mention' only, the mentioned user")
    language: Optional[str] = Field(None, description="For 'pre' only, the programming language of the entity text")


class TelegramMessage(BaseModel):
    """Telegram message object."""
    
    message_id: int = Field(..., description="Unique message identifier inside this chat")
    message_thread_id: Optional[int] = Field(None, description="Unique identifier of a message thread")
    from_user: Optional[TelegramUser] = Field(None, alias="from", description="Sender of the message")
    sender_chat: Optional[TelegramChat] = Field(None, description="Sender of the message, sent on behalf of a chat")
    date: int = Field(..., description="Date the message was sent in Unix time")
    chat: TelegramChat = Field(..., description="Conversation the message belongs to")
    forward_from: Optional[TelegramUser] = Field(None, description="For forwarded messages, sender of the original message")
    forward_from_chat: Optional[TelegramChat] = Field(None, description="For messages forwarded from channels")
    forward_date: Optional[int] = Field(None, description="For forwarded messages, date the original message was sent")
    is_automatic_forward: Optional[bool] = Field(None, description="True if the message is a channel post that was automatically forwarded")
    reply_to_message: Optional["TelegramMessage"] = Field(None, description="For replies, the original message")
    via_bot: Optional[TelegramUser] = Field(None, description="Bot through which the message was sent")
    edit_date: Optional[int] = Field(None, description="Date the message was last edited in Unix time")
    has_protected_content: Optional[bool] = Field(None, description="True if the message can't be forwarded")
    media_group_id: Optional[str] = Field(None, description="The unique identifier of a media message group")
    author_signature: Optional[str] = Field(None, description="Signature of the post author for messages in channels")
    
    # Content fields
    text: Optional[str] = Field(None, description="For text messages, the actual UTF-8 text of the message")
    entities: Optional[List[TelegramMessageEntity]] = Field(None, description="For text messages, special entities")
    caption: Optional[str] = Field(None, description="Caption for animation, audio, document, photo, video or voice")
    caption_entities: Optional[List[TelegramMessageEntity]] = Field(None, description="For messages with a caption, special entities")
    
    # Other message types (simplified for MVP)
    audio: Optional[Dict[str, Any]] = Field(None, description="Information about the audio file")
    document: Optional[Dict[str, Any]] = Field(None, description="Information about the general file")
    animation: Optional[Dict[str, Any]] = Field(None, description="Information about the animation")
    photo: Optional[List[Dict[str, Any]]] = Field(None, description="Available sizes of the photo")
    sticker: Optional[Dict[str, Any]] = Field(None, description="Information about the sticker")
    video: Optional[Dict[str, Any]] = Field(None, description="Information about the video")
    video_note: Optional[Dict[str, Any]] = Field(None, description="Information about the video message")
    voice: Optional[Dict[str, Any]] = Field(None, description="Information about the voice message")
    contact: Optional[Dict[str, Any]] = Field(None, description="Information about the shared contact")
    location: Optional[Dict[str, Any]] = Field(None, description="Information about the shared location")
    venue: Optional[Dict[str, Any]] = Field(None, description="Information about the venue")
    
    # Service messages
    new_chat_members: Optional[List[TelegramUser]] = Field(None, description="New members that were added to the chat")
    left_chat_member: Optional[TelegramUser] = Field(None, description="A member was removed from the chat")
    new_chat_title: Optional[str] = Field(None, description="A chat title was changed to this value")
    new_chat_photo: Optional[List[Dict[str, Any]]] = Field(None, description="A chat photo was changed")
    delete_chat_photo: Optional[bool] = Field(None, description="Service message: the chat photo was deleted")
    group_chat_created: Optional[bool] = Field(None, description="Service message: the group has been created")
    

# Fix forward reference
TelegramMessage.model_rebuild()


class TelegramCallbackQuery(BaseModel):
    """Telegram callback query from inline keyboard."""
    
    id: str = Field(..., description="Unique identifier for this query")
    from_user: TelegramUser = Field(..., alias="from", description="Sender")
    message: Optional[TelegramMessage] = Field(None, description="Message with the callback button")
    inline_message_id: Optional[str] = Field(None, description="Identifier of the message sent via the bot")
    chat_instance: str = Field(..., description="Global identifier corresponding to the chat")
    data: Optional[str] = Field(None, description="Data associated with the callback button")
    game_short_name: Optional[str] = Field(None, description="Short name of a Game")


class TelegramUpdate(BaseModel):
    """Telegram update object - the main webhook payload."""
    
    update_id: int = Field(..., description="The update's unique identifier")
    message: Optional[TelegramMessage] = Field(None, description="New incoming message")
    edited_message: Optional[TelegramMessage] = Field(None, description="New version of a known message")
    channel_post: Optional[TelegramMessage] = Field(None, description="New incoming channel post")
    edited_channel_post: Optional[TelegramMessage] = Field(None, description="New version of a known channel post")
    callback_query: Optional[TelegramCallbackQuery] = Field(None, description="New incoming callback query")
    
    # Other update types (not needed for MVP)
    inline_query: Optional[Dict[str, Any]] = Field(None, description="New incoming inline query")
    chosen_inline_result: Optional[Dict[str, Any]] = Field(None, description="Result of an inline query chosen by user")
    shipping_query: Optional[Dict[str, Any]] = Field(None, description="New incoming shipping query")
    pre_checkout_query: Optional[Dict[str, Any]] = Field(None, description="New incoming pre-checkout query")
    poll: Optional[Dict[str, Any]] = Field(None, description="New poll state")
    poll_answer: Optional[Dict[str, Any]] = Field(None, description="User changed their answer in a non-anonymous poll")
    my_chat_member: Optional[Dict[str, Any]] = Field(None, description="Bot's chat member status was updated")
    chat_member: Optional[Dict[str, Any]] = Field(None, description="Chat member's status was updated")
    chat_join_request: Optional[Dict[str, Any]] = Field(None, description="A request to join the chat has been sent")
    
    def get_message(self) -> Optional[TelegramMessage]:
        """Get the message from this update, regardless of its type."""
        return (
            self.message or 
            self.edited_message or 
            self.channel_post or 
            self.edited_channel_post or
            (self.callback_query.message if self.callback_query else None)
        )
    
    def get_user(self) -> Optional[TelegramUser]:
        """Get the user who triggered this update."""
        if self.message and self.message.from_user:
            return self.message.from_user
        elif self.edited_message and self.edited_message.from_user:
            return self.edited_message.from_user
        elif self.callback_query:
            return self.callback_query.from_user
        elif self.channel_post and self.channel_post.from_user:
            return self.channel_post.from_user
        elif self.edited_channel_post and self.edited_channel_post.from_user:
            return self.edited_channel_post.from_user
        return None
    
    def get_chat(self) -> Optional[TelegramChat]:
        """Get the chat where this update occurred."""
        message = self.get_message()
        return message.chat if message else None
