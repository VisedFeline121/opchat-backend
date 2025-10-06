"""Message processor for async message handling."""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from app.core.messaging.broker import get_message_broker
from app.core.observability.metrics import (
    log_counter_increment,
    log_histogram_record,
    log_processing_event,
)
from app.db.db import get_db
from app.repositories.chat_repo import ChatRepo
from app.repositories.message_repo import MessageRepo
from app.repositories.user_repo import UserRepo

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Background processor for handling pending messages."""

    def __init__(self):
        self.broker = get_message_broker()
        self.message_repo = None
        self.chat_repo = None
        self.user_repo = None

        # Set up delay queue for exponential backoff retries
        try:
            self.broker.setup_delay_queue()
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to setup delay queue: {e}")
            # Continue without delay queue - will fall back to immediate requeue

    def _get_repositories(self):
        """Get repository instances with database session."""
        if not self.message_repo:
            db = next(get_db())
            self.message_repo = MessageRepo(db)
            self.chat_repo = ChatRepo(db)
            self.user_repo = UserRepo(db)
        return self.message_repo, self.chat_repo, self.user_repo

    def process_message_callback(self, channel, method, properties, body):
        """Callback for processing pending messages with retry logic."""
        start_time = time.time()
        retry_count = 0
        max_retries = 3
        message_id = None

        try:
            # Get retry count from headers
            if properties.headers and "x-retry-count" in properties.headers:
                retry_count = properties.headers["x-retry-count"]
                max_retries = properties.headers.get("x-max-retries", 3)

            # Parse message data
            message_data = json.loads(body)
            message_id = message_data.get("id")
            logger.info(
                f"Processing pending message: {message_id} (retry: {retry_count}/{max_retries})"
            )

            # Log processing start
            log_processing_event(
                "processing_started", message_id, retry_count=retry_count
            )

            # Get repositories
            message_repo, chat_repo, user_repo = self._get_repositories()

            # Validate message data
            if not self._validate_message_data(message_data):
                logger.error(f"Invalid message data: {message_data}")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # Check if message already exists (idempotency)
            existing_message = message_repo.get_by_idempotency_key(
                message_data.get("idempotency_key")
            )
            if existing_message:
                logger.info(f"Message already exists, skipping: {existing_message.id}")
                # Publish the existing message to WS Gateway
                self._publish_existing_message(existing_message)
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

            # Create message in database
            message = self._create_message(message_data, message_repo)
            if not message:
                logger.error(f"Failed to create message: {message_data}")
                self._handle_retry(
                    channel,
                    method,
                    properties,
                    body,
                    retry_count,
                    max_retries,
                    "Failed to create message",
                )
                return

            # Publish message.created event
            self._publish_created_message(message)

            # Acknowledge successful processing
            channel.basic_ack(delivery_tag=method.delivery_tag)

            # Log successful processing metrics
            processing_time = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds
            log_counter_increment(
                "messages_processed_total", labels={"status": "success"}
            )
            log_histogram_record("message_processing_duration_ms", processing_time)
            log_processing_event(
                "processing_completed", message_id, processing_time_ms=processing_time
            )

            logger.info(f"Successfully processed message: {message.id}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            log_counter_increment(
                "processing_errors_total", labels={"error_type": "json_decode"}
            )
            log_processing_event(
                "processing_failed", message_id, error_type="json_decode"
            )
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            log_counter_increment(
                "processing_errors_total", labels={"error_type": "general"}
            )
            log_processing_event(
                "processing_failed", message_id, error_type="general", error=str(e)
            )
            self._handle_retry(
                channel, method, properties, body, retry_count, max_retries, str(e)
            )

    def _handle_retry(
        self, channel, method, properties, body, retry_count, max_retries, error_msg
    ):
        """Handle message retry with exponential backoff."""
        if retry_count < max_retries:
            # Increment retry count
            new_retry_count = retry_count + 1

            # Calculate exponential backoff delay (1s, 2s, 4s, 8s, 16s)
            delay_seconds = 2**retry_count

            # Log retry metrics
            log_counter_increment(
                "message_retries_total", labels={"retry_count": str(new_retry_count)}
            )
            log_processing_event(
                "message_retry",
                None,
                retry_count=new_retry_count,
                delay_seconds=delay_seconds,
            )

            logger.warning(
                f"Retrying message in {delay_seconds}s (attempt {new_retry_count}/{max_retries}): {error_msg}"
            )

            # Parse message data from body
            try:
                message_data = json.loads(body)
            except json.JSONDecodeError:
                logger.error("Failed to parse message body for retry")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # Update message data with new retry count
            message_data["retry_count"] = new_retry_count
            message_data["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Send to delay queue with exponential backoff
            try:
                from app.core.messaging.broker import MessageBroker

                broker = MessageBroker()
                broker.publish_to_delay_queue(message_data, delay_seconds)

                # Acknowledge original message (it's now in delay queue)
                channel.basic_ack(delivery_tag=method.delivery_tag)

                logger.info(f"Message sent to delay queue for {delay_seconds}s retry")

            except Exception as delay_error:
                logger.error(f"Failed to send message to delay queue: {delay_error}")
                # Fallback to immediate requeue if delay queue fails
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        else:
            # Max retries exceeded, send to DLQ
            logger.error(
                f"Max retries exceeded for message, sending to DLQ: {error_msg}"
            )

            # Log DLQ metrics
            log_counter_increment(
                "messages_sent_to_dlq_total", labels={"max_retries": str(max_retries)}
            )
            log_processing_event(
                "message_sent_to_dlq", None, max_retries=max_retries, error=error_msg
            )

            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _validate_message_data(self, message_data: Dict[str, Any]) -> bool:
        """Validate message data structure."""
        required_fields = ["id", "chat_id", "sender_id", "content", "idempotency_key"]
        return all(field in message_data for field in required_fields)

    def _create_message(self, message_data: Dict[str, Any], message_repo: MessageRepo):
        """Create message in database."""
        try:
            # Save to database
            return message_repo.create_message(
                UUID(message_data["chat_id"]),
                UUID(message_data["sender_id"]),
                message_data["content"],
                message_data["idempotency_key"],
            )
        except Exception as e:
            logger.error(f"Failed to create message: {e}")
            return None

    def _publish_existing_message(self, message):
        """Publish existing message to WS Gateway."""
        message_data = {
            "id": str(message.id),
            "chat_id": str(message.chat_id),
            "sender_id": str(message.sender_id),
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        self.broker.publish_message_created(str(message.chat_id), message_data)

    def _publish_created_message(self, message):
        """Publish created message to WS Gateway."""
        message_data = {
            "id": str(message.id),
            "chat_id": str(message.chat_id),
            "sender_id": str(message.sender_id),
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        self.broker.publish_message_created(str(message.chat_id), message_data)

    def start_processing(self):
        """Start processing pending messages with reliability features."""
        try:
            # Set up message processor queue with DLQ
            queue_name = self.broker.setup_message_processor_queue()

            # Set up DLQ monitoring
            self.broker.setup_dlq_monitoring()

            # Configure consumer with prefetch limit for reliability
            self.broker.channel.basic_qos(
                prefetch_count=1
            )  # Process one message at a time

            # Start consuming
            self.broker.start_consuming(
                queue_name, self.process_message_callback, "message_processor"
            )

            logger.info("Message processor started with reliability features")
            self.broker.process_messages()

        except KeyboardInterrupt:
            logger.info("Message processor stopped by user")
        except Exception as e:
            logger.error(f"Error in message processor: {e}")
            raise
        finally:
            self.broker.close()


# Global message processor instance
message_processor = MessageProcessor()
