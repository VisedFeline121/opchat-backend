"""Transaction context manager for coordinated multi-repository operations."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session


@contextmanager
def transaction_scope(session_factory) -> Generator[Session, None, None]:
    """
    Context manager for coordinated multi-repository operations.

    Provides a session that can be shared across multiple repositories
    for atomic operations spanning multiple aggregates.

    Usage:
        with transaction_scope(SessionLocal) as session:
            chat = chat_repo.create_group_chat(..., session=session)
            message_repo.create_message(..., session=session)
            # Both operations committed together

    Args:
        session_factory: SQLAlchemy session factory (e.g., SessionLocal)

    Yields:
        Session: SQLAlchemy session for coordinated operations

    Raises:
        Exception: Any exception from repository operations (after rollback)
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        try:
            session.close()
        except Exception:
            # Ignore close errors - session cleanup is best effort
            pass
