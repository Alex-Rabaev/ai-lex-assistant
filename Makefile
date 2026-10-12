.PHONY: help install run-onboarding-bot run-universal-bot run-dev test clean migrate setup-telegram-webhook show-logs test-logging test-marketing run-websocket-worker run-temporal-worker run-follow-up-worker

help:
	@echo "Available commands:"
	@echo "  install                  Install dependencies"
	@echo "  run-onboarding-bot       Start the onboarding bot"
	@echo "  run-universal-bot        Start the universal bot (alias for run-onboarding-bot)"
	@echo "  run-dev                  Start in development mode with auto-reload"
	@echo "  run-conversations-worker Start the conversations worker"
	@echo "  run-outbound-worker      Start the outbound message worker"
	@echo "  run-websocket-worker     Start the WebSocket worker (for webchat)"
	@echo "  run-temporal-worker      Start the Temporal worker (for analysis workflows)"
	@echo "  run-follow-up-worker     Start the follow-up worker (runs every 5 min)"
	@echo "  setup-telegram-webhook   Set Telegram webhook URL"
	@echo "  show-logs                Show conversation logs"
	@echo "  test-logging             Test the logging system"
	@echo "  test-marketing           Test marketing research functionality"
	@echo "  test                     Run tests"
	@echo "  migrate                  Run database migration"
	@echo "  clean                    Clean cache files"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

run-onboarding-bot:
	@echo "Starting Universal Onboarding Bot..."
	@echo "Bot will be available at: http://localhost:8000"
	@echo "Webhook endpoints:"
	@echo "  - General: POST /api/v1/onboarding/webhook"
	@echo "  - WhatsApp: POST /api/v1/onboarding/webhook/whatsapp"
	@echo "  - Telegram: POST /api/v1/onboarding/webhook/telegram"
	@echo ""
	uvicorn app.main:app --host 0.0.0.0 --port 8000

run-universal-bot: run-onboarding-bot

run-dev:
	@echo "Starting in development mode with auto-reload..."
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-conversations-worker:
	@echo "Starting Conversations Worker..."
	@echo "Worker will consume from 'incoming_messages' and publish to 'outbound_messages'"
	@echo "Press Ctrl+C to stop gracefully"
	@echo ""
	python -m app.modules.conversations.worker

run-outbound-worker:
	@echo "Starting Outbound Worker..."
	@echo "Worker will consume messages from RabbitMQ 'outbound_messages' queue"
	@echo "Press Ctrl+C to stop gracefully"
	@echo ""
	python -m app.modules.outbound.worker

run-websocket-worker:
	@echo "Starting WebSocket Worker..."
	@echo "Worker will consume messages from RabbitMQ 'websocket_messages' queue"
	@echo "and deliver them to connected WebSocket clients"
	@echo "Press Ctrl+C to stop gracefully"
	@echo ""
	python -m app.modules.websocket_worker.worker

run-temporal-worker:
	@echo "Starting Temporal Worker..."
	@echo "Worker will poll Temporal task queue for analysis workflows"
	@echo "Requires Temporal Service running on $(TEMPORAL_HOST:-localhost:7233)"
	@echo "Press Ctrl+C to stop gracefully"
	@echo ""
	python -m app.modules.workflows.temporal_worker

setup-telegram-webhook:
	@echo "Setting up Telegram webhook..."
	@echo "Enter your public domain (e.g., https://yourdomain.com):"
	@read domain; \
	python -c "from dotenv import load_dotenv; load_dotenv(); import os; import requests; token=os.getenv('TELEGRAM_BOT_TOKEN'); url=f'https://api.telegram.org/bot{token}/setWebhook'; webhook_url=f'$$domain/api/v1/onboarding/webhook/telegram'; response=requests.post(url, json={'url': webhook_url}); print(f'Webhook set to: {webhook_url}'); print(f'Response: {response.json()}')" 2>/dev/null || echo "❌ Make sure TELEGRAM_BOT_TOKEN is set in .env file"

test:
	@echo "Running tests..."
	python app/universal_bot/test_onboarding_bot.py

show-logs:
	@echo "Showing conversation logs..."
	python app/universal_bot/show_logs.py

test-logging:
	@echo "Testing logging system..."
	python app/universal_bot/test_bot_logging.py

test-marketing:
	@echo "Testing marketing research functionality..."
	python app/universal_bot/test_marketing_research.py

migrate:
	@echo "Running database migration..."
	prisma migrate dev --name "universal_bot_updates"

clean:
	@echo "Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

check-env:
	@echo "Checking required environment variables..."
	@python -c "from app.core.config import settings; print('✓ All environment variables loaded successfully')"
