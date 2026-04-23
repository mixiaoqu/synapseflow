import asyncio
from types import SimpleNamespace

from app.agents.nodes.kb_chat.plan_query import (
    build_adaptive_policy,
    build_llm_adaptive_policy,
)


class FakePlannerLlm:
    def __init__(self, content: str | Exception) -> None:
        self.content = content

    async def ainvoke(self, prompt: str):
        assert "Current user question:" in prompt
        if isinstance(self.content, Exception):
            raise self.content
        return SimpleNamespace(content=self.content)


def test_build_adaptive_policy_maps_complex_comparison():
    policy = build_adaptive_policy(
        query="正式员工和外包人员的报销规则有什么区别？",
        intent="comparison",
        complexity="complex",
        reason="用户要求比较多个对象的制度差异。",
    )

    assert policy == {
        "intent": "comparison",
        "complexity": "complex",
        "retrieval_required": True,
        "max_queries": 4,
        "result_limit": 12,
        "context_budget": 12000,
        "reason": "用户要求比较多个对象的制度差异。",
    }


def test_build_adaptive_policy_allows_pure_chitchat_to_skip_retrieval():
    policy = build_adaptive_policy(
        query="早上好",
        intent="chitchat",
        complexity="simple",
        reason="纯寒暄。",
    )

    assert policy["retrieval_required"] is False
    assert policy["max_queries"] == 0
    assert policy["result_limit"] == 0
    assert policy["context_budget"] == 0


def test_build_adaptive_policy_trusts_planner_chitchat_label():
    policy = build_adaptive_policy(
        query="你好，报销标准是什么？",
        intent="chitchat",
        complexity="simple",
        reason="寒暄。",
    )

    assert policy["intent"] == "chitchat"
    assert policy["complexity"] == "simple"
    assert policy["retrieval_required"] is False
    assert policy["max_queries"] == 0


def test_build_adaptive_policy_skips_out_of_scope_retrieval():
    policy = build_adaptive_policy(
        query="帮我写一首诗",
        intent="out_of_scope",
        complexity="normal",
        reason="用户请求不属于知识库问答。",
    )

    assert policy["intent"] == "out_of_scope"
    assert policy["retrieval_required"] is False
    assert policy["max_queries"] == 0
    assert policy["result_limit"] == 0
    assert policy["context_budget"] == 0


def test_build_llm_adaptive_policy_parses_llm_labels():
    policy = asyncio.run(
        build_llm_adaptive_policy(
            "差旅报销怎么申请？",
            llm_factory=lambda: FakePlannerLlm(
                '{"intent":"procedural","complexity":"normal","reason":"用户询问流程。"}'
            ),
        )
    )

    assert policy["intent"] == "procedural"
    assert policy["complexity"] == "normal"
    assert policy["result_limit"] == 8
    assert policy["reason"] == "用户询问流程。"


def test_build_llm_adaptive_policy_falls_back_on_llm_error():
    policy = asyncio.run(
        build_llm_adaptive_policy(
            "报销标准是什么？",
            llm_factory=lambda: FakePlannerLlm(RuntimeError("planner unavailable")),
        )
    )

    assert policy["intent"] == "kb_lookup"
    assert policy["complexity"] == "normal"
    assert policy["retrieval_required"] is True
    assert policy["reason"] == "Fallback default policy."
