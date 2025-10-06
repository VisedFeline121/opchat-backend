"""Tests for messaging infrastructure."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from app.core.messaging.broker import MessageBroker


class TestMessageBroker:
    """Test MessageBroker functionality."""

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_initialization_success(self, mock_connection_class):
        """Test successful broker initialization."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()

        assert broker.connection is not None
        assert broker.channel is not None
        mock_connection_class.assert_called_once()
        mock_channel.exchange_declare.assert_called()

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_initialization_connection_error(self, mock_connection_class):
        """Test broker initialization with connection error."""
        mock_connection_class.side_effect = AMQPConnectionError("Connection failed")

        with pytest.raises(AMQPConnectionError):
            MessageBroker()

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_setup_consumer_queue(self, mock_connection_class):
        """Test shared consumer queue setup (consumer group pattern)."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        queue_name = broker.setup_consumer_queue("test_instance")

        # Should use shared queue name for consumer group pattern
        assert queue_name == "ws_gateway_consumers"
        mock_channel.queue_declare.assert_called_with(queue=queue_name, durable=True)
        assert mock_channel.queue_bind.call_count == 2  # message and presence bindings

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_publish_message_pending(self, mock_connection_class):
        """Test publishing message.pending event."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        message_data = {
            "id": "msg123",
            "chat_id": "chat456",
            "sender_id": "user789",
            "content": "Hello world",
            "idempotency_key": "key123",
        }

        broker.publish_message_pending("chat456", message_data)

        mock_channel.basic_publish.assert_called_once()
        call_args = mock_channel.basic_publish.call_args
        assert call_args[1]["exchange"] == "conv.message.pending"
        assert call_args[1]["routing_key"] == "conv.chat456.message.pending"
        assert call_args[1]["body"] == json.dumps(message_data)

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_publish_message_created(self, mock_connection_class):
        """Test publishing message.created event."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        message_data = {
            "id": "msg123",
            "chat_id": "chat456",
            "sender_id": "user789",
            "content": "Hello world",
            "created_at": "2024-01-01T00:00:00Z",
        }

        broker.publish_message_created("chat456", message_data)

        mock_channel.basic_publish.assert_called_once()
        call_args = mock_channel.basic_publish.call_args
        assert call_args[1]["exchange"] == "conv.message.created"
        assert call_args[1]["routing_key"] == "conv.chat456.message.created"
        assert call_args[1]["body"] == json.dumps(message_data)

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_publish_presence_updated(self, mock_connection_class):
        """Test publishing presence.updated event."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        presence_data = {
            "user_id": "user123",
            "status": "online",
            "at": "2024-01-01T00:00:00Z",
        }

        broker.publish_presence_updated("user123", presence_data)

        mock_channel.basic_publish.assert_called_once()
        call_args = mock_channel.basic_publish.call_args
        assert call_args[1]["exchange"] == "presence.updated"
        assert call_args[1]["routing_key"] == "presence.user123"
        assert call_args[1]["body"] == json.dumps(presence_data)

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_is_connected(self, mock_connection_class):
        """Test connection status check."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.is_closed = False
        mock_channel.is_closed = False
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        assert broker.is_connected() is True

        # Test disconnected state
        mock_connection.is_closed = True
        assert broker.is_connected() is False

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_close(self, mock_connection_class):
        """Test connection close."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.is_closed = False
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        broker.close()

        mock_connection.close.assert_called_once()

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_reconnect(self, mock_connection_class):
        """Test reconnection."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        broker.reconnect()

        # Should have been called twice (initial + reconnect)
        assert mock_connection_class.call_count == 2

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_start_consuming(self, mock_connection_class):
        """Test starting consumer with consumer group pattern."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        callback = Mock()

        broker.start_consuming("ws_gateway_consumers", callback, "instance_1")

        mock_channel.basic_consume.assert_called_once_with(
            queue="ws_gateway_consumers",
            on_message_callback=callback,
            consumer_tag="ws_gateway_instance_1",
            auto_ack=False,
        )

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_stop_consuming(self, mock_connection_class):
        """Test stopping consumer."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()

        # Test stopping specific consumer
        broker.stop_consuming("ws_gateway_instance_1")
        mock_channel.basic_cancel.assert_called_with("ws_gateway_instance_1")

        # Test stopping all consumers
        broker.stop_consuming()
        mock_channel.stop_consuming.assert_called_once()

    @patch("app.core.messaging.broker.pika.BlockingConnection")
    def test_setup_message_processor_queue(self, mock_connection_class):
        """Test message processor queue setup."""
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        broker = MessageBroker()
        queue_name = broker.setup_message_processor_queue()

        assert queue_name == "message_processor"
        # Check that queue_declare was called with DLQ arguments
        mock_channel.queue_declare.assert_called()
        # Verify the main queue was declared with DLQ configuration
        calls = mock_channel.queue_declare.call_args_list
        main_queue_call = None
        for call in calls:
            if call[1].get("queue") == "message_processor" and "arguments" in call[1]:
                main_queue_call = call
                break
        assert main_queue_call is not None
        assert (
            main_queue_call[1]["arguments"]["x-dead-letter-exchange"]
            == "dlx.failed.messages"
        )
        mock_channel.queue_bind.assert_called_with(
            exchange="conv.message.pending",
            queue=queue_name,
            routing_key="conv.*.message.pending",
        )
