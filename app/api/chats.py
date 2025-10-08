"""Chat Management API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.chat import (
    AddMemberRequest,
    ChatCreatedResponse,
    ChatListResponse,
    ChatMembersResponse,
    ChatResponse,
    ChatType,
    CreateChatRequest,
    MemberAddedResponse,
    MembershipResponse,
    SuccessResponse,
    UserResponse,
)
from app.db.db import get_db
from app.dependencies import get_chat_service
from app.models.chat import Chat, DirectMessage, GroupChat
from app.models.membership import Membership
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


def _membership_to_response(membership: Membership) -> MembershipResponse:
    """Convert Membership model to MembershipResponse."""
    return MembershipResponse(
        user_id=membership.user_id,  # type: ignore[arg-type]
        role=membership.role.value,
        joined_at=membership.joined_at,  # type: ignore[arg-type]
        user=UserResponse(
            id=membership.user.id,  # type: ignore[arg-type]
            username=membership.user.username,  # type: ignore[arg-type]
        ),
    )


def _chat_to_response(chat: Chat) -> ChatResponse:
    """Convert Chat model to ChatResponse."""
    members = [_membership_to_response(m) for m in chat.memberships]

    response_data = {
        "id": chat.id,  # type: ignore[arg-type]
        "type": ChatType(chat.type),
        "created_at": chat.created_at,  # type: ignore[arg-type]
        "members": members,
    }

    # Add type-specific fields
    if isinstance(chat, DirectMessage):
        response_data["dm_key"] = chat.dm_key  # type: ignore[arg-type]
    elif isinstance(chat, GroupChat):
        response_data["topic"] = chat.topic  # type: ignore[arg-type]

    return ChatResponse(**response_data)  # type: ignore[arg-type]


@router.get("/", response_model=ChatListResponse)
async def list_user_chats(
    db: Annotated[Session, Depends(get_db)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user)
):
    """List all chats for the current user."""
    # TODO: Replace with actual user ID from authentication
    current_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

    try:
        chats = chat_service.get_user_chats(current_user_id, session=db)
        chat_responses = [_chat_to_response(chat) for chat in chats]

        return ChatListResponse(chats=chat_responses, total=len(chat_responses))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user chats: {str(e)}",
        ) from e


@router.post(
    "/", response_model=ChatCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def create_chat(
    request: CreateChatRequest,
    db: Annotated[Session, Depends(get_db)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user)
):
    """Create a new chat (DM or group)."""
    # TODO: Replace with actual user ID from authentication
    current_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

    try:
        if request.type == ChatType.DM:
            # Create direct message
            if len(request.participant_ids) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Direct messages must have exactly 2 participants",
                )

            # Find the other participant (not the current user)
            other_user_id = next(
                uid for uid in request.participant_ids if uid != current_user_id
            )

            chat = chat_service.create_direct_message(
                current_user_id, other_user_id, session=db
            )
        else:
            # Create group chat
            # Topic is guaranteed to be non-None for group chats due to validation
            assert request.topic is not None
            chat = chat_service.create_group_chat(
                current_user_id, request.topic, request.participant_ids, session=db
            )

        chat_response = _chat_to_response(chat)
        return ChatCreatedResponse(
            message="Chat created successfully",
            data=chat_response,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat: {str(e)}",
        ) from e


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat_details(
    chat_id: str,
    db: Annotated[Session, Depends(get_db)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user)
):
    """Get details of a specific chat."""
    # TODO: Replace with actual user ID from authentication
    current_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

    try:
        chat_uuid = UUID(chat_id)
        chat = chat_service.get_chat_by_id(chat_uuid, session=db)

        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found",
            )

        # Check if user is a member
        if not chat_service.is_user_member_of_chat(
            chat_uuid, current_user_id, session=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this chat",
            )

        return _chat_to_response(chat)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid chat ID format: {str(e)}",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat details: {str(e)}",
        ) from e


@router.get("/{chat_id}/members", response_model=ChatMembersResponse)
async def list_chat_members(
    chat_id: str,
    db: Annotated[Session, Depends(get_db)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user)
):
    """List members of a specific chat."""
    # TODO: Replace with actual user ID from authentication
    current_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

    try:
        chat_uuid = UUID(chat_id)

        # Check if user is a member
        if not chat_service.is_user_member_of_chat(
            chat_uuid, current_user_id, session=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this chat",
            )

        members = chat_service.get_chat_members(chat_uuid, session=db)
        member_responses = [_membership_to_response(m) for m in members]

        return ChatMembersResponse(
            members=member_responses, total=len(member_responses)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid chat ID format: {str(e)}",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat members: {str(e)}",
        ) from e


@router.post(
    "/{chat_id}/members",
    response_model=MemberAddedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    chat_id: str,
    request: AddMemberRequest,
    db: Annotated[Session, Depends(get_db)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user)
):
    """Add a member to a group chat."""
    # TODO: Replace with actual user ID from authentication
    current_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

    try:
        chat_uuid = UUID(chat_id)
        membership = chat_service.add_member_to_chat(
            chat_uuid, request.user_id, current_user_id, request.role, session=db
        )

        membership_response = _membership_to_response(membership)
        return MemberAddedResponse(
            message="Member added successfully",
            data=membership_response,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add member: {str(e)}",
        ) from e


@router.delete("/{chat_id}/members/{user_id}", response_model=SuccessResponse)
async def remove_member(
    chat_id: str,
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user)
):
    """Remove a member from a group chat."""
    # TODO: Replace with actual user ID from authentication
    current_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

    try:
        chat_uuid = UUID(chat_id)
        user_uuid = UUID(user_id)

        chat_service.remove_member_from_chat(
            chat_uuid, user_uuid, current_user_id, session=db
        )

        return SuccessResponse(message="Member removed successfully", data=None)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove member: {str(e)}",
        ) from e
