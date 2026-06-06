"""Team-related schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TeamRole = Literal["owner", "admin", "member"]
TeamBulkAction = Literal["delete"]


class TeamCreate(BaseModel):
    """Create team request."""

    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    code: str | None = Field(default=None, max_length=50, description="团队编码")
    description: str | None = Field(default=None, description="团队描述")
    member_ids: list[int] = Field(default_factory=list, description="创建时批量绑定的成员用户 ID 列表")


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


class TeamListResponse(BaseModel):
    """Paginated team list response."""

    items: list[TeamResponse]
    total: int
    page: int
    page_size: int


class TeamBulkActionRequest(BaseModel):
    """Bulk operation request for teams."""

    team_ids: list[int] = Field(..., min_length=1, description="团队 ID 列表")
    action: TeamBulkAction = Field(..., description="批量操作类型")


class TeamBulkActionResponse(BaseModel):
    """Bulk operation result for teams."""

    affected: int

class TeamMemberCreate(BaseModel):
    """Create team member request."""

    user_id: int = Field(..., description="用户 ID")
    role: TeamRole = Field(default="member", description="团队角色")


class TeamMemberUpdate(BaseModel):
    """Update team member request."""

    role: TeamRole = Field(..., description="团队角色")


class TeamMemberBulkRoleUpdate(BaseModel):
    """Bulk update team member roles request."""

    user_ids: list[int] = Field(..., min_length=1, description="用户 ID 列表")
    role: TeamRole = Field(..., description="团队角色")


class TeamMemberBulkDelete(BaseModel):
    """Bulk remove team members request."""

    user_ids: list[int] = Field(..., min_length=1, description="用户 ID 列表")


class TeamMemberResponse(BaseModel):
    """Team member response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    role: str
    created_at: datetime
    updated_at: datetime
