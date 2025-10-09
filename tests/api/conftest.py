"""API tests conftest.py - imports fixtures from repositories."""

# Import fixtures from repositories conftest
from tests.repositories.conftest import (
    sample_users,
    sample_dm,
    sample_group_chat,
    sample_messages,
    user_repo,
    chat_repo,
    message_repo,
    uuid_generator,
)

# Placeholder user removed - authentication now uses JWT tokens
