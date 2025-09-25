"""Database connection manager and session factory."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Import models to ensure they're registered with Base.metadata

# Database configuration
APP_DATABASE_URL = os.getenv("APP_DATABASE_URL")

# Connection pool configuration with proper defaults
POOL_SIZE = int(os.getenv("POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("MAX_OVERFLOW", "20"))
POOL_RECYCLE = int(os.getenv("POOL_RECYCLE", "3600"))  # 1 hour
POOL_TIMEOUT = int(os.getenv("POOL_TIMEOUT", "30"))  # 30 seconds
POOL_PRE_PING = os.getenv("POOL_PRE_PING", "true").lower() == "true"
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

# Create engine with connection pooling (QueuePool is default)
if APP_DATABASE_URL is None:
    raise ValueError("APP_DATABASE_URL environment variable is required")

engine = create_engine(
    APP_DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,
    pool_timeout=POOL_TIMEOUT,
    pool_pre_ping=POOL_PRE_PING,  # Validates connections before use
    echo=SQL_ECHO,  # SQL logging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides database sessions.

    Yields:
        Session: SQLAlchemy session that automatically closes after use

    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_engine():
    """Get the SQLAlchemy engine for advanced use cases."""
    return engine


def get_session_local():
    """Get the SessionLocal factory for testing or advanced use cases."""
    return SessionLocal
