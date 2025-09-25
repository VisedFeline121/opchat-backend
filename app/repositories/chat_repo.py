"""Chat repository."""

from typing import List, Optional, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.chat import Chat, DirectMessage, GroupChat
from app.models.membership import MemberRole, Membership
from app.repositories.base_repo import BaseRepo

logger = get_logger(__name__)


class ChatRepo(BaseRepo):
    """Chat repository."""

    def _create_direct_message_implementation(
        self, session: Session, user1_id: UUID, user2_id: UUID
    ) -> DirectMessage:
        """Implementation of direct message creation."""
        logger.debug(f"Creating direct message between users {user1_id} and {user2_id}")

        # Validate users are different
        if user1_id == user2_id:
            logger.warning(f"Attempted to create DM with same user: {user1_id}")
            raise ValueError("Cannot create direct message with the same user")

        # Check if DM already exists
        existing_dm = cast(
            Optional[DirectMessage],
            DirectMessage.find_by_users(session, user1_id, user2_id),
        )
        if existing_dm:
            logger.debug(f"Returning existing DM: {existing_dm.id}")
            return existing_dm

        # Create new DM with memberships
        dm_key = DirectMessage.create_dm_key(user1_id, user2_id)
        dm = DirectMessage(dm_key=dm_key)
        session.add(dm)
        session.flush()  # Generate ID

        # Add both users as members
        membership1 = Membership(
            chat_id=dm.id, user_id=user1_id, role=MemberRole.MEMBER
        )
        membership2 = Membership(
            chat_id=dm.id, user_id=user2_id, role=MemberRole.MEMBER
        )
        session.add(membership1)
        session.add(membership2)
        session.flush()

        logger.info(
            f"Created direct message: {dm.id} between {user1_id} and {user2_id}"
        )
        return dm

    def create_direct_message(
        self, user1_id: UUID, user2_id: UUID, session: Optional[Session] = None
    ) -> DirectMessage:
        """Create a direct message between two users."""
        return cast(
            DirectMessage,
            self._execute_with_session(
                lambda s: self._create_direct_message_implementation(
                    s, user1_id, user2_id
                ),
                session=session,
                operation_name="create_direct_message",
            ),
        )

    def _create_group_chat_implementation(
        self, session: Session, creator_id: UUID, topic: str, member_ids: List[UUID]
    ) -> GroupChat:
        """Implementation of group chat creation."""
        # Ensure creator is included in member list
        all_member_ids = set(member_ids)
        all_member_ids.add(creator_id)

        # Create group chat
        group = GroupChat(topic=topic)
        session.add(group)
        session.flush()  # Generate ID

        # Add creator as admin
        creator_membership = Membership(
            chat_id=group.id, user_id=creator_id, role=MemberRole.ADMIN
        )
        session.add(creator_membership)

        # Add other members (excluding creator to avoid duplicate)
        for member_id in all_member_ids:
            if member_id != creator_id:
                membership = Membership(
                    chat_id=group.id, user_id=member_id, role=MemberRole.MEMBER
                )
                session.add(membership)

        session.flush()
        return group

    def create_group_chat(
        self,
        creator_id: UUID,
        topic: str,
        member_ids: List[UUID],
        session: Optional[Session] = None,
    ) -> GroupChat:
        """Create a group chat with members."""
        return cast(
            GroupChat,
            self._execute_with_session(
                lambda s: self._create_group_chat_implementation(
                    s, creator_id, topic, member_ids
                ),
                session=session,
                operation_name="create_group_chat",
            ),
        )

    def _get_user_chats_implementation(
        self, session: Session, user_id: UUID
    ) -> List[Chat]:
        """Implementation of user chats retrieval."""
        return cast(
            List[Chat],
            (
                session.query(Chat)
                .join(Membership)
                .filter(Membership.user_id == user_id)
                .order_by(Chat.created_at.desc())
                .all()
            ),
        )

    def get_user_chats(
        self, user_id: UUID, session: Optional[Session] = None
    ) -> List[Chat]:
        """Get all chats a user is a member of."""
        return cast(
            List[Chat],
            self._execute_with_session(
                lambda s: self._get_user_chats_implementation(s, user_id),
                session=session,
                operation_name="get_user_chats",
            ),
        )

    def _add_member_implementation(
        self, session: Session, chat_id: UUID, user_id: UUID, role: MemberRole
    ) -> Membership:
        """Implementation of member addition."""
        # Check if membership already exists
        existing = (
            session.query(Membership)
            .filter(Membership.chat_id == chat_id, Membership.user_id == user_id)
            .first()
        )

        if existing:
            # Update role if different
            if existing.role != role:
                existing.role = role  # type: ignore[assignment]
                session.flush()
            return existing

        # Create new membership
        membership = Membership(chat_id=chat_id, user_id=user_id, role=role)
        session.add(membership)
        session.flush()
        return membership

    def add_member(
        self,
        chat_id: UUID,
        user_id: UUID,
        role: MemberRole = MemberRole.MEMBER,
        session: Optional[Session] = None,
    ) -> Membership:
        """Add a member to a chat."""
        return cast(
            Membership,
            self._execute_with_session(
                lambda s: self._add_member_implementation(s, chat_id, user_id, role),
                session=session,
                operation_name="add_member",
            ),
        )

    def _remove_member_implementation(
        self, session: Session, chat_id: UUID, user_id: UUID
    ) -> None:
        """Implementation of member removal."""
        session.query(Membership).filter(
            Membership.chat_id == chat_id, Membership.user_id == user_id
        ).delete()

    def remove_member(
        self, chat_id: UUID, user_id: UUID, session: Optional[Session] = None
    ) -> None:
        """Remove a member from a chat."""
        self._execute_with_session(
            lambda s: self._remove_member_implementation(s, chat_id, user_id),
            session=session,
            operation_name="remove_member",
        )

    def _is_member_implementation(
        self, session: Session, chat_id: UUID, user_id: UUID
    ) -> bool:
        """Implementation of membership check."""
        membership = (
            session.query(Membership)
            .filter(Membership.chat_id == chat_id, Membership.user_id == user_id)
            .first()
        )
        return membership is not None

    def is_member(
        self, chat_id: UUID, user_id: UUID, session: Optional[Session] = None
    ) -> bool:
        """Check if a user is a member of a chat."""
        return cast(
            bool,
            self._execute_with_session(
                lambda s: self._is_member_implementation(s, chat_id, user_id),
                session=session,
                operation_name="is_member",
            ),
        )

    def _get_chat_by_id_implementation(
        self, session: Session, chat_id: UUID
    ) -> Optional[Chat]:
        """Implementation of chat retrieval by ID."""
        return cast(
            Optional[Chat], session.query(Chat).filter(Chat.id == chat_id).one_or_none()
        )

    def get_chat_by_id(
        self, chat_id: UUID, session: Optional[Session] = None
    ) -> Optional[Chat]:
        """Get a chat by ID."""
        return cast(
            Optional[Chat],
            self._execute_with_session(
                lambda s: self._get_chat_by_id_implementation(s, chat_id),
                session=session,
                operation_name="get_chat_by_id",
            ),
        )

    def _get_chat_members_implementation(
        self, session: Session, chat_id: UUID
    ) -> List[Membership]:
        """Implementation of chat members retrieval."""
        return cast(
            List[Membership],
            (
                session.query(Membership)
                .filter(Membership.chat_id == chat_id)
                .order_by(Membership.joined_at.asc())
                .all()
            ),
        )

    def get_chat_members(
        self, chat_id: UUID, session: Optional[Session] = None
    ) -> List[Membership]:
        """Get all members of a chat."""
        return cast(
            List[Membership],
            self._execute_with_session(
                lambda s: self._get_chat_members_implementation(s, chat_id),
                session=session,
                operation_name="get_chat_members",
            ),
        )
