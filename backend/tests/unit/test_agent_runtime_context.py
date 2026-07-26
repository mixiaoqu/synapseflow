import asyncio
from types import SimpleNamespace

from app.agents.main.intent import build_agent_classification
from app.agents.runtime.sub_agents import get_sub_agent_definitions
from app.application.agent import input_builder as graph_input_module


class RelativeTimeClassificationLlm:
    def __init__(self) -> None:
        self.prompt = ""

    async def ainvoke(self, prompt: str):
        self.prompt = prompt
        return SimpleNamespace(
            content=(
                "{"
                '"request_type":"data_query",'
                '"task_shape":"single_sub_agent",'
                '"goal_clarity":"clear",'
                '"domain_hints":["business_ops"],'
                '"intent":{"kind":"data_query","goal":"查询2026-06-26至2026-07-25的销售总额"},'
                '"risk_hint":"none",'
                '"reason":"用户请求实时销售统计"'
                "}"
            )
        )


def test_graph_input_adds_backend_runtime_context(monkeypatch):
    expected = {
        "current_datetime": "2026-07-25T10:30:00+08:00",
        "timezone": "Asia/Shanghai",
    }
    monkeypatch.setattr(
        graph_input_module,
        "build_runtime_context",
        lambda: expected,
        raising=False,
    )

    result = graph_input_module.prepare_agent_input(query="查询最近30天销售额")

    assert result["runtime_context"] == expected


def test_classification_resolves_relative_time_into_explicit_goal():
    llm = RelativeTimeClassificationLlm()
    runtime_context = {
        "current_datetime": "2026-07-25T10:30:00+08:00",
        "timezone": "Asia/Shanghai",
    }

    result = asyncio.run(
        build_agent_classification(
            "查询最近30天销售额",
            sub_agents=get_sub_agent_definitions(),
            runtime_context=runtime_context,
            llm_factory=lambda: llm,
        )
    )

    assert "2026-07-25T10:30:00+08:00" in llm.prompt
    assert "Asia/Shanghai" in llm.prompt
    assert result["intent"]["goal"] == "查询2026-06-26至2026-07-25的销售总额"
    assert "time_range" not in result["intent"]
    assert result["domain_hints"] == ["business_ops"]
