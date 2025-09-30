"""Authentication API endpoints."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.auth_utils import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from app.core.config import settings
from app.core.rate_limiter import rate_limiter
from app.db.db import get_db
from app.dependencies import get_user_repo
from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepo
from app.schemas.auth import (
    LoginRequest,
    Token,
    TokenRefresh,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: UserCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_repo: Annotated[UserRepo, Depends(get_user_repo)],
):
    """Create a new user account."""

    # Check rate limit for signup
    if not await rate_limiter.check_ip_rate_limit(
        request,
        "signup",
        settings.SIGNUP_RATE_LIMIT_PER_MINUTE,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again later.",
        )

    # Check if username already exists
    existing_user = user_repo.get_by_username(user_data.username, session=db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        )

    # Create new user
    password_hash = get_password_hash(user_data.password)
    user = user_repo.create_user(
        username=user_data.username, password_hash=password_hash, session=db
    )
    db.commit()

    # Create tokens
    access_token = create_access_token(UUID(str(user.id)))
    refresh_token = create_refresh_token(UUID(str(user.id)))

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_repo: Annotated[UserRepo, Depends(get_user_repo)],
):
    """Authenticate user and return tokens."""

    # Check rate limit for login
    if not await rate_limiter.check_ip_rate_limit(
        request,
        "login",
        settings.AUTH_RATE_LIMIT_PER_MINUTE,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    # Get user by username
    user = user_repo.get_by_username(login_data.username, session=db)
    if not user or not verify_password(login_data.password, str(user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Update last login time
    user.last_login_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    db.commit()

    # Create tokens
    access_token = create_access_token(UUID(str(user.id)))
    refresh_token = create_refresh_token(UUID(str(user.id)))

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


@router.post("/logout")
async def logout(current_user: Annotated[User, Depends(get_current_active_user)]):
    """Logout user (invalidate tokens)."""
    # For JWT tokens, we can't invalidate them server-side without a blacklist
    # In a production system, you'd want to implement token blacklisting
    # For now, we just return success - tokens will expire naturally
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: TokenRefresh,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_repo: Annotated[UserRepo, Depends(get_user_repo)],
):
    """Refresh access token using refresh token."""

    # Check rate limit for refresh
    if not await rate_limiter.check_ip_rate_limit(
        request,
        "refresh",
        settings.REFRESH_RATE_LIMIT_PER_MINUTE,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Please try again later.",
        )

    try:
        # Validate refresh token
        payload = jwt.decode(
            refresh_data.refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Check if user still exists and is active
        user = user_repo.get_user_by_id(user_id, session=db)
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Create new tokens
        access_token = create_access_token(UUID(str(user.id)))
        new_refresh_token = create_refresh_token(UUID(str(user.id)))

        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from None


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get current user's profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    user_repo: Annotated[UserRepo, Depends(get_user_repo)],
):
    """Update current user's profile."""

    # Check if new username is already taken (if username is being updated)
    if user_update.username and user_update.username != current_user.username:
        existing_user = user_repo.get_by_username(user_update.username, session=db)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
            )
        current_user.username = user_update.username  # type: ignore[assignment]

    # Update password if provided
    if user_update.password:
        current_user.password_hash = get_password_hash(user_update.password)  # type: ignore[assignment]

    db.commit()
    db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.delete("/me")
async def delete_current_user_account(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete current user's account."""
    # In a production system, you might want to:
    # 1. Soft delete (mark as deleted instead of hard delete)
    # 2. Anonymize data instead of deleting
    # 3. Add confirmation step

    db.delete(current_user)
    db.commit()

    return {"message": "Account successfully deleted"}
