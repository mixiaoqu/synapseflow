import asyncio
from types import SimpleNamespace

import pytest

from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)
from app.services.document_indexer import (
    _merge_entity_records,
    finalize_document_graph,
    index_document_graph,
)


def test_index_document_graph_runs_full_chunk_pipeline(monkeypatch):
    events = []

    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def get_child_chunks_for_document(self, document_id):
            return [
                SimpleNamespace(
                    id=101,
                    content="ProjectApp 默认绑定 AssistantProfile",
                    section_path="绑定关系",
                ),
                SimpleNamespace(
                    id=102,
                    content="ProjectApp 也关联 AssistantProfile",
                    section_path="绑定关系 / 扩展",
                ),
            ]

    class FakeStore:
        async def delete_document_graph(self, *, document_id):
            events.append(("delete", document_id))

        async def upsert_chunks(self, chunks):
            events.append(("chunks", [chunk.document_chunk_id for chunk in chunks]))

        async def upsert_entities(self, entities):
            events.append(("entities", [entity.normalized_name for entity in entities]))

        async def link_entities_to_chunks(self, rows):
            events.append(("mentions", [(row["normalized_name"], row["document_chunk_id"]) for row in rows]))

        async def upsert_relations(self, relations):
            events.append(("relations", [relation.relation_type for relation in relations]))

        async def prune_orphan_entities(self):
            events.append(("prune",))

        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            events.append(("summary-list", knowledge_base_id, team_id, tuple(normalized_names)))
            return []

        async def upsert_entity_summaries(self, rows):
            events.append(("summary-upsert", len(rows)))

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            assert normalized_names == []
            events.append(("relation-summary-list", knowledge_base_id, team_id, document_id))
            return []

        async def upsert_relation_summaries(self, rows):
            events.append(("relation-summary-upsert", len(rows)))

    extraction = ChunkGraphExtraction(
        chunk=GraphChunkRecord(
            team_id=2,
            knowledge_base_id=9,
            document_id=1,
            document_chunk_id=101,
            document_title="系统说明",
            section_path="绑定关系",
        ),
        entities=[
            GraphEntityRecord(
                team_id=2,
                knowledge_base_id=9,
                document_id=1,
                document_chunk_id=101,
                normalized_name="projectapp",
                display_name="ProjectApp",
                entity_type="COMPONENT",
                aliases=(),
                attributes={"owner": "平台组"},
                evidence="ProjectApp 默认绑定 AssistantProfile",
            )
        ],
        relations=[
            GraphRelationRecord(
                team_id=2,
                knowledge_base_id=9,
                document_id=1,
                document_chunk_id=101,
                source_normalized_name="projectapp",
                target_normalized_name="assistantprofile",
                relation_type="USES",
                attributes={"mode": "auto"},
                evidence="ProjectApp 默认绑定 AssistantProfile",
            )
        ],
    )
    second_extraction = ChunkGraphExtraction(
        chunk=GraphChunkRecord(
            team_id=2,
            knowledge_base_id=9,
            document_id=1,
            document_chunk_id=102,
            document_title="系统说明",
            section_path="绑定关系 / 扩展",
        ),
        entities=[
            GraphEntityRecord(
                team_id=2,
                knowledge_base_id=9,
                document_id=1,
                document_chunk_id=102,
                normalized_name="projectapp",
                display_name="ProjectApp",
                entity_type="COMPONENT",
                aliases=(),
                attributes={"owner": "平台组"},
                evidence="ProjectApp 也关联 AssistantProfile",
            ),
            GraphEntityRecord(
                team_id=2,
                knowledge_base_id=9,
                document_id=1,
                document_chunk_id=102,
                normalized_name="assistantprofile",
                display_name="AssistantProfile",
                entity_type="COMPONENT",
                aliases=(),
                attributes={"scope": "default"},
                evidence="ProjectApp 也关联 AssistantProfile",
            ),
        ],
        relations=[
            GraphRelationRecord(
                team_id=2,
                knowledge_base_id=9,
                document_id=1,
                document_chunk_id=102,
                source_normalized_name="projectapp",
                target_normalized_name="assistantprofile",
                relation_type="USES",
                attributes={"mode": "auto"},
                evidence="ProjectApp 也关联 AssistantProfile",
            )
        ],
    )

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

    async def fake_execute(stmt):
        return SimpleNamespace(one_or_none=lambda: SimpleNamespace(team_id=2, knowledge_base_id=9))

    monkeypatch.setattr(
        "app.services.document_indexer.DocumentChunkRepository",
        FakeChunkRepository,
    )
    monkeypatch.setattr(
        "app.services.document_indexer.config_registry.get_graph_config",
        lambda: DummyGraphConfig(),
    )
    monkeypatch.setattr(
        "app.services.document_indexer.get_graph_store",
        lambda: FakeStore(),
    )
    monkeypatch.setattr(
        "app.services.document_indexer.extract_chunk_graphs_batch",
        lambda items: asyncio.sleep(
            0,
            result=[
                extraction if chunk.document_chunk_id == 101 else second_extraction
                for chunk, _chunk_text in items
            ],
        ),
    )
    monkeypatch.setattr(
        "app.services.document_indexer.normalize_chunk_graph",
        lambda *, chunk, entities, relations: ChunkGraphExtraction(
            chunk=chunk,
            entities=entities,
            relations=relations,
        ),
    )

    summary = asyncio.run(
        index_document_graph(
            SimpleNamespace(execute=fake_execute),
            document_id=1,
            title="系统说明",
            commit=False,
        )
    )

    assert summary == {"chunks": 2, "entities": 2, "mentions": 3, "relations": 1}
    assert events[0] == ("delete", 1)
    assert ("chunks", [101, 102]) in events
    assert ("entities", ["projectapp", "assistantprofile"]) in events
    assert ("mentions", [("projectapp", 101), ("projectapp", 102), ("assistantprofile", 102)]) in events
    assert ("relations", ["USES"]) in events
    assert any(item[0] == "summary-list" for item in events)
    assert ("relation-summary-list", 9, 2, 1) in events
    assert any(item == ("summary-upsert", 0) for item in events)
    assert ("prune",) in events


