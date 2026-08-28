import asyncio

from app.agents.knowledge_qa.nodes.plan_retrieval import build_knowledge_qa_retrieval_plan
from app.agents.knowledge_qa.nodes.retrieve import knowledge_qa_retrieve_node


def _state(**overrides):
    state = {
        "query": "Order 是什么？",
        "normalized_query": "Order 定义",
        "semantic_queries": ["Order 是什么", "Order 订单模型"],
        "lexical_terms": ["Order"],
        "query_plan_attempt": 1,
        "retrieval_strategy": "text_only",
        "retrieval_execution_plan": {
            "channels": {"vector": {"recall_k": 8}, "lexical": {"lexical_k": 4}},
            "rerank": {"enabled": True},
            "context": {"final_top_k": 4, "llm_reference_top_k": 4, "budget_chars": 9000},
        },
        "team_id": 1,
        "knowledge_base_id": 1,
        "allowed_document_statuses": [],
    }
    state.update(overrides)
    return state


def test_execution_plan_uses_validated_text_retrieval_profile():
    plan = build_knowledge_qa_retrieval_plan(retrieval_profile="standard")

    assert plan["mode"] == "text_only"
    assert plan["retrieval_profile"] == "standard"
    assert set(plan["channels"]) == {"vector", "lexical"}


def test_retrieve_runs_one_channel_request_for_one_goal(monkeypatch):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    calls = []

    async def fake_retrieval(**kwargs):
        calls.append(kwargs)
        return {
            "retrieved_docs": [{
                "content": "Order 是订单模型。",
                "metadata": {"document_chunk_id": 1, "document_title": "Order model"},
            }],
            "semantic_queries": kwargs["semantic_queries"],
            "lexical_terms": kwargs["lexical_terms"],
            "retrieval_trace": {"merged_candidate_count": 1, "rerank": {"output_count": 1}},
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_retrieval)
    result = asyncio.run(knowledge_qa_retrieve_node(_state()))

    assert len(calls) == 1
    assert calls[0]["semantic_queries"] == ["Order 是什么", "Order 订单模型"]
    assert calls[0]["lexical_terms"] == ["Order"]
    assert result["retrieval_result"]["status"] == "found"


def test_missed_goal_requests_only_one_rewrite(monkeypatch):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    async def fake_retrieval(**kwargs):
        return {
            "retrieved_docs": [],
            "semantic_queries": kwargs["semantic_queries"],
            "lexical_terms": kwargs["lexical_terms"],
            "kb_retrieval_status": "no_hits",
            "retrieval_trace": {},
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_retrieval)
    first = asyncio.run(knowledge_qa_retrieve_node(_state()))
    second = asyncio.run(knowledge_qa_retrieve_node(_state(query_plan_attempt=2)))

    assert first["should_replan"] is True
    assert first["retrieval_result"]["status"] == "replan_required"
    assert second["should_replan"] is False
    assert second["retrieval_result"]["status"] == "no_hits"


def test_retrieved_facts_are_answerable_without_completeness_gate(monkeypatch):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    async def fake_retrieval(**kwargs):
        return {
            "retrieved_docs": [
                {"content": "在权益中心编辑 PLUS 权益。", "metadata": {"document_chunk_id": 10}},
                {"content": "会员列表显示到期时间。", "metadata": {"document_chunk_id": 11}},
            ],
            "semantic_queries": kwargs["semantic_queries"],
            "lexical_terms": kwargs["lexical_terms"],
            "retrieval_trace": {},
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_retrieval)
    result = asyncio.run(knowledge_qa_retrieve_node(_state()))

    assert result["should_replan"] is False
    assert result["retrieval_result"]["status"] == "found"
    assert result["retrieval_result"]["metrics"]["primary_count"] == 2
