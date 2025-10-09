"""Message API endpoints."""

from datetime import datetime
from typing import Annotated, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas.message import (
    MessageHistoryResponse,
    MessageResponse,
    MessageSentResponse,
    SenderResponse,
    SendMessageRequest,
)
from app.core.auth.auth_utils import get_current_active_user
from app.db.db import get_db
from app.dependencies import get_message_service
from app.models.message import Message
from app.models.user import User
from app.services.message_service import MessageService

router = APIRouter(prefix="/chats", tags=["messages"])


def _message_to_response(message: Message) -> MessageResponse:
    """Convert Message model to MessageResponse."""
    return MessageResponse(
        id=message.id,  # type: ignore[arg-type]
        chat_id=message.chat_id,  # type: ignore[arg-type]
        sender_id=message.sender_id,  # type: ignore[arg-type]
        content=message.content,  # type: ignore[arg-type]
        created_at=message.created_at,  # type: ignore[arg-type]
        sender=SenderResponse(
            id=message.sender.id,  # type: ignore[arg-type]
            username=message.sender.username,  # type: ignore[arg-type]
        ),
    )


@router.post(
    "/{chat_id}/messages",
    response_model=MessageSentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to a chat",
    description="Send a new message to the specified chat. Requires membership in the chat.",
)
async def send_message(
    chat_id: UUID,
    request: SendMessageRequest,
    message_service: Annotated[MessageService, Depends(get_message_service)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MessageSentResponse:
    """Send a message to a chat."""
    try:
        message = message_service.send_message(
            chat_id=chat_id,
            sender_id=cast(UUID, current_user.id),
            content=request.content,
            idempotency_key=request.idempotency_key,
            session=db,
        )

        return MessageSentResponse(
            message=_message_to_response(message),
            idempotency_key=request.idempotency_key,
        )

    except ValueError as e:
        if "not a member" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this chat",
            ) from e
        elif "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found",
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get(
    "/{chat_id}/messages",
    response_model=MessageHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chat message history",
    description="Retrieve message history for a chat with pagination support.",
)
async def get_chat_messages(
    chat_id: UUID,
    message_service: Annotated[MessageService, Depends(get_message_service)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(50, ge=1, le=100, description="Number of messages to retrieve"),
    after_timestamp: Optional[datetime] = Query(
        None, description="Get messages after this timestamp (cursor-based pagination)"
    ),
    before_timestamp: Optional[datetime] = Query(
        None, description="Get messages before this timestamp (backward pagination)"
    ),
) -> MessageHistoryResponse:
    """Get chat message history with pagination."""
    try:
        # Validate request parameters
        if after_timestamp and before_timestamp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot specify both after_timestamp and before_timestamp",
            )

        # Get messages based on pagination type
        if before_timestamp:
            messages = message_service.get_chat_history_before(
                chat_id=chat_id,
                user_id=cast(UUID, current_user.id),
                before_timestamp=before_timestamp,
                limit=limit,
                session=db,
            )
        else:
            messages = message_service.get_chat_history(
                chat_id=chat_id,
                user_id=cast(UUID, current_user.id),
                after_timestamp=after_timestamp,
                limit=limit,
                session=db,
            )

        # Convert to response format
        message_responses = [_message_to_response(msg) for msg in messages]

        # Determine pagination info
        has_more = len(messages) == limit
        next_cursor = None
        prev_cursor = None

        if has_more and messages:
            if before_timestamp:
                # For backward pagination, next cursor is the oldest message timestamp
                prev_cursor = cast(datetime, messages[-1].created_at)
            else:
                # For forward pagination, next cursor is the newest message timestamp
                next_cursor = cast(datetime, messages[-1].created_at)

        # TODO: Get actual total count from database for accurate total
        # For now, we'll estimate based on whether we got a full page
        total = len(messages) + (1 if has_more else 0)

        return MessageHistoryResponse(
            messages=message_responses,
            total=total,
            has_more=has_more,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
        )

    except ValueError as e:
        if "not a member" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this chat",
            ) from e
        elif "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found",
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get(
    "/{chat_id}/messages/{message_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific message",
    description="Retrieve a specific message by ID. Requires membership in the chat.",
)
async def get_message(
    chat_id: UUID,
    message_id: UUID,
    message_service: Annotated[MessageService, Depends(get_message_service)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> MessageResponse:
    """Get a specific message by ID."""
    try:
        message = message_service.get_message_by_id(
            message_id=message_id,
            user_id=cast(UUID, current_user.id),
            session=db,
        )

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        return _message_to_response(message)

    except ValueError as e:
        if "not a member" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this chat",
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
