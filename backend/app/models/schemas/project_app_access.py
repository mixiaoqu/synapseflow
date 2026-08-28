"""Schemas for project application server-to-server credentials."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectAppAccessCreate(BaseModel):
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)


class ProjectAppAccessUpdate(BaseModel):
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)


class ProjectAppAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_app_id: int
    client_id: str
    client_secret_last_four: str
    allowed_origins: list[str] = Field(default_factory=list)
    token_version: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ProjectAppAccessIssuedResponse(ProjectAppAccessResponse):
    client_secret: str
