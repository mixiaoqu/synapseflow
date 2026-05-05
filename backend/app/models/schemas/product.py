"""Product schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=120)
    team_id: int = Field(..., gt=0)
    description: str | None = None
    is_active: bool = True


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str | None = None
    code: str
    name: str
    description: str | None = None
    is_active: bool
    project_count: int = 0
    created_at: datetime
    updated_at: datetime
