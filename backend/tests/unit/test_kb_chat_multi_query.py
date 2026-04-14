import asyncio

from app.agents.nodes.kb_chat.retrieve import user_kb_retrieve_node
from app.services.vector_store import reciprocal_rank_fusion_many


def test_reciprocal_rank_fusion_many_merges_multiple_rankings():
    rank_a = [
        {
            "chunk_text": "alpha",
            "document_id": 1,
            "chunk_index": 0,
            "distance": 0.11,
            "document_title": "Doc A",
            "metadata": {},
        },
        {
            "chunk_text": "beta",
            "document_id": 2,
            "chunk_index": 0,
            "distance": 0.21,
            "document_title": "Doc B",
            "metadata": {},
        },
    ]
    rank_b = [
        {
            "chunk_text": "beta",
            "document_id": 2,
            "chunk_index": 0,
            "distance": 0.18,
            "document_title": "Doc B",
            "metadata": {},
        },
        {
            "chunk_text": "gamma",
            "document_id": 3,
            "chunk_index": 0,
            "distance": 0.15,
            "document_title": "Doc C",
            "metadata": {},
        },
    ]

    fused = reciprocal_rank_fusion_many([rank_a, rank_b], rrf_k=60, limit=3)

    assert [row["document_id"] for row in fused] == [2, 1, 3]
    assert fused[0]["distance"] == 0.18


def test_user_kb_retrieve_node_uses_multi_query_path(monkeypatch):
    import app.agents.nodes.kb_chat.retrieve as retrieve_module

    captured: dict[str, object] = {}

    async def fake_build_queries(
        query: str,
        *,
        chat_history: list[dict[str, str]] | None = None,
        memory_summary: str | None = None,
    ):
        assert query == "How do I configure the generation model?"
        assert chat_history == []
        assert memory_summary is None
        return [
            "How do I configure the generation model?",
            "generation model config",
            "models.yaml generation model",
        ]

    async def fake_multi_query_retrieval(**kwargs):
        captured.update(kwargs)
        return {
            "retrieved_docs": [],
            "context": "",
            "kb_retrieval_status": "ok",
        }

    monkeypatch.setattr(retrieve_module, "build_kb_chat_retrieval_queries", fake_build_queries)
    monkeypatch.setattr(retrieve_module, "run_multi_query_kb_retrieval", fake_multi_query_retrieval)

    state = {
        "query": "How do I configure the generation model?",
        "knowledge_base_id": 9,
        "category_id": 4,
        "user_id": 42,
        "allowed_document_statuses": ["published"],
    }
    result = asyncio.run(user_kb_retrieve_node(state))

    assert result["kb_retrieval_status"] == "ok"
    assert result["retrieval_queries"] == [
        "How do I configure the generation model?",
        "generation model config",
        "models.yaml generation model",
    ]
    assert captured["query"] == "How do I configure the generation model?"
    assert captured["knowledge_base_id"] == 9
    assert captured["category_id"] == 4
    assert captured["document_statuses"] == ["published"]
