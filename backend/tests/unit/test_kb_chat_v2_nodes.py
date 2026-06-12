import asyncio
from types import SimpleNamespace

from app.agents.graphs.kb_chat_v2_graph import create_kb_chat_v2_graph
from app.agents.nodes.kb_chat_v2.analyze import (
    build_kb_chat_v2_execution_plan,
    kb_chat_v2_analyze_node,
)
from app.agents.nodes.kb_chat_v2.answer import (
    KB_V2_CHITCHAT_REPLY,
    build_kb_chat_v2_answer_text,
)
from app.agents.nodes.kb_chat_v2.entity_grounding import kb_chat_v2_entity_grounding_node
from app.agents.nodes.kb_chat_v2.evaluate import (
    evaluate_retrieval_evidence,
    kb_chat_v2_evaluate_node,
)
from app.agents.nodes.kb_chat_v2.retrieve import (
    _doc_key,
    _merge_text_and_graph_docs,
    kb_chat_v2_retrieve_node,
)
from app.agents.nodes.kb_chat_v2.rewrite_query import build_kb_chat_v2_rewrite
from app.agents.nodes.kb_chat_v2.route import kb_chat_v2_route_node


class FakeJsonLlm:
    def __init__(self, content: str | Exception) -> None:
        self.content = content
        self.prompts: list[str] = []

    async def ainvoke(self, prompt: str):
        self.prompts.append(prompt)
        if isinstance(self.content, Exception):
            raise self.content
        return SimpleNamespace(content=self.content)

    async def astream(self, prompt: str):
        self.prompts.append(prompt)
        if isinstance(self.content, Exception):
            raise self.content
        yield SimpleNamespace(content=str(self.content))


class UnexpectedAnswerLlm:
    async def ainvoke(self, prompt: str):  # pragma: no cover
        raise AssertionError("answer LLM should not be called")


class FakeAnswerLlm:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompts: list[str] = []

    async def ainvoke(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.content)

    async def astream(self, prompt: str):
        self.prompts.append(prompt)
        yield SimpleNamespace(content=self.content)


def test_kb_chat_v2_graph_routes_chitchat_directly_to_answer():
    graph = create_kb_chat_v2_graph(
        planner_llm_factory=lambda: FakeJsonLlm(
            '{"question_type":"chitchat","retrieval_strategy":"skip","retrieval_complexity":"fast",'
            '"needs_clarification":false,"reason":"Greeting."}'
        ),
        answer_llm_factory=lambda: UnexpectedAnswerLlm(),
    )

    result = asyncio.run(
        graph.ainvoke(
            {
                "query": "hello",
                "chat_history": [],
                "memory_summary": None,
                "retrieved_docs": [],
                "context": "",
            }
        )
    )

    assert result["question_type"] == "chitchat"
    assert result["retrieval_strategy"] == "skip"
    assert result["retrieval_required"] is False
    assert result["text_queries"] == []
    assert result["retrieval_trace"]["text"]["skipped"] is True
    assert result["answer_status"] == "chitchat"
    assert result["answer"] == KB_V2_CHITCHAT_REPLY


