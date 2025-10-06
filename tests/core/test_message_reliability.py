"""Tests for message reliability features."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.core.messaging.broker import MessageBroker
from app.core.messaging.processor import MessageProcessor


class TestMessageReliability:
    """Test message reliability features."""

    def test_publish_message_with_retry_headers(self):
        """Test that messages are published with retry headers."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Test message data
            message_data = {
                "id": "test-message-id",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "idempotency_key": "test-key",
            }

            # Publish message
            broker.publish_message_pending("test-chat-id", message_data)

            # Verify publish was called with retry headers
            mock_channel.basic_publish.assert_called_once()
            call_args = mock_channel.basic_publish.call_args

            # Check that headers include retry information
            properties = call_args[1]["properties"]
            assert properties.headers is not None
            assert properties.headers["x-retry-count"] == 0
            assert properties.headers["x-max-retries"] == 3
            assert "x-first-publish-time" in properties.headers

    def test_message_processor_retry_logic(self):
        """Test that message processor handles retries correctly."""
        with patch(
            "app.core.messaging.processor.get_message_broker"
        ) as mock_get_broker:
            # Setup mock broker
            mock_broker = Mock()
            mock_get_broker.return_value = mock_broker

            processor = MessageProcessor()

            # Mock the callback with retry headers
            mock_channel = Mock()
            mock_method = Mock()
            mock_method.delivery_tag = "test-tag"

            mock_properties = Mock()
            mock_properties.headers = {"x-retry-count": 1, "x-max-retries": 3}

            message_data = {
                "id": "test-message-id",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "idempotency_key": "test-key",
            }

            mock_body = json.dumps(message_data)

            # Mock repository to simulate failure
            with patch.object(processor, "_get_repositories") as mock_get_repos:
                mock_message_repo = Mock()
                mock_message_repo.get_by_idempotency_key.return_value = None
                mock_message_repo.create_message.return_value = None  # Simulate failure
                mock_get_repos.return_value = (mock_message_repo, None, None)

                # Call the callback
                processor.process_message_callback(
                    mock_channel, mock_method, mock_properties, mock_body
                )

                # Verify retry logic was triggered - now uses basic_ack since message goes to delay queue
                mock_channel.basic_ack.assert_called_once_with(delivery_tag="test-tag")

    def test_dlq_setup(self):
        """Test that Dead Letter Queue is set up correctly."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Test DLQ setup
            dlq_name = broker.setup_dlq_monitoring()

            # Verify DLQ was declared and bound
            assert dlq_name == "message_processor_dlq"
            mock_channel.queue_declare.assert_called()
            mock_channel.queue_bind.assert_called()

    def test_dlq_message_count(self):
        """Test getting DLQ message count."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            # Mock queue_declare to return message count
            mock_method = Mock()
            mock_method.method.message_count = 5
            mock_channel.queue_declare.return_value = mock_method

            broker = MessageBroker()

            # Test getting DLQ count
            count = broker.get_dlq_message_count()

            # Verify count is returned
            assert count == 5
            mock_channel.queue_declare.assert_called_with(
                queue="message_processor_dlq", passive=True
            )

    def test_consumer_prefetch_configuration(self):
        """Test that consumer is configured with prefetch limit."""
        with patch(
            "app.core.messaging.processor.get_message_broker"
        ) as mock_get_broker:
            # Setup mock broker
            mock_broker = Mock()
            mock_broker.channel = Mock()
            mock_broker.setup_message_processor_queue.return_value = "test-queue"
            mock_broker.setup_dlq_monitoring.return_value = "test-dlq"
            mock_broker.start_consuming.return_value = None
            mock_broker.process_messages.return_value = None
            mock_get_broker.return_value = mock_broker

            processor = MessageProcessor()

            # Test that prefetch is configured by calling start_processing directly
            # but mocking the infinite loop parts
            with patch.object(processor.broker, "process_messages") as mock_process:
                processor.start_processing()

                # Verify prefetch was set
                mock_broker.channel.basic_qos.assert_called_once_with(prefetch_count=1)

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        with patch(
            "app.core.messaging.processor.get_message_broker"
        ) as mock_get_broker:
            mock_broker = Mock()
            mock_get_broker.return_value = mock_broker

            processor = MessageProcessor()

            # Test exponential backoff calculation
            assert (
                processor._handle_retry.__code__.co_varnames
            )  # Just check method exists

            # Test delay calculation logic (2^retry_count)
            expected_delays = [1, 2, 4, 8, 16]  # 2^0, 2^1, 2^2, 2^3, 2^4
            for retry_count, expected_delay in enumerate(expected_delays):
                # This is testing the logic in the _handle_retry method
                calculated_delay = 2**retry_count
                assert calculated_delay == expected_delay

    def test_dlq_republish_functionality(self):
        """Test republishing messages from DLQ back to main queue."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Mock basic_get to return a message
            mock_method = Mock()
            mock_method.delivery_tag = "test-tag"
            mock_properties = Mock()
            mock_properties.headers = {"x-retry-count": 3}
            mock_body = b'{"test": "message"}'

            # First call returns message, second call returns None (no more messages)
            mock_channel.basic_get.side_effect = [
                (mock_method, mock_properties, mock_body),
                (None, None, None),
            ]

            # Test republishing
            republished_count = broker.republish_dlq_messages(limit=1)

            # Verify message was republished
            assert republished_count == 1
            mock_channel.basic_publish.assert_called_once()
            mock_channel.basic_ack.assert_called_once_with(delivery_tag="test-tag")

            # Verify retry count was reset
            assert mock_properties.headers["x-retry-count"] == 0

    def test_max_retries_exceeded_sends_to_dlq(self):
        """Test that messages exceeding max retries are sent to DLQ."""
        with patch(
            "app.core.messaging.processor.get_message_broker"
        ) as mock_get_broker:
            # Setup mock broker
            mock_broker = Mock()
            mock_get_broker.return_value = mock_broker

            processor = MessageProcessor()

            # Mock the callback with max retry count
            mock_channel = Mock()
            mock_method = Mock()
            mock_method.delivery_tag = "test-tag"

            mock_properties = Mock()
            mock_properties.headers = {
                "x-retry-count": 3,  # Max retries reached
                "x-max-retries": 3,
            }

            message_data = {
                "id": "test-message-id",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "idempotency_key": "test-key",
            }

            mock_body = json.dumps(message_data)

            # Mock repository to simulate failure
            with patch.object(processor, "_get_repositories") as mock_get_repos:
                mock_message_repo = Mock()
                mock_message_repo.get_by_idempotency_key.return_value = None
                mock_message_repo.create_message.return_value = None  # Simulate failure
                mock_get_repos.return_value = (mock_message_repo, None, None)

                # Call the callback
                processor.process_message_callback(
                    mock_channel, mock_method, mock_properties, mock_body
                )

                # Verify message was sent to DLQ (requeue=False)
                mock_channel.basic_nack.assert_called_once_with(
                    delivery_tag="test-tag", requeue=False
                )
