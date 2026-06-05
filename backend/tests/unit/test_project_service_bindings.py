import pytest
from pydantic import ValidationError

from app.models.schemas.project import ProjectAppCopy, ProjectAppCreate


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


def test_project_app_copy_schema_accepts_new_identity_and_inactive_default():
    payload = ProjectAppCopy(
        code="app-a-copy",
        name="应用A 副本",
    )

    assert payload.code == "app-a-copy"
    assert payload.name == "应用A 副本"
    assert payload.is_active is False
