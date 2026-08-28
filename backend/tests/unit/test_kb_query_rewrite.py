import asyncio
from types import SimpleNamespace

from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


def test_build_kb_chat_retrieval_queries_falls_back_to_original_when_llm_fails():
    def _raise_llm():
        raise RuntimeError("llm unavailable")

    result = asyncio.run(
        build_kb_chat_retrieval_queries(
            "生成模型怎么配置 models.yaml？",
            llm_factory=_raise_llm,
        )
    )

    assert result["queries"] == ["生成模型怎么配置 models.yaml？"]


def test_build_kb_chat_retrieval_queries_uses_runtime_context_in_fallback():
    def _raise_llm():
        raise RuntimeError("llm unavailable")

    result = asyncio.run(
        build_kb_chat_retrieval_queries(
            "这个页面怎么配置？",
            runtime_context={"page_name": "嵌入式助手"},
            llm_factory=_raise_llm,
        )
    )

    assert result["queries"][0] == "嵌入式助手 这个页面怎么配置？"
    assert len(result["queries"]) <= 4


def test_build_kb_chat_retrieval_queries_prefers_llm_search_translation():
    class _FakeLLM:
        async def ainvoke(self, _: str):
            return SimpleNamespace(
                content=(
                    '{"queries": ["生成模型 models.yaml 配置 provider model 参数", '
                    '"models.yaml 生成模型 接入 配置"], '
                    '"candidate_entities": ["models.yaml", "生成模型"]}'
                )
            )

    result = asyncio.run(
        build_kb_chat_retrieval_queries(
            "生成模型怎么配置？",
            llm_factory=lambda: _FakeLLM(),
        )
    )

    assert result["queries"][0] == "生成模型 models.yaml 配置 provider model 参数"
    assert "生成模型怎么配置？" not in result["queries"]
    assert result["candidate_entities"] == ["models.yaml", "生成模型"]
    assert len(result["queries"]) == 2


def test_build_kb_chat_retrieval_queries_keeps_all_llm_search_translations():
    class _FakeLLM:
        async def ainvoke(self, _: str):
            return SimpleNamespace(
                content=(
                    '{"queries": ['
                    '"助手 配置 模型 参数", '
                    '"知识库 检索 改写 查询", '
                    '"嵌入式助手 页面 配置", '
                    '"文档 索引 发布 检索", '
                    '"敏感词 检查 策略"], '
                    '"candidate_entities": ["助手", "知识库"]}'
                )
            )

    result = asyncio.run(
        build_kb_chat_retrieval_queries(
            "这些分别怎么配置？",
            llm_factory=lambda: _FakeLLM(),
            max_queries=1,
        )
    )

    assert result["queries"] == [
        "助手 配置 模型 参数",
        "知识库 检索 改写 查询",
        "嵌入式助手 页面 配置",
        "文档 索引 发布 检索",
        "敏感词 检查 策略",
    ]
