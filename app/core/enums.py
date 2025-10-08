"""Shared enums used across the application."""

from enum import Enum


class MemberRole(str, Enum):
    """Member role enumeration."""

    MEMBER = "member"
    ADMIN = "admin"
