import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.common.execution_budget import AgentLimits, consume_operation
from app.agents.common.task_result import build_task_result
from app.agents.main.graph import create_agent_graph
from app.agents.runtime.tools import (
    AgentToolDefinition,
    build_business_ops_input,
    get_tool_definitions,
)
from app.application.agent.input_builder import prepare_agent_input


def call(name="search_knowledge", call_id="c1", goal="查询适用规则", **args):
    return {"name": name, "id": call_id, "args": {"goal": goal, **args}}


def finish(status="answered", goal="结合规则与客户资料给出建议", message="已有材料足够回答"):
    return AIMessage(
        content=json.dumps({"goal": goal, "status": status, "message": message}, ensure_ascii=False)
    )


class ChildWorkflow:
    def __init__(self, callback=None, data_kind="action_result"):
        self.inputs = []
        self.callback = callback
        self.data_kind = data_kind

    async def astream(self, state, **kwargs):
        self.inputs.append(state)
        if self.callback:
            await self.callback(state)
        result = build_task_result(
            state,
            handler_id=state["workflow_id"],
            status="success",
            answer_status="answered",
            title="查询完成",
            message="已获得指定范围的结果",
        )
        result["data"] = {"kind": self.data_kind, "content": {"customer_id": 17, "count": 0}}
        yield {"type": "updates", "data": {"compose_result": {"task_result": result}}}


def input_state(**kwargs):
    agent_input = prepare_agent_input(
        query="结合规则与客户资料给出建议",
        knowledge_base_id=3,
        user_id=7,
        team_id=2,
        project_app_id=9,
        **kwargs,
    )
    agent_input["tool_context"] = {
        "business_tools": [{"name": "客户查询", "description": "查询当前客户资料"}]
    }
    return {"input": agent_input}


def make_graph(llm, child=None, **kwargs):
    child = child or ChildWorkflow()
    return (
        create_agent_graph(
            planner_llm_factory=lambda: llm,
            answer_llm_factory=lambda: llm,
            tool_workflows={tool.name: child for tool in get_tool_definitions()},
            **kwargs,
        ),
        child,
    )


def test_direct_answer_uses_existing_context_without_tool_execution(scripted_agent_llm):
    llm = scripted_agent_llm([finish(goal="总结已有材料")])
    graph, child = make_graph(llm)
    result = asyncio.run(
        graph.ainvoke(input_state(chat_history=[{"role": "user", "content": "产品A价格100元"}]))
    )
    assert not child.inputs
    assert result["response"]["status"] == "answered"
    assert "产品A价格100元" in llm.answer_prompts[0]


def test_independent_calls_execute_in_parallel(scripted_agent_llm):
    async def run():
        ready = asyncio.Event()
        started = []

        async def barrier(state):
            started.append(state)
            if len(started) == 2:
                ready.set()
            await ready.wait()

        llm = scripted_agent_llm(
            [
                AIMessage(
                    content="获取规则和客户资料",
                    tool_calls=[call(), call("query_business_data", "c2", "查询客户资料")],
                ),
                finish(),
            ]
        )
        graph, child = make_graph(llm, ChildWorkflow(barrier))
        result = await asyncio.wait_for(graph.ainvoke(input_state()), timeout=2)
        assert len(child.inputs) == 2
        assert result["operation_count"] == 2
        assert {
            message.tool_call_id for message in llm.prompts[1] if isinstance(message, ToolMessage)
        } == {"c1", "c2"}
        assert result["plan"] == "获取规则和客户资料"

    asyncio.run(run())


