import asyncio
import json

from langchain_core.messages import AIMessage

from app.agents.common.execution_budget import AgentLimits
from app.agents.main.nodes.decide import build_decide_node
from app.application.agent import input_builder as graph_input_module


def test_graph_input_adds_backend_runtime_context(monkeypatch):
    expected = {"current_datetime": "2026-07-25T10:30:00+08:00", "timezone": "Asia/Shanghai"}
    monkeypatch.setattr(graph_input_module, "build_runtime_context", lambda: expected)
    result = graph_input_module.prepare_agent_input(query="查询最近30天销售额")
    assert result["runtime_context"] == expected


def test_decision_receives_authoritative_time_for_relative_dates(scripted_agent_llm):
    goal = "查询2026-06-26至2026-07-25的销售总额"

    def resolve(messages):
        assert "2026-07-25T10:30:00+08:00" in messages[1].content
        assert "Asia/Shanghai" in messages[1].content
        return AIMessage(
            content=json.dumps(
                {
                    "goal": goal,
                    "status": "out_of_scope",
                    "message": "当前没有对应查询能力",
                },
                ensure_ascii=False,
            )
        )

    agent_input = graph_input_module.prepare_agent_input(query="查询最近30天销售额")
    agent_input["runtime_context"] = {
        "current_datetime": "2026-07-25T10:30:00+08:00",
        "timezone": "Asia/Shanghai",
    }
    llm = scripted_agent_llm([resolve])
    node = build_decide_node(tools=(), planner_llm_factory=lambda: llm, limits=AgentLimits())
    result = asyncio.run(node({"input": agent_input}))
    assert result["decision"]["goal"] == goal
