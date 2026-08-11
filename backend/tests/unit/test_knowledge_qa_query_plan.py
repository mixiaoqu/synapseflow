import asyncio

from app.agents.knowledge_qa.query_plan import build_knowledge_query_plan


class _FakePlanner:
    def __init__(self, content: str):
        self.content = content

    async def ainvoke(self, _prompt):
        return type("Response", (), {"content": self.content})()


def test_query_plan_preserves_goal_and_limits_retrieval_expressions():
    result = asyncio.run(
        build_knowledge_query_plan(
            "满1000减50活动如何配置",
            llm_factory=lambda: _FakePlanner(
                """{
                  "normalized_query": "满1000减50活动如何配置",
                  "retrieval_profile": "standard",
                  "semantic_queries": ["满减活动设置", "订单优惠规则", "营销活动满减", "多余查询"],
                  "lexical_terms": ["满减活动", "门槛金额", "优惠金额", "多余词"],
                  "reason": "保留活动门槛与优惠金额"
                }"""
            ),
        )
    )

    assert result["semantic_queries"] == [
        "满1000减50活动如何配置",
        "满减活动设置",
        "订单优惠规则",
    ]
    assert result["lexical_terms"] == ["满减活动", "门槛金额", "优惠金额"]
    assert result["normalized_query"] == "满1000减50活动如何配置"
    assert result["retrieval_profile"] == "standard"


def test_query_plan_rewrite_excludes_queries_already_executed():
    result = asyncio.run(
        build_knowledge_query_plan(
            "员工内购模块是什么",
            attempt=2,
            previous_plan={
                "normalized_query": "员工内购模块是什么",
                "retrieval_profile": "standard",
            },
            retrieval_feedback={"used_queries": ["员工内购模块是什么", "员工内购模块定义"]},
            llm_factory=lambda: _FakePlanner(
                """{
                  "semantic_queries": ["员工内购模块定义", "员工内购会员模式说明"],
                  "lexical_terms": ["员工内购模式"],
                  "retrieval_profile": "broad"
                }"""
            ),
        )
    )

    assert result["semantic_queries"] == ["员工内购会员模式说明"]
    assert result["lexical_terms"] == ["员工内购模式"]
    assert result["normalized_query"] == "员工内购模块是什么"
    assert result["retrieval_profile"] == "standard"
    assert result["replan_exhausted"] is False


def test_query_plan_stops_retry_when_no_new_expression_is_available():
    result = asyncio.run(
        build_knowledge_query_plan(
            "员工内购模块是什么",
            attempt=2,
            previous_plan={"normalized_query": "员工内购模块是什么"},
            retrieval_feedback={"used_queries": ["员工内购模块定义", "员工内购模块"]},
            llm_factory=lambda: _FakePlanner(
                '{"semantic_queries":["员工内购模块定义"],"lexical_terms":["员工内购模块"]}'
            ),
        )
    )

    assert result["semantic_queries"] == []
    assert result["lexical_terms"] == []
    assert result["replan_exhausted"] is True
