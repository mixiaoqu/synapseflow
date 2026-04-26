import asyncio
from types import SimpleNamespace

from app.agents.nodes.kb_chat.plan_query import (
    build_llm_retrieval_plan,
    build_retrieval_plan,
    user_kb_plan_query_node,
)


class FakePlannerLlm:
    def __init__(self, content: str | Exception) -> None:
        self.content = content

    async def ainvoke(self, prompt: str):
        assert "Current user question:" in prompt
        if isinstance(self.content, Exception):
            raise self.content
        return SimpleNamespace(content=self.content)


def test_build_retrieval_plan_maps_compare_lookup():
    plan = build_retrieval_plan(
        plan_name="compare_lookup",
        reason="The user asks for differences across two policies.",
    )

    assert plan["plan_name"] == "compare_lookup"
    assert plan["retrieval_required"] is True
    assert plan["rewrite"]["mode"] == "llm"
    assert plan["rewrite"]["max_queries"] == 3
    assert plan["retrieval"]["mode"] == "hybrid"
    assert plan["retrieval"]["rerank_enabled"] is True
    assert plan["answer"]["response_mode"] == "grounded"


def test_build_retrieval_plan_maps_chitchat_to_no_retrieval():
    plan = build_retrieval_plan(
        plan_name="chitchat",
        reason="Pure greeting without a KB question.",
    )

    assert plan["retrieval_required"] is False
    assert plan["rewrite"]["mode"] == "skip"
    assert plan["retrieval"]["mode"] == "none"
    assert plan["answer"]["response_mode"] == "chitchat"


def test_build_llm_retrieval_plan_parses_llm_route():
    plan = asyncio.run(
        build_llm_retrieval_plan(
            "How do I submit a reimbursement request?",
            llm_factory=lambda: FakePlannerLlm(
                '{"plan_name":"procedural_lookup","reason":"Asks for workflow steps."}'
            ),
        )
    )

    assert plan["plan_name"] == "procedural_lookup"
    assert plan["rewrite"]["mode"] == "heuristic"
    assert plan["retrieval"]["mode"] == "hybrid"
    assert plan["reason"] == "Asks for workflow steps."


def test_user_kb_plan_query_node_falls_back_to_default_plan_on_llm_error(monkeypatch):
    import app.agents.nodes.kb_chat.plan_query as plan_module

    async def fake_build_llm_retrieval_plan(*args, **kwargs):
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(plan_module, "build_llm_retrieval_plan", fake_build_llm_retrieval_plan)

    result = asyncio.run(
        user_kb_plan_query_node(
            {
                "query": "What is the vacation policy?",
                "chat_history": [],
                "memory_summary": None,
            }
        )
    )

    assert result["retrieval_plan"]["plan_name"] == "fast_lookup"
    assert result["retrieval_plan"]["retrieval"]["mode"] == "vector"
