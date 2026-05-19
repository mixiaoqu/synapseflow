import asyncio
from types import SimpleNamespace

from app.agents.graphs.kb_chat_v2_graph import create_kb_chat_v2_graph
from app.agents.nodes.kb_chat_v2.analyze import (
    build_kb_chat_v2_execution_plan,
    kb_chat_v2_analyze_node,
)
from app.agents.nodes.kb_chat_v2.answer import (
    KB_V2_CHITCHAT_REPLY,
    KB_V2_NO_ANSWER_REPLY,
    build_kb_chat_v2_answer_text,
)
from app.agents.nodes.kb_chat_v2.evaluate import evaluate_retrieval_evidence
from app.agents.nodes.kb_chat_v2.retrieve import _doc_key, _merge_text_and_graph_docs
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
            '{"question_type":"chitchat","retrieval_complexity":"fast",'
            '"retrieval_required":false,"reason":"Greeting."}'
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
    assert result["retrieval_required"] is False
    assert result["text_queries"] == []
    assert result["retrieval_trace"]["text"]["skipped"] is True
    assert result["answer_status"] == "chitchat"
    assert result["answer"] == KB_V2_CHITCHAT_REPLY


def test_kb_chat_v2_graph_builds_execution_plan():
    graph = create_kb_chat_v2_graph(
        planner_llm_factory=lambda: FakeJsonLlm(
            '{"question_type":"procedural_lookup","retrieval_complexity":"broad",'
            '"retrieval_required":true,"reason":"The user asks for an end-to-end process."}'
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

    assert result["question_type"] == "procedural_lookup"
    assert result["retrieval_complexity"] == "broad"
    assert result["retrieval_required"] is True
    assert result["retrieval_execution_plan"]["context"]["final_top_k"] == 12
    assert result["retrieval_execution_plan"]["channels"]["graph"]["limit"] == 12


def test_kb_chat_v2_rewrite_extracts_queries_and_candidate_entities():
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


def test_kb_chat_v2_execution_plan_maps_complexity():
    plan = build_kb_chat_v2_execution_plan(
        question_type="summary_lookup",
        retrieval_required=True,
        retrieval_complexity="broad",
    )

    assert plan["rewrite"]["max_queries"] == 5
    assert plan["channels"]["vector"]["recall_k"] == 40
    assert plan["channels"]["lexical"]["recall_k"] == 32
    assert plan["rerank"]["top_k"] == 12
    assert plan["context"]["budget_chars"] == 15000


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
                '{"question_type":"procedural_lookup","retrieval_complexity":"broad",'
                '"retrieval_required":true,"reason":"The user asks for an end-to-end process."}'
            ),
        )
    )

    assert result["question_type"] == "procedural_lookup"
    assert result["retrieval_required"] is True
    assert result["retrieval_execution_plan"]["rewrite"]["max_queries"] == 4
    assert result["retrieval_execution_plan"]["channels"]["graph"]["limit"] == 12
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


def test_kb_chat_v2_answer_templates_no_answer_without_answer_llm():
    answer, _trace = asyncio.run(
        build_kb_chat_v2_answer_text(
            {
                "query": "How are A and B related?",
                "retrieval_evaluation": {
                    "status": "empty",
                    "next_action": "no_answer",
                    "reason": "No usable evidence.",
                },
            },
            llm_factory=lambda: UnexpectedAnswerLlm(),
        )
    )

    assert answer == KB_V2_NO_ANSWER_REPLY


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


def test_kb_chat_v2_answer_templates_clarification_without_answer_llm():
    answer, _trace = asyncio.run(
        build_kb_chat_v2_answer_text(
            {
                "query": "How are they related?",
                "retrieval_evaluation": {
                    "status": "clarification_needed",
                    "next_action": "clarify",
                    "reason": "Missing entity.",
                    "clarification_need": {
                        "examples": ["Order module", "Payment module"],
                    },
                },
            },
            llm_factory=lambda: UnexpectedAnswerLlm(),
        )
    )

    assert "实体或模块" in answer
    assert "Order module" in answer


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
                    "graph_relation_type": "DEPENDS_ON",
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
    try:
        _doc_key({"metadata": {"document_id": 1, "chunk_index": 7}})
    except ValueError as exc:
        assert "document_chunk_id" in str(exc)
    else:
        raise AssertionError("expected _doc_key to reject missing document_chunk_id")


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
