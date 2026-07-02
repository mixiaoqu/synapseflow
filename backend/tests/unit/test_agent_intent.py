import asyncio

from app.agents.common.agent_intent import build_agent_intent


class UnexpectedLlm:
    async def ainvoke(self, prompt: str):
        raise AssertionError("deterministic route should not call planner llm")


def test_permission_question_about_member_management_routes_to_knowledge_qa():
    result = asyncio.run(
        build_agent_intent(
            "在会员列表中，一个门店负责人（store_principal）能否编辑其他门店会员的资料？能否冻结/解冻会员？",
            llm_factory=lambda: UnexpectedLlm(),
        )
    )

    assert result["type"] == "knowledge_qa"


def test_how_to_member_list_question_routes_to_knowledge_qa():
    result = asyncio.run(
        build_agent_intent(
            "门店负责人如何查看会员列表和会员资料？",
            llm_factory=lambda: UnexpectedLlm(),
        )
    )

    assert result["type"] == "knowledge_qa"


def test_product_inventory_price_query_routes_to_business_ops():
    result = asyncio.run(
        build_agent_intent(
            "帮我查询门店 store_1001 的可乐库存和价格",
            llm_factory=lambda: UnexpectedLlm(),
        )
    )

    assert result["type"] == "business_ops"
