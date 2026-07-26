"""Project and project-application schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectAppTerminalType = Literal["web", "h5", "mini_program", "admin", "api", "other"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProjectUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProjectCopy(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    is_active: bool = False


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    product_id: int
    product_code: str | None = None
    product_name: str | None = None
    code: str
    name: str
    description: str | None = None
    is_active: bool
    app_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class ProjectBulkActionRequest(BaseModel):
    project_ids: list[int] = Field(default_factory=list, min_length=1)
    action: Literal["enable", "disable", "delete"]


class ProjectBulkActionResponse(BaseModel):
    action: Literal["enable", "disable", "delete"]
    affected_ids: list[int] = Field(default_factory=list)
    affected_count: int = 0


class ProjectAppCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    knowledge_base_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    default_assistant_id: int | None = Field(default=None, gt=0)
    widget_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    terminal_type: ProjectAppTerminalType = "web"
    is_active: bool = True


class ProjectAppUpdate(BaseModel):
    code: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    knowledge_base_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    default_assistant_id: int | None = Field(default=None, gt=0)
    widget_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    terminal_type: ProjectAppTerminalType = "web"
    is_active: bool = True


class ProjectAppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    code: str
    name: str
    description: str | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    default_assistant_id: int | None = None
    default_assistant_name: str | None = None
    widget_version: str
    terminal_type: ProjectAppTerminalType = "web"
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectAppListResponse(BaseModel):
    items: list[ProjectAppResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class ProjectAppBulkActionRequest(BaseModel):
    app_ids: list[int] = Field(default_factory=list, min_length=1)
    action: Literal["enable", "disable", "delete"]


class ProjectAppBulkActionResponse(BaseModel):
    action: Literal["enable", "disable", "delete"]
    affected_ids: list[int] = Field(default_factory=list)
    affected_count: int = 0
