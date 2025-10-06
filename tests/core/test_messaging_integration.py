"""Integration tests for messaging infrastructure with real RabbitMQ."""

import pytest
import json
import time
from app.core.messaging.broker import MessageBroker


class TestMessageBrokerIntegration:
    """Test MessageBroker with real RabbitMQ connection."""

    @pytest.fixture
    def broker(self):
        """Create message broker instance."""
        broker = MessageBroker()
        yield broker
        broker.close()

    def test_real_rabbitmq_connection(self, broker):
        """Test connection to real RabbitMQ."""
        assert broker.is_connected() is True

    def test_real_rabbitmq_queue_setup(self, broker):
        """Test shared queue setup with real RabbitMQ (consumer group pattern)."""
        queue_name = broker.setup_consumer_queue("integration_test")
        assert queue_name == "ws_gateway_consumers"

    def test_real_rabbitmq_publish_message(self, broker):
        """Test publishing message with real RabbitMQ."""
        message_data = {
            "id": "msg_integration_123",
            "chat_id": "chat_integration_456",
            "sender_id": "user_integration_789",
            "content": "Integration test message",
            "created_at": "2024-01-01T00:00:00Z",
        }

        # This should not raise an exception
        broker.publish_message_created("chat_integration_456", message_data)

    def test_real_rabbitmq_publish_presence(self, broker):
        """Test publishing presence with real RabbitMQ."""
        presence_data = {
            "user_id": "user_integration_123",
            "status": "online",
            "at": "2024-01-01T00:00:00Z",
        }

        # This should not raise an exception
        broker.publish_presence_updated("user_integration_123", presence_data)

    def test_real_rabbitmq_reconnect(self, broker):
        """Test reconnection with real RabbitMQ."""
        assert broker.is_connected() is True

        # Close connection
        broker.close()
        assert broker.is_connected() is False

        # Reconnect
        broker.reconnect()
        assert broker.is_connected() is True
