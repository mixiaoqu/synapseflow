import pytest

from app.agents.main.nodes.respond import (
    _direct_prompt,
    _execution_prompt,
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
