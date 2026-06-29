import asyncio

from app.services.graph_indexer import DEFAULT_GRAPH_BATCH_SIZE, GraphIndexer
from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphMentionRecord,
    GraphRelationEvidenceRecord,
    GraphRelationRecord,
    build_entity_id,
)


def test_graph_indexer_batches_new_graph_objects():
    calls = []

    class FakeStore:
        async def upsert_chunks(self, chunks):
            calls.append(("chunks", len(chunks)))

        async def upsert_entities(self, entities):
            calls.append(("entities", len(entities)))

        async def upsert_mentions(self, mentions):
            calls.append(("mentions", len(mentions)))

        async def upsert_relations(self, relations):
            calls.append(("relations", len(relations)))

        async def upsert_relation_evidences(self, evidences):
            calls.append(("relation_evidences", len(evidences)))

        async def refresh_related_evidence_counts(self, *, team_id, knowledge_base_id):
            calls.append(("refresh", team_id, knowledge_base_id))

    entity_id = build_entity_id(team_id=1, knowledge_base_id=2, entity_type="MODULE", name="Payment")
    entities = [
        GraphEntityRecord(
            id=build_entity_id(team_id=1, knowledge_base_id=2, entity_type="MODULE", name=f"Entity {index}"),
            team_id=1,
            knowledge_base_id=2,
            name=f"Entity {index}",
            entity_type="MODULE",
        )
        for index in range(DEFAULT_GRAPH_BATCH_SIZE + 1)
    ]
    summary = asyncio.run(
        GraphIndexer(FakeStore()).index_batch_graph(
            chunks=[
                GraphChunkRecord(
                    team_id=1,
                    knowledge_base_id=2,
                    document_id=3,
                    document_chunk_id=4,
                    chunk_index=0,
                    document_title="图谱",
                    section_path=None,
                )
            ],
            entities=entities,
            mentions=[
                GraphMentionRecord(
                    team_id=1,
                    knowledge_base_id=2,
                    entity_id=entity_id,
                    document_id=3,
                    document_chunk_id=index + 1,
                    mention_text="Payment",
                )
                for index in range(DEFAULT_GRAPH_BATCH_SIZE + 1)
            ],
            relations=[
                GraphRelationRecord(
                    team_id=1,
                    knowledge_base_id=2,
                    source_entity_id=entity_id,
                    target_entity_id=entity_id,
                    relation_type="RELATED_TO",
                )
            ],
            relation_evidences=[
                GraphRelationEvidenceRecord(
                    id=f"ev-{index}",
                    team_id=1,
                    knowledge_base_id=2,
                    source_entity_id=entity_id,
                    target_entity_id=entity_id,
                    document_id=3,
                    document_chunk_id=index + 1,
                    relation_type="RELATED_TO",
                    evidence_text="evidence",
                    evidence_hash=f"hash-{index}",
                )
                for index in range(DEFAULT_GRAPH_BATCH_SIZE + 1)
            ],
            team_id=1,
            knowledge_base_id=2,
        )
    )

    assert summary["relation_evidences"] == DEFAULT_GRAPH_BATCH_SIZE + 1
    assert ("chunks", 1) in calls
    assert [item for item in calls if item[0] == "entities"] == [
        ("entities", DEFAULT_GRAPH_BATCH_SIZE),
        ("entities", 1),
    ]
    assert [item for item in calls if item[0] == "relation_evidences"] == [
        ("relation_evidences", DEFAULT_GRAPH_BATCH_SIZE),
        ("relation_evidences", 1),
    ]
    assert ("refresh", 1, 2) in calls
