import asyncio
from types import SimpleNamespace

import pytest

from app.services.document_indexer import finalize_document_graph, index_document_graph
from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationCandidate,
    build_entity_id,
)


def _entity(name: str, entity_type: str) -> GraphEntityRecord:
    return GraphEntityRecord(
        id=build_entity_id(team_id=2, knowledge_base_id=9, entity_type=entity_type, name=name),
        team_id=2,
        knowledge_base_id=9,
        name=name,
        entity_type=entity_type,
    )


def test_index_document_graph_writes_new_graph_records(monkeypatch):
    events = []

    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def get_parent_chunks_for_document(self, document_id):
            return [SimpleNamespace(id=101, content="chunk", chunk_index=0, section_path="绑定关系", metadata_={})]

    class FakeStore:
        async def delete_document_graph(self, *, document_id, team_id, knowledge_base_id):
            events.append(("delete", document_id, team_id, knowledge_base_id))

        async def upsert_chunks(self, chunks):
            events.append(("chunks", [chunk.document_chunk_id for chunk in chunks]))

        async def upsert_entities(self, entities):
            events.append(("entities", [entity.name for entity in entities]))

        async def upsert_mentions(self, mentions):
            events.append(("mentions", [(mention.entity_id, mention.document_chunk_id) for mention in mentions]))

        async def upsert_relations(self, relations):
            events.append(("relations", [relation.relation_type for relation in relations]))

        async def upsert_relation_evidences(self, evidences):
            events.append(("relation_evidences", [evidence.evidence_hash for evidence in evidences]))

        async def refresh_related_evidence_counts(self, *, team_id, knowledge_base_id):
            events.append(("refresh", team_id, knowledge_base_id))

        async def prune_orphan_entities(self, *, team_id, knowledge_base_id):
            events.append(("prune", team_id, knowledge_base_id))

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

    async def fake_execute(stmt):
        return SimpleNamespace(one_or_none=lambda: SimpleNamespace(team_id=2, knowledge_base_id=9))

    extraction = ChunkGraphExtraction(
        chunk=GraphChunkRecord(
            team_id=2,
            knowledge_base_id=9,
            document_id=1,
            document_chunk_id=101,
            chunk_index=0,
            document_title="系统说明",
            section_path="绑定关系",
            content_hash="chunk-hash",
        ),
        entities=[_entity("ProjectApp", "COMPONENT"), _entity("AssistantProfile", "COMPONENT")],
        relation_candidates=[
            GraphRelationCandidate(
                source_name="ProjectApp",
                source_entity_type="COMPONENT",
                target_name="AssistantProfile",
                target_entity_type="COMPONENT",
                relation_type="TRIGGERS",
                evidence_text="ProjectApp 默认绑定 AssistantProfile",
            )
        ],
    )

    monkeypatch.setattr("app.services.document_indexer.DocumentChunkRepository", FakeChunkRepository)
    monkeypatch.setattr("app.services.document_indexer.config_registry.get_graph_config", lambda: DummyGraphConfig())
    monkeypatch.setattr("app.services.document_indexer.get_graph_store", lambda: FakeStore())
    monkeypatch.setattr(
        "app.services.document_indexer._prepare_chunk_extractions",
        lambda **kwargs: asyncio.sleep(0, result=[extraction]),
    )

    summary = asyncio.run(
        index_document_graph(
            SimpleNamespace(execute=fake_execute),
            document_id=1,
            title="系统说明",
            commit=False,
        )
    )

    assert summary["entities"] == 2
    assert summary["relations"] == 1
    assert summary["relation_evidences"] == 1
    assert ("delete", 1, 2, 9) in events
    assert ("refresh", 2, 9) in events
    assert ("prune", 2, 9) in events
    assert ("chunks", [101]) in events
    assert ("entities", ["ProjectApp", "AssistantProfile"]) in events
    assert any(item[0] == "mentions" for item in events)
    assert ("relations", ["TRIGGERS"]) in events
    assert any(item[0] == "relation_evidences" for item in events)


def test_index_document_graph_requires_document_team_and_knowledge_base(monkeypatch):
    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def get_parent_chunks_for_document(self, document_id):
            return []

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

    async def fake_execute(stmt):
        return SimpleNamespace(one_or_none=lambda: None)

    monkeypatch.setattr("app.services.document_indexer.DocumentChunkRepository", FakeChunkRepository)
    monkeypatch.setattr("app.services.document_indexer.config_registry.get_graph_config", lambda: DummyGraphConfig())

    with pytest.raises(ValueError, match="Document 1 must belong to a team and knowledge base"):
        asyncio.run(
            index_document_graph(
                SimpleNamespace(execute=fake_execute),
                document_id=1,
                title="系统说明",
                commit=False,
            )
        )


def test_finalize_document_graph_waits_for_missing_chunk_extraction(monkeypatch):
    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def get_parent_chunks_for_document(self, document_id):
            return [SimpleNamespace(id=101, content="chunk", chunk_index=0, section_path=None, metadata_={})]

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

    async def fake_execute(stmt):
        return SimpleNamespace(one_or_none=lambda: SimpleNamespace(team_id=2, knowledge_base_id=9))

    monkeypatch.setattr("app.services.document_indexer.DocumentChunkRepository", FakeChunkRepository)
    monkeypatch.setattr("app.services.document_indexer.config_registry.get_graph_config", lambda: DummyGraphConfig())

    summary = asyncio.run(
        finalize_document_graph(
            SimpleNamespace(execute=fake_execute),
            document_id=1,
            title="系统说明",
            commit=False,
        )
    )

    assert summary == {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0, "relation_evidences": 0}
