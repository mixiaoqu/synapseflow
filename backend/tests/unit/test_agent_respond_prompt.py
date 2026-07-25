import pytest

from app.agents.nodes.agent_orchestration.respond import (
    build_direct_response_prompt,
    build_synthesized_response_prompt,
)


@pytest.mark.parametrize(
    "prompt_builder",
    [build_direct_response_prompt, build_synthesized_response_prompt],
)
def test_response_prompts_include_trusted_runtime_context(prompt_builder):
    state = {
        "query": "今天是什么时候",
        "runtime_context": {
            "current_datetime": "2026-07-25T10:30:00+08:00",
            "timezone": "Asia/Shanghai",
        },
    }

    prompt = prompt_builder(state)

    assert '"current_datetime": "2026-07-25T10:30:00+08:00"' in prompt
    assert '"timezone": "Asia/Shanghai"' in prompt
    assert "涉及当前环境的事实只能使用可信运行时上下文，不得自行猜测" in prompt
