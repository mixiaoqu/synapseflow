import asyncio

from app.agents.main.nodes.respond import build_respond_node, build_response_prompt
from app.application.agent.input_builder import prepare_agent_input


def test_response_preserves_context_evidence_and_assistant_settings(scripted_agent_llm):
    state = {
        "input": prepare_agent_input(
            query="根据以上销售分析，有什么建议？",
            assistant_name="业务助手",
            assistant_rule_template="使用简短段落",
            chat_history=[{"role": "assistant", "content": "3月退款率较高，4月销售额下降。"}],
        ),
        "decision": {
            "goal": "根据已有分析提出建议",
            "status": "answered",
            "message": "已有材料足够",
        },
        "result": {
            "answer_status": "failed",
            "sources": [],
            "answer_material": {"business_results": [], "public_error": "一次查询失败"},
        },
    }
    state["input"]["runtime_context"] = {"current_datetime": "2026-07-25T10:30:00+08:00"}
    prompt = build_response_prompt(state)
    assert "2026-07-25T10:30:00+08:00" in prompt
    assert "3月退款率较高，4月销售额下降。" in prompt
    assert "使用简短段落" in prompt
    llm = scripted_agent_llm()
    result = asyncio.run(build_respond_node(answer_llm_factory=lambda: llm)(state))
    assert result["response"]["status"] == "answered"


def test_empty_generated_answer_is_a_generation_failure(scripted_agent_llm):
    llm = scripted_agent_llm(answer=" ")
    state = {
        "input": prepare_agent_input(query="你好"),
        "decision": {"goal": "问候", "status": "answered", "message": "直接回应"},
    }
    result = asyncio.run(build_respond_node(answer_llm_factory=lambda: llm)(state))
    assert result["response"]["status"] == "generation_failed"
