import asyncio
from types import SimpleNamespace

from app.agents.main.intent import build_agent_classification
from app.agents.runtime.sub_agents import get_sub_agent_definitions


class BusinessClassificationLlm:
    async def ainvoke(self, prompt: str):
        return SimpleNamespace(
            content=(
                "{"
                '"request_type":"data_query",'
                '"task_shape":"single_sub_agent",'
                '"goal_clarity":"clear",'
                '"needs_sub_agent":true,'
                '"domain_hints":["business_ops"],'
                '"sub_tasks":[{"sub_agent_id":"business_ops","goal":"查询会员数量","depends_on":[]}],'
                '"intent":{"kind":"data_query","goal":"查询会员数量"},'
                '"risk_hint":"none",'
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

    assert result["task_shape"] == "single_sub_agent"
    assert result["domain_hints"] == ["business_ops"]
    assert "keyword_hints" not in result
