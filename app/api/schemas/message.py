"""Message API request/response schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# Base Models
class MessageBase(BaseModel):
    """Base message information."""

    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    created_at: datetime


class SenderBase(BaseModel):
    """Base sender information."""

    id: uuid.UUID
    username: str


# Request Models
class SendMessageRequest(BaseModel):
    """Request model for sending a new message."""

    content: str = Field(
        ..., min_length=1, max_length=4000, description="Message content"
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional idempotency key to prevent duplicate messages",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        """Validate message content."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty or only whitespace")
        return v.strip()


class GetMessageHistoryRequest(BaseModel):
    """Request model for getting message history."""

    limit: int = Field(
        50, ge=1, le=100, description="Number of messages to retrieve (1-100)"
    )
    after_timestamp: Optional[datetime] = Field(
        None, description="Get messages after this timestamp (cursor-based pagination)"
    )
    before_timestamp: Optional[datetime] = Field(
        None, description="Get messages before this timestamp (backward pagination)"
    )

    @field_validator("after_timestamp", "before_timestamp")
    @classmethod
    def validate_timestamps(cls, v):
        """Validate timestamp is not in the future."""
        if v and v > datetime.now(datetime.timezone.utc):
            raise ValueError("Timestamp cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_timestamp_combination(self):
        """Validate that after_timestamp and before_timestamp are not both provided."""
        if self.after_timestamp and self.before_timestamp:
            raise ValueError("Cannot specify both after_timestamp and before_timestamp")
        return self


# Response Models
class SenderResponse(SenderBase):
    """Sender information in API responses."""

    pass


class MessageResponse(MessageBase):
    """Message information in API responses."""

    sender: SenderResponse = Field(..., description="Message sender information")


class MessageHistoryResponse(BaseModel):
    """Response model for message history."""

    messages: List[MessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages in the chat")
    has_more: bool = Field(..., description="Whether there are more messages available")
    next_cursor: Optional[datetime] = Field(
        None, description="Timestamp for next page (if has_more is true)"
    )
    prev_cursor: Optional[datetime] = Field(
        None, description="Timestamp for previous page (if available)"
    )


class MessageSentResponse(BaseModel):
    """Response model for successful message sending."""

    message: MessageResponse = Field(..., description="The sent message")
    idempotency_key: Optional[str] = Field(
        None, description="Idempotency key used (if provided)"
    )


# Error Models
class MessageErrorResponse(BaseModel):
    """Standard error response format for message operations."""

    error: dict = Field(..., description="Error details")

    class Config:
        """Example error response."""

        json_schema_extra = {
            "example": {
                "error": {
                    "code": "MESSAGE_NOT_FOUND",
                    "message": "Message with the specified ID was not found",
                }
            }
        }


# Success Models
class MessageSuccessResponse(BaseModel):
    """Standard success response format for message operations."""

    message: str = Field(..., description="Success message")
    data: Optional[dict] = Field(None, description="Additional response data")
