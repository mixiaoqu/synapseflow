import asyncio

from app.agents.nodes.kb_chat.analyze import build_kb_chat_execution_plan
from app.agents.nodes.kb_chat.retrieve import kb_chat_retrieve_node


def test_kb_chat_execution_plan_selects_strategy_from_question_type():
    definition_plan = build_kb_chat_execution_plan(
        question_type="definition_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )
    relationship_plan = build_kb_chat_execution_plan(
        question_type="relationship_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )
    summary_plan = build_kb_chat_execution_plan(
        question_type="summary_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )

    assert definition_plan["retrieval_strategy"] == "text_then_graph"
    assert definition_plan["text_enabled"] is True
    assert definition_plan["graph_enabled"] is True
    assert relationship_plan["retrieval_strategy"] == "graph_then_text"
    assert relationship_plan["text_enabled"] is True
    assert relationship_plan["graph_enabled"] is True
    assert summary_plan["retrieval_strategy"] == "parallel_fusion"
    assert summary_plan["text_enabled"] is True
    assert summary_plan["graph_enabled"] is True


def test_kb_chat_retrieve_text_only_runs_only_text_channel(monkeypatch):
    import app.agents.nodes.kb_chat.retrieve as retrieve_module

    calls: list[str] = []

    async def fake_text_retrieval(**kwargs):
        calls.append("text")
        return {
            "retrieved_docs": [
                {
                    "content": "Order 是订单模型。",
                    "metadata": {
                        "source": "text",
                        "document_title": "Order model",
                        "document_chunk_id": 1,
                    },
                }
            ],
            "retrieval_trace": {"rerank": {}, "total_latency_ms": 3},
        }

    async def fake_graph_retrieve(self, **kwargs):  # pragma: no cover
        calls.append("graph")
        raise AssertionError("graph retrieval should not run for text_only")

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_text_retrieval)
    monkeypatch.setattr(retrieve_module.GraphRetriever, "retrieve", fake_graph_retrieve)

    result = asyncio.run(
        kb_chat_retrieve_node(
            {
                "query": "Order 是什么？",
                "question_type": "definition_lookup",
                "retrieval_strategy": "text_only",
                "retrieval_execution_plan": {
                    "retrieval_strategy": "text_only",
                    "text_enabled": True,
                    "graph_enabled": False,
                    "channels": {
                        "vector": {"recall_k": 8},
                        "lexical": {"lexical_k": 4},
                        "graph": {"enabled": False, "limit": 0},
                    },
                    "rerank": {"enabled": False},
                    "context": {"final_top_k": 4, "llm_reference_top_k": 4, "budget_chars": 9000},
                },
                "semantic_queries": ["Order 是什么"],
                "lexical_terms": ["Order"],
                "candidate_entities": ["Order"],
                "chat_history": [],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
            }
        )
    )

    assert calls == ["text"]
    assert result["retrieval_trace"]["retrieval_strategy"] == "text_only"
    assert result["retrieval_trace"]["text"]["text_hits"] == 1
    assert result["retrieval_trace"]["graph"]["graph_used"] is False
    assert result["primary_evidence_docs"][0]["metadata"]["source"] == "text"


def test_kb_chat_retrieve_graph_only_runs_only_graph_channel(monkeypatch):
    import app.agents.nodes.kb_chat.retrieve as retrieve_module

    calls: list[str] = []

    async def fake_text_retrieval(**kwargs):  # pragma: no cover
        calls.append("text")
        raise AssertionError("text retrieval should not run for graph_only")

    async def fake_graph_retrieve(self, **kwargs):
        calls.append("graph")
        return {
            "retrieved_docs": [],
            "graph_facts": {
                "text": [
                    {
                        "content": "Order 通过 user_id 关联 User。",
                        "document_title": "Order -> User",
                        "document_chunk_id": 2,
                        "graph_mode": "relation_evidence",
                        "evidence": "Order.user_id -> User.id",
                        "matched_entities": ["Order", "User"],
                    }
                ],
                "entities": [],
                "relations": [
                    {
                        "source": {"normalized_name": "order", "display_name": "Order"},
                        "target": {"normalized_name": "user", "display_name": "User"},
                        "relation_type": "RELATED_TO",
                        "evidence": "Order.user_id -> User.id",
                    }
                ],
                "paths": [],
                "evidence": [],
            },
            "trace": {"graph_used": True, "graph_hits": 1, "latency_ms": 2},
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_text_retrieval)
    monkeypatch.setattr(retrieve_module.GraphRetriever, "retrieve", fake_graph_retrieve)
    async def fake_resolve_graph_candidate_entities(**kwargs):
        return {
            "candidate_entities": ["Order", "User"],
            "trace": {"resolved_entities": ["Order", "User"]},
        }

    monkeypatch.setattr(
        retrieve_module,
        "resolve_graph_candidate_entities",
        fake_resolve_graph_candidate_entities,
    )

    result = asyncio.run(
        kb_chat_retrieve_node(
            {
                "query": "Order 和 User 什么关系？",
                "question_type": "relationship_lookup",
                "retrieval_strategy": "graph_only",
                "retrieval_execution_plan": {
                    "retrieval_strategy": "graph_only",
                    "text_enabled": False,
                    "graph_enabled": True,
                    "channels": {
                        "vector": {"enabled": False, "recall_k": 0},
                        "lexical": {"enabled": False, "lexical_k": 0},
                        "graph": {"enabled": True, "limit": 4, "graph_mode": "relation_evidence"},
                    },
                    "rerank": {"enabled": False},
                    "context": {"final_top_k": 4, "llm_reference_top_k": 4, "budget_chars": 9000},
                },
                "semantic_queries": ["Order User relation"],
                "lexical_terms": ["Order", "User"],
                "candidate_entities": ["Order", "User"],
                "relation_pairs": [],
                "relation_queries": [],
                "chat_history": [],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
            }
        )
    )

    assert calls == ["graph"]
    assert result["retrieval_trace"]["retrieval_strategy"] == "graph_only"
    assert result["retrieval_trace"]["text"]["skipped"] is True
    assert result["retrieval_trace"]["graph"]["graph_hits"] == 1
    assert result["primary_evidence_docs"][0]["metadata"]["source"] == "graph"
