import asyncio

from app.services.graph_indexer import DEFAULT_GRAPH_BATCH_SIZE, GraphIndexer
from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)


def test_graph_models_expose_minimal_document_and_chunk_fields():
    chunk = GraphChunkRecord(
        team_id=7,
        knowledge_base_id=8,
        document_id=12,
        document_chunk_id=34,
        document_title="部署说明",
        section_path="安装 / 数据库",
    )
    entity = GraphEntityRecord(
        document_id=12,
        document_chunk_id=34,
        normalized_name="postgresql",
        display_name="PostgreSQL",
        entity_type="DATABASE",
        aliases=("Postgres",),
        attributes={"version": "15"},
        evidence="结果写入 PostgreSQL",
    )
    relation = GraphRelationRecord(
        team_id=7,
        knowledge_base_id=8,
        document_id=12,
        document_chunk_id=34,
        source_normalized_name="projectapp",
        target_normalized_name="postgresql",
        relation_type="USES",
        attributes={"mode": "direct"},
        evidence="ProjectApp 使用 PostgreSQL",
    )

    assert chunk.document_id == 12
    assert chunk.team_id == 7
    assert chunk.knowledge_base_id == 8
    assert entity.display_name == "PostgreSQL"
    assert relation.relation_type == "USES"


def test_graph_indexer_writes_chunk_entities_and_relations():
    calls = []

    class FakeStore:
        async def upsert_chunk(self, chunk):
            calls.append(("chunk", chunk))

        async def upsert_entity(self, entity):
            calls.append(("entity", entity))

        async def link_entity_to_chunk(self, *, normalized_name, chunk):
            calls.append(("mention", normalized_name, chunk.document_chunk_id))

        async def upsert_relation(self, relation):
            calls.append(("relation", relation))

    indexer = GraphIndexer(FakeStore())
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=3,
        document_id=1,
        document_chunk_id=101,
        document_title="系统设计",
        section_path="关系图谱",
    )
    entities = [
        GraphEntityRecord(
            document_id=1,
            document_chunk_id=101,
            normalized_name="projectapp",
            display_name="ProjectApp",
            entity_type="COMPONENT",
            aliases=(),
            attributes={},
            evidence="ProjectApp 默认绑定 AssistantProfile",
        ),
        GraphEntityRecord(
            document_id=1,
            document_chunk_id=101,
            normalized_name="assistantprofile",
            display_name="AssistantProfile",
            entity_type="COMPONENT",
            aliases=(),
            attributes={},
            evidence="ProjectApp 默认绑定 AssistantProfile",
        ),
    ]
    relations = [
        GraphRelationRecord(
            team_id=1,
            knowledge_base_id=3,
            document_id=1,
            document_chunk_id=101,
            source_normalized_name="projectapp",
            target_normalized_name="assistantprofile",
            relation_type="USES",
            attributes={},
            evidence="ProjectApp 默认绑定 AssistantProfile",
        )
    ]

    summary = asyncio.run(
        indexer.index_chunk_graph(
            chunk=chunk,
            entities=entities,
            relations=relations,
        )
    )

    assert summary == {"chunks": 1, "entities": 2, "mentions": 2, "relations": 1}
    assert calls[0][0] == "chunk"
    assert [item[0] for item in calls].count("entity") == 2
    assert [item[0] for item in calls].count("mention") == 2
    assert [item[0] for item in calls].count("relation") == 1


def test_graph_indexer_skips_relation_without_known_entities():
    calls = []

    class FakeStore:
        async def upsert_chunk(self, chunk):
            calls.append(("chunk", chunk))

        async def upsert_entity(self, entity):
            calls.append(("entity", entity))

        async def link_entity_to_chunk(self, *, normalized_name, chunk):
            calls.append(("mention", normalized_name, chunk.document_chunk_id))

        async def upsert_relation(self, relation):
            calls.append(("relation", relation))

    indexer = GraphIndexer(FakeStore())
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=3,
        document_id=2,
        document_chunk_id=202,
        document_title="配置说明",
        section_path=None,
    )
    entities = [
        GraphEntityRecord(
            document_id=2,
            document_chunk_id=202,
            normalized_name="neo4j",
            display_name="Neo4j",
            entity_type="DATABASE",
            aliases=(),
            attributes={},
            evidence="Neo4j 作为图数据库",
        )
    ]
    relations = [
        GraphRelationRecord(
            team_id=1,
            knowledge_base_id=3,
            document_id=2,
            document_chunk_id=202,
            source_normalized_name="neo4j",
            target_normalized_name="unknown-service",
            relation_type="USES",
            attributes={},
            evidence="无效关系",
        )
    ]

    summary = asyncio.run(indexer.index_chunk_graph(chunk=chunk, entities=entities, relations=relations))

    assert summary["relations"] == 0
    assert [item[0] for item in calls].count("relation") == 0


def test_graph_indexer_batches_writes_by_default_batch_size():
    calls = []

    class FakeStore:
        async def upsert_chunks(self, chunks):
            calls.append(("chunks", len(chunks)))

        async def upsert_entities(self, entities):
            calls.append(("entities", len(entities)))

        async def link_entities_to_chunks(self, rows):
            calls.append(("mentions", len(rows)))

        async def upsert_relations(self, relations):
            calls.append(("relations", len(relations)))

    indexer = GraphIndexer(FakeStore())
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=3,
        document_id=9,
        document_chunk_id=1,
        document_title="批次测试",
        section_path=None,
    )
    entities = [
        GraphEntityRecord(
            document_id=9,
            document_chunk_id=index + 1,
            normalized_name=f"entity-{index}",
            display_name=f"Entity {index}",
            entity_type="OTHER",
            aliases=(),
            attributes={},
            evidence="batch",
        )
        for index in range(DEFAULT_GRAPH_BATCH_SIZE + 1)
    ]
    mentions = [
        {
            "normalized_name": entity.normalized_name,
            "team_id": 1,
            "knowledge_base_id": 3,
            "document_id": 9,
            "document_chunk_id": entity.document_chunk_id,
        }
        for entity in entities
    ]

    summary = asyncio.run(
        indexer.index_batch_graph(
            chunks=[chunk],
            entities=entities,
            mentions=mentions,
            relations=[],
        )
    )

    assert summary == {
        "chunks": 1,
        "entities": DEFAULT_GRAPH_BATCH_SIZE + 1,
        "mentions": DEFAULT_GRAPH_BATCH_SIZE + 1,
        "relations": 0,
    }
    assert ("chunks", 1) in calls
    assert [item for item in calls if item[0] == "entities"] == [
        ("entities", DEFAULT_GRAPH_BATCH_SIZE),
        ("entities", 1),
    ]
    assert [item for item in calls if item[0] == "mentions"] == [
        ("mentions", DEFAULT_GRAPH_BATCH_SIZE),
        ("mentions", 1),
    ]
