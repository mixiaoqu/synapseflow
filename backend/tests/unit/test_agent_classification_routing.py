import asyncio
from types import SimpleNamespace

from app.agents.main.understanding import build_request_understanding


class DelegatedUnderstandingLlm:
    async def ainvoke(self, prompt: str):
        return SimpleNamespace(
            content=(
                "{"
                '"goal":"查询会员数量",'
                '"clarity":"clear",'
                '"clarification_question":null,'
                '"handling":"delegated",'
                '"task_structure":"atomic",'
                '"reason":"需要查询实时会员数据"'
                "}"
            )
        )


def test_understanding_identifies_an_atomic_delegated_request():
    result = asyncio.run(
        build_request_understanding(
            "查询当前会员数量",
            llm_factory=DelegatedUnderstandingLlm,
        )
    )

    assert result["handling"] == "delegated"
    assert result["task_structure"] == "atomic"
    assert result["goal"] == "查询会员数量"
