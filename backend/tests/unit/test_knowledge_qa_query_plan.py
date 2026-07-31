import asyncio
from types import SimpleNamespace

from app.agents.knowledge_qa.query_plan import build_knowledge_query_plan


class _FakePlanner:
    def __init__(self, content: str):
        self.content = content

    async def ainvoke(self, _prompt: str):
        return SimpleNamespace(content=self.content)


def test_query_plan_preserves_original_and_adds_parameter_abstract_query():
    result = asyncio.run(
        build_knowledge_query_plan(
            "查询满1000减50活动的配置方法",
            original_query="满1000减50怎么弄",
            llm_factory=lambda: _FakePlanner(
                """
                {
                  "question_type": "attribute_lookup",
                  "retrieval_complexity": "standard",
                  "standalone_query": "满1000减50的活动如何配置",
                  "business_objects": ["满减活动"],
                  "action": "创建活动",
                  "parameters": {"threshold": 1000, "discount": 50},
                  "ambiguity": {"needs_clarification": false},
                  "subtasks": [{
                    "goal": "查找满减活动的创建入口和配置方法",
                    "semantic_queries": ["营销活动中心满减活动配置步骤"],
                    "parameter_abstract_queries": ["满减活动创建入口", "满减规则设置流程"],
                    "lexical_terms": ["满减活动", "创建活动", "活动管理"],
                    "evidence_requirement": "文档明确说明创建入口或配置步骤"
                  }]
                }
                """
            ),
        )
    )

    assert result["semantic_queries"] == [
        "满1000减50怎么弄",
        "满1000减50的活动如何配置",
        "查找满减活动的创建入口和配置方法",
        "营销活动中心满减活动配置步骤",
        "满减活动创建入口",
        "满减规则设置流程",
    ]
    assert result["query_parameters"] == {"threshold": 1000, "discount": 50}
    assert result["retrieval_subtasks"][0]["parameter_abstract_queries"] == [
        "满减活动创建入口",
        "满减规则设置流程",
    ]
    assert result["query_plan_trace"]["original_query_preserved"] is True
    assert result["query_plan_trace"]["subtask_count"] == 1


def test_query_plan_requests_clarification_when_meaning_changes_the_answer():
    result = asyncio.run(
        build_knowledge_query_plan(
            "控销设置中的仅限怎么设置",
            original_query="控销设置，仅限怎么设置",
            llm_factory=lambda: _FakePlanner(
                """
                {
                  "question_type": "attribute_lookup",
                  "retrieval_complexity": "standard",
                  "standalone_query": "控销设置中的仅限如何设置",
                  "business_objects": ["控销设置"],
                  "action": "设置仅限规则",
                  "parameters": {},
                  "ambiguity": {
                    "needs_clarification": true,
                    "clarification_question": "你说的“仅限”是指仅限门店、商品还是会员？",
                    "candidates": ["仅限门店", "仅限商品", "仅限会员"]
                  },
                  "subtasks": []
                }
                """
            ),
        )
    )

    assert result["semantic_queries"][0] == "控销设置，仅限怎么设置"
    assert result["ambiguity"]["needs_clarification"] is True
    assert result["retrieval_subtasks"] == []


