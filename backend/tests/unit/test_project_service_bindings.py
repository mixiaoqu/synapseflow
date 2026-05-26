import pytest
from pydantic import ValidationError

from app.models.schemas.project import ProjectAppCreate


def test_project_app_create_schema_accepts_single_knowledge_base_id():
    payload = ProjectAppCreate(
        code="app-a",
        name="应用A",
        knowledge_base_id=11,
    )

    assert payload.knowledge_base_id == 11


def test_project_app_create_schema_requires_knowledge_base_id():
    with pytest.raises(ValidationError):
        ProjectAppCreate(
            code="app-a",
            name="应用A",
        )
