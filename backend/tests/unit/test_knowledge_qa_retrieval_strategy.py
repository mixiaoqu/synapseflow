import asyncio

from app.agents.knowledge_qa.nodes.plan_retrieval import (
    build_knowledge_qa_retrieval_plan,
)
from app.agents.knowledge_qa.nodes.retrieve import knowledge_qa_retrieve_node


async def _mark_all_covered(results, **_kwargs):
    return {
        "subtasks": [
            {
                "id": result["id"],
                "status": "covered",
                "failure_reason": "none",
                "reason": "证据满足要求",
                "discovered_terms": [],
            }
            for result in results
        ],
        "latency_ms": 1,
    }


def test_kb_chat_execution_plan_selects_strategy_from_question_type():
    definition_plan = build_knowledge_qa_retrieval_plan(
        question_type="definition_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )
    relationship_plan = build_knowledge_qa_retrieval_plan(
        question_type="relationship_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )
    summary_plan = build_knowledge_qa_retrieval_plan(
        question_type="summary_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )

    assert definition_plan["mode"] == "text_only"
    assert definition_plan["channels"]["vector"]["enabled"] is True
    assert definition_plan["channels"]["graph"]["enabled"] is False
    assert relationship_plan["mode"] == "graph_then_text"
    assert relationship_plan["channels"]["graph"]["enabled"] is True
    assert summary_plan["mode"] == "parallel_fusion"
    assert summary_plan["channels"]["graph"]["enabled"] is True


def test_kb_chat_execution_plan_uses_multi_hop_graph_for_dependency_queries():
    dependency_plan = build_knowledge_qa_retrieval_plan(
        question_type="dependency_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )

    assert dependency_plan["mode"] == "graph_then_text"
    assert dependency_plan["channels"]["graph"]["graph_mode"] == "relation_evidence"
    assert dependency_plan["channels"]["graph"]["max_hops"] == 3


def test_kb_chat_retrieve_text_only_runs_one_structured_subtask(monkeypatch):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    calls: list[str] = []

    async def fake_text_retrieval(**kwargs):
        calls.append(kwargs["query"])
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
            "retrieval_trace": {},
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_text_retrieval)
    monkeypatch.setattr(retrieve_module, "assess_subtask_coverage", _mark_all_covered)

    result = asyncio.run(
        knowledge_qa_retrieve_node(
            {
                "query": "Order 是什么？",
                "standalone_query": "Order 是什么？",
                "business_objects": ["Order"],
                "question_type": "definition_lookup",
                "retrieval_strategy": "text_only",
                "retrieval_execution_plan": {
                    "channels": {
                        "vector": {"recall_k": 8},
                        "lexical": {"lexical_k": 4},
                    },
                    "rerank": {"enabled": False},
                    "context": {
                        "final_top_k": 4,
                        "llm_reference_top_k": 4,
                        "budget_chars": 9000,
                    },
                },
                "retrieval_subtasks": [
                    {
                        "id": "task_1",
                        "goal": "解释 Order 的定义",
                        "semantic_queries": ["Order 是什么"],
                        "parameter_abstract_queries": [],
                        "lexical_terms": ["Order"],
                        "evidence_requirement": "文档明确给出 Order 的定义",
                    }
                ],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
            }
        )
    )

    assert calls == ["解释 Order 的定义"]
    assert result["retrieval_result"]["status"] == "found"
    assert result["retrieval_result"]["metrics"]["text_hit_count"] == 1
    assert result["retrieval_result"]["coverage_complete"] is True


def test_kb_chat_retrieve_runs_subtasks_independently(monkeypatch):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    calls: list[str] = []

    async def fake_text_retrieval(**kwargs):
        calls.append(kwargs["query"])
        return {
            "retrieved_docs": [
                {
                    "content": f"{kwargs['query']} 的证据",
                    "metadata": {
                        "source": "text",
                        "document_title": kwargs["query"],
                        "document_chunk_id": len(calls),
                    },
                }
            ],
            "retrieval_trace": {},
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_text_retrieval)
    monkeypatch.setattr(retrieve_module, "assess_subtask_coverage", _mark_all_covered)

    result = asyncio.run(
        knowledge_qa_retrieve_node(
            {
                "query": "介绍员工内购会员的权益和区别",
                "standalone_query": "介绍员工内购会员的权益配置及与其他会员的区别",
                "business_objects": ["员工内购会员"],
                "question_type": "summary_lookup",
                "retrieval_strategy": "text_only",
                "retrieval_execution_plan": {
                    "channels": {
                        "vector": {"recall_k": 16},
                        "lexical": {"lexical_k": 12},
                    },
                    "rerank": {"enabled": False},
                    "context": {
                        "final_top_k": 4,
                        "llm_reference_top_k": 4,
                        "budget_chars": 9000,
                    },
                },
                "retrieval_subtasks": [
                    {
                        "id": "task_1",
                        "goal": "员工内购会员的权益如何配置",
                        "semantic_queries": [],
                        "parameter_abstract_queries": [],
                        "lexical_terms": ["员工内购", "权益配置"],
                        "evidence_requirement": "说明权益配置方式",
                    },
                    {
                        "id": "task_2",
                        "goal": "员工内购会员与其他会员模式有什么区别",
                        "semantic_queries": [],
                        "parameter_abstract_queries": [],
                        "lexical_terms": ["员工内购", "会员模式"],
                        "evidence_requirement": "说明模式差异",
                    },
                ],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
            }
        )
    )

    assert calls == [
        "员工内购会员的权益如何配置",
        "员工内购会员与其他会员模式有什么区别",
    ]
    assert result["retrieval_result"]["metrics"]["text_hit_count"] == 2
    assert result["retrieval_result"]["coverage_complete"] is True


def test_kb_chat_retrieve_requests_one_replan_for_weak_evidence(monkeypatch):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    async def fake_text_retrieval(**_kwargs):
        return {
            "retrieved_docs": [
                {
                    "content": "会员类型页面包含员工内购模式。",
                    "metadata": {
                        "source": "text",
                        "document_title": "会员类型操作指南",
                        "section_path": "员工内购模式",
                        "document_chunk_id": 9,
                    },
                }
            ],
            "retrieval_trace": {},
        }

    async def fake_coverage(results, **_kwargs):
        return {
            "subtasks": [
                {
                    "id": results[0]["id"],
                    "status": "weak",
                    "failure_reason": "terminology_mismatch",
                    "reason": "文档使用员工内购模式，而查询使用员工内购模块。",
                    "discovered_terms": ["员工内购模式", "内购会员"],
                }
            ],
            "latency_ms": 1,
        }

    monkeypatch.setattr(retrieve_module, "run_kb_channel_text_retrieval", fake_text_retrieval)
    monkeypatch.setattr(retrieve_module, "assess_subtask_coverage", fake_coverage)

    result = asyncio.run(
        knowledge_qa_retrieve_node(
            {
                "query": "员工内购模块是什么",
                "standalone_query": "员工内购模块是什么",
                "business_objects": ["员工内购模块"],
                "query_plan_attempt": 1,
                "retrieval_strategy": "text_only",
                "retrieval_execution_plan": {
                    "channels": {
                        "vector": {"recall_k": 8},
                        "lexical": {"lexical_k": 6},
                    },
                    "rerank": {"enabled": False},
                    "context": {
                        "final_top_k": 4,
                        "llm_reference_top_k": 4,
                        "budget_chars": 9000,
                    },
                },
                "retrieval_subtasks": [
                    {
                        "id": "task_1",
                        "goal": "解释员工内购模块",
                        "semantic_queries": ["员工内购模块定义"],
                        "parameter_abstract_queries": [],
                        "lexical_terms": ["员工内购模块"],
                        "evidence_requirement": "说明定义和作用",
                    }
                ],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
            }
        )
    )

    assert result["should_replan"] is True
    assert result["retrieval_result"]["status"] == "replan_required"
    assert result["retrieval_feedback"]["failed_subtasks"][0]["discovered_terms"] == [
        "员工内购模式",
        "内购会员",
    ]


def test_kb_chat_retrieve_answers_supported_partial_evidence_without_replan(
    monkeypatch,
):
    import app.agents.knowledge_qa.nodes.retrieve as retrieve_module

    async def fake_text_retrieval(**_kwargs):
        return {
            "retrieved_docs": [
                {
                    "content": "在权益中心编辑 PLUS权益名称和PLUS权益内容。",
                    "metadata": {
                        "source": "text",
                        "document_title": "权益中心操作指南",
                        "section_path": "编辑权益内容",
                        "document_chunk_id": 10,
                    },
                },
                {
                    "content": "会员列表显示PLUS会员到期时间。",
                    "metadata": {
                        "source": "text",
                        "document_title": "会员列表操作指南",
                        "section_path": "列表字段",
                        "document_chunk_id": 11,
                    },
                },
            ],
            "retrieval_trace": {},
        }

    async def fake_coverage(results, **_kwargs):
        return {
            "subtasks": [
                {
                    "id": results[0]["id"],
                    "status": "partial",
                    "failure_reason": "insufficient_evidence",
                    "reason": "可以回答权益配置，但没有开通流程。",
                    "supported_evidence_indices": [1],
                    "supported_claims": ["PLUS权益名称和内容在权益中心编辑。"],
                    "discovered_terms": ["权益中心", "PLUS权益"],
                }
            ],
            "latency_ms": 1,
        }

    monkeypatch.setattr(
        retrieve_module,
        "run_kb_channel_text_retrieval",
        fake_text_retrieval,
    )
    monkeypatch.setattr(
        retrieve_module,
        "assess_subtask_coverage",
        fake_coverage,
    )

    result = asyncio.run(
        knowledge_qa_retrieve_node(
            {
                "query": "Plus会员如何设置",
                "standalone_query": "Plus会员如何设置",
                "business_objects": ["Plus会员"],
                "query_plan_attempt": 1,
                "retrieval_strategy": "text_only",
                "retrieval_execution_plan": {
                    "channels": {
                        "vector": {"recall_k": 8},
                        "lexical": {"lexical_k": 6},
                    },
                    "rerank": {"enabled": False},
                    "context": {
                        "final_top_k": 4,
                        "llm_reference_top_k": 4,
                        "budget_chars": 9000,
                    },
                },
                "retrieval_subtasks": [
                    {
                        "id": "task_1",
                        "goal": "查找Plus会员设置方法",
                        "semantic_queries": ["付费会员配置"],
                        "parameter_abstract_queries": [],
                        "lexical_terms": ["Plus会员", "付费会员"],
                        "evidence_requirement": "说明可配置内容和操作入口",
                    }
                ],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
            }
        )
    )

    subtask_result = result["retrieval_result"]["subtask_results"][0]
    assert result["should_replan"] is False
    assert result["retrieval_result"]["status"] == "found"
    assert result["retrieval_result"]["coverage_complete"] is False
    assert result["retrieval_result"]["metrics"]["primary_count"] == 1
    assert subtask_result["answerable"] is True
    assert subtask_result["coverage_status"] == "partial"
    assert subtask_result["supported_claims"] == [
        "PLUS权益名称和内容在权益中心编辑。"
    ]
