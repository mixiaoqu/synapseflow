from app.agents.nodes.kb_chat.generate_answer import (
    KB_NO_HITS_REPLY,
    should_skip_kb_llm,
    should_skip_kb_llm_with_options,
)


def test_should_skip_kb_llm_keeps_default_retrieval_fallback():
    state = {"kb_retrieval_status": "no_hits", "retrieved_docs": []}

    assert should_skip_kb_llm(state) == KB_NO_HITS_REPLY


def test_should_skip_kb_llm_with_options_can_keep_llm_path_for_no_hits():
    state = {"kb_retrieval_status": "no_hits", "retrieved_docs": []}

    assert should_skip_kb_llm_with_options(state, include_retrieval_fallback=False) is None