def test_kb_chat_v2_graph_builds_execution_plan():
    async def fake_retrieve_node(state):
        return {
            "retrieved_docs": [],
            "primary_evidence_docs": [],
            "supporting_evidence_docs": [],
            "metadata_evidence_docs": [],
            "primary_context": "",
            "supporting_context": "",
            "metadata_context": "",
            "context": "",
            "retrieval_trace": {
                "retrieval_strategy": state.get("retrieval_strategy"),
                "text": {"text_hits": 0},
                "graph": {"graph_hits": 0, "empty_reason": "no_hits"},
                "final_hits": 0,
                "empty_reason": "no_hits",
            },
        }

    async def fake_evaluate_node(state, llm_factory=None):
        return {
            "retrieval_evaluation": {
                "status": "insufficient",
                "next_action": "answer",
                "reason": "test",
            }
        }

    graph_module = __import__("app.agents.graphs.kb_chat_v2_graph", fromlist=["unused"])
    original_retrieve_node = graph_module.kb_chat_v2_retrieve_node
    original_evaluate_node = graph_module.kb_chat_v2_evaluate_node
    graph_module.kb_chat_v2_retrieve_node = fake_retrieve_node
    graph_module.kb_chat_v2_evaluate_node = fake_evaluate_node
    try:
        graph = create_kb_chat_v2_graph(
            planner_llm_factory=lambda: FakeJsonLlm(
                '{"question_type":"summary_lookup","retrieval_strategy":"parallel_fusion","retrieval_complexity":"broad",'
                '"needs_clarification":false,"reason":"The user asks for an end-to-end process."}'
            ),
            answer_llm_factory=lambda: FakeJsonLlm("Grounded answer."),
        )
    
        result = asyncio.run(
            graph.ainvoke(
                {
                    "query": "How does the refund flow work end to end?",
                    "chat_history": [],
                    "memory_summary": None,
                    "retrieved_docs": [],
                    "context": "",
                }
            )
        )
    finally:
        graph_module.kb_chat_v2_retrieve_node = original_retrieve_node
        graph_module.kb_chat_v2_evaluate_node = original_evaluate_node

    assert result["question_type"] == "summary_lookup"
    assert result["retrieval_complexity"] == "broad"
    assert result["retrieval_strategy"] == "parallel_fusion"
    assert result["retrieval_required"] is True
    assert result["retrieval_execution_plan"]["context"]["final_top_k"] == 12
    assert result["retrieval_execution_plan"]["retrieval_strategy"] == "parallel_fusion"
    assert result["retrieval_execution_plan"]["channels"]["graph"]["limit"] == 12


def test_kb_chat_v2_graph_routes_through_entity_grounding_before_retrieve():
    async def fake_entity_grounding_node(state):
        return {
            "grounded_entities": [
                {
                    "normalized_name": "project_app",
                    "display_name": "项目应用",
                    "match_field": "display_name",
                    "score": 1.0,
                }
            ],
            "ungrounded_entities": [],
            "grounding_trace": {"input_count": 1, "grounded_count": 1},
        }

    async def fake_retrieve_node(state):
        assert state["grounded_entities"][0]["normalized_name"] == "project_app"
        return {
            "retrieved_docs": [
                {
                    "content": "项目应用需要绑定助手配置。",
                    "metadata": {"document_chunk_id": 11, "source": "text_graph"},
                }
            ],
            "primary_evidence_docs": [
                {
                    "content": "项目应用需要绑定助手配置。",
                    "metadata": {"document_chunk_id": 11, "source": "text_graph"},
                }
            ],
            "supporting_evidence_docs": [],
            "metadata_evidence_docs": [],
            "primary_context": "[1] 文档A\n项目应用需要绑定助手配置。",
            "supporting_context": "",
            "metadata_context": "",
            "context": "[1] 文档A\n项目应用需要绑定助手配置。",
            "retrieval_trace": {"text": {"text_hits": 1}, "graph": {"graph_hits": 1}},
        }

    graph_module = __import__("app.agents.graphs.kb_chat_v2_graph", fromlist=["unused"])
    original_grounding_node = graph_module.kb_chat_v2_entity_grounding_node
    original_retrieve_node = graph_module.kb_chat_v2_retrieve_node
    graph_module.kb_chat_v2_entity_grounding_node = fake_entity_grounding_node
    graph_module.kb_chat_v2_retrieve_node = fake_retrieve_node
    try:
        graph = create_kb_chat_v2_graph(
            planner_llm_factory=lambda: FakeJsonLlm(
                '{"question_type":"relationship_lookup","retrieval_strategy":"parallel_fusion","retrieval_complexity":"standard",'
                '"needs_clarification":false,"reason":"关系问题需要图谱参与。"}'
            ),
            evaluator_llm_factory=lambda: FakeJsonLlm(
                '{"status":"sufficient","next_action":"answer","reason":"Enough.","diagnostic":{"failure_stage":"unknown","details":"ok"}}'
            ),
            answer_llm_factory=lambda: FakeAnswerLlm("grounded answer"),
        )

        result = asyncio.run(
            graph.ainvoke(
                {
                    "query": "项目应用和助手配置是什么关系？",
                    "chat_history": [],
                    "memory_summary": None,
                    "page_context": {},
                    "page_config": {},
                    "retrieved_docs": [],
                    "context": "",
                }
            )
        )
    finally:
        graph_module.kb_chat_v2_entity_grounding_node = original_grounding_node
        graph_module.kb_chat_v2_retrieve_node = original_retrieve_node

    assert "grounding_trace" in result
    assert "primary_evidence_docs" in result


