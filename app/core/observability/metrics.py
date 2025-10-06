"""Structured logging for observability and metrics collection."""

# mypy: ignore-errors

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def log_metric(
    event_type: str,
    value: Optional[float] = None,
    labels: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> None:
    """
    Log structured metrics for observability.

    Args:
        event_type: Type of metric event (e.g., 'counter_increment', 'histogram_record')
        value: Numeric value for histograms/gauges
        labels: Key-value pairs for metric labels
        **kwargs: Additional fields to include in the log
    """
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "instance_id": os.getenv("INSTANCE_ID", "unknown"),
        "service": "opchat-backend",
    }

    if value is not None:
        log_data["value"] = value

    if labels:
        log_data["labels"] = labels

    # Add any additional fields
    log_data.update(kwargs)

    # Log as JSON for easy parsing
    logger.info(json.dumps(log_data))


def log_counter_increment(
    name: str, labels: Optional[Dict[str, str]] = None, **kwargs: Any
) -> None:
    """Log a counter increment event."""
    log_metric(
        event_type="counter_increment", counter_name=name, labels=labels, **kwargs
    )


def log_histogram_record(
    name: str, value: float, labels: Optional[Dict[str, str]] = None, **kwargs: Any
) -> None:
    """Log a histogram record event."""
    log_metric(
        event_type="histogram_record",
        histogram_name=name,
        value=value,
        labels=labels,
        **kwargs,
    )


def log_gauge_set(
    name: str, value: float, labels: Optional[Dict[str, str]] = None, **kwargs: Any
) -> None:
    """Log a gauge set event."""
    log_metric(
        event_type="gauge_set", gauge_name=name, value=value, labels=labels, **kwargs
    )


def log_connection_event(event: str, service: str, **kwargs: Any) -> None:
    """Log connection-related events."""
    log_metric(
        event_type="connection_event", connection_event=event, service=service, **kwargs
    )


def log_processing_event(
    event: str, message_id: Optional[str] = None, **kwargs: Any
) -> None:
    """Log message processing events."""
    log_metric(
        event_type="processing_event",
        processing_event=event,
        message_id=message_id,
        **kwargs,
    )


def log_dlq_event(event: str, dlq_name: str, **kwargs: Any) -> None:
    """Log DLQ-related events."""
    log_metric(event_type="dlq_event", dlq_event=event, dlq_name=dlq_name, **kwargs)
