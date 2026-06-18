import asyncio

from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphMentionRecord,
    GraphRelationEvidenceRecord,
    GraphRelationRecord,
)
from app.services.graph_store import Neo4jGraphStore, NullGraphStore


def test_null_graph_store_accepts_new_graph_objects():
    store = NullGraphStore()
    chunk = GraphChunkRecord(
        team_id=1,
        knowledge_base_id=2,
        document_id=3,
        document_chunk_id=4,
        chunk_index=0,
        document_title="系统说明",
        section_path=None,
    )
    entity = GraphEntityRecord(
        id="entity-1",
        team_id=1,
        knowledge_base_id=2,
        name="Payment",
        entity_type="MODULE",
    )
    mention = GraphMentionRecord(
        team_id=1,
        knowledge_base_id=2,
        entity_id="entity-1",
        document_id=3,
        document_chunk_id=4,
        mention_text="Payment",
    )
    relation = GraphRelationRecord(
        team_id=1,
        knowledge_base_id=2,
        source_entity_id="entity-1",
        target_entity_id="entity-2",
        relation_type="RELATED_TO",
    )
    evidence = GraphRelationEvidenceRecord(
        id="evidence-1",
        team_id=1,
        knowledge_base_id=2,
        source_entity_id="entity-1",
        target_entity_id="entity-2",
        document_id=3,
        document_chunk_id=4,
        relation_type="RELATED_TO",
        evidence_text="Payment relates to Gateway",
        evidence_hash="hash-1",
    )

    asyncio.run(store.upsert_chunks([chunk]))
    asyncio.run(store.upsert_entities([entity]))
    asyncio.run(store.upsert_mentions([mention]))
    asyncio.run(store.upsert_relations([relation]))
    asyncio.run(store.upsert_relation_evidences([evidence]))
    asyncio.run(store.refresh_related_evidence_counts())

    assert asyncio.run(store.lookup_entities_for_grounding(knowledge_base_id=2, team_id=1, candidate="payment")) == []


def test_delete_knowledge_base_graph_removes_legacy_entity_summary_nodes():
    store = Neo4jGraphStore.__new__(Neo4jGraphStore)
    calls = []

    async def fake_run(query: str, **params):
        calls.append((query, params))

    store._run = fake_run

    asyncio.run(store.delete_knowledge_base_graph(knowledge_base_id=12, team_id=34))

    assert "MATCH (s:EntitySummary)" in calls[0][0]
    assert calls[0][1] == {"team_id": 34, "knowledge_base_id": 12}