def test_kb_chat_v2_rewrite_extracts_queries_and_candidate_entities(monkeypatch):
    async def fake_build_kb_chat_retrieval_queries(*args, **kwargs):
        return {
            "queries": ["Prescription Flow relationship"],
            "candidate_entities": ["Prescription Flow", "Payment"],
        }

    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.rewrite_query.build_kb_chat_retrieval_queries",
        fake_build_kb_chat_retrieval_queries,
    )

    result = asyncio.run(
        build_kb_chat_v2_rewrite(
            "What is the relationship between `Prescription Flow` and Payment?",
            chat_history=[],
            memory_summary=None,
            page_context={},
            rewrite_plan={
                "question_type": "relationship_lookup",
                "retrieval_complexity": "standard",
                "max_queries": 3,
                "strategies": ["query_compaction", "relationship_focus"],
            },
        )
    )

    assert result["text_queries"]
    assert "Prescription Flow" in result["candidate_entities"]
    assert "Payment" in result["candidate_entities"]
    assert result["rewrite_trace"]["query_count"] == len(result["text_queries"])
    assert result["rewrite_trace"]["engine"] == "llm"
    assert result["rewrite_trace"]["policy"] == "relationship_lookup"


def test_kb_chat_v2_rewrite_emits_relation_queries_for_anchored_relation_question(monkeypatch):
    async def fake_build_kb_chat_retrieval_queries(*args, **kwargs):
        return {
            "queries": ["用户 下一级"],
            "candidate_entities": ["用户"],
            "relation_pairs": [],
            "relation_queries": [
                {
                    "anchor_entity": "用户",
                    "relation_hint": "下一级",
                    "relation_category": "hierarchy_child",
                    "direction": "outgoing",
                    "target_entity": None,
                }
            ],
            "target_attributes": [],
            "entity_constraints": {},
        }

    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.rewrite_query.build_kb_chat_retrieval_queries",
        fake_build_kb_chat_retrieval_queries,
    )

    result = asyncio.run(
        build_kb_chat_v2_rewrite(
            "用户的下一级是什么",
            chat_history=[],
            memory_summary=None,
            page_context={},
            rewrite_plan={
                "question_type": "relationship_lookup",
                "retrieval_complexity": "standard",
                "max_queries": 3,
                "strategies": ["query_compaction", "relationship_focus"],
            },
        )
    )

    assert result["candidate_entities"] == ["用户"]
    assert result["relation_queries"][0]["direction"] == "outgoing"


def test_kb_chat_v2_entity_grounding_node_keeps_ungrounded_entities():
    async def fake_grounding_func(**kwargs):
        return {
            "grounded_entities": [],
            "ungrounded_entities": ["未知模块"],
            "grounding_trace": {"input_count": 1, "grounded_count": 0},
        }

    result = asyncio.run(
        kb_chat_v2_entity_grounding_node(
            {
                "candidate_entities": ["未知模块"],
                "knowledge_base_id": 1,
                "team_id": 1,
                "graph_enabled": True,
            },
            grounding_func=fake_grounding_func,
        )
    )

    assert result["ungrounded_entities"] == ["未知模块"]


