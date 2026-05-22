import asyncio

from app.services.kb_graph_retrieval import GraphRetriever


class FakeGraphStore:
    async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
        assert knowledge_base_id == 7
        assert team_id == 3
        return [
            {
                "document_id": 10,
                "document_chunk_id": 20,
                "document_title": "Integration Guide",
                "section_path": "Payments",
                "chunk_text": "Prescription Flow connects to Payment through order settlement.",
                "relation_type": "CONNECTS_TO",
                "evidence": "Prescription Flow connects to Payment",
                "matched_entities": ["Prescription Flow", "Payment"],
            }
        ]


class FailingGraphStore:
    async def search_related_evidence(self, *, entity_names, knowledge_base_id, team_id, limit):
        raise RuntimeError("neo4j unavailable")


def test_graph_retriever_returns_normalized_docs_and_trace():
    result = asyncio.run(
        GraphRetriever(store=FakeGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow", "Payment"],
            knowledge_base_id=7,
            team_id=3,
        )
    )

    assert result["retrieved_docs"][0]["content"].startswith("Prescription Flow")
    metadata = result["retrieved_docs"][0]["metadata"]
    assert metadata["source"] == "graph"
    assert metadata["document_id"] == 10
    assert "chunk_index" not in metadata
    assert metadata["graph_relation_type"] == "CONNECTS_TO"
    assert result["trace"]["graph_used"] is True
    assert result["trace"]["graph_hits"] == 1


def test_graph_retriever_degrades_when_disabled():
    result = asyncio.run(
        GraphRetriever(store=FakeGraphStore(), enabled=False).retrieve(
            candidate_entities=["Prescription Flow"],
            knowledge_base_id=7,
            team_id=3,
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["graph_used"] is False
    assert result["trace"]["empty_reason"] == "disabled"


def test_graph_retriever_degrades_on_store_error():
    result = asyncio.run(
        GraphRetriever(store=FailingGraphStore(), enabled=True).retrieve(
            candidate_entities=["Prescription Flow"],
            knowledge_base_id=7,
            team_id=3,
        )
    )

    assert result["retrieved_docs"] == []
    assert result["trace"]["graph_used"] is True
    assert result["trace"]["empty_reason"] == "error"
