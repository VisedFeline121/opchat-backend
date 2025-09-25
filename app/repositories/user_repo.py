"""User repository."""

from datetime import datetime
from typing import List, Optional, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.user import User
from app.repositories.base_repo import BaseRepo

logger = get_logger(__name__)


class UserRepo(BaseRepo):
    """User repository."""

    def _create_user_implementation(
        self, session: Session, username: str, password_hash: str
    ) -> User:
        """Implementation of user creation."""
        logger.debug(f"Creating user with username: {username}")

        # Input validation
        if not username or not username.strip():
            logger.warning("Attempted to create user with empty username")
            raise ValueError("Username cannot be empty or whitespace-only")
        if len(username) > 255:
            logger.warning(
                f"Attempted to create user with username too long: {len(username)} chars"
            )
            raise ValueError("Username cannot exceed 255 characters")
        if not password_hash:
            logger.warning(
                f"Attempted to create user {username} with empty password hash"
            )
            raise ValueError("Password hash cannot be empty")

        user = User(username=username.strip(), password_hash=password_hash)
        session.add(user)
        session.flush()  # Generate ID without committing

        logger.info(f"Created user: {user.id} ({user.username})")
        return user

    def create_user(
        self, username: str, password_hash: str, session: Optional[Session] = None
    ) -> User:
        """Create a new user."""
        return cast(
            User,
            self._execute_with_session(
                lambda session: self._create_user_implementation(
                    session, username, password_hash
                ),
                session=session,
                operation_name="create_user",
            ),
        )

    def _get_user_by_id_implementation(
        self, session: Session, user_id: UUID
    ) -> Optional[User]:
        """Implementation of user retrieval."""
        # Validate UUID input
        if isinstance(user_id, str):
            try:
                from uuid import UUID as UUIDType

                user_id = UUIDType(user_id)
            except ValueError as e:
                raise ValueError(f"Invalid UUID format: {user_id}") from e
        elif user_id is None:
            raise ValueError("User ID cannot be None")

        return cast(
            Optional[User], session.query(User).filter(User.id == user_id).one_or_none()
        )

    def get_user_by_id(
        self, user_id: UUID, session: Optional[Session] = None
    ) -> Optional[User]:
        """Get a user by id."""
        return cast(
            Optional[User],
            self._execute_with_session(
                lambda session: self._get_user_by_id_implementation(session, user_id),
                session=session,
                operation_name="get_user_by_id",
            ),
        )

    def _get_by_username_implementation(
        self, session: Session, username: str
    ) -> Optional[User]:
        """Implementation of user retrieval by username."""
        return cast(
            Optional[User],
            session.query(User).filter(User.username == username).one_or_none(),
        )

    def get_by_username(
        self, username: str, session: Optional[Session] = None
    ) -> Optional[User]:
        """Get a user by username."""
        return cast(
            Optional[User],
            self._execute_with_session(
                lambda session: self._get_by_username_implementation(session, username),
                session=session,
                operation_name="get_by_username",
            ),
        )

    def _update_last_login_at_implementation(
        self, session: Session, user_id: UUID, last_login_at: datetime
    ) -> Optional[User]:
        """Implementation of last login at update."""
        user = cast(
            Optional[User], session.query(User).filter(User.id == user_id).one_or_none()
        )
        if user:
            user.last_login_at = last_login_at  # type: ignore[assignment]
            session.flush()
        return user

    def update_last_login_at(
        self, user_id: UUID, last_login_at: datetime, session: Optional[Session] = None
    ) -> Optional[User]:
        """Update the last login at timestamp."""
        return cast(
            Optional[User],
            self._execute_with_session(
                lambda session: self._update_last_login_at_implementation(
                    session, user_id, last_login_at
                ),
                session=session,
                operation_name="update_last_login_at",
            ),
        )

    def _get_all_users_implementation(self, session: Session) -> List[User]:
        """Implementation of all users retrieval."""
        return cast(List[User], session.query(User).all())

    def get_all_users(self, session=None) -> List[User]:
        """Get all users."""
        return cast(
            List[User],
            self._execute_with_session(
                lambda session: self._get_all_users_implementation(session),
                session=session,
                operation_name="get_all_users",
            ),
        )

    def _delete_user_implementation(self, session: Session, user_id: UUID) -> None:
        """Implementation of user deletion."""
        session.query(User).filter(User.id == user_id).delete()

    def delete_user(self, user_id: UUID, session: Optional[Session] = None) -> None:
        """Delete a user."""
        self._execute_with_session(
            lambda session: self._delete_user_implementation(session, user_id),
            session=session,
            operation_name="delete_user",
        )
