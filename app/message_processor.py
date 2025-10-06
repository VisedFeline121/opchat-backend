"""
Message Processor CLI

Background worker for processing pending messages.
Run this as a separate service to handle async message processing.
"""

import logging
import sys

from app.core.messaging.processor import message_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for message processor."""
    try:
        logger.info("Starting OpChat Message Processor...")
        message_processor.start_processing()
    except KeyboardInterrupt:
        logger.info("Message processor stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Message processor failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
