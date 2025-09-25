"""Logging configuration for OpChat."""

import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Optional

import yaml


def setup_logging(
    config_path: Optional[str] = None,
    default_level: int = logging.INFO,
    env_key: str = "LOG_CFG",
) -> None:
    """
    Setup logging configuration from YAML file.

    Args:
        config_path: Path to logging config file
        default_level: Default logging level if config file not found
        env_key: Environment variable name for config path override
    """
    # Check environment variable first
    path_str = os.getenv(env_key, config_path)

    # Default path if none provided - use environment-specific config
    if path_str is None:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        config_dir = Path(__file__).parent.parent.parent / "config"

        # Try environment-specific config first
        env_config = config_dir / f"logging.{environment}.yaml"
        if env_config.exists():
            path = env_config
        else:
            # Fall back to default config
            path = config_dir / "logging.yaml"
    else:
        path = Path(path_str)

    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    if path.exists():
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f.read())
            logging.config.dictConfig(config)

            logger = logging.getLogger(__name__)
            logger.info(f"Logging configured from {path}")

        except Exception as e:
            print(f"Error loading logging configuration from {path}: {e}")
            logging.basicConfig(level=default_level)
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load logging config, using basic config: {e}")
    else:
        print(f"Logging config file not found at {path}, using basic configuration")
        logging.basicConfig(level=default_level)
        logger = logging.getLogger(__name__)
        logger.warning(f"Logging config file not found at {path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def configure_sqlalchemy_logging(echo: bool = False, echo_pool: bool = False) -> None:
    """
    Configure SQLAlchemy logging levels.

    Args:
        echo: Enable SQL statement logging
        echo_pool: Enable connection pool logging
    """
    if echo:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    if echo_pool:
        logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


def log_startup_info() -> None:
    """Log application startup information."""
    logger = get_logger(__name__)
    logger.info("=" * 50)
    logger.info("OpChat Backend Starting Up")
    logger.info("=" * 50)
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info("=" * 50)


def log_shutdown_info() -> None:
    """Log application shutdown information."""
    logger = get_logger(__name__)
    logger.info("=" * 50)
    logger.info("OpChat Backend Shutting Down")
    logger.info("=" * 50)
