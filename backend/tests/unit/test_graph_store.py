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
    assert params["rows"][0]["team_id"] == 1
    assert params["rows"][0]["knowledge_base_id"] == 2


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
                    relation_type="USES",
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
