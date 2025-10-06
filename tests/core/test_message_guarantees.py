"""Tests for message guarantees (idempotency, deduplication, DLQ handling)."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.core.messaging.broker import MessageBroker


class TestMessageGuarantees:
    """Test message guarantees functionality."""

    def test_message_id_tracking_in_publish(self):
        """Test that message IDs are properly tracked in RabbitMQ properties."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Test message data
            message_data = {
                "id": "test-message-123",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "idempotency_key": "test-key-123",
            }

            # Publish message
            broker.publish_message_pending("test-chat-id", message_data)

            # Verify publish was called with message ID
            mock_channel.basic_publish.assert_called_once()
            call_args = mock_channel.basic_publish.call_args

            # Check that message ID is set in properties
            properties = call_args[1]["properties"]
            assert properties.message_id == "test-message-123"
            assert properties.delivery_mode == 2  # Persistent
            assert properties.content_type == "application/json"

            # Check headers include idempotency key
            assert properties.headers["x-idempotency-key"] == "test-key-123"

    def test_duplicate_message_deduplication(self):
        """Test that duplicate message IDs are not published."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Test message data
            message_data = {
                "id": "duplicate-message-123",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "idempotency_key": "test-key-123",
            }

            # Publish message first time
            broker.publish_message_pending("test-chat-id", message_data)
            assert mock_channel.basic_publish.call_count == 1

            # Try to publish same message again
            broker.publish_message_pending("test-chat-id", message_data)

            # Should still be only 1 call (duplicate was skipped)
            assert mock_channel.basic_publish.call_count == 1

    def test_dlq_with_expiration_policies(self):
        """Test that DLQ is set up with proper expiration policies."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Test DLQ setup
            dlq_name = broker.setup_dlq_monitoring()

            # Verify DLQ was declared with expiration policies
            mock_channel.queue_declare.assert_called()
            calls = mock_channel.queue_declare.call_args_list

            # Find the DLQ declaration call
            dlq_call = None
            for call in calls:
                if call[1].get("queue") == "message_processor_dlq":
                    dlq_call = call
                    break

            assert dlq_call is not None
            args = dlq_call[1]["arguments"]
            assert args["x-message-ttl"] == 86400000  # 24 hours
            assert args["x-expires"] == 604800000  # 7 days
            assert args["x-max-length"] == 10000  # Max 10k messages
            assert args["x-overflow"] == "drop-head"  # Drop oldest when full

    def test_dlq_message_inspection(self):
        """Test DLQ message inspection functionality."""
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
            mock_properties.message_id = "test-message-123"
            mock_properties.headers = {"x-retry-count": 3}
            mock_properties.content_type = "application/json"
            mock_properties.timestamp = int(datetime.now().timestamp() * 1000)
            mock_body = b'{"id": "test-message-123", "content": "test"}'

            # First call returns message, second call returns None
            mock_channel.basic_get.side_effect = [
                (mock_method, mock_properties, mock_body),
                (None, None, None),
            ]

            # Test message inspection
            messages = broker.inspect_dlq_messages(limit=1)

            # Verify message was inspected
            assert len(messages) == 1
            message = messages[0]
            assert message["message_id"] == "test-message-123"
            assert message["delivery_tag"] == "test-tag"
            assert message["data"]["id"] == "test-message-123"

            # Verify message was rejected back to DLQ
            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag="test-tag", requeue=True
            )

    def test_dlq_message_details_by_id(self):
        """Test getting specific DLQ message details by message ID."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Mock basic_get to return messages
            mock_method1 = Mock()
            mock_method1.delivery_tag = "tag1"
            mock_properties1 = Mock()
            mock_properties1.message_id = "message-1"
            mock_properties1.headers = {}
            mock_properties1.content_type = "application/json"
            mock_properties1.timestamp = int(datetime.now().timestamp() * 1000)
            mock_body1 = b'{"id": "message-1", "content": "test1"}'

            mock_method2 = Mock()
            mock_method2.delivery_tag = "tag2"
            mock_properties2 = Mock()
            mock_properties2.message_id = "message-2"
            mock_properties2.headers = {}
            mock_properties2.content_type = "application/json"
            mock_properties2.timestamp = int(datetime.now().timestamp() * 1000)
            mock_body2 = b'{"id": "message-2", "content": "test2"}'

            # Return two messages then None
            mock_channel.basic_get.side_effect = [
                (mock_method1, mock_properties1, mock_body1),
                (mock_method2, mock_properties2, mock_body2),
                (None, None, None),
            ]

            # Test getting specific message details
            message_details = broker.get_dlq_message_details(message_id="message-2")

            # Verify correct message was returned
            assert message_details is not None
            assert message_details["message_id"] == "message-2"
            assert message_details["data"]["content"] == "test2"

    def test_dlq_cleanup_old_messages(self):
        """Test cleanup of old messages from DLQ."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Mock old message (25 hours old)
            old_timestamp = int(datetime.now().timestamp() * 1000) - (
                25 * 60 * 60 * 1000
            )
            mock_method_old = Mock()
            mock_method_old.delivery_tag = "old-tag"
            mock_properties_old = Mock()
            mock_properties_old.message_id = "old-message"
            mock_properties_old.timestamp = old_timestamp
            mock_body_old = b'{"id": "old-message"}'

            # Mock recent message (1 hour old)
            recent_timestamp = int(datetime.now().timestamp() * 1000) - (
                1 * 60 * 60 * 1000
            )
            mock_method_recent = Mock()
            mock_method_recent.delivery_tag = "recent-tag"
            mock_properties_recent = Mock()
            mock_properties_recent.message_id = "recent-message"
            mock_properties_recent.timestamp = recent_timestamp
            mock_body_recent = b'{"id": "recent-message"}'

            # Return old message first, then recent message, then None
            mock_channel.basic_get.side_effect = [
                (mock_method_old, mock_properties_old, mock_body_old),
                (mock_method_recent, mock_properties_recent, mock_body_recent),
                (None, None, None),
            ]

            # Test cleanup with 24 hour max age
            cleaned_count = broker.cleanup_dlq_messages(max_age_hours=24)

            # Verify old message was cleaned up
            assert cleaned_count == 1
            mock_channel.basic_ack.assert_called_once_with(delivery_tag="old-tag")

            # Verify recent message was rejected back to queue
            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag="recent-tag", requeue=True
            )

    def test_message_created_with_message_id(self):
        """Test that message.created events include message ID."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Test message data
            message_data = {
                "id": "created-message-123",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "created_at": "2024-01-01T00:00:00Z",
            }

            # Publish message created event
            broker.publish_message_created("test-chat-id", message_data)

            # Verify publish was called with message ID
            mock_channel.basic_publish.assert_called_once()
            call_args = mock_channel.basic_publish.call_args

            # Check that message ID is set in properties
            properties = call_args[1]["properties"]
            assert properties.message_id == "created-message-123"
            assert properties.delivery_mode == 2  # Persistent
            assert properties.content_type == "application/json"

    def test_processed_message_ids_tracking(self):
        """Test that processed message IDs are properly tracked."""
        with patch(
            "app.core.messaging.broker.pika.BlockingConnection"
        ) as mock_connection:
            # Setup mock
            mock_channel = Mock()
            mock_connection.return_value.channel.return_value = mock_channel

            broker = MessageBroker()

            # Initially no processed messages
            assert len(broker.processed_message_ids) == 0

            # Test message data
            message_data = {
                "id": "tracked-message-123",
                "chat_id": "test-chat-id",
                "sender_id": "test-sender-id",
                "content": "Test message",
                "idempotency_key": "test-key-123",
            }

            # Publish message
            broker.publish_message_pending("test-chat-id", message_data)

            # Verify message ID was tracked
            assert "tracked-message-123" in broker.processed_message_ids
            assert len(broker.processed_message_ids) == 1
