import asyncio

from app.services import graph_store
from app.services.graph_models import GraphEntityRecord, GraphRelationRecord


def test_prepare_attributes_prefixes_keys_and_filters_empty_values():
    result = graph_store._prepare_attributes(
        {
            "owner": "平台组",
            "version": " 15 ",
            "enabled": True,
            "empty": "",
            "nested": {"x": 1},
        }
    )

    assert result == {
        "attr_owner": "平台组",
        "attr_version": "15",
        "attr_enabled": True,
        "attr_nested": "{'x': 1}",
    }


def test_get_graph_store_reuses_neo4j_store_for_same_config(monkeypatch):
    created = []

    class DummyGraphConfig:
        enabled = True
        indexing_enabled = True
        uri = "bolt://neo4j:7687"
        username = "neo4j"
        password = "secret"
        database = "neo4j"

    class FakeNeo4jGraphStore:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(graph_store.config_registry, "get_graph_config", lambda: DummyGraphConfig())
    monkeypatch.setattr(graph_store, "Neo4jGraphStore", FakeNeo4jGraphStore)
    monkeypatch.setattr(graph_store, "_GRAPH_STORE_CACHE", {})

    first = graph_store.get_graph_store()
    second = graph_store.get_graph_store()

    assert first is second
    assert created == [
        {
            "uri": "bolt://neo4j:7687",
            "username": "neo4j",
            "password": "secret",
            "database": "neo4j",
        }
    ]


def test_upsert_entities_scopes_entity_identity_by_team_and_knowledge_base():
    calls = []
    store = object.__new__(graph_store.Neo4jGraphStore)

    async def fake_run(query, **params):
        calls.append((query, params))

    store._run = fake_run

    asyncio.run(
        store.upsert_entities(
            [
                GraphEntityRecord(
                    team_id=1,
                    knowledge_base_id=2,
                    document_id=10,
                    document_chunk_id=100,
                    normalized_name="projectapp",
                    display_name="ProjectApp",
                    entity_type="COMPONENT",
                    aliases=(),
                    attributes={},
                    evidence="ProjectApp 默认绑定 AssistantProfile",
                )
            ]
        )
    )

    query, params = calls[0]
    assert "MERGE (e:Entity {" in query
    assert "team_id: row.team_id" in query
    assert "knowledge_base_id: row.knowledge_base_id" in query
    assert "normalized_name: row.normalized_name" in query
    assert "e.canonical_name = row.canonical_name" in query
    assert "e.alias_keys = row.alias_keys" in query
    assert params["rows"][0]["team_id"] == 1
    assert params["rows"][0]["knowledge_base_id"] == 2
    assert params["rows"][0]["canonical_name"] == "ProjectApp"
    assert params["rows"][0]["alias_keys"] == []


def test_entity_lookup_queries_include_alias_keys():
    query = graph_store.Neo4jGraphStore.lookup_entities_for_grounding.__code__.co_consts
    joined = "\n".join(str(item) for item in query)

    assert "e.alias_keys" in joined
    assert "alias_key = $candidate" in joined


def test_upsert_relations_scopes_related_identity_by_team_and_knowledge_base():
    calls = []
    store = object.__new__(graph_store.Neo4jGraphStore)

    async def fake_run(query, **params):
        calls.append((query, params))

    store._run = fake_run

    asyncio.run(
        store.upsert_relations(
            [
                GraphRelationRecord(
                    team_id=1,
                    knowledge_base_id=2,
                    document_id=10,
                    document_chunk_id=100,
                    source_normalized_name="projectapp",
                    target_normalized_name="assistantprofile",
                    relation_type="TRIGGERS",
                    attributes={},
                    evidence="ProjectApp 默认绑定 AssistantProfile",
                )
            ]
        )
    )

    query, _params = calls[0]
    assert "MATCH (source:Entity {" in query
    assert "team_id: row.team_id" in query
    assert "knowledge_base_id: row.knowledge_base_id" in query
    assert "MATCH (target:Entity {" in query
    assert "MERGE (source)-[r:RELATED {" in query
    assert "team_id: row.team_id" in query
    assert "knowledge_base_id: row.knowledge_base_id" in query
    assert "source_normalized_name: row.source_normalized_name" in query
    assert "target_normalized_name: row.target_normalized_name" in query
    assert "relation_type: row.relation_type" in query
    assert "MERGE (evidence:RelationEvidence {" in query
    assert "MERGE (source)-[:HAS_RELATION_EVIDENCE]->(evidence)" in query
    assert "MERGE (evidence)-[:EVIDENCE_TARGET]->(target)" in query
    assert "MATCH (chunk:Chunk {document_chunk_id: row.document_chunk_id})" in query
    assert "MERGE (evidence)-[:FROM_CHUNK]->(chunk)" in query


def test_delete_knowledge_base_graph_detaches_scoped_summary_entity_evidence_and_chunk_nodes():
    calls = []
    store = object.__new__(graph_store.Neo4jGraphStore)

    async def fake_run(query, **params):
        calls.append((query, params))

    store._run = fake_run

    asyncio.run(store.delete_knowledge_base_graph(knowledge_base_id=2, team_id=1))

    assert len(calls) == 4

    summary_query, summary_params = calls[0]
    assert "MATCH (s:EntitySummary)" in summary_query
    assert "s.team_id = $team_id" in summary_query
    assert "s.knowledge_base_id = $knowledge_base_id" in summary_query
    assert "DETACH DELETE s" in summary_query
    assert summary_params == {"knowledge_base_id": 2, "team_id": 1}

    evidence_query, evidence_params = calls[1]
    assert "MATCH (re:RelationEvidence)" in evidence_query
    assert "re.team_id = $team_id" in evidence_query
    assert "re.knowledge_base_id = $knowledge_base_id" in evidence_query
    assert "DETACH DELETE re" in evidence_query
    assert evidence_params == {"knowledge_base_id": 2, "team_id": 1}

    entity_query, entity_params = calls[2]
    assert "MATCH (e:Entity)" in entity_query
    assert "e.team_id = $team_id" in entity_query
    assert "e.knowledge_base_id = $knowledge_base_id" in entity_query
    assert "DETACH DELETE e" in entity_query
    assert entity_params == {"knowledge_base_id": 2, "team_id": 1}

    chunk_query, chunk_params = calls[3]
    assert "MATCH (c:Chunk)" in chunk_query
    assert "c.team_id = $team_id" in chunk_query
    assert "c.knowledge_base_id = $knowledge_base_id" in chunk_query
    assert "DETACH DELETE c" in chunk_query
    assert chunk_params == {"knowledge_base_id": 2, "team_id": 1}
