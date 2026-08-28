"""Admin-facing user management schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminUserCreate(BaseModel):
    """Create user request for admin tools."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    role: str = Field(..., min_length=3, max_length=30)
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    """Partial admin update for a user."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    role: str | None = Field(default=None, min_length=3, max_length=30)
    is_active: bool | None = None


class AdminUserResponse(BaseModel):
    """Admin-facing user summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    team_names: list[str] = Field(default_factory=list)
    team_count: int = 0
    team_memberships: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AdminUserBulkAction(BaseModel):
    """Batch action request for admin user management."""

    user_ids: list[int] = Field(..., min_length=1)
    action: Literal["enable", "disable", "delete"]


class UserListResponse(BaseModel):
    """Paginated user list response."""

    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int
