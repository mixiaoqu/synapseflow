"""Team-related schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    """Create team request."""

    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    code: str | None = Field(default=None, max_length=50, description="团队编码")
    description: str | None = Field(default=None, description="团队描述")


class TeamUpdate(BaseModel):
    """Update team request."""

    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    code: str | None = Field(default=None, max_length=50, description="团队编码")
    description: str | None = Field(default=None, description="团队描述")


class TeamResponse(BaseModel):
    """Team response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime

class TeamMemberCreate(BaseModel):
    """Create team member request."""

    user_id: int = Field(..., description="用户 ID")
    role: str = Field(default="member", description="团队角色")


class TeamMemberUpdate(BaseModel):
    """Update team member request."""

    role: str = Field(..., description="团队角色")


class TeamMemberResponse(BaseModel):
    """Team member response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    role: str
    created_at: datetime
    updated_at: datetime