def test_kb_chat_v2_execution_plan_maps_complexity():
    plan = build_kb_chat_v2_execution_plan(
        question_type="summary_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="broad",
    )

    assert plan["rewrite"]["max_queries"] == 5
    assert plan["channels"]["text"]["recall_k"] == 40
    assert plan["channels"]["text"]["lexical_k"] == 32
    assert plan["rerank"]["enabled"] is True
    assert plan["rerank"]["top_k"] == 12
    assert plan["context"]["budget_chars"] == 15000
    assert plan["retrieval_strategy"] == "parallel_fusion"
    assert plan["channels"]["graph"]["intent"] == "neighborhood_lookup"
    assert plan["channels"]["graph"]["requires_grounding"] is True
    assert plan["channels"]["graph"]["max_hops"] == 1
    assert plan["fusion"]["policy"] == "text_primary"


def test_kb_chat_v2_execution_plan_routes_by_intent():
    summary_plan = build_kb_chat_v2_execution_plan(
        question_type="summary_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )
    attribute_plan = build_kb_chat_v2_execution_plan(
        question_type="attribute_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )
    definition_plan = build_kb_chat_v2_execution_plan(
        question_type="definition_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )

    assert summary_plan["rewrite"]["strategies"][:2] == ["query_compaction", "terminology_normalization"]
    assert "multi_aspect_split" in summary_plan["rewrite"]["strategies"]
    assert "attribute_focus" in attribute_plan["rewrite"]["strategies"]
    assert "definition_focus" in definition_plan["rewrite"]["strategies"]
    assert summary_plan["retrieval_strategy"] == "parallel_fusion"
    assert attribute_plan["channels"]["graph"]["enabled"] is True
    assert definition_plan["channels"]["text"]["enabled"] is True
    assert summary_plan["channels"]["graph"]["intent"] == "neighborhood_lookup"
    assert summary_plan["channels"]["graph"]["max_hops"] == 1
    assert attribute_plan["channels"]["graph"]["intent"] == "entity_summary"
    assert definition_plan["channels"]["graph"]["intent"] == "entity_summary"


def test_kb_chat_v2_execution_plan_boosts_graph_for_relationship_lookup():
    relationship_plan = build_kb_chat_v2_execution_plan(
        question_type="relationship_lookup",
        retrieval_strategy="parallel_fusion",
        retrieval_complexity="standard",
    )

    assert relationship_plan["channels"]["graph"]["intent"] == "relation_lookup"
    assert relationship_plan["channels"]["graph"]["requires_grounding"] is True
    assert relationship_plan["channels"]["graph"]["max_hops"] == 1
    assert relationship_plan["fusion"]["policy"] == "balanced"
    assert relationship_plan["fusion"]["graph_boost"] == "high"


def test_kb_chat_v2_analyze_node_merges_route_and_plan():
    result = asyncio.run(
        kb_chat_v2_analyze_node(
            {
                "query": "How does the refund flow work end to end?",
                "chat_history": [],
                "memory_summary": None,
                "page_context": {},
                "page_config": {},
            },
            llm_factory=lambda: FakeJsonLlm(
                '{"question_type":"summary_lookup","retrieval_strategy":"parallel_fusion","retrieval_complexity":"broad",'
                '"needs_clarification":false,"reason":"The user asks for an end-to-end process."}'
            ),
        )
    )

    assert result["question_type"] == "summary_lookup"
    assert result["retrieval_required"] is True
    assert result["retrieval_strategy"] == "parallel_fusion"
    assert result["needs_clarification"] is False
    assert result["retrieval_execution_plan"]["rewrite"]["max_queries"] == 5
    assert result["retrieval_execution_plan"]["channels"]["graph"]["limit"] == 12
    assert result["retrieval_execution_plan"]["channels"]["graph"]["intent"] == "neighborhood_lookup"
    assert result["retrieval_execution_plan"]["fusion"]["policy"] == "text_primary"
    assert "route_trace" in result
    assert "plan_trace" in result


def test_kb_chat_v2_evaluate_uses_llm_judge_for_sufficient_evidence():
    llm = FakeJsonLlm(
        '{"status":"sufficient","next_action":"answer",'
        '"reason":"The evidence directly states the relation.",'
        '"diagnostic":{"failure_stage":"unknown","details":"Evidence is enough."}}'
    )

    result = asyncio.run(
        evaluate_retrieval_evidence(
            {
                "query": "How are A and B related?",
                "question_type": "relationship_lookup",
                "retrieval_complexity": "standard",
                "text_queries": ["A B relation"],
                "candidate_entities": ["A", "B"],
                "retrieved_docs": [{"content": "A depends on B.", "metadata": {}}],
                "context": "A depends on B.",
                "retrieval_trace": {"final_hits": 1},
            },
            llm_factory=lambda: llm,
        )
    )

    assert result["status"] == "sufficient"
    assert result["next_action"] == "answer"
    assert "retrieved evidence" in llm.prompts[0].lower()


def test_kb_chat_v2_evaluate_falls_back_to_sufficient_on_llm_error():
    result = asyncio.run(
        evaluate_retrieval_evidence(
            {
                "query": "How are A and B related?",
                "retrieved_docs": [{"content": "A mentions B.", "metadata": {}}],
                "context": "A mentions B.",
                "retrieval_trace": {"final_hits": 1},
            },
            llm_factory=lambda: FakeJsonLlm(RuntimeError("judge unavailable")),
        )
    )

    assert result["status"] == "sufficient"
    assert result["next_action"] == "answer"
    assert result["diagnostic"]["failure_stage"] == "evaluate"


def test_kb_chat_v2_answer_ignores_no_answer_evaluation():
    llm = FakeAnswerLlm("根据已召回内容，A 和 B 存在依赖关系。")

    answer, _trace = asyncio.run(
        build_kb_chat_v2_answer_text(
            {
                "query": "How are A and B related?",
                "primary_context": "[1] 文档A\nA depends on B.",
                "retrieval_evaluation": {
                    "status": "empty",
                    "next_action": "no_answer",
                    "reason": "No usable evidence.",
                },
            },
            llm_factory=lambda: llm,
        )
    )

    assert answer == "根据已召回内容，A 和 B 存在依赖关系。"
    assert llm.prompts


def test_kb_chat_v2_answer_uses_llm_when_no_answer_has_retrieved_docs():
    llm = FakeAnswerLlm("根据已召回内容，[可选商品] 表示可以附加选择的商品。")

    answer, _trace = asyncio.run(
        build_kb_chat_v2_answer_text(
            {
                "query": "看到处方模板库显示[可选商品]时，应该怎么理解？",
                "retrieved_docs": [
                    {
                        "content": "[可选商品] 表示可以按业务需要追加选择的商品。",
                        "metadata": {"document_title": "处方模板说明"},
                    }
                ],
                "context": "[1] 处方模板说明\n[可选商品] 表示可以按业务需要追加选择的商品。",
                "retrieval_evaluation": {
                    "status": "empty",
                    "next_action": "no_answer",
                    "reason": "No usable evidence.",
                },
            },
            llm_factory=lambda: llm,
        )
    )

    assert answer == "根据已召回内容，[可选商品] 表示可以附加选择的商品。"
    assert llm.prompts


def test_kb_chat_v2_answer_ignores_clarification_evaluation():
    llm = FakeAnswerLlm("根据资料，项目应用需要绑定助手配置。")

    answer, _trace = asyncio.run(
        build_kb_chat_v2_answer_text(
            {
                "query": "How are they related?",
                "primary_context": "[1] 文档A\n项目应用需要绑定助手配置。",
                "retrieval_evaluation": {
                    "status": "clarification_needed",
                    "next_action": "clarify",
                    "reason": "Missing entity.",
                    "clarification_need": {
                        "examples": ["Order module", "Payment module"],
                    },
                },
            },
            llm_factory=lambda: llm,
        )
    )

    assert answer == "根据资料，项目应用需要绑定助手配置。"
    assert llm.prompts


def test_kb_chat_v2_evaluate_node_does_not_set_answer_status():
    result = asyncio.run(
        kb_chat_v2_evaluate_node(
            {
                "query": "How are A and B related?",
                "retrieved_docs": [],
                "context": "",
                "retrieval_trace": {"final_hits": 0},
            },
            llm_factory=lambda: FakeJsonLlm(
                '{"status":"empty","next_action":"no_answer","reason":"No hits.",'
                '"diagnostic":{"failure_stage":"retrieve","details":"no hits"}}'
            ),
        )
    )

    assert result["retrieval_evaluation"]["status"] == "sufficient"
    assert result["retrieval_evaluation"]["diagnostic"]["failure_stage"] == "evaluate_bypassed"
    assert "evaluate_trace" in result
    assert "answer_status" not in result


def test_kb_chat_v2_merge_prefers_document_chunk_id_over_chunk_index():
    merged = _merge_text_and_graph_docs(
        text_docs=[
            {
                "content": "Expanded parent window text.",
                "metadata": {
                    "document_id": 1,
                    "document_chunk_id": 101,
                    "chunk_index": 7,
                    "source": "text",
                },
            }
        ],
        graph_docs=[
            {
                "content": "Graph evidence text.",
                "metadata": {
                    "document_id": 1,
                    "document_chunk_id": 101,
                    "chunk_index": 101,
                    "graph_evidence": "A depends on B",
                    "graph_relation_type": "REQUIRES_PERMISSION",
                    "matched_entities": ["A", "B"],
                    "source": "graph",
                },
            }
        ],
        final_top_k=4,
    )

    assert len(merged) == 1
    assert merged[0]["metadata"]["source"] == "text_graph"
    assert merged[0]["metadata"]["chunk_index"] == 7
    assert merged[0]["metadata"]["graph_evidence"] == "A depends on B"


def test_kb_chat_v2_doc_key_requires_document_chunk_id():
    assert _doc_key({"metadata": {"source": "graph_summary", "normalized_name": "prescription flow"}}) == (
        "summary",
        "",
        "prescription flow",
    )


def test_kb_chat_v2_retrieve_splits_primary_supporting_and_metadata(monkeypatch):
    async def fake_run_kb_text_retrieval(**kwargs):
        return {
            "retrieved_docs": [
                {
                    "content": "热词用于提升搜索召回效率。",
                    "metadata": {
                        "source": "text",
                        "document_title": "热词搜索操作指南",
                        "document_chunk_id": 1,
                    },
                }
            ],
            "retrieval_trace": {},
        }

    async def fake_graph_retrieve(self, **kwargs):
        return {
            "retrieved_docs": [],
            "graph_primary_docs": [],
            "graph_supporting_docs": [
                {
                    "content": "热词影响搜索结果的命中效率。",
                    "metadata": {
                        "source": "graph_relation_summary",
                        "document_title": "热词 -> 搜索结果",
                        "graph_relation_type": "AFFECTS",
                        "supporting_section": "关键关系",
                    },
                },
                {
                    "content": "热词（DATABASE 类型实体）",
                    "metadata": {
                        "source": "graph_summary",
                        "document_title": "热词",
                        "normalized_name": "hot_word",
                        "supporting_section": "实体摘要",
                    },
                },
            ],
            "trace": {},
        }

    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.retrieve.run_kb_text_retrieval",
        fake_run_kb_text_retrieval,
    )
    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.retrieve.GraphRetriever.retrieve",
        fake_graph_retrieve,
    )

    result = asyncio.run(
        kb_chat_v2_retrieve_node(
            {
                "query": "热词有什么作用？",
                "question_type": "purpose_lookup",
                "retrieval_strategy": "parallel_fusion",
                "retrieval_execution_plan": {
                    "retrieval_strategy": "parallel_fusion",
                    "channels": {"text": {}, "graph": {}},
                    "rerank": {},
                    "context": {"final_top_k": 8, "budget_chars": 9000},
                },
                "text_queries": ["热词 作用"],
                "candidate_entities": ["热词"],
                "chat_history": [],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
                "retrieval_version_mode": "live",
            }
        )
    )

    assert len(result["primary_evidence_docs"]) == 1
    assert len(result["supporting_evidence_docs"]) == 2
    assert len(result["metadata_evidence_docs"]) == 0
    assert "热词用于提升搜索召回效率" in result["primary_context"]
    assert "[实体摘要]" in result["supporting_context"]
    assert "[关键关系]" in result["supporting_context"]
    assert "热词影响搜索结果的命中效率" in result["supporting_context"]
    assert "DATABASE 类型实体" in result["supporting_context"]
    assert result["retrieval_trace"]["primary_count"] == 1
    assert result["retrieval_trace"]["supporting_count"] == 2
    assert result["retrieval_trace"]["metadata_count"] == 0


def test_kb_chat_v2_retrieve_reranks_primary_evidence_after_dedupe(monkeypatch):
    async def fake_run_multi_query_kb_text_retrieval(**kwargs):
        return {
            "retrieved_docs": [
                {
                    "content": "项目应用需要绑定助手配置。",
                    "metadata": {
                        "document_chunk_id": 11,
                        "document_title": "文档A",
                        "source": "text",
                    },
                },
                {
                    "content": "助手配置用于控制对话入口。",
                    "metadata": {
                        "document_chunk_id": 12,
                        "document_title": "文档B",
                        "source": "text",
                    },
                },
            ],
            "retrieval_trace": {"rerank": {}},
        }

    async def fake_graph_retrieve(self, **kwargs):
        return {
            "retrieved_docs": [
                {
                    "content": "项目应用需要绑定助手配置。",
                    "metadata": {
                        "document_chunk_id": 11,
                        "document_title": "文档A",
                        "source": "graph",
                        "graph_relation_type": "REQUIRES_PERMISSION",
                        "graph_evidence": "项目应用依赖助手配置。",
                        "matched_entities": ["项目应用", "助手配置"],
                    },
                }
            ],
            "graph_primary_docs": [
                {
                    "content": "项目应用需要绑定助手配置。",
                    "metadata": {
                        "document_chunk_id": 11,
                        "document_title": "文档A",
                        "source": "graph",
                        "graph_relation_type": "REQUIRES_PERMISSION",
                        "graph_evidence": "项目应用依赖助手配置。",
                        "matched_entities": ["项目应用", "助手配置"],
                    },
                }
            ],
            "graph_supporting_docs": [
                {
                    "content": "项目应用依赖助手配置。",
                    "metadata": {
                        "source": "graph_evidence_summary",
                        "document_title": "文档A",
                        "supporting_section": "关联证据",
                    },
                }
            ],
            "trace": {"graph_hits": 1},
        }

    async def fake_rerank_retrieved_docs(query, docs, top_k):
        return list(reversed(docs[:top_k]))

    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.retrieve.run_multi_query_kb_text_retrieval",
        fake_run_multi_query_kb_text_retrieval,
    )
    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.retrieve.GraphRetriever.retrieve",
        fake_graph_retrieve,
    )
    monkeypatch.setattr(
        "app.agents.nodes.kb_chat_v2.retrieve.rerank_retrieved_docs",
        fake_rerank_retrieved_docs,
    )

    result = asyncio.run(
        kb_chat_v2_retrieve_node(
            {
                "query": "项目应用和助手配置是什么关系？",
                "question_type": "relationship_lookup",
                "retrieval_strategy": "parallel_fusion",
                "retrieval_execution_plan": {
                    "retrieval_strategy": "parallel_fusion",
                    "channels": {
                        "text": {"recall_k": 8, "lexical_k": 4},
                        "graph": {
                            "enabled": True,
                            "limit": 6,
                            "intent": "relation_lookup",
                            "graph_mode": "relation_evidence",
                        },
                    },
                    "rerank": {"enabled": True, "top_k": 4},
                    "context": {"final_top_k": 4, "llm_reference_top_k": 4, "budget_chars": 8000},
                },
                "text_queries": ["项目应用 助手配置 关系", "项目应用 依赖 助手配置"],
                "grounded_entities": [
                    {"normalized_name": "project_app"},
                    {"normalized_name": "assistant_profile"},
                ],
                "relation_pairs": [{"source": "project_app", "target": "assistant_profile"}],
                "relation_queries": [],
                "chat_history": [],
                "team_id": 1,
                "knowledge_base_id": 1,
                "allowed_document_statuses": [],
                "retrieval_version_mode": "live",
            }
        )
    )

    assert result["retrieved_docs"][0]["metadata"]["document_chunk_id"] == 12
    assert result["primary_evidence_docs"][1]["metadata"]["source"] == "text_graph"
    assert "[关联证据]" in result["supporting_context"]


