import asyncio
from types import SimpleNamespace

from app.agents.common.agent_intent import build_agent_classification
from app.agents.runtime.sub_agents import get_sub_agent_definitions


TARGET_ORDER_NUMBER = "1649210480789511"


class ContextAwareClassificationLlm:
    async def ainvoke(self, prompt: str):
        resolved = TARGET_ORDER_NUMBER in prompt
        goal = (
            f"查询订单号{TARGET_ORDER_NUMBER}的订单详情"
            if resolved
            else "查询上一轮订单列表中的第13笔订单详情"
        )
        return SimpleNamespace(
            content=(
                "{"
                '"request_type":"data_query",'
                '"task_shape":"single_sub_agent",'
                f'"goal_clarity":"{"clear" if resolved else "unclear"}",'
                '"needs_sub_agent":true,'
                '"domain_hints":["business_ops"],'
                f'"sub_tasks":[{{"sub_agent_id":"business_ops","goal":"{goal}","depends_on":[]}}],'
                f'"intent":{{"kind":"data_query","goal":"{goal}"}},'
                '"risk_hint":"none",'
                '"reason":"根据上一轮列表解析序号引用"'
                "}"
            )
        )


def test_classification_can_resolve_late_ordinal_reference_from_recent_history():
    order_lines = [
        f"第{index}笔：订单号 {TARGET_ORDER_NUMBER if index == 13 else f'order-{index:02d}'}，商品示例信息"
        for index in range(1, 16)
    ]

    result = asyncio.run(
        build_agent_classification(
            "查一下第13笔",
            sub_agents=get_sub_agent_definitions(),
            chat_history=[
                {"role": "user", "content": "查询2024年全年退款中的订单"},
                {"role": "assistant", "content": "\n".join(order_lines)},
            ],
            llm_factory=ContextAwareClassificationLlm,
        )
    )

    assert result["goal_clarity"] == "clear"
    assert result["intent"]["goal"] == f"查询订单号{TARGET_ORDER_NUMBER}的订单详情"
    assert result["sub_tasks"][0]["goal"] == f"查询订单号{TARGET_ORDER_NUMBER}的订单详情"
