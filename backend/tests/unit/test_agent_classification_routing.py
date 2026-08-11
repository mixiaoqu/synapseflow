import asyncio
from types import SimpleNamespace

from app.agents.main.intent import build_agent_classification
from app.agents.runtime.sub_agents import get_sub_agent_definitions


class BusinessClassificationLlm:
    async def ainvoke(self, prompt: str):
        return SimpleNamespace(
            content=(
                "{"
                '"goal":"查询会员数量",'
                '"clarity":"clear",'
                '"clarification_question":null,'
                '"handling":"capabilities",'
                '"capability_ids":["business_ops"],'
                '"reason":"需要查询实时会员数据"'
                "}"
            )
        )


def test_classification_keeps_valid_llm_domain_selection():
    result = asyncio.run(
        build_agent_classification(
            "如何查询会员数量",
            sub_agents=get_sub_agent_definitions(),
            llm_factory=BusinessClassificationLlm,
        )
    )

    assert result["handling"] == "capabilities"
    assert result["capability_ids"] == ["business_ops"]
    assert result["goal"] == "查询会员数量"