def test_index_document_graph_requires_document_team_and_knowledge_base(monkeypatch):
    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def get_child_chunks_for_document(self, document_id):
            return []

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

    async def fake_execute(stmt):
        return SimpleNamespace(one_or_none=lambda: None)

    monkeypatch.setattr(
        "app.services.document_indexer.DocumentChunkRepository",
        FakeChunkRepository,
    )
    monkeypatch.setattr(
        "app.services.document_indexer.config_registry.get_graph_config",
        lambda: DummyGraphConfig(),
    )

    with pytest.raises(ValueError, match="Document 1 must belong to a team and knowledge base"):
        asyncio.run(
            index_document_graph(
                SimpleNamespace(execute=fake_execute),
                document_id=1,
                title="ç³»ç»Ÿè¯´æ˜Ž",
                commit=False,
            )
        )


def test_finalize_document_graph_refreshes_relation_summaries_for_current_document(monkeypatch):
    events = []

    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def get_child_chunks_for_document(self, document_id):
            return [
                SimpleNamespace(
                    id=101,
                    metadata_={
                        "graph_extraction": {
                            "status": "indexed",
                            "entities": [
                                {"normalized_name": "projectapp"},
                                {"normalized_name": "assistantprofile"},
                            ],
                            "relations": [
                                {
                                    "source_normalized_name": "projectapp",
                                    "target_normalized_name": "assistantprofile",
                                    "relation_type": "USES",
                                }
                            ],
                        }
                    },
                )
            ]

    class FakeStore:
        async def prune_orphan_entities(self):
            events.append(("prune",))

        async def list_entity_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names):
            events.append(("entity-summary-list", knowledge_base_id, team_id, tuple(normalized_names)))
            return []

        async def upsert_entity_summaries(self, rows):
            events.append(("entity-summary-upsert", len(rows)))

        async def list_relation_summary_contexts(self, *, knowledge_base_id, team_id, normalized_names, document_id=None):
            assert normalized_names == []
            events.append(("relation-summary-list", knowledge_base_id, team_id, document_id))
            return []

        async def upsert_relation_summaries(self, rows):
            events.append(("relation-summary-upsert", len(rows)))

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

    async def fake_execute(stmt):
        return SimpleNamespace(one_or_none=lambda: SimpleNamespace(team_id=2, knowledge_base_id=9))

    monkeypatch.setattr(
        "app.services.document_indexer.DocumentChunkRepository",
        FakeChunkRepository,
    )
    monkeypatch.setattr(
        "app.services.document_indexer.config_registry.get_graph_config",
        lambda: DummyGraphConfig(),
    )
    monkeypatch.setattr(
        "app.services.document_indexer.get_graph_store",
        lambda: FakeStore(),
    )

    summary = asyncio.run(
        finalize_document_graph(
            SimpleNamespace(execute=fake_execute),
            document_id=1,
            title="系统说明",
            commit=False,
        )
    )

    assert summary == {"chunks": 1, "entities": 2, "mentions": 2, "relations": 1}
    assert ("prune",) in events
    assert ("entity-summary-list", 9, 2, ("assistantprofile", "projectapp")) in events
    assert ("relation-summary-list", 9, 2, 1) in events


def test_merge_entity_records_prefers_human_display_name_over_normalized_name():
    existing = GraphEntityRecord(
        team_id=1,
        knowledge_base_id=40,
        document_id=1,
        document_chunk_id=1,
        normalized_name="commodity",
        display_name="commodity",
        entity_type="BUSINESS_OBJECT",
        aliases=("商品",),
        attributes={"attr_description": "商品基础信息"},
        evidence="commodity",
    )
    incoming = GraphEntityRecord(
        team_id=1,
        knowledge_base_id=40,
        document_id=1,
        document_chunk_id=2,
        normalized_name="commodity",
        display_name="商品",
        entity_type="BUSINESS_OBJECT",
        aliases=("商品信息",),
        attributes={},
        evidence="商品基础信息",
    )

    merged = _merge_entity_records(existing, incoming)

    assert merged.display_name == "商品"