def test_serial_call_receives_original_previous_result_and_trusted_identity(scripted_agent_llm):
    llm = scripted_agent_llm(
        [
            AIMessage(content="", tool_calls=[call("query_business_data", "c1", "查询客户资料")]),
            AIMessage(
                content="根据客户资料查找适用规则",
                tool_calls=[call(call_id="c2", result_ids=["c1"], context="只分析已选客户")],
            ),
            finish(),
        ]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    second = child.inputs[1]
    first_message = next(message for message in llm.prompts[1] if isinstance(message, ToolMessage))
    payload = json.loads(first_message.content)
    assert payload["result_id"] == "c1"
    assert "result_id" not in payload["result"]
    assert second["dependency_results"]["c1"]["data"]["content"]["customer_id"] == 17
    assert second["user_id"] == 7 and second["team_id"] == 2
    assert second["task_context"] == "只分析已选客户"
    assert second["metadata"]["parent_task_id"] == "c2"
    assert len(result["executions"]) == 2


def test_duplicate_calls_reuse_results_within_and_across_rounds(scripted_agent_llm):
    llm = scripted_agent_llm(
        [
            AIMessage(content="", tool_calls=[call(), call(call_id="c2")]),
            AIMessage(content="", tool_calls=[call(call_id="c3")]),
            finish(),
        ]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(child.inputs) == 1
    assert result["executions"]["c2"]["reused_from"] == "c1"
    assert result["executions"]["c3"]["reused_from"] == "c1"
    assert result["result"]["success_count"] == 1


@pytest.mark.parametrize(
    "tool_call,code",
    [
        (call("unknown_tool"), "TOOL_UNAVAILABLE"),
        (call(team_id=999), "INVALID_TOOL_ARGUMENTS"),
        (call(result_ids=["unknown"]), "UNKNOWN_RESULT"),
        (call(goal=" "), "INVALID_TOOL_ARGUMENTS"),
    ],
)
def test_invalid_calls_return_feedback_without_execution(scripted_agent_llm, tool_call, code):
    llm = scripted_agent_llm(
        [AIMessage(content="", tool_calls=[tool_call]), finish(status="failed", message="无法继续")]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    assert not child.inputs
    assert result["executions"]["c1"]["task_result"]["errors"][0]["code"] == code
    assert code in next(
        message.content for message in llm.prompts[1] if isinstance(message, ToolMessage)
    )
    assert result["response"]["status"] == "failed"


def test_unavailable_tools_are_not_bound_and_cannot_be_executed(scripted_agent_llm):
    llm = scripted_agent_llm(
        [
            AIMessage(content="", tool_calls=[call("query_business_data")]),
            finish(status="out_of_scope"),
        ]
    )
    graph, child = make_graph(llm)
    state = input_state()
    state["input"]["tool_context"] = {"business_tools": []}
    result = asyncio.run(graph.ainvoke(state))
    assert {schema["function"]["name"] for schema in llm.schemas[0]} == {"search_knowledge"}
    assert not child.inputs
    assert result["response"]["status"] == "out_of_scope"


def test_new_tool_is_usable_without_changing_decision_prompt(scripted_agent_llm):
    tool = AgentToolDefinition(
        name="test_lookup",
        workflow_id="test_workflow",
        description="查询测试对象",
        input_builder=build_business_ops_input,
        available=lambda _: True,
    )
    child = ChildWorkflow(data_kind="test_record")
    llm = scripted_agent_llm([AIMessage(content="", tool_calls=[call("test_lookup")]), finish()])
    graph = create_agent_graph(
        tools=(tool,),
        tool_workflows={tool.name: child},
        planner_llm_factory=lambda: llm,
        answer_llm_factory=lambda: llm,
    )
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(child.inputs) == 1
    assert result["response"]["status"] == "answered"
    assert "test_lookup" not in llm.prompts[0][0].content

    assert "test_record" in llm.answer_prompts[0]
    assert "customer_id" in llm.answer_prompts[0]


def test_shared_budget_includes_internal_queries(scripted_agent_llm):
    async def consume(_):
        consume_operation()

    llm = scripted_agent_llm(
        [
            AIMessage(content="", tool_calls=[call()]),
            AIMessage(content="", tool_calls=[call(call_id="c2", goal="另一个问题")]),
            finish(status="partial"),
        ]
    )
    graph, child = make_graph(llm, ChildWorkflow(consume), limits=AgentLimits(max_operations=2))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(child.inputs) == 1
    assert result["operation_count"] == 2
    assert (
        result["executions"]["c2"]["task_result"]["errors"][0]["code"]
        == "EXECUTION_BUDGET_EXHAUSTED"
    )


def test_call_limit_and_round_limit_bound_execution(scripted_agent_llm):
    llm = scripted_agent_llm(
        [AIMessage(content="", tool_calls=[call(), call(call_id="c2", goal="第二个问题")])]
    )
    graph, child = make_graph(llm, limits=AgentLimits(max_rounds=1, max_calls=1))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(child.inputs) == 1
    assert result["executions"]["c2"]["task_result"]["errors"][0]["code"] == "TOOL_CALL_LIMIT"
    assert result["response"]["status"] == "partial"


def test_timeout_is_reported_and_child_is_cancelled(scripted_agent_llm):
    cancelled = []

    async def wait(_):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    llm = scripted_agent_llm([AIMessage(content="", tool_calls=[call()]), finish(status="failed")])
    graph, _ = make_graph(llm, ChildWorkflow(wait), limits=AgentLimits(call_timeout=0.01))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert cancelled == [True]
    assert result["executions"]["c1"]["task_result"]["errors"][0]["code"] == "TOOL_TIMEOUT"


def test_cancelled_run_does_not_leave_child_tasks_running(scripted_agent_llm):
    async def run():
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def wait(_):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        llm = scripted_agent_llm([AIMessage(content="", tool_calls=[call()])])
        graph, _ = make_graph(llm, ChildWorkflow(wait))
        task = asyncio.create_task(graph.ainvoke(input_state()))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()

    asyncio.run(run())


@pytest.mark.parametrize(
    "response",
    [
        AIMessage(content="", tool_calls=[call(), call()]),
    ],
)
def test_invalid_model_protocol_fails_explicitly(scripted_agent_llm, response):
    llm = scripted_agent_llm([response])
    graph, child = make_graph(llm)
    with pytest.raises(ValueError):
        asyncio.run(graph.ainvoke(input_state()))
    assert not child.inputs


def test_clarification_is_delivered_without_more_model_or_tool_calls(scripted_agent_llm):
    llm = scripted_agent_llm(
        [finish(status="clarification_needed", message="请提供需要查询的客户名称。")]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    assert result["response"]["answer"] == "请提供需要查询的客户名称。"
    assert not child.inputs and not llm.answer_prompts


def test_stream_events_identify_round_and_each_parallel_call(scripted_agent_llm):
    async def run():
        llm = scripted_agent_llm(
            [
                AIMessage(
                    content="", tool_calls=[call(), call("query_business_data", "c2", "查询客户")]
                ),
                finish(),
            ]
        )
        graph, _ = make_graph(llm)
        chunks = [
            chunk
            async for chunk in graph.astream(
                input_state(), stream_mode=["updates", "custom"], version="v2"
            )
        ]
        events = [chunk["data"] for chunk in chunks if chunk["type"] == "custom"]
        completed = [
            event
            for event in events
            if event.get("node_id") == "execute" and event.get("activity_status") == "completed"
        ]
        assert {event["tool_call_id"] for event in completed} == {"c1", "c2"}
        assert all(event["round"] == 1 for event in completed)
        assert all(event["round"] == 2 for event in events if event.get("node_id") == "respond")

    asyncio.run(run())


def test_catalog_context_exposes_only_authorized_read_only_operations(monkeypatch):
    from types import SimpleNamespace

    from app.application.agent import tool_context

    scopes = []
    read = SimpleNamespace(
        name="客户资料",
        description="查询客户等级",
        read_only=True,
        params=[
            SimpleNamespace(key="customer_id", description="客户ID", required=True),
            SimpleNamespace(key="optional", description="可选项", required=False),
        ],
    )
    write = SimpleNamespace(name="修改客户", description="写入资料", read_only=False, params=[])

    class Catalog:
        async def list_available_operations(self, app_id):
            scopes.append(app_id)
            return [read, write]

    monkeypatch.setattr(tool_context, "BusinessOperationService", Catalog)
    state = input_state()
    context = asyncio.run(tool_context.prepare_tool_context(state["input"]))
    assert scopes == [9]
    assert context["business_tools"] == [
        {
            "name": "客户资料",
            "description": "查询客户等级",
            "required_inputs": [{"name": "customer_id", "description": "客户ID"}],
        }
    ]
    state["input"]["tool_context"] = context
    schema = next(
        tool for tool in get_tool_definitions() if tool.name == "query_business_data"
    ).schema(state["input"])
    assert "查询客户等级" in schema["function"]["description"]
    assert schema["function"]["parameters"]["additionalProperties"] is False
    assert schema["function"]["strict"] is True
    assert set(schema["function"]["parameters"]["required"]) == {"goal", "context", "result_ids"}


@pytest.mark.parametrize(
    "invalid,field",
    [
        (finish(status="in_progress", message="需要调用知识库检索能力"), "status"),
        (AIMessage(content="准备继续检索"), "json_invalid"),
        (AIMessage(content='{"status":"answered"}'), "goal"),
        (
            AIMessage(content='{"goal":"目标","status":"answered","message":"说明","extra":1}'),
            "extra",
        ),
        (AIMessage(content=""), "json_invalid"),
    ],
)
def test_invalid_final_decision_is_corrected_with_schema_feedback(
    scripted_agent_llm, invalid, field
):
    from langchain_core.messages import SystemMessage

    llm = scripted_agent_llm(
        [invalid, finish(status="clarification_needed", message="请确认查询范围。")]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    assert result["decision_count"] == 2
    assert result["response"]["status"] == "clarification_needed"
    assert not child.inputs and not llm.answer_prompts
    feedback = llm.prompts[1][-1]
    assert isinstance(feedback, SystemMessage)
    assert "校验错误" in feedback.content and field in feedback.content
    assert llm.prompts[1][-2] == invalid
    assert "JSON Schema" in llm.prompts[1][0].content
    assert '"enum"' in llm.prompts[1][0].content
    assert '"in_progress"' not in llm.prompts[1][0].content


def test_reported_in_progress_response_can_be_corrected_to_a_real_tool_call(scripted_agent_llm):
    invalid = finish(
        status="in_progress",
        goal="根据用户提供的名称“小王”检索对应资料",
        message="需要调用知识库检索能力，以小王为关键词查找匹配资料",
    )
    llm = scripted_agent_llm(
        [
            invalid,
            AIMessage(content="", tool_calls=[call(goal="检索名称为小王的资料")]),
            finish(),
        ]
    )
    state = input_state(
        chat_history=[
            {"role": "user", "content": "查一下小王"},
            {"role": "assistant", "content": "请提供完整名称。"},
        ]
    )
    state["input"]["query"] = "它的全名就叫小王"
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(state))
    assert result["decision_count"] == 3
    assert len(child.inputs) == 1
    assert child.inputs[0]["query"] == "检索名称为小王的资料"
    assert child.inputs[0]["user_id"] == 7 and child.inputs[0]["team_id"] == 2
    assert "它的全名就叫小王" in llm.prompts[1][1].content
    assert "请提供完整名称" in llm.prompts[1][1].content
    assert result["response"]["status"] == "answered"
    assert not any(isinstance(m, ToolMessage) for m in llm.prompts[1])


@pytest.mark.parametrize("max_rounds,expected_calls", [(1, 1), (2, 2), (6, 3)])
def test_invalid_decision_stops_at_correction_or_round_budget(
    scripted_agent_llm, max_rounds, expected_calls
):
    llm = scripted_agent_llm([finish(status="in_progress")] * 3)
    graph, child = make_graph(llm, limits=AgentLimits(max_rounds=max_rounds))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(llm.prompts) == expected_calls
    assert result["decision_count"] == expected_calls
    assert result["pending_calls"] == []
    assert result["response"]["status"] == "failed"
    assert "校验" in result["response"]["answer"]
    assert not child.inputs and not llm.answer_prompts


def test_second_correction_can_succeed(scripted_agent_llm):
    llm = scripted_agent_llm(
        [finish(status="in_progress"), AIMessage(content="错误格式"), finish()]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    assert result["response"]["status"] == "answered"
    assert result["decision_count"] == len(llm.prompts) == 3
    assert not child.inputs


def test_correction_failure_preserves_completed_results_for_partial_answer(scripted_agent_llm):
    llm = scripted_agent_llm(
        [
            AIMessage(content="", tool_calls=[call()]),
            *[finish(status="in_progress")] * 3,
        ]
    )
    graph, child = make_graph(llm)
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(child.inputs) == 1
    assert result["decision_count"] == 4
    assert result["response"]["status"] == "partial"
    assert result["executions"]["c1"]["status"] == "success"
    assert '"customer_id": 17' in llm.answer_prompts[0]
    assert "两次纠正仍未通过校验" in llm.answer_prompts[0]
    assert len([m for m in result["messages"] if isinstance(m, ToolMessage)]) == 1


def test_correction_budget_is_shared_with_later_decisions(scripted_agent_llm):
    llm = scripted_agent_llm(
        [
            finish(status="in_progress"),
            AIMessage(content="", tool_calls=[call()]),
        ]
    )
    graph, child = make_graph(llm, limits=AgentLimits(max_rounds=2))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert len(llm.prompts) == result["decision_count"] == 2
    assert len(child.inputs) == 1
    assert result["response"]["status"] == "partial"


def test_expired_deadline_prevents_correction(scripted_agent_llm, monkeypatch):
    import app.agents.main.nodes.decide as decision_module

    clock = [100.0]

    def invalid(_):
        clock[0] = 102.0
        return finish(status="in_progress")

    monkeypatch.setattr(decision_module, "monotonic", lambda: clock[0])
    llm = scripted_agent_llm([invalid])
    graph, child = make_graph(llm, limits=AgentLimits(run_timeout=1))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert result["deadline"] == 101.0
    assert result["decision_count"] == len(llm.prompts) == 1
    assert result["response"]["status"] == "failed"
    assert "预算已用尽" in result["response"]["answer"]
    assert not child.inputs


def test_correction_timeout_is_bounded_and_cancels_model(scripted_agent_llm):
    cancelled = []

    class SlowCorrection(scripted_agent_llm):
        async def ainvoke(self, messages):
            if not self.prompts:
                return await super().ainvoke(messages)
            self.prompts.append(messages)
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

    llm = SlowCorrection([finish(status="in_progress")])
    graph, child = make_graph(llm, limits=AgentLimits(model_timeout=0.05))
    result = asyncio.run(graph.ainvoke(input_state()))
    assert result["decision_count"] == len(llm.prompts) == 2
    assert cancelled == [True]
    assert result["response"]["status"] == "failed"
    assert not child.inputs


def test_cancelling_correction_propagates_without_synthetic_result(scripted_agent_llm):
    async def run():
        started = asyncio.Event()
        stopped = asyncio.Event()

        class WaitingCorrection(scripted_agent_llm):
            async def ainvoke(self, messages):
                if not self.prompts:
                    return await super().ainvoke(messages)
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    stopped.set()

        llm = WaitingCorrection([finish(status="in_progress")])
        graph, child = make_graph(llm)
        task = asyncio.create_task(graph.ainvoke(input_state()))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set() and not child.inputs

    asyncio.run(run())


def test_correction_stream_events_keep_actual_model_rounds(scripted_agent_llm):
    async def run():
        llm = scripted_agent_llm(
            [
                finish(status="in_progress"),
                finish(status="clarification_needed"),
            ]
        )
        graph, _ = make_graph(llm)
        chunks = [
            c
            async for c in graph.astream(
                input_state(), stream_mode=["updates", "custom"], version="v2"
            )
        ]
        events = [c["data"] for c in chunks if c["type"] == "custom"]
        starts = [
            e["round"]
            for e in events
            if e.get("node_id") == "decide" and e.get("activity_status") == "running"
        ]
        assert starts == [1, 2]
        assert any(e.get("activity_status") == "error" and e["round"] == 1 for e in events)
        assert all(e["round"] == 2 for e in events if e.get("node_id") == "respond")

    asyncio.run(run())


def test_main_agent_runs_web_workflow_and_preserves_sources(scripted_agent_llm, monkeypatch):
    from app.agents.web_search.graph import create_web_search_graph
    from app.services.web_search import settings

    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-key")

    class PublicGateway:
        async def search(self, query):
            assert query == "公开产品指南"
            return [{
                "url": "https://example.com/guide", "title": "产品指南",
                "snippet": "搜索摘要", "published_at": None,
                "fetched_at": "2026-08-28T00:00:00+00:00",
            }]

        async def extract(self, urls):
            assert urls == ["https://example.com/guide"]
            return {urls[0]: "已经提取的公开正文"}

    llm = scripted_agent_llm([
        AIMessage(content="", tool_calls=[call("search_web", "web1", "公开产品指南")]),
        finish(),
    ])
    workflows = {tool.name: ChildWorkflow() for tool in get_tool_definitions()}
    workflows["search_web"] = create_web_search_graph(gateway_factory=PublicGateway)
    graph = create_agent_graph(
        planner_llm_factory=lambda: llm, answer_llm_factory=lambda: llm,
        tool_workflows=workflows,
    )
    result = asyncio.run(graph.ainvoke(input_state()))
    assert result["operation_count"] == 3
    assert result["response"]["sources"][0]["metadata"]["url"] == "https://example.com/guide"
    assert result["result"]["knowledge_context"] == []
    assert "已经提取的公开正文" in llm.answer_prompts[0]
    assert "https://example.com/guide" in llm.answer_prompts[0]
    assert "search_snippet" in llm.answer_prompts[0]
