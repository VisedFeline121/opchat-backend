"""Tests for BaseRepo."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.base_repo import BaseRepo


class SampleRepo(BaseRepo):
    """Sample implementation of BaseRepo for testing."""

    def sample_operation(self, param, session=None):
        """Sample method that uses _execute_with_session."""
        return self._execute_with_session(
            lambda s: self._sample_operation_impl(s, param),
            session=session,
            operation_name="sample_operation",
        )

    def _sample_operation_impl(self, session, param):
        """Test implementation that can succeed or fail."""
        if param == "fail":
            raise IntegrityError("Test error", None, None)
        session.execute("SELECT 1")  # Dummy operation
        return f"success_{param}"


class TestBaseRepo:
    """Test cases for BaseRepo."""

    @pytest.fixture
    def mock_session_factory(self):
        """Mock session factory."""
        mock_session = Mock()
        mock_factory = Mock(return_value=mock_session)
        return mock_factory, mock_session

    @pytest.fixture
    def test_repo(self, mock_session_factory):
        """Test repository instance."""
        factory, _ = mock_session_factory
        return SampleRepo(factory)

    def test_auto_commit_mode_success(self, test_repo, mock_session_factory):
        """Test auto-commit mode with successful operation."""
        factory, mock_session = mock_session_factory

        result = test_repo.sample_operation("test_param")

        # Verify session lifecycle
        factory.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        assert result == "success_test_param"

    def test_auto_commit_mode_with_error(self, test_repo, mock_session_factory):
        """Test auto-commit mode with error - should rollback."""
        factory, mock_session = mock_session_factory

        with pytest.raises(IntegrityError):
            test_repo.sample_operation("fail")

        # Verify rollback and cleanup
        factory.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_coordinated_mode_success(self, test_repo, mock_session_factory):
        """Test coordinated mode - uses provided session, doesn't commit."""
        factory, _ = mock_session_factory
        external_session = Mock()

        result = test_repo.sample_operation("test_param", session=external_session)

        # Should not create new session or commit
        factory.assert_not_called()
        external_session.commit.assert_not_called()
        external_session.rollback.assert_not_called()
        external_session.close.assert_not_called()
        assert result == "success_test_param"

    def test_coordinated_mode_with_error(self, test_repo, mock_session_factory):
        """Test coordinated mode with error - doesn't rollback (caller's responsibility)."""
        factory, _ = mock_session_factory
        external_session = Mock()

        with pytest.raises(IntegrityError):
            test_repo.sample_operation("fail", session=external_session)

        # Should not manage external session
        factory.assert_not_called()
        external_session.commit.assert_not_called()
        external_session.rollback.assert_not_called()
        external_session.close.assert_not_called()

    @patch("app.repositories.base_repo.logger")
    def test_error_logging_with_context(
        self, mock_logger, test_repo, mock_session_factory
    ):
        """Test that errors are logged with operation context."""
        factory, mock_session = mock_session_factory

        with pytest.raises(IntegrityError):
            test_repo.sample_operation("fail")

        # Verify error was logged
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "sample_operation" in call_args[0][0]
        assert "Test error" in call_args[0][0]

    def test_original_exception_preserved(self, test_repo, mock_session_factory):
        """Test that original SQLAlchemy exceptions are re-raised unchanged."""
        factory, mock_session = mock_session_factory

        with pytest.raises(IntegrityError) as exc_info:
            test_repo.sample_operation("fail")

        # Verify it contains the original error message
        assert "Test error" in str(exc_info.value)
