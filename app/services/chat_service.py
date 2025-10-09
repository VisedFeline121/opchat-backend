"""Chat service for business logic."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import MemberRole
from app.core.logging.logging import get_logger
from app.models.chat import Chat, DirectMessage, GroupChat
from app.models.membership import Membership
from app.repositories.chat_repo import ChatRepo
from app.repositories.user_repo import UserRepo

logger = get_logger(__name__)

# Business rules constants
MAX_GROUP_CHAT_MEMBERS = 100
MIN_GROUP_CHAT_MEMBERS = 2
MAX_GROUP_CHAT_TOPIC_LENGTH = 255


class ChatService:
    """Chat service for business logic."""

    def __init__(self, chat_repo: ChatRepo, user_repo: UserRepo):
        """Initialize the chat service."""
        self.chat_repo = chat_repo
        self.user_repo = user_repo

    def create_direct_message(
        self, user1_id: UUID, user2_id: UUID, session: Optional[Session] = None
    ) -> DirectMessage:
        """Create a direct message between two users."""
        logger.info(f"Creating DM between users {user1_id} and {user2_id}")

        # Business rule: Users cannot create DMs with themselves
        if user1_id == user2_id:
            raise ValueError("Cannot create direct message with yourself")

        # Validate users exist
        self.chat_repo.validate_users_exist([user1_id, user2_id], session=session)

        # Create the DM (repository handles duplicate detection)
        dm = self.chat_repo.create_direct_message(user1_id, user2_id, session=session)
        logger.info(f"Created DM: {dm.id}")
        return dm

    def create_group_chat(
        self,
        creator_id: UUID,
        topic: str,
        member_ids: List[UUID],
        session: Optional[Session] = None,
    ) -> GroupChat:
        """Create a group chat with members."""
        logger.info(f"Creating group chat '{topic}' by user {creator_id}")

        # Business rule: Topic cannot be empty or too long
        if not topic or not topic.strip():
            raise ValueError("Group chat topic cannot be empty")

        if len(topic.strip()) > MAX_GROUP_CHAT_TOPIC_LENGTH:
            raise ValueError(
                f"Group chat topic cannot exceed {MAX_GROUP_CHAT_TOPIC_LENGTH} characters"
            )

        # Business rule: Remove duplicates and ensure creator is included
        all_user_ids = set(member_ids)
        all_user_ids.add(creator_id)

        # Business rule: Group chat must have at least minimum members
        if len(all_user_ids) < MIN_GROUP_CHAT_MEMBERS:
            raise ValueError(
                f"Group chat must have at least {MIN_GROUP_CHAT_MEMBERS} members"
            )

        # Business rule: Group chat cannot exceed maximum members
        if len(all_user_ids) > MAX_GROUP_CHAT_MEMBERS:
            raise ValueError(
                f"Group chat cannot have more than {MAX_GROUP_CHAT_MEMBERS} members"
            )

        # Validate all users exist
        self.chat_repo.validate_users_exist(list(all_user_ids), session=session)

        # Create the group chat
        group = self.chat_repo.create_group_chat(
            creator_id, topic.strip(), member_ids, session=session
        )
        logger.info(f"Created group chat: {group.id} with {len(all_user_ids)} members")
        return group

    def get_user_chats(
        self, user_id: UUID, session: Optional[Session] = None
    ) -> List[Chat]:
        """Get all chats a user is a member of."""
        logger.debug(f"Getting chats for user {user_id}")
        return self.chat_repo.get_user_chats(user_id, session=session)

    def get_chat_by_id(
        self, chat_id: UUID, session: Optional[Session] = None
    ) -> Optional[Chat]:
        """Get a chat by ID."""
        logger.debug(f"Getting chat {chat_id}")
        return self.chat_repo.get_chat_by_id(chat_id, session=session)

    def get_chat_members(
        self, chat_id: UUID, session: Optional[Session] = None
    ) -> List[Membership]:
        """Get all members of a chat."""
        logger.debug(f"Getting members for chat {chat_id}")
        return self.chat_repo.get_chat_members(chat_id, session=session)

    def add_member_to_chat(
        self,
        chat_id: UUID,
        user_id: UUID,
        added_by_id: UUID,
        role: MemberRole = MemberRole.MEMBER,
        session: Optional[Session] = None,
    ) -> Membership:
        """Add a member to a chat."""
        logger.info(f"Adding user {user_id} to chat {chat_id} by user {added_by_id}")

        # Business rule: Users cannot add themselves
        if user_id == added_by_id:
            raise ValueError("Users cannot add themselves to a chat")

        # Validate chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError(f"Chat {chat_id} not found")

        # Business rule: Cannot add members to direct messages
        if self.chat_repo.is_direct_message(chat_id, session=session):
            raise ValueError("Cannot add members to direct messages")

        # Validate user exists
        self.chat_repo.validate_users_exist([user_id], session=session)

        # Check if user adding member is authorized
        if not self.chat_repo.is_member(chat_id, added_by_id, session=session):
            raise ValueError(f"User {added_by_id} is not a member of chat {chat_id}")

        # For group chats, check if user has admin rights
        if self.chat_repo.is_group_chat(chat_id, session=session):
            user_role = self.chat_repo.get_user_role_in_chat(
                chat_id, added_by_id, session=session
            )
            if user_role != MemberRole.ADMIN:
                raise ValueError(
                    f"User {added_by_id} does not have admin rights in chat {chat_id}"
                )

            # Business rule: Check group chat member limit
            current_members = self.chat_repo.get_chat_members(chat_id, session=session)
            if len(current_members) >= MAX_GROUP_CHAT_MEMBERS:
                raise ValueError(
                    f"Group chat cannot have more than {MAX_GROUP_CHAT_MEMBERS} members"
                )

        # Add the member
        membership = self.chat_repo.add_member(chat_id, user_id, role, session=session)
        logger.info(f"Added user {user_id} to chat {chat_id} with role {role}")
        return membership

    def remove_member_from_chat(
        self,
        chat_id: UUID,
        user_id: UUID,
        removed_by_id: UUID,
        session: Optional[Session] = None,
    ) -> None:
        """Remove a member from a chat."""
        logger.info(
            f"Removing user {user_id} from chat {chat_id} by user {removed_by_id}"
        )

        # Validate chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError(f"Chat {chat_id} not found")

        # Check if user removing member is authorized
        if not self.chat_repo.is_member(chat_id, removed_by_id, session=session):
            raise ValueError(f"User {removed_by_id} is not a member of chat {chat_id}")

        # Check if user being removed is a member
        if not self.chat_repo.is_member(chat_id, user_id, session=session):
            raise ValueError(f"User {user_id} is not a member of chat {chat_id}")

        # For group chats, check permissions and business rules
        if self.chat_repo.is_group_chat(chat_id, session=session):
            # Check if user being removed is the last admin (regardless of who's removing them)
            user_being_removed_role = self.chat_repo.get_user_role_in_chat(
                chat_id, user_id, session=session
            )
            if user_being_removed_role == MemberRole.ADMIN:
                # Count remaining admins
                all_members = self.chat_repo.get_chat_members(chat_id, session=session)
                admin_count = sum(1 for m in all_members if m.role == MemberRole.ADMIN)
                if admin_count <= 1:
                    raise ValueError("Cannot remove the last admin from a group chat")

            # Business rule: Only admins can remove other users (not themselves)
            if user_id != removed_by_id:
                user_role = self.chat_repo.get_user_role_in_chat(
                    chat_id, removed_by_id, session=session
                )
                if user_role != MemberRole.ADMIN:
                    raise ValueError(
                        f"User {removed_by_id} does not have admin rights in chat {chat_id}"
                    )

        # For direct messages, users can only remove themselves
        if self.chat_repo.is_direct_message(chat_id, session=session):
            if user_id != removed_by_id:
                raise ValueError(
                    "Users can only remove themselves from direct messages"
                )

        # Remove the member
        self.chat_repo.remove_member(chat_id, user_id, session=session)
        logger.info(f"Removed user {user_id} from chat {chat_id}")

    def is_user_member_of_chat(
        self, chat_id: UUID, user_id: UUID, session: Optional[Session] = None
    ) -> bool:
        """Check if a user is a member of a chat."""
        return self.chat_repo.is_member(chat_id, user_id, session=session)

    def get_user_role_in_chat(
        self, chat_id: UUID, user_id: UUID, session: Optional[Session] = None
    ) -> Optional[MemberRole]:
        """Get the role of a user in a chat."""
        return self.chat_repo.get_user_role_in_chat(chat_id, user_id, session=session)

    def promote_member_to_admin(
        self,
        chat_id: UUID,
        user_id: UUID,
        promoted_by_id: UUID,
        session: Optional[Session] = None,
    ) -> Membership:
        """Promote a member to admin in a group chat."""
        logger.info(
            f"Promoting user {user_id} to admin in chat {chat_id} by user {promoted_by_id}"
        )

        # Business rule: Only group chats can have admins
        if not self.chat_repo.is_group_chat(chat_id, session=session):
            raise ValueError("Only group chats can have admins")

        # Validate chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError(f"Chat {chat_id} not found")

        # Check if user promoting is authorized (must be admin)
        promoter_role = self.chat_repo.get_user_role_in_chat(
            chat_id, promoted_by_id, session=session
        )
        if promoter_role != MemberRole.ADMIN:
            raise ValueError(
                f"User {promoted_by_id} does not have admin rights in chat {chat_id}"
            )

        # Check if user being promoted is a member
        if not self.chat_repo.is_member(chat_id, user_id, session=session):
            raise ValueError(f"User {user_id} is not a member of chat {chat_id}")

        # Check if user is already an admin
        current_role = self.chat_repo.get_user_role_in_chat(
            chat_id, user_id, session=session
        )
        if current_role == MemberRole.ADMIN:
            raise ValueError(f"User {user_id} is already an admin in chat {chat_id}")

        # Promote the member
        membership = self.chat_repo.add_member(
            chat_id, user_id, MemberRole.ADMIN, session=session
        )
        logger.info(f"Promoted user {user_id} to admin in chat {chat_id}")
        return membership

    def demote_admin_to_member(
        self,
        chat_id: UUID,
        user_id: UUID,
        demoted_by_id: UUID,
        session: Optional[Session] = None,
    ) -> Membership:
        """Demote an admin to member in a group chat."""
        logger.info(
            f"Demoting user {user_id} from admin in chat {chat_id} by user {demoted_by_id}"
        )

        # Business rule: Only group chats can have admins
        if not self.chat_repo.is_group_chat(chat_id, session=session):
            raise ValueError("Only group chats can have admins")

        # Validate chat exists
        chat = self.chat_repo.get_chat_by_id(chat_id, session=session)
        if not chat:
            raise ValueError(f"Chat {chat_id} not found")

        # Check if user demoting is authorized (must be admin)
        demoter_role = self.chat_repo.get_user_role_in_chat(
            chat_id, demoted_by_id, session=session
        )
        if demoter_role != MemberRole.ADMIN:
            raise ValueError(
                f"User {demoted_by_id} does not have admin rights in chat {chat_id}"
            )

        # Check if user being demoted is a member
        if not self.chat_repo.is_member(chat_id, user_id, session=session):
            raise ValueError(f"User {user_id} is not a member of chat {chat_id}")

        # Check if user is actually an admin
        current_role = self.chat_repo.get_user_role_in_chat(
            chat_id, user_id, session=session
        )
        if current_role != MemberRole.ADMIN:
            raise ValueError(f"User {user_id} is not an admin in chat {chat_id}")

        # Business rule: Prevent demoting the last admin
        all_members = self.chat_repo.get_chat_members(chat_id, session=session)
        admin_count = sum(1 for m in all_members if m.role == MemberRole.ADMIN)
        if admin_count <= 1:
            raise ValueError("Cannot demote the last admin from a group chat")

        # Demote the admin
        membership = self.chat_repo.add_member(
            chat_id, user_id, MemberRole.MEMBER, session=session
        )
        logger.info(f"Demoted user {user_id} from admin in chat {chat_id}")
        return membership

    def get_chat_owner(
        self, chat_id: UUID, session: Optional[Session] = None
    ) -> Optional[UUID]:
        """Get the owner/creator of a chat."""
        if self.chat_repo.is_direct_message(chat_id, session=session):
            # For DMs, there's no single owner - both users are equal
            return None

        # For group chats, find the creator (first admin by creation time)
        members = self.chat_repo.get_chat_members(chat_id, session=session)
        admin_members = [m for m in members if m.role == MemberRole.ADMIN]
        if admin_members:
            # Return the admin who joined first (creator)
            return min(admin_members, key=lambda m: m.joined_at).user_id  # type: ignore[arg-type,return-value]

        return None

    def is_user_chat_owner(
        self, chat_id: UUID, user_id: UUID, session: Optional[Session] = None
    ) -> bool:
        """Check if a user is the owner/creator of a chat."""
        owner_id = self.get_chat_owner(chat_id, session=session)
        return owner_id == user_id if owner_id else False
