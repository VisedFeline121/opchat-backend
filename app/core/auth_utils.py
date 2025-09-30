"""Authentication utilities for OpChat."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.db import get_db
from app.dependencies import get_user_repo
from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepo

# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# OAuth2 scheme for token handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# JWT settings
JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenData(BaseModel):
    """Data embedded in JWT token."""

    user_id: UUID
    exp: datetime

    def model_dump(self, **kwargs):
        """Override model_dump to serialize UUID as string and datetime as timestamp."""
        data = super().model_dump(**kwargs)
        data["user_id"] = str(data["user_id"])
        # Convert timezone-aware datetime to timestamp for JWT
        if isinstance(data["exp"], datetime):
            data["exp"] = int(data["exp"].timestamp())
        return data

    @classmethod
    def from_payload(cls, payload: dict):
        """Create TokenData from JWT payload, converting timestamp back to datetime."""
        data = payload.copy()
        # Convert timestamp back to timezone-aware datetime
        if "exp" in data and isinstance(data["exp"], (int, float)):
            data["exp"] = datetime.fromtimestamp(data["exp"], tz=timezone.utc)
        return cls(**data)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    result = pwd_context.verify(plain_password, hashed_password)
    return bool(result)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    result = pwd_context.hash(password)
    return str(result)


def create_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = TokenData(user_id=user_id, exp=expire).model_dump()
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return str(encoded_jwt)


def create_access_token(user_id: UUID) -> str:
    """Create a new access token."""
    return create_token(user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: UUID) -> str:
    """Create a new refresh token."""
    return create_token(user_id, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepo = Depends(get_user_repo),
    db: Session = Depends(get_db),
) -> User:
    """Dependency to get current authenticated user from token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_data = TokenData.from_payload(payload)

        if datetime.now(timezone.utc) > token_data.exp:
            raise credentials_exception

    except JWTError:
        raise credentials_exception from None

    user = user_repo.get_user_by_id(token_data.user_id, session=db)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to get current active user."""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user
