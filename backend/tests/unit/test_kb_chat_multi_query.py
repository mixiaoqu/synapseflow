import asyncio

from app.agents.nodes.kb_chat.retrieve import user_kb_retrieve_node
from app.agents.nodes.kb_chat.rewrite_query import user_kb_rewrite_query_node
from app.services.vector_store import reciprocal_rank_fusion_many


def test_reciprocal_rank_fusion_many_merges_multiple_rankings():
    rank_a = [
        {
            "chunk_text": "alpha",
            "document_id": 1,
            "document_chunk_id": 101,
            "chunk_index": 0,
            "distance": 0.11,
            "document_title": "Doc A",
            "metadata": {},
        },
        {
            "chunk_text": "beta",
            "document_id": 2,
            "document_chunk_id": 102,
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
            "document_chunk_id": 102,
            "chunk_index": 0,
            "distance": 0.18,
            "document_title": "Doc B",
            "metadata": {},
        },
        {
            "chunk_text": "gamma",
            "document_id": 3,
            "document_chunk_id": 103,
            "chunk_index": 0,
            "distance": 0.15,
            "document_title": "Doc C",
            "metadata": {},
        },
    ]

    fused = reciprocal_rank_fusion_many([rank_a, rank_b], rrf_k=60, limit=3)

    assert [row["document_id"] for row in fused] == [2, 1, 3]
    assert fused[0]["distance"] == 0.18


def test_user_kb_rewrite_query_node_uses_llm_plan(monkeypatch):
    import app.agents.nodes.kb_chat.rewrite_query as rewrite_module

    captured: dict[str, object] = {}

    async def fake_build_queries(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return [
            "How do I configure the generation model?",
            "generation model config",
            "models.yaml generation model",
        ]

    monkeypatch.setattr(rewrite_module, "build_kb_chat_retrieval_queries", fake_build_queries)

    state = {
        "query": "How do I configure the generation model?",
        "chat_history": [],
        "memory_summary": None,
        "retrieval_plan": {
            "retrieval_required": True,
            "rewrite": {
                "enabled": True,
                "mode": "llm",
                "max_queries": 3,
                "strategies": ["multi_aspect_split", "terminology_normalization"],
            },
        },
    }

    result = asyncio.run(user_kb_rewrite_query_node(state))

    assert result["retrieval_queries"][1] == "generation model config"
    assert result["rewrite_trace"]["engine"] == "llm"
    assert result["rewrite_trace"]["query_count"] == 3
    assert captured["mode"] == "llm"
    assert captured["max_queries"] == 3
    assert captured["strategies"] == ["multi_aspect_split", "terminology_normalization"]


def test_user_kb_retrieve_node_uses_multi_query_path(monkeypatch):
    import app.agents.nodes.kb_chat.retrieve as retrieve_module

    captured: dict[str, object] = {}

    async def fake_multi_query_retrieval(**kwargs):
        captured.update(kwargs)
        return {
            "retrieved_docs": [],
            "context": "",
            "kb_retrieval_status": "ok",
        }

    monkeypatch.setattr(retrieve_module, "run_multi_query_kb_retrieval", fake_multi_query_retrieval)

    state = {
        "query": "How do I configure the generation model?",
        "knowledge_base_id": 9,
        "category_id": 4,
        "user_id": 42,
        "allowed_document_statuses": ["published"],
        "retrieval_queries": [
            "How do I configure the generation model?",
            "generation model config",
            "models.yaml generation model",
        ],
        "retrieval_plan": {
            "retrieval_required": True,
            "retrieval": {
                "mode": "hybrid",
                "recall_k": 14,
                "lexical_k": 8,
                "rerank_enabled": True,
                "final_top_k": 6,
                "llm_reference_top_k": 4,
                "context_budget": 9000,
            },
        },
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
    assert captured["result_limit"] == 6
    assert captured["llm_reference_top_k"] == 4
    assert captured["context_budget"] == 9000
    assert captured["document_statuses"] == ["published"]
    assert captured["retrieval_mode"] == "hybrid"
    assert captured["rerank_enabled"] is True


def test_user_kb_retrieve_node_skips_when_plan_disables_retrieval():
    state = {
        "query": "hello",
        "retrieval_plan": {
            "retrieval_required": False,
            "plan_name": "chitchat",
            "reason": "Greeting only.",
        },
    }

    result = asyncio.run(user_kb_retrieve_node(state))

    assert result["kb_retrieval_status"] == "skipped"
    assert result["retrieved_docs"] == []
    assert result["kb_retrieval_status"] == "skipped"
