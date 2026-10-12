# Conversations Module

Message processing and response generation module that bridges webhooks and outbound delivery.

## Overview

The Conversations module acts as the "brain" between incoming webhooks and outbound message delivery:

- **Receives**: User messages from `incoming_messages` queue (from webhooks)
- **Processes**: Generates responses (test responses for MVP, LLM in future)
- **Sends**: Publishes responses to `outbound_messages` queue (to outbound module)

## Architecture

```
Webhooks → incoming_messages → Conversations Worker → Conversations Service → outbound_messages → Outbound
```

### Components

1. **ConversationsWorker** (`worker.py`): RabbitMQ consumer (orchestrator)
2. **ConversationsService** (`service.py`): Business logic (response generation)
3. **ConversationsPublisher** (`publisher.py`): Publishes to outbound_messages queue

## Usage

### Running the Worker

```bash
# Using Makefile
make run-conversations-worker

# Or directly
python -m app.modules.conversations.worker
```

## Message Flow

### Input (from incoming_messages):
```json
{
  "assistant_id": "691ccd8225eee2a50317434a",
  "connection_id": "691ccd8325eee2a50317434b",
  "user_id": "telegram_284639219",
  "type": "message",
  "text": "Hello bot",
  "message_id": "123"
}
```

### Output (to outbound_messages):
```json
{
  "assistant_id": "691ccd8225eee2a50317434a",
  "connection_id": "691ccd8325eee2a50317434b",
  "user_id": "telegram_284639219",
  "type": "message",
  "response_text": "🤖 Test Response\n\n📝 You said: Hello bot\n...",
  "original_message_id": "123",
  "parse_mode": "HTML"
}
```

## MVP Scope

Current implementation:
- ✅ Processes text messages
- ✅ Processes callback queries
- ✅ Generates test responses
- ✅ Publishes to outbound queue
- ❌ LLM integration (future)
- ❌ Conversation history (future)

## Future Enhancements

- LLM agent integration for smart responses
- Conversation history storage in MongoDB
- Context management
- Multi-turn conversations
- Personalization

## License

Internal use only.

