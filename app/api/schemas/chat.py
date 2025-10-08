"""Chat API request/response schemas."""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import MemberRole


# Enums
class ChatType(str, Enum):
    """Chat type enumeration."""

    DM = "dm"
    GROUP = "group"


# Base Models
class UserBase(BaseModel):
    """Base user information."""

    id: uuid.UUID
    username: str


class MembershipBase(BaseModel):
    """Base membership information."""

    user_id: uuid.UUID
    role: MemberRole
    joined_at: datetime


class ChatBase(BaseModel):
    """Base chat information."""

    id: uuid.UUID
    type: ChatType
    created_at: datetime


# Request Models
class CreateChatRequest(BaseModel):
    """Request model for creating a new chat."""

    type: ChatType = Field(..., description="Type of chat: 'dm' or 'group'")
    participant_ids: List[uuid.UUID] = Field(
        ..., min_length=1, description="List of participant user IDs"
    )
    topic: Optional[str] = Field(
        None,
        max_length=255,
        description="Topic for group chats (required for group chats)",
    )

    @field_validator("participant_ids")
    @classmethod
    def validate_participant_ids(cls, v, info):
        """Validate participant IDs based on chat type."""
        if info.data and "type" in info.data:
            chat_type = info.data["type"]
            if chat_type == ChatType.DM and len(v) != 2:
                raise ValueError("Direct messages must have exactly 2 participants")
            elif chat_type == ChatType.GROUP and len(v) < 2:
                raise ValueError("Group chats must have at least 2 participants")
        return v

    @model_validator(mode="after")
    def validate_topic_for_group(self):
        """Validate topic is provided for group chats."""
        if self.type == ChatType.GROUP and not self.topic:
            raise ValueError("Group chats must have a topic")
        return self


class AddMemberRequest(BaseModel):
    """Request model for adding a member to a group chat."""

    user_id: uuid.UUID = Field(..., description="User ID to add to the chat")
    role: MemberRole = Field(MemberRole.MEMBER, description="Role for the new member")


# Response Models
class UserResponse(UserBase):
    """User information in API responses."""

    pass


class MembershipResponse(MembershipBase):
    """Membership information in API responses."""

    user: UserResponse


class DirectMessageResponse(ChatBase):
    """Direct message chat response."""

    type: Literal[ChatType.DM] = ChatType.DM
    dm_key: str = Field(..., description="Unique key for the DM pair")
    members: List[MembershipResponse] = Field(..., description="Chat members")


class GroupChatResponse(ChatBase):
    """Group chat response."""

    type: Literal[ChatType.GROUP] = ChatType.GROUP
    topic: str = Field(..., description="Group chat topic")
    members: List[MembershipResponse] = Field(..., description="Chat members")


class ChatResponse(BaseModel):
    """Generic chat response that can be either DM or group."""

    id: uuid.UUID
    type: ChatType
    created_at: datetime
    members: List[MembershipResponse]

    # Optional fields based on type
    dm_key: Optional[str] = None
    topic: Optional[str] = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ChatListResponse(BaseModel):
    """Response model for listing user chats."""

    chats: List[ChatResponse] = Field(..., description="List of user's chats")
    total: int = Field(..., description="Total number of chats")


class ChatMembersResponse(BaseModel):
    """Response model for listing chat members."""

    members: List[MembershipResponse] = Field(..., description="List of chat members")
    total: int = Field(..., description="Total number of members")


# Error Models
class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: dict = Field(..., description="Error details")

    class Config:
        """Example error response."""

        json_schema_extra = {
            "example": {
                "error": {
                    "code": "CHAT_NOT_FOUND",
                    "message": "Chat with the specified ID was not found",
                }
            }
        }


# Success Models
class SuccessResponse(BaseModel):
    """Standard success response format."""

    message: str = Field(..., description="Success message")
    data: Optional[dict] = Field(None, description="Additional response data")


class ChatCreatedResponse(SuccessResponse):
    """Response for successful chat creation."""

    data: ChatResponse = Field(..., description="Created chat information")


class MemberAddedResponse(SuccessResponse):
    """Response for successful member addition."""

    data: MembershipResponse = Field(..., description="Added member information")
