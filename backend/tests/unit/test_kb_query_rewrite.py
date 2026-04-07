import asyncio
from types import SimpleNamespace

from app.services.kb_query_rewrite import build_kb_chat_retrieval_queries


def test_build_kb_chat_retrieval_queries_fallback_keeps_original_and_terms():
    queries = asyncio.run(
        build_kb_chat_retrieval_queries(
            "How do I configure models.yaml for the generation model?",
            allow_llm=False,
        )
    )

    assert queries[0] == "How do I configure models.yaml for the generation model?"
    assert any("models.yaml" in query for query in queries[1:])
    assert len(queries) <= 4


def test_build_kb_chat_retrieval_queries_merges_llm_and_fallback_results():
    class _FakeLLM:
        async def ainvoke(self, _: str):
            return SimpleNamespace(
                content='{"queries": ["generation model config", "models.yaml generation model"]}'
            )

    queries = asyncio.run(
        build_kb_chat_retrieval_queries(
            "How do I configure the generation model?",
            llm_factory=lambda: _FakeLLM(),
            allow_llm=True,
        )
    )

    assert queries[0] == "How do I configure the generation model?"
    assert "generation model config" in queries
    assert "models.yaml generation model" in queries
    assert len(queries) <= 4
