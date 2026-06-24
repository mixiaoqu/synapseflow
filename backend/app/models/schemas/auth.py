"""Authentication and user-related schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    """Register request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserLogin(BaseModel):
    """Login request."""

    username_or_email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Public user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Bearer token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
