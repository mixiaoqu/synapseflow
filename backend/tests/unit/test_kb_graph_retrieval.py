import asyncio

from app.services.kb_graph_retrieval import GraphRetriever


class FakeGraphStore:
    async def search_relation_evidence_for_pairs(self, *, relation_pairs, knowledge_base_id, team_id, limit):
        return []

    async def search_relation_evidence_for_queries(self, *, relation_queries, knowledge_base_id, team_id, limit):
        return []

    async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
        assert entity_names == ["Prescription Flow", "Payment"]
        return [
            {
                "document_id": 10,
                "document_chunk_id": 20,
                "document_title": "Integration Guide",
                "section_path": "Payments",
                "relation_type": "CONFIGURES",
                "evidence": "Prescription Flow connects to Payment",
                "source_entity_id": "entity-prescription-flow",
                "source_name": "Prescription Flow",
                "source_entity_type": "WORKFLOW",
                "target_entity_id": "entity-payment",
                "target_name": "Payment",
                "target_entity_type": "MODULE",
                "matched_entities": ["Prescription Flow", "Payment"],
            }
        ]

    async def search_relation_paths(
        self,
        *,
        entity_names,
        relation_pairs,
        relation_queries,
        knowledge_base_id,
        team_id,
        max_hops,
        limit,
    ):
        assert max_hops >= 2
        return [
            {
                "path_id": "path-1",
                "signature": "Prescription Flow -[CONFIGURES]-> Payment -[CALLS]-> Gateway",
                "hop_count": 2,
                "matched_entities": ["Prescription Flow", "Payment", "Gateway"],
                "relation_types": ["CONFIGURES", "CALLS"],
                "evidence": [],
            }
        ]


class FailingGraphStore:
    async def search_relation_evidence_for_pairs(self, **kwargs):
        raise RuntimeError("neo4j unavailable")

    async def search_relation_evidence_for_queries(self, **kwargs):
        raise RuntimeError("neo4j unavailable")

    async def search_related_evidence(self, **kwargs):
        raise RuntimeError("neo4j unavailable")

    async def search_relation_paths(self, **kwargs):
        raise RuntimeError("neo4j unavailable")


def test_graph_retriever_returns_relation_evidence_and_paths():
    result = asyncio.run(
        GraphRetriever(store=FakeGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow", "Payment"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="relation_lookup",
            max_hops=2,
        )
    )

    text_fact = result["graph_facts"]["text"][0]
    relation_fact = result["graph_facts"]["relations"][0]
    entity_fact = result["graph_facts"]["entities"][0]
    path_fact = result["graph_facts"]["paths"][0]
    assert text_fact["content"] == "Prescription Flow connects to Payment"
    assert relation_fact["source"]["name"] == "Prescription Flow"
    assert relation_fact["target"]["name"] == "Payment"
    assert entity_fact["name"] == "Prescription Flow"
    assert path_fact["signature"].startswith("Prescription Flow")
    assert result["trace"]["graph_mode"] == "relation_evidence"
    assert result["trace"]["graph_hits"] >= 4


def test_graph_retriever_skips_definition_lookup():
    result = asyncio.run(
        GraphRetriever(store=FakeGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="definition_lookup",
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["graph_mode"] == "disabled"
    assert result["trace"]["empty_reason"] == "skipped_for_question_type"


def test_graph_retriever_degrades_on_store_error():
    result = asyncio.run(
        GraphRetriever(store=FailingGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow"],
            relation_pairs=[],
            relation_queries=[],
            knowledge_base_id=7,
            team_id=3,
            question_type="relation_lookup",
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["empty_reason"] == "error"