def test_query_plan_replans_failed_subtask_with_retrieval_feedback():
    result = asyncio.run(
        build_knowledge_query_plan(
            "了解员工内购模块的定义",
            original_query="员工内购模块是什么",
            attempt=2,
            previous_plan={
                "standalone_query": "员工内购模块是什么",
                "business_objects": ["员工内购模块"],
                "action": "了解定义",
                "query_parameters": {},
                "ambiguity": {"needs_clarification": False},
            },
            retrieval_feedback={
                "failed_subtasks": [
                    {
                        "id": "task_1",
                        "goal": "解释员工内购模块",
                    }
                ],
                "used_queries": ["员工内购模块定义"],
            },
            llm_factory=lambda: _FakePlanner(
                """
                {
                  "question_type": "definition_lookup",
                  "retrieval_complexity": "standard",
                  "standalone_query": "不应覆盖原问题",
                  "business_objects": ["不应覆盖"],
                  "action": "不应覆盖",
                  "parameters": {},
                  "ambiguity": {"needs_clarification": false},
                  "subtasks": [{
                    "goal": "解释员工内购会员模式",
                    "semantic_queries": [
                      "员工内购模块定义",
                      "员工内购模式的定义和作用"
                    ],
                    "parameter_abstract_queries": ["内购会员模式说明"],
                    "lexical_terms": ["员工内购模式", "内购会员"],
                    "evidence_requirement": "说明员工内购模式的定义和作用"
                  }]
                }
                """
            ),
        )
    )

    assert result["standalone_query"] == "员工内购模块是什么"
    assert result["business_objects"] == ["员工内购模块"]
    assert result["query_plan_attempt"] == 2
    assert result["retrieval_subtasks"][0]["id"] == "task_1"
    assert result["retrieval_subtasks"][0]["semantic_queries"] == [
        "员工内购模式的定义和作用"
    ]


def test_query_plan_allows_replan_to_split_one_failed_subtask():
    result = asyncio.run(
        build_knowledge_query_plan(
            "设置满减活动",
            original_query="满1000减49怎么设置",
            attempt=2,
            previous_plan={
                "standalone_query": "满1000减49怎么设置",
                "business_objects": ["满减活动"],
                "action": "设置",
                "query_parameters": {"threshold": 1000, "discount": 49},
                "ambiguity": {"needs_clarification": False},
            },
            retrieval_feedback={
                "failed_subtasks": [{"id": "task_1", "goal": "查找满减设置方法"}],
                "used_queries": ["满减活动设置"],
            },
            llm_factory=lambda: _FakePlanner(
                """
                {
                  "question_type": "flow_lookup",
                  "retrieval_complexity": "standard",
                  "standalone_query": "不应覆盖原问题",
                  "business_objects": ["不应覆盖"],
                  "action": "不应覆盖",
                  "parameters": {},
                  "ambiguity": {"needs_clarification": false},
                  "subtasks": [
                    {
                      "goal": "查找满减活动入口",
                      "semantic_queries": ["促销活动创建入口"],
                      "parameter_abstract_queries": [],
                      "lexical_terms": ["促销活动", "满减优惠"],
                      "evidence_requirement": "说明满减活动入口"
                    },
                    {
                      "goal": "查找满减字段设置方法",
                      "semantic_queries": ["满足金额与优惠金额设置"],
                      "parameter_abstract_queries": [],
                      "lexical_terms": ["满足金额", "优惠金额"],
                      "evidence_requirement": "说明两个金额字段的含义和保存方式"
                    }
                  ]
                }
                """
            ),
        )
    )

    assert [item["id"] for item in result["retrieval_subtasks"]] == [
        "task_1",
        "task_2",
    ]
    assert result["replan_exhausted"] is False


def test_query_plan_stops_retry_when_no_new_subtask_is_available():
    result = asyncio.run(
        build_knowledge_query_plan(
            "设置满减活动",
            original_query="满1000减49怎么设置",
            attempt=2,
            previous_plan={
                "standalone_query": "满1000减49怎么设置",
                "business_objects": ["满减活动"],
                "action": "设置",
                "query_parameters": {"threshold": 1000, "discount": 49},
                "ambiguity": {"needs_clarification": False},
            },
            retrieval_feedback={
                "failed_subtasks": [{"id": "task_1", "goal": "查找满减设置方法"}],
                "used_queries": ["满减活动设置"],
            },
            llm_factory=lambda: _FakePlanner(
                """
                {
                  "question_type": "flow_lookup",
                  "retrieval_complexity": "standard",
                  "standalone_query": "不应覆盖原问题",
                  "business_objects": ["不应覆盖"],
                  "action": "不应覆盖",
                  "parameters": {},
                  "ambiguity": {"needs_clarification": false},
                  "subtasks": []
                }
                """
            ),
        )
    )

    assert result["retrieval_subtasks"] == []
    assert result["replan_exhausted"] is True
