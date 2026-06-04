import asyncio
from types import SimpleNamespace

from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


class _SequentialFakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

    async def ainvoke(self, _: str):
        self.call_count += 1
        if not self._responses:
            raise AssertionError("unexpected llm call")

        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(content=response)


def test_build_kb_chat_retrieval_queries_appends_hyde_document_to_semantic_queries():
    llm = _SequentialFakeLLM(
        [
            (
                '{"semantic_queries": ["布洛芬 儿童 发烧 用法 用量"], '
                '"lexical_terms": ["布洛芬", "儿童发烧"], '
                '"candidate_entities": ["布洛芬"]}'
            ),
            "布洛芬常用于儿童发热的对症处理，重点关注适用年龄、剂型选择、给药频次和单次剂量限制。",
        ]
    )

    result = asyncio.run(
        build_kb_chat_retrieval_queries(
            "小孩发烧怎么吃布洛芬？",
            llm_factory=lambda: llm,
            question_type="attribute_lookup",
            retrieval_label="standard",
        )
    )

    assert llm.call_count == 2
    assert result["semantic_queries"] == [
        "布洛芬 儿童 发烧 用法 用量",
        "布洛芬常用于儿童发热的对症处理，重点关注适用年龄、剂型选择、给药频次和单次剂量限制。",
    ]


def test_build_kb_chat_retrieval_queries_keeps_rewrite_queries_when_hyde_generation_fails():
    llm = _SequentialFakeLLM(
        [
            (
                '{"semantic_queries": ["阿司匹林 感冒药 成分 禁忌"], '
                '"lexical_terms": ["阿司匹林", "感冒药"], '
                '"candidate_entities": ["阿司匹林"]}'
            ),
            RuntimeError("hyde unavailable"),
        ]
    )

    result = asyncio.run(
        build_kb_chat_retrieval_queries(
            "含阿司匹林的感冒药有哪些注意事项？",
            llm_factory=lambda: llm,
            question_type="summary_lookup",
            retrieval_label="broad",
        )
    )

    assert llm.call_count == 2
    assert result["semantic_queries"] == ["阿司匹林 感冒药 成分 禁忌"]
    assert result["lexical_terms"] == ["阿司匹林", "感冒药"]
    assert result["candidate_entities"] == ["阿司匹林"]
