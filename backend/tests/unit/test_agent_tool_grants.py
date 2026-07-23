from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.application.agent_tool_catalog_service import AgentToolCatalogService
from app.db.models import AgentTool, ToolProvider
from app.models.schemas.tool_provider import AgentToolGrantReplace
from app.repositories.agent_tool_repository import AgentToolRecord


class FakeGrantRepository:
    def __init__(self, records: list[AgentToolRecord]) -> None:
        self.records = records
        self.replaced_with: list[int] | None = None

    async def get_project_app(self, **kwargs):
        return SimpleNamespace(id=11)

    async def get_project_app_team_id(self, **kwargs):
        return 7

    async def get_tool_records_by_ids(self, tool_ids: list[int]):
        requested = set(tool_ids)
        return [record for record in self.records if record.tool.id in requested]

    async def replace_grants(self, *, project_app_id: int, agent_tool_ids: list[int]):
        assert project_app_id == 11
        self.replaced_with = agent_tool_ids

    async def list_grants(self, *, project_app_id: int):
        assert project_app_id == 11
        return []


def _tool_record(
    tool_id: int,
    *,
    team_id: int = 7,
    publish_status: str = "published",
    sync_status: str = "active",
    schema_hash: str = "schema",
    approved_schema_hash: str | None = "schema",
    provider_enabled: bool = True,
) -> AgentToolRecord:
    provider = ToolProvider(id=tool_id, team_id=team_id, code=f"provider_{tool_id}", enabled=provider_enabled)
    tool = AgentTool(
        id=tool_id,
        provider_id=provider.id,
        team_id=team_id,
        external_name=f"tool_{tool_id}",
        external_display_name=f"工具 {tool_id}",
        schema_hash=schema_hash,
        approved_schema_hash=approved_schema_hash,
        sync_status=sync_status,
        publish_status=publish_status,
        tool_key=f"provider_{tool_id}_tool_{tool_id}",
        name=f"工具 {tool_id}",
    )
    return AgentToolRecord(tool=tool, provider=provider, team_name="测试团队")


def _service(records: list[AgentToolRecord]):
    service = AgentToolCatalogService.__new__(AgentToolCatalogService)
    service.repository = FakeGrantRepository(records)
    return service


def test_replace_grant_payload_rejects_non_positive_tool_ids():
    with pytest.raises(ValidationError):
        AgentToolGrantReplace(agent_tool_ids=[1, 0, -2])


@pytest.mark.asyncio
async def test_replace_grants_deduplicates_ids_before_atomic_replace():
    service = _service([_tool_record(1), _tool_record(2)])

    response = await service.replace_grants(
        project_id=3,
        app_id=5,
        payload=SimpleNamespace(agent_tool_ids=[2, 1, 2]),
    )

    assert service.repository.replaced_with == [1, 2]
    assert response.items == []


@pytest.mark.asyncio
async def test_replace_grants_accepts_empty_selection():
    service = _service([])

    await service.replace_grants(
        project_id=3,
        app_id=5,
        payload=SimpleNamespace(agent_tool_ids=[]),
    )

    assert service.repository.replaced_with == []


@pytest.mark.asyncio
async def test_replace_grants_rejects_tools_from_another_team():
    service = _service([_tool_record(1, team_id=8)])

    with pytest.raises(HTTPException, match="当前团队") as exc_info:
        await service.replace_grants(
            project_id=3,
            app_id=5,
            payload=SimpleNamespace(agent_tool_ids=[1]),
        )

    assert exc_info.value.status_code == 400
    assert service.repository.replaced_with is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record", "expected_message"),
    [
        (_tool_record(1, publish_status="draft"), "未发布"),
        (_tool_record(1, sync_status="removed"), "同步状态正常"),
        (_tool_record(1, approved_schema_hash="old-schema"), "Schema"),
        (_tool_record(1, provider_enabled=False), "提供方"),
    ],
)
async def test_replace_grants_rejects_unavailable_tools(record, expected_message):
    service = _service([record])

    with pytest.raises(HTTPException, match=expected_message) as exc_info:
        await service.replace_grants(
            project_id=3,
            app_id=5,
            payload=SimpleNamespace(agent_tool_ids=[1]),
        )

    assert exc_info.value.status_code == 400
    assert service.repository.replaced_with is None
