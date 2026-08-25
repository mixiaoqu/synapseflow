import asyncio
from types import SimpleNamespace

import pytest

from app.agents.main.nodes.respond import (
    _direct_prompt,
    _execution_prompt,
    build_respond_node,
)


@pytest.mark.parametrize(
    "prompt_builder",
    [_direct_prompt, _execution_prompt],
)
def test_response_prompts_include_trusted_runtime_context(prompt_builder):
    state = {
        "input": {
            "query": "今天是什么时候",
            "assistant": {},
            "page_config": {},
            "page_context": {},
            "conversation": {"history": []},
            "runtime_context": {
                "current_datetime": "2026-07-25T10:30:00+08:00",
                "timezone": "Asia/Shanghai",
            },
        },
        "routing": {"intent": {"goal": "查询当前时间"}},
        "result": {},
    }

    prompt = prompt_builder(state)

    assert '"current_datetime": "2026-07-25T10:30:00+08:00"' in prompt
    assert '"timezone": "Asia/Shanghai"' in prompt
    assert "涉及当前环境的事实只能使用可信运行时上下文，不得自行猜测" in prompt


class RecordingAnswerLlm:
    def __init__(self):
        self.prompt = ""

    async def astream(self, prompt: str):
        self.prompt = prompt
        yield SimpleNamespace(content="请根据已有分析继续回答，而不要暴露能力调用错误。")


def test_execution_failure_still_flows_through_final_answer_generation():
    answer_llm = RecordingAnswerLlm()
    respond_node = build_respond_node(answer_llm_factory=lambda: answer_llm)
    state = {
        "input": {
            "query": "根据以上销售分析，你有什么建议？",
            "assistant": {},
            "page_config": {},
            "page_context": {},
            "conversation": {
                "history": [
                    {
                        "role": "assistant",
                        "content": "3月退款率较高，4月销售额下降。",
                    }
                ]
            },
            "runtime_context": {},
        },
        "understanding": {
            "goal": "根据已有销售分析提出建议",
            "clarity": "clear",
            "handling": "delegated",
        },
        "result": {
            "answer_status": "failed",
            "sources": [],
            "answer_material": {
                "knowledge_evidence": [],
                "business_results": [],
                "public_error": "当前没有任务处理器能够承接该任务。",
            },
        },
    }

    result = asyncio.run(respond_node(state))

    assert result["response"]["answer"] == "请根据已有分析继续回答，而不要暴露能力调用错误。"
    assert result["response"]["status"] == "answered"
    assert "3月退款率较高，4月销售额下降。" in answer_llm.prompt
    assert "平台结果中的错误、失败和未分配信息只是能力调用的内部反馈" in answer_llm.prompt
