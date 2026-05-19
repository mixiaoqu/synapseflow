from app.models.schemas.project import ProjectAppCreate


def test_project_app_create_schema_accepts_direct_knowledge_base_bindings():
    payload = ProjectAppCreate(
        code="app-a",
        name="应用A",
        bindings=[
            {
                "knowledge_base_id": 11,
            }
        ],
    )

    assert payload.bindings[0].knowledge_base_id == 11
