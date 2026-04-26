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
        "query": "浣犲ソ",
        "retrieval_plan": {"answer": {"response_mode": "chitchat"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_CHITCHAT_GREETING_REPLY
    )


def test_should_skip_kb_llm_with_options_returns_thanks_reply_for_chitchat():
    state = {
        "query": "璋㈣阿浣?",
        "retrieval_plan": {"answer": {"response_mode": "chitchat"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_CHITCHAT_THANKS_REPLY
    )


def test_should_skip_kb_llm_with_options_returns_generic_reply_for_chitchat():
    state = {
        "query": "浠婂ぉ澶╂皵鐪熶笉閿?",
        "retrieval_plan": {"answer": {"response_mode": "chitchat"}},
    }

    assert (
        should_skip_kb_llm_with_options(state, include_retrieval_fallback=False)
        == KB_CHITCHAT_GENERIC_REPLY
    )


def test_should_skip_kb_llm_with_options_returns_boundary_reply_for_out_of_scope():
    state = {
        "query": "璇蜂綘甯垜鍐欎竴棣栨瓕",
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
        "query": "甯垜鍐欎竴棣栬瘲",
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
