import asyncio

from app.services.graph_extraction import extract_chunk_graph
from app.services.graph_models import GraphChunkRecord


def test_extract_chunk_graph_parses_llm_json_into_records():
    class FakeResponse:
        content = """
        {
          "entities": [
            {
              "name": "ProjectApp",
              "type": "COMPONENT",
              "aliases": ["project app"],
              "attributes": {"owner": "平台组"},
              "evidence": "ProjectApp 默认绑定 AssistantProfile"
            },
            {
              "name": "AssistantProfile",
              "type": "COMPONENT",
              "aliases": [],
              "attributes": {"scope": "default"},
              "evidence": "ProjectApp 默认绑定 AssistantProfile"
            }
          ],
          "relations": [
            {
              "source": "ProjectApp",
              "target": "AssistantProfile",
              "type": "USES",
              "attributes": {"mode": "auto"},
              "evidence": "ProjectApp 默认绑定 AssistantProfile"
            }
          ]
        }
        """

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            assert "ProjectApp 默认绑定 AssistantProfile" in prompt
            return FakeResponse()

    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=1,
        document_chunk_id=10,
        document_title="系统说明",
        section_path="绑定关系",
    )

    result = asyncio.run(
        extract_chunk_graph(
            chunk=chunk,
            chunk_text="ProjectApp 默认绑定 AssistantProfile",
            llm_factory=lambda: FakeLLM(),
        )
    )

    assert [entity.display_name for entity in result.entities] == [
        "ProjectApp",
        "AssistantProfile",
    ]
    assert result.entities[0].attributes == {"owner": "平台组"}
    assert result.relations[0].source_normalized_name == "projectapp"
    assert result.relations[0].target_normalized_name == "assistantprofile"
    assert result.relations[0].attributes == {"mode": "auto"}


def test_extract_chunk_graph_returns_empty_result_on_invalid_json():
    class FakeResponse:
        content = "not-json"

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            return FakeResponse()

    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=2,
        document_chunk_id=20,
        document_title="空结果",
        section_path=None,
    )

    result = asyncio.run(
        extract_chunk_graph(
            chunk=chunk,
            chunk_text="Neo4j 作为图数据库",
            llm_factory=lambda: FakeLLM(),
        )
    )

    assert result.entities == []
    assert result.relations == []
