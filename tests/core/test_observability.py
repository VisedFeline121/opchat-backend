"""Tests for observability and metrics collection."""

import json
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.core.observability.metrics import (
    log_metric,
    log_counter_increment,
    log_histogram_record,
    log_gauge_set,
    log_connection_event,
    log_processing_event,
    log_dlq_event,
)


class TestObservabilityMetrics:
    """Test observability metrics collection."""

    def test_log_metric_basic(self):
        """Test basic metric logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_metric("test_event", value=42.5, labels={"key": "value"})

            # Verify logger was called
            mock_logger.info.assert_called_once()

            # Parse the logged JSON
            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "test_event"
            assert logged_data["value"] == 42.5
            assert logged_data["labels"]["key"] == "value"
            assert "timestamp" in logged_data
            assert "instance_id" in logged_data
            assert "service" in logged_data

    def test_log_counter_increment(self):
        """Test counter increment logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_counter_increment("test_counter", labels={"status": "success"})

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "counter_increment"
            assert logged_data["counter_name"] == "test_counter"
            assert logged_data["labels"]["status"] == "success"

    def test_log_histogram_record(self):
        """Test histogram record logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_histogram_record(
                "test_histogram", 150.5, labels={"operation": "create"}
            )

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "histogram_record"
            assert logged_data["histogram_name"] == "test_histogram"
            assert logged_data["value"] == 150.5
            assert logged_data["labels"]["operation"] == "create"

    def test_log_gauge_set(self):
        """Test gauge set logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_gauge_set("test_gauge", 75.0, labels={"type": "memory"})

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "gauge_set"
            assert logged_data["gauge_name"] == "test_gauge"
            assert logged_data["value"] == 75.0
            assert logged_data["labels"]["type"] == "memory"

    def test_log_connection_event(self):
        """Test connection event logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_connection_event("connected", "rabbitmq", host="localhost")

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "connection_event"
            assert logged_data["connection_event"] == "connected"
            assert logged_data["service"] == "rabbitmq"
            assert logged_data["host"] == "localhost"

    def test_log_processing_event(self):
        """Test processing event logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_processing_event("processing_started", "msg-123", retry_count=2)

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "processing_event"
            assert logged_data["processing_event"] == "processing_started"
            assert logged_data["message_id"] == "msg-123"
            assert logged_data["retry_count"] == 2

    def test_log_dlq_event(self):
        """Test DLQ event logging."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_dlq_event("dlq_created", "test_dlq", message_count=5)

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "dlq_event"
            assert logged_data["dlq_event"] == "dlq_created"
            assert logged_data["dlq_name"] == "test_dlq"
            assert logged_data["message_count"] == 5

    def test_log_metric_with_additional_fields(self):
        """Test metric logging with additional fields."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_metric("custom_event", custom_field="custom_value", another_field=123)

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "custom_event"
            assert logged_data["custom_field"] == "custom_value"
            assert logged_data["another_field"] == 123

    def test_log_metric_without_optional_fields(self):
        """Test metric logging without optional fields."""
        with patch("app.core.observability.metrics.logger") as mock_logger:
            log_metric("simple_event")

            logged_data = json.loads(mock_logger.info.call_args[0][0])

            assert logged_data["event_type"] == "simple_event"
            assert "value" not in logged_data
            assert "labels" not in logged_data
