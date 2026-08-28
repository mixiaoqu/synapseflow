import asyncio
import json

from langchain_core.messages import AIMessage

from app.agents.common.execution_budget import AgentLimits
from app.agents.main.nodes.decide import build_decide_node
from app.application.agent.input_builder import prepare_agent_input

TARGET_ORDER_NUMBER = "1649210480789511"


def test_decision_receives_late_ordinal_reference_from_recent_history(scripted_agent_llm):
    order_lines = [
        f"第{index}笔：订单号 {TARGET_ORDER_NUMBER if index == 13 else f'order-{index:02d}'}，商品示例信息"
        for index in range(1, 16)
    ]

    def resolve(messages):
        assert TARGET_ORDER_NUMBER in messages[1].content
        return AIMessage(
            content=json.dumps(
                {
                    "goal": f"查询订单号{TARGET_ORDER_NUMBER}的订单详情",
                    "status": "out_of_scope",
                    "message": "当前未配置对应查询能力",
                },
                ensure_ascii=False,
            )
        )

    llm = scripted_agent_llm([resolve])
    node = build_decide_node(tools=(), planner_llm_factory=lambda: llm, limits=AgentLimits())
    result = asyncio.run(
        node(
            {
                "input": prepare_agent_input(
                    query="查一下第13笔",
                    chat_history=[
                        {"role": "user", "content": "查询2024年全年退款中的订单"},
                        {"role": "assistant", "content": "\n".join(order_lines)},
                    ],
                )
            }
        )
    )
    assert result["decision"]["goal"] == f"查询订单号{TARGET_ORDER_NUMBER}的订单详情"
