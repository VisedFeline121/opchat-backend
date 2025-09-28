"""Base repository class."""

from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseRepo:
    """Base repository class."""

    def __init__(self, session_factory):
        """Initialize the repository."""
        self.session_factory = session_factory

    def _execute_with_session(self, operation, session=None, operation_name="unknown"):
        """Execute a function with the session."""
        if session is not None:
            # Coordinated mode - use provided session, don't commit
            return operation(session)
        # Auto-commit mode - create, use, commit, close
        session = self.session_factory()
        try:
            result = operation(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            self._log_error(operation_name, e)
            raise
        finally:
            session.close()

    def _log_error(self, operation_name, error, **context):
        """Log an error."""
        logger.error(f"Error in {operation_name}: {error}", extra=context)