def test_kb_chat_v2_answer_prompt_prefers_primary_evidence_and_keeps_supporting_context():
    llm = FakeAnswerLlm("项目应用需要先绑定助手配置后才能启用对话入口。")

    answer, _trace = asyncio.run(
        build_kb_chat_v2_answer_text(
            {
                "query": "项目应用和助手配置是什么关系？",
                "primary_context": "[1] 文档A\n项目应用需要绑定助手配置。",
                "supporting_context": "[1] 关系摘要\nProjectApp 依赖 AssistantProfile。",
                "metadata_context": "",
                "retrieval_evaluation": {
                    "status": "sufficient",
                    "next_action": "answer",
                    "reason": "enough",
                },
            },
            llm_factory=lambda: llm,
        )
    )

    assert "绑定助手配置" in answer
    assert "Primary evidence" in llm.prompts[0]
    assert "Supporting evidence" in llm.prompts[0]


def test_kb_chat_v2_evaluate_uses_primary_and_supporting_context_fields():
    llm = FakeJsonLlm(
        '{"status":"sufficient","next_action":"answer","reason":"Enough.","diagnostic":{"failure_stage":"unknown","details":"ok"}}'
    )

    result = asyncio.run(
        evaluate_retrieval_evidence(
            {
                "query": "项目应用和助手配置是什么关系？",
                "primary_context": "[1] 文档A\n项目应用需要绑定助手配置。",
                "supporting_context": "[1] 关系摘要\nProjectApp 依赖 AssistantProfile。",
                "retrieved_docs": [{"content": "项目应用需要绑定助手配置。", "metadata": {}}],
            },
            llm_factory=lambda: llm,
        )
    )

    assert result["status"] == "sufficient"
    assert "Primary evidence" in llm.prompts[0]
    assert "Supporting evidence" in llm.prompts[0]


def test_kb_chat_v2_route_raises_when_planner_fails():
    try:
        asyncio.run(
            kb_chat_v2_route_node(
                {
                    "query": "How does payment work?",
                    "chat_history": [],
                    "memory_summary": None,
                    "page_context": {},
                    "page_config": {},
                },
                llm_factory=lambda: FakeJsonLlm(RuntimeError("planner unavailable")),
            )
        )
    except RuntimeError as exc:
        assert "route failed" in str(exc)
    else:
        raise AssertionError("expected route node to fail explicitly")
