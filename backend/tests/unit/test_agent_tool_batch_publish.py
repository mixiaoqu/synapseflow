from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.application.agent_tool_catalog_service import AgentToolCatalogService
from app.db.models import AgentTool, ToolProvider
from app.models.schemas.tool_provider import AgentToolBatchPublishRequest
from app.repositories.agent_tool_repository import AgentToolRecord


class FakePermissionService:
    async def can_access_team(self, user, team_id):
        return True


class FakeRepository:
    def __init__(self, records):
        self.records = records
        self.saved = []

    async def get_tool_records_by_ids(self, tool_ids):
        wanted = set(tool_ids)
        return [record for record in self.records if record.tool.id in wanted]

    async def save_tools(self, tools):
        self.saved = list(tools)


def _record(tool_id, *, sync_status="active", publish_status="draft"):
    provider = ToolProvider(id=1, team_id=1, code="medical", name="医疗中心")
    tool = AgentTool(
        id=tool_id,
        provider_id=1,
        team_id=1,
        external_name=f"tool_{tool_id}",
        external_display_name=f"工具 {tool_id}",
        tool_key=f"medical_tool_{tool_id}",
        name=f"工具 {tool_id}",
        schema_hash=f"hash-{tool_id}",
        sync_status=sync_status,
        publish_status=publish_status,
    )
    return AgentToolRecord(tool=tool, provider=provider, team_name="团队")


def _service(records):
    service = AgentToolCatalogService.__new__(AgentToolCatalogService)
    service.user = SimpleNamespace(id=1, role="operator")
    service.permission_service = FakePermissionService()
    service.repository = FakeRepository(records)
    return service


@pytest.mark.asyncio
async def test_batch_publish_validates_then_publishes_all_tools():
    records = [_record(1), _record(2, publish_status="needs_review")]
    service = _service(records)

    result = await service.batch_publish_tools(
        AgentToolBatchPublishRequest(tool_ids=[2, 1, 2])
    )

    assert result.published_ids == [1, 2]
    assert result.published_count == 2
    assert service.repository.saved == [record.tool for record in records]
    for record in records:
        assert record.tool.publish_status == "published"
        assert record.tool.approved_schema_hash == record.tool.schema_hash


@pytest.mark.asyncio
async def test_batch_publish_is_atomic_when_tool_is_missing_or_inactive():
    active = _record(1)
    inactive = _record(2, sync_status="removed")
    service = _service([active, inactive])

    with pytest.raises(HTTPException, match="同步状态正常"):
        await service.batch_publish_tools(AgentToolBatchPublishRequest(tool_ids=[1, 2]))
    assert service.repository.saved == []
    assert active.tool.publish_status == "draft"

    with pytest.raises(HTTPException, match="不存在"):
        await service.batch_publish_tools(AgentToolBatchPublishRequest(tool_ids=[1, 3]))
    assert service.repository.saved == []
