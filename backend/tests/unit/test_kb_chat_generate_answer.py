import asyncio

from app.agents.nodes.kb_chat.generate_answer import (
    KB_CHITCHAT_GENERIC_REPLY,
    KB_CHITCHAT_GREETING_REPLY,
    KB_CHITCHAT_THANKS_REPLY,
    KB_NO_HITS_REPLY,
    KB_OUT_OF_SCOPE_REPLY,
    generate_kb_chat_answer_text,
    should_skip_kb_llm,
    should_skip_kb_llm_with_options,
)


def test_should_skip_kb_llm_keeps_default_retrieval_fallback():
    state = {"kb_retrieval_status": "no_hits", "retrieved_docs": []}

    assert should_skip_kb_llm(state) == KB_NO_HITS_REPLY


def test_should_skip_kb_llm_with_options_can_keep_llm_path_for_no_hits():
    state = {"kb_retrieval_status": "no_hits", "retrieved_docs": []}

    assert should_skip_kb_llm_with_options(state, include_retrieval_fallback=False) is None


def test_should_skip_kb_llm_with_options_returns_greeting_reply_for_chitchat():
    state = {
        "query": "你好",
        "retrieval_plan": {"answer": {"response_mode": "chitchat"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_CHITCHAT_GREETING_REPLY
    )


def test_should_skip_kb_llm_with_options_returns_thanks_reply_for_chitchat():
    state = {
        "query": "谢谢",
        "retrieval_plan": {"answer": {"response_mode": "chitchat"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_CHITCHAT_THANKS_REPLY
    )


def test_should_skip_kb_llm_with_options_returns_generic_reply_for_chitchat():
    state = {
        "query": "今天天气真不错",
        "retrieval_plan": {"answer": {"response_mode": "chitchat"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_CHITCHAT_GENERIC_REPLY
    )


def test_should_skip_kb_llm_with_options_returns_boundary_reply_for_out_of_scope():
    state = {
        "query": "请你帮我写一首歌",
        "retrieval_plan": {"answer": {"response_mode": "out_of_scope"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_OUT_OF_SCOPE_REPLY
    )


def test_generate_kb_chat_answer_text_short_circuits_out_of_scope_without_llm():
    class UnexpectedLlm:
        async def ainvoke(self, prompt: str):  # pragma: no cover - should not be called
            raise AssertionError("LLM should not be called for out_of_scope replies")

    state = {
        "query": "帮我生成一段宣传文案",
        "retrieval_plan": {"answer": {"response_mode": "out_of_scope"}},
        "kb_retrieval_status": "skipped",
        "retrieved_docs": [],
        "context": "",
    }

    answer = asyncio.run(
        generate_kb_chat_answer_text(
            state,
            llm_factory=lambda: UnexpectedLlm(),
        )
    )

    assert answer == KB_OUT_OF_SCOPE_REPLY


def test_fixed_chitchat_and_boundary_replies_are_readable_chinese():
    assert KB_CHITCHAT_GREETING_REPLY == (
        "你好，我主要负责回答当前知识库中的制度、流程、规则和文档内容。"
        "你可以继续问我相关问题。"
    )
    assert KB_CHITCHAT_THANKS_REPLY == "不客气，我可以继续帮你查询当前知识库里的内容。"
    assert KB_CHITCHAT_GENERIC_REPLY == (
        "你好，我主要负责回答当前知识库相关问题，例如制度、流程、规则和文档内容。"
        "你可以继续问我相关问题。"
    )
    assert KB_OUT_OF_SCOPE_REPLY == (
        "我主要负责回答当前知识库相关问题，例如制度、流程、规则和文档内容。"
        "当前这个请求不属于知识库问答范围，你可以继续问我知识库里的内容。"
    )
