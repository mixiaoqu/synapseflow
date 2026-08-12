import asyncio
from types import SimpleNamespace

from app.agents.main.understanding import build_request_understanding

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
                f'"goal":"{goal}",'
                f'"clarity":"{"clear" if resolved else "unclear"}",'
                '"clarification_question":null,'
                '"handling":"delegated",'
                '"task_structure":"atomic",'
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
        build_request_understanding(
            "查一下第13笔",
            chat_history=[
                {"role": "user", "content": "查询2024年全年退款中的订单"},
                {"role": "assistant", "content": "\n".join(order_lines)},
            ],
            llm_factory=ContextAwareClassificationLlm,
        )
    )

    assert result["clarity"] == "clear"
    assert result["goal"] == f"查询订单号{TARGET_ORDER_NUMBER}的订单详情"
    assert result["handling"] == "delegated"
