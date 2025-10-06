"""RabbitMQ message broker implementation."""

# mypy: ignore-errors

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.channel import Channel

import pika
from pika.exceptions import AMQPChannelError, AMQPConnectionError
from pika.exchange_type import ExchangeType

from app.core.config.config import settings
from app.core.observability.metrics import (
    log_connection_event,
    log_counter_increment,
    log_dlq_event,
)

logger = logging.getLogger(__name__)


class MessageBroker:
    """RabbitMQ message broker for event publishing and consumption."""

    def __init__(self) -> None:
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[Union["Channel", "BlockingChannel"]] = None
        self.processed_message_ids: set = (
            set()
        )  # Track processed message IDs for deduplication
        self._connect()

    def _connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=settings.RABBITMQ_HOST,
                    port=settings.RABBITMQ_PORT,
                    virtual_host=settings.RABBITMQ_VHOST,
                    credentials=pika.PlainCredentials(
                        settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
                    ),
                    heartbeat=600,
                    blocked_connection_timeout=300,
                )
            )
            self.channel = self.connection.channel()
            self._setup_infrastructure()
            logger.info("Connected to RabbitMQ successfully")
            log_connection_event("connected", "rabbitmq", host=settings.RABBITMQ_HOST)
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            log_connection_event("connection_failed", "rabbitmq", error=str(e))
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to RabbitMQ: {e}")
            raise

    def _setup_infrastructure(self) -> None:
        """Set up exchanges and basic infrastructure."""
        try:
            if self.channel:
                # Declare topic exchange for pending message events (API -> Background Processor)
                self.channel.exchange_declare(
                    exchange="conv.message.pending",
                    exchange_type=ExchangeType.topic,
                    durable=True,
                )

                # Declare topic exchange for created message events (Background Processor -> WS Gateway)
                self.channel.exchange_declare(
                    exchange="conv.message.created",
                    exchange_type=ExchangeType.topic,
                    durable=True,
                )

                # Declare topic exchange for presence events
                self.channel.exchange_declare(
                    exchange="presence.updated",
                    exchange_type=ExchangeType.topic,
                    durable=True,
                )

                # Declare Dead Letter Exchange for failed messages
                self.channel.exchange_declare(
                    exchange="dlx.failed.messages",
                    exchange_type=ExchangeType.topic,
                    durable=True,
                )

            logger.info("RabbitMQ infrastructure setup completed")
        except AMQPChannelError as e:
            logger.error(f"Failed to setup RabbitMQ infrastructure: {e}")
            raise

    def setup_consumer_queue(self, instance_id: Optional[str] = None) -> str:
        """Set up shared consumer queue for WS Gateway instances (consumer group pattern)."""
        # Use shared queue name for consumer group pattern
        queue_name = "ws_gateway_consumers"

        try:
            # Declare durable queue (only needs to be done once, but idempotent)
            if self.channel:
                self.channel.queue_declare(queue=queue_name, durable=True)

                # Bind to message events - all chat messages
                self.channel.queue_bind(
                    exchange="conv.message.created",
                    queue=queue_name,
                    routing_key="conv.*.message.created",
                )

                # Bind to presence events - all presence updates
                self.channel.queue_bind(
                    exchange="presence.updated",
                    queue=queue_name,
                    routing_key="presence.*",
                )

            logger.info(
                f"Set up shared consumer queue: {queue_name} (instance: {instance_id or 'any'})"
            )
            return queue_name
        except AMQPChannelError as e:
            logger.error(f"Failed to setup consumer queue {queue_name}: {e}")
            raise

    def setup_message_processor_queue(self) -> str:
        """Set up queue for message processor (background worker) with DLQ support."""
        queue_name = "message_processor"
        dlq_name = "message_processor_dlq"

        try:
            if self.channel:
                # Declare Dead Letter Queue for failed messages
                self.channel.queue_declare(queue=dlq_name, durable=True)

                # Bind DLQ to Dead Letter Exchange
                self.channel.queue_bind(
                    exchange="dlx.failed.messages",
                    queue=dlq_name,
                    routing_key="message_processor.failed",
                )

                # Declare main queue with DLQ configuration
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": "dlx.failed.messages",
                        "x-dead-letter-routing-key": "message_processor.failed",
                        "x-message-ttl": 3600000,  # 1 hour TTL for messages
                        "x-max-retries": 3,  # Max 3 retries
                    },
                )

                # Bind to pending message events - all pending messages
                self.channel.queue_bind(
                    exchange="conv.message.pending",
                    queue=queue_name,
                    routing_key="conv.*.message.pending",
                )

            logger.info(
                f"Set up message processor queue: {queue_name} with DLQ: {dlq_name}"
            )
            return queue_name
        except AMQPChannelError as e:
            logger.error(f"Failed to setup message processor queue {queue_name}: {e}")
            raise

    def publish_message_pending(self, chat_id: str, message_data: Dict[str, Any]):
        """Publish message.pending event (API -> Background Processor) with retry headers and message ID."""
        routing_key = f"conv.{chat_id}.message.pending"
        message_id = message_data.get("id")

        # Check for duplicate message ID
        if message_id in self.processed_message_ids:
            logger.warning(
                f"Duplicate message ID detected, skipping publish: {message_id}"
            )
            return

        try:
            # Add retry tracking headers
            headers = {
                "x-retry-count": 0,
                "x-max-retries": 3,
                "x-first-publish-time": int(datetime.now().timestamp() * 1000),
                "x-idempotency-key": message_data.get("idempotency_key", ""),
            }

            if self.channel:
                self.channel.basic_publish(
                    exchange="conv.message.pending",
                    routing_key=routing_key,
                    body=json.dumps(message_data),
                    properties=pika.BasicProperties(
                        message_id=message_id,  # RabbitMQ message ID for deduplication
                        delivery_mode=2,  # Make message persistent
                        content_type="application/json",
                        headers=headers,
                    ),
                )

            # Track processed message ID
            self.processed_message_ids.add(message_id)

            # Log metrics
            log_counter_increment(
                "messages_published_total",
                labels={"event_type": "message_pending", "chat_id": chat_id},
            )

            logger.info(
                f"Published message.pending for chat {chat_id} with message ID {message_id} and retry headers"
            )
        except AMQPChannelError as e:
            logger.error(f"Failed to publish message.pending for chat {chat_id}: {e}")
            log_counter_increment(
                "publish_errors_total",
                labels={"event_type": "message_pending", "error_type": "channel_error"},
            )
            raise

    def publish_message_created(self, chat_id: str, message_data: Dict[str, Any]):
        """Publish message.created event (Background Processor -> WS Gateway) with message ID."""
        routing_key = f"conv.{chat_id}.message.created"
        message_id = message_data.get("id")

        try:
            if self.channel:
                self.channel.basic_publish(
                    exchange="conv.message.created",
                    routing_key=routing_key,
                    body=json.dumps(message_data),
                    properties=pika.BasicProperties(
                        message_id=message_id,  # RabbitMQ message ID for deduplication
                        delivery_mode=2,  # Make message persistent
                        content_type="application/json",
                    ),
                )

            # Log metrics
            log_counter_increment(
                "messages_published_total",
                labels={"event_type": "message_created", "chat_id": chat_id},
            )

            logger.info(
                f"Published message.created for chat {chat_id} with message ID {message_id}"
            )
        except AMQPChannelError as e:
            logger.error(f"Failed to publish message.created for chat {chat_id}: {e}")
            log_counter_increment(
                "publish_errors_total",
                labels={"event_type": "message_created", "error_type": "channel_error"},
            )
            raise

    def publish_presence_updated(self, user_id: str, presence_data: Dict[str, Any]):
        """Publish presence.updated event."""
        routing_key = f"presence.{user_id}"

        try:
            if self.channel:
                self.channel.basic_publish(
                    exchange="presence.updated",
                    routing_key=routing_key,
                    body=json.dumps(presence_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type="application/json",
                    ),
                )

            logger.info(f"Published presence.updated for user {user_id}")
        except AMQPChannelError as e:
            logger.error(f"Failed to publish presence.updated for user {user_id}: {e}")
            raise

    def is_connected(self) -> bool:
        """Check if broker is connected."""
        return (
            self.connection is not None
            and not self.connection.is_closed
            and self.channel is not None
            and not self.channel.is_closed
        )

    def reconnect(self):
        """Reconnect to RabbitMQ."""
        logger.info("Reconnecting to RabbitMQ...")
        self.close()
        self._connect()

    def start_consuming(
        self, queue_name: str, callback: Callable, instance_id: Optional[str] = None
    ):
        """Start consuming messages from the shared queue (consumer group pattern)."""
        try:
            # Set up consumer with instance identification
            consumer_tag = (
                f"ws_gateway_{instance_id}" if instance_id else "ws_gateway_consumer"
            )

            if self.channel:
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=callback,
                    consumer_tag=consumer_tag,
                    auto_ack=False,  # Manual acknowledgment for reliability
                )

            logger.info(f"Started consuming from {queue_name} with tag: {consumer_tag}")
        except AMQPChannelError as e:
            logger.error(f"Failed to start consuming from {queue_name}: {e}")
            raise

    def stop_consuming(self, consumer_tag: Optional[str] = None) -> None:
        """Stop consuming messages."""
        try:
            if self.channel:
                if consumer_tag:
                    self.channel.basic_cancel(consumer_tag)
                    logger.info(f"Stopped consuming with tag: {consumer_tag}")
                else:
                    self.channel.stop_consuming()
                    logger.info("Stopped consuming from all queues")
        except AMQPChannelError as e:
            logger.error(f"Failed to stop consuming: {e}")
            raise

    def process_messages(self, timeout: Optional[float] = None):
        """Process messages (blocking call for consumer group)."""
        try:
            if self.connection:
                # BlockingConnection doesn't have start_consuming, it's handled by the channel
                self.connection.process_data_events(time_limit=timeout or 0)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping consumer...")
            if self.channel:
                self.channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error processing messages: {e}")
            raise

    def setup_dlq_monitoring(self) -> str:
        """Set up Dead Letter Queue for monitoring failed messages with expiration policies."""
        dlq_name = "message_processor_dlq"

        try:
            if self.channel:
                # Declare DLQ with message expiration and cleanup policies
                self.channel.queue_declare(
                    queue=dlq_name,
                    durable=True,
                    arguments={
                        "x-message-ttl": 86400000,  # 24 hours message TTL
                        "x-expires": 604800000,  # 7 days queue expiration
                        "x-max-length": 10000,  # Max 10k messages in DLQ
                        "x-overflow": "drop-head",  # Drop oldest messages when full
                    },
                )

                # Bind DLQ to Dead Letter Exchange
                self.channel.queue_bind(
                    exchange="dlx.failed.messages",
                    queue=dlq_name,
                    routing_key="message_processor.failed",
                )

            logger.info(
                f"Set up DLQ monitoring for: {dlq_name} with expiration policies"
            )

            # Log DLQ setup
            log_dlq_event(
                "dlq_created",
                dlq_name,
                message_ttl=86400000,
                queue_expires=604800000,
                max_length=10000,
            )

            return dlq_name
        except AMQPChannelError as e:
            logger.error(f"Failed to setup DLQ monitoring: {e}")
            raise

    def get_dlq_message_count(self, dlq_name: str = "message_processor_dlq") -> int:
        """Get the number of messages in the Dead Letter Queue."""
        try:
            if self.channel:
                # Use queue_declare with passive=True to get queue info
                result = self.channel.queue_declare(queue=dlq_name, passive=True)
                if (
                    result
                    and hasattr(result, "method")
                    and hasattr(result.method, "message_count")
                ):
                    return int(result.method.message_count)
            return 0
        except AMQPChannelError as e:
            logger.error(f"Failed to get DLQ message count: {e}")
            return 0

    def republish_dlq_messages(
        self, dlq_name: str = "message_processor_dlq", limit: int = 10
    ):
        """Republish messages from DLQ back to main queue for retry."""
        try:
            messages_republished = 0

            if not self.channel:
                return messages_republished

            while messages_republished < limit:
                # Use basic_get for synchronous operation
                try:
                    method, properties, body = self.channel.basic_get(
                        queue=dlq_name, auto_ack=False
                    )
                except TypeError:
                    # Some pika versions require callback, skip for now
                    break

                if method is None:
                    # No more messages in DLQ
                    break

                # Reset retry count and republish to main queue
                if properties.headers:
                    properties.headers["x-retry-count"] = 0

                # Republish to main message processor queue
                if self.channel:
                    self.channel.basic_publish(
                        exchange="",
                        routing_key="message_processor",
                        body=body,
                        properties=properties,
                    )

                    # Acknowledge the DLQ message
                    self.channel.basic_ack(delivery_tag=method.delivery_tag)
                messages_republished += 1

                logger.info(
                    f"Republished message from DLQ (count: {messages_republished})"
                )

            logger.info(f"Republished {messages_republished} messages from DLQ")
            return messages_republished

        except AMQPChannelError as e:
            logger.error(f"Failed to republish DLQ messages: {e}")
            return 0

    def inspect_dlq_messages(
        self, dlq_name: str = "message_processor_dlq", limit: int = 10
    ) -> List[Dict]:
        """Inspect messages in DLQ for debugging and analysis."""
        try:
            messages: List[Dict] = []

            if not self.channel:
                return messages

            for _ in range(limit):
                # Use basic_get for synchronous operation
                try:
                    method, properties, body = self.channel.basic_get(
                        queue=dlq_name, auto_ack=False
                    )
                except TypeError:
                    # Some pika versions require callback, skip for now
                    break

                if method is None:
                    break

                # Parse message data
                try:
                    message_data = json.loads(body)
                except json.JSONDecodeError:
                    message_data = {"raw_body": body.decode("utf-8", errors="ignore")}

                # Extract message information
                message_info = {
                    "delivery_tag": method.delivery_tag,
                    "message_id": properties.message_id,
                    "headers": properties.headers or {},
                    "content_type": properties.content_type,
                    "timestamp": properties.timestamp,
                    "data": message_data,
                }

                messages.append(message_info)

                # Reject message back to DLQ (don't acknowledge)
                if self.channel:
                    self.channel.basic_nack(
                        delivery_tag=method.delivery_tag, requeue=True
                    )

            logger.info(f"Inspected {len(messages)} messages from DLQ")
            return messages

        except AMQPChannelError as e:
            logger.error(f"Failed to inspect DLQ messages: {e}")
            return []

    def get_dlq_message_details(
        self, dlq_name: str = "message_processor_dlq", message_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Get detailed information about a specific DLQ message by message ID."""
        try:
            # Get all messages and find the one with matching message_id
            messages = self.inspect_dlq_messages(dlq_name, limit=100)

            for message in messages:
                if message.get("message_id") == message_id:
                    return message

            logger.warning(f"Message with ID {message_id} not found in DLQ")
            return None

        except Exception as e:
            logger.error(f"Failed to get DLQ message details: {e}")
            return None

    def cleanup_dlq_messages(
        self, dlq_name: str = "message_processor_dlq", max_age_hours: int = 24
    ) -> int:
        """Remove old messages from DLQ based on age."""
        try:
            messages_cleaned = 0
            max_age_ms = max_age_hours * 60 * 60 * 1000
            current_time = int(datetime.now().timestamp() * 1000)

            if not self.channel:
                return messages_cleaned

            while True:
                # Use basic_get for synchronous operation
                try:
                    method, properties, body = self.channel.basic_get(
                        queue=dlq_name, auto_ack=False
                    )
                except TypeError:
                    # Some pika versions require callback, skip for now
                    break

                if method is None:
                    break

                # Check message age
                message_time = properties.timestamp or 0
                if current_time - message_time > max_age_ms:
                    # Message is too old, acknowledge to remove it
                    if self.channel:
                        self.channel.basic_ack(delivery_tag=method.delivery_tag)
                    messages_cleaned += 1
                    logger.debug(
                        f"Cleaned up old message from DLQ: {properties.message_id}"
                    )
                else:
                    # Message is not old enough, reject back to queue
                    if self.channel:
                        self.channel.basic_nack(
                            delivery_tag=method.delivery_tag, requeue=True
                        )
                    break  # Stop processing since messages are ordered by age

            logger.info(f"Cleaned up {messages_cleaned} old messages from DLQ")
            return messages_cleaned

        except AMQPChannelError as e:
            logger.error(f"Failed to cleanup DLQ messages: {e}")
            return 0

    def close(self):
        """Close connection."""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")


# Global message broker instance (lazy initialization)
_message_broker_instance: Optional[MessageBroker] = None


def get_message_broker() -> MessageBroker:
    """Get the global message broker instance (lazy initialization)."""
    global _message_broker_instance
    if _message_broker_instance is None:
        _message_broker_instance = MessageBroker()
    return _message_broker_instance
