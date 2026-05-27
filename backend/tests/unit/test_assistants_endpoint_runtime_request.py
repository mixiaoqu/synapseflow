from types import SimpleNamespace

from app.api.v1.endpoints.assistants import _build_runtime_request


def test_build_runtime_request_preserves_assistant_scope():
    assistant = SimpleNamespace(
        id=11,
        name="购物助手",
        team_id=3,
        knowledge_base_id=27,
        category_id=9,
        welcome_message="你好",
        placeholder_text="请输入问题",
        llm_model_key="deepseek-v4-pro",
        persona_prompt="你是一个购物表单助手",
        rule_template="只根据知识库回答",
        suggested_prompts=["每年购物金额输入框是什么"],
    )

    request = _build_runtime_request(
        assistant=assistant,
        query="每年购物金额输入框是什么",
        session_id="session-1",
    )

    assert request.team_id == 3
    assert request.knowledge_base_id == 27
    assert request.knowledge_base_ids == [27]
    assert request.category_id == 9
    assert request.assistant_id == 11
    assert request.query == "每年购物金额输入框是什么"
