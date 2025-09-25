"""Tests for transaction context manager."""

import pytest
from unittest.mock import Mock
from sqlalchemy.exc import IntegrityError

from app.repositories.transaction import transaction_scope


class TestTransactionScope:
    """Test cases for transaction_scope context manager."""

    @pytest.fixture
    def mock_session_factory(self):
        """Mock session factory with mock session."""
        mock_session = Mock()
        mock_factory = Mock(return_value=mock_session)
        return mock_factory, mock_session

    def test_transaction_scope_commit_success(self, mock_session_factory):
        """Test that successful operations are committed."""
        factory, mock_session = mock_session_factory

        with transaction_scope(factory) as session:
            # Simulate some operations
            session.add("something")
            session.flush()

        # Verify session lifecycle
        factory.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_transaction_scope_rollback_on_error(self, mock_session_factory):
        """Test that errors trigger rollback."""
        factory, mock_session = mock_session_factory

        with pytest.raises(ValueError):
            with transaction_scope(factory) as session:
                session.add("something")
                raise ValueError("Test error")

        # Verify rollback occurred
        factory.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()

    def test_transaction_scope_session_always_closed(self, mock_session_factory):
        """Test that session is always closed even if close() raises exception."""
        factory, mock_session = mock_session_factory
        mock_session.close.side_effect = Exception("Close error")

        # Should not raise the close error
        with transaction_scope(factory) as session:
            session.add("something")

        # Verify close was attempted
        mock_session.close.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_coordinated_multi_repo_operations(
        self,
        user_repo,
        chat_repo,
        message_repo,
        sample_users,
        test_session_factory,
        clean_db,
    ):
        """Test coordinated operations across multiple repositories."""
        alice, bob = sample_users[0], sample_users[1]

        # Use transaction scope for coordinated operations
        with transaction_scope(test_session_factory) as session:
            # Create a new user
            new_user = user_repo.create_user(
                "coordinated_user", "hash123", session=session
            )

            # Create DM between alice and new user
            dm = chat_repo.create_direct_message(alice.id, new_user.id, session=session)

            # Send message in the DM
            message = message_repo.create_message(
                chat_id=dm.id,
                sender_id=alice.id,
                content="Hello coordinated world!",
                idempotency_key="coord_msg_key",
                session=session,
            )

            # All operations should be in the same transaction
            assert new_user.username == "coordinated_user"
            assert dm.dm_key is not None
            assert message.content == "Hello coordinated world!"

        # After transaction commits, all should be persisted
        persisted_user = user_repo.get_by_username("coordinated_user")
        assert persisted_user is not None
        assert persisted_user.id == new_user.id

        persisted_dm = chat_repo.get_chat_by_id(dm.id)
        assert persisted_dm is not None

        persisted_message = message_repo.get_by_idempotency_key("coord_msg_key")
        assert persisted_message is not None
        assert persisted_message.content == "Hello coordinated world!"

    def test_coordinated_rollback_on_error(
        self, user_repo, chat_repo, sample_users, test_session_factory, clean_db
    ):
        """Test that error in coordinated transaction rolls back all operations."""
        alice = sample_users[0]

        with pytest.raises(ValueError):
            with transaction_scope(test_session_factory) as session:
                # Create a user
                new_user = user_repo.create_user(
                    "rollback_user", "hash123", session=session
                )

                # Create DM
                dm = chat_repo.create_direct_message(
                    alice.id, new_user.id, session=session
                )

                # Force an error
                raise ValueError("Coordinated operation failed")

        # None of the operations should be persisted
        rolled_back_user = user_repo.get_by_username("rollback_user")
        assert rolled_back_user is None

    def test_transaction_scope_preserves_original_exception(self, mock_session_factory):
        """Test that original exceptions are preserved and re-raised."""
        factory, mock_session = mock_session_factory

        original_error = IntegrityError("Constraint violation", None, None)

        with pytest.raises(IntegrityError) as exc_info:
            with transaction_scope(factory):
                raise original_error

        # Should be the exact same exception
        assert exc_info.value is original_error
        mock_session.rollback.assert_called_once()

    def test_transaction_scope_returns_session(self, mock_session_factory):
        """Test that context manager yields the session."""
        factory, mock_session = mock_session_factory

        with transaction_scope(factory) as session:
            assert session is mock_session

        factory.assert_called_once()
