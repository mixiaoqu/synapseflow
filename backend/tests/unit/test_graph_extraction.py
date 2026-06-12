import asyncio

from app.services.graph_extraction import extract_chunk_graph, extract_chunk_graphs_batch
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
              "type": "TRIGGERS",
              "attributes": {"mode": "auto"},
              "evidence": "ProjectApp 默认绑定 AssistantProfile"
            }
          ]
        }
        """

    seen_prompts = []

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            seen_prompts.append(prompt)
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
    assert "PAGE" in seen_prompts[0]
    assert "BUTTON" in seen_prompts[0]
    assert "WORKFLOW" in seen_prompts[0]
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


def test_extract_chunk_graphs_batch_parses_multiple_chunks_with_one_llm_call():
    calls = []

    class FakeResponse:
        content = """
        {
          "chunks": [
            {
              "document_chunk_id": 10,
              "entities": [
                {"name": "ProjectApp", "type": "COMPONENT", "aliases": [], "attributes": {}, "evidence": "ProjectApp 默认绑定 AssistantProfile"}
              ],
              "relations": []
            },
            {
              "document_chunk_id": 20,
              "entities": [
                {"name": "AssistantProfile", "type": "COMPONENT", "aliases": [], "attributes": {}, "evidence": "AssistantProfile 提供助手配置"}
              ],
              "relations": []
            }
          ]
        }
        """

    class FakeLLM:
        async def ainvoke(self, prompt: str):
            calls.append(prompt)
            assert "document_chunk_id" in prompt
            assert "ProjectApp 默认绑定 AssistantProfile" in prompt
            assert "AssistantProfile 提供助手配置" in prompt
            return FakeResponse()

    chunks = [
        GraphChunkRecord(
            team_id=1,
            knowledge_base_id=2,
            document_id=1,
            document_chunk_id=10,
            document_title="系统说明",
            section_path="绑定关系",
        ),
        GraphChunkRecord(
            team_id=1,
            knowledge_base_id=2,
            document_id=1,
            document_chunk_id=20,
            document_title="系统说明",
            section_path="助手配置",
        ),
    ]

    results = asyncio.run(
        extract_chunk_graphs_batch(
            [(chunks[0], "ProjectApp 默认绑定 AssistantProfile"), (chunks[1], "AssistantProfile 提供助手配置")],
            llm_factory=lambda: FakeLLM(),
        )
    )

    assert len(calls) == 1
    assert [result.chunk.document_chunk_id for result in results] == [10, 20]
    assert [result.entities[0].display_name for result in results] == [
        "ProjectApp",
        "AssistantProfile",
    ]
