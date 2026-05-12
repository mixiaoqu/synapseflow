import asyncio
from types import SimpleNamespace

from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)
from app.services.document_indexer import index_document_graph


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
                )
            ]

    class FakeStore:
        async def delete_document_graph(self, *, document_id):
            events.append(("delete", document_id))

        async def upsert_chunk(self, chunk):
            events.append(("chunk", chunk.document_chunk_id))

        async def upsert_entity(self, entity):
            events.append(("entity", entity.normalized_name))

        async def link_entity_to_chunk(self, *, normalized_name, chunk):
            events.append(("mention", normalized_name, chunk.document_chunk_id))

        async def upsert_relation(self, relation):
            events.append(("relation", relation.relation_type))

        async def prune_orphan_entities(self):
            events.append(("prune",))

    extraction = ChunkGraphExtraction(
        chunk=GraphChunkRecord(
            document_id=1,
            document_chunk_id=101,
            document_title="系统说明",
            section_path="绑定关系",
        ),
        entities=[
            GraphEntityRecord(
                document_id=1,
                document_chunk_id=101,
                normalized_name="projectapp",
                display_name="ProjectApp",
                entity_type="COMPONENT",
                aliases=(),
                evidence="ProjectApp 默认绑定 AssistantProfile",
            )
        ],
        relations=[
            GraphRelationRecord(
                document_id=1,
                document_chunk_id=101,
                source_normalized_name="projectapp",
                target_normalized_name="projectapp",
                relation_type="USES",
                evidence="无效自引用",
            )
        ],
    )

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True

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
        "app.services.document_indexer.extract_chunk_graph",
        lambda **kwargs: asyncio.sleep(0, result=extraction),
    )
    monkeypatch.setattr(
        "app.services.document_indexer.normalize_chunk_graph",
        lambda *, chunk, entities, relations: ChunkGraphExtraction(
            chunk=chunk,
            entities=entities,
            relations=[],
        ),
    )

    summary = asyncio.run(
        index_document_graph(
            object(),
            document_id=1,
            title="系统说明",
            commit=False,
        )
    )

    assert summary == {"chunks": 1, "entities": 1, "mentions": 1, "relations": 0}
    assert events[0] == ("delete", 1)
    assert ("chunk", 101) in events
    assert ("entity", "projectapp") in events
    assert ("mention", "projectapp", 101) in events
    assert events[-1] == ("prune",)
