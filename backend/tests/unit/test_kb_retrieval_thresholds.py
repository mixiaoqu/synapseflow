import asyncio
from types import SimpleNamespace

from app.core.config.schemas import (
    RagChunkConfig,
    RagConfig,
    RagEvaluateConfig,
    RagEvaluateWeights,
    RagRetrievalConfig,
)
from app.services import kb_retrieval


def _rag_config(*, rerank_threshold: float | None = 0.35) -> RagConfig:
    return RagConfig(
        chunk=RagChunkConfig(size=700, overlap=100),
        retrieval=RagRetrievalConfig(
            k_first=32,
            k_iteration=32,
            distance_threshold=0.5,
            distance_threshold_iteration=0.6,
            rerank_threshold=rerank_threshold,
            fallback_top_n=3,
            final_top_k=10,
            llm_reference_top_k=10,
            hybrid_enabled=True,
            lexical_k=32,
            rrf_k=60,
            hybrid_pool_limit=64,
            kb_context_max_chars=12000,
        ),
        evaluate=RagEvaluateConfig(
            context_max_chars=3000,
            pass_threshold=0.75,
            weights=RagEvaluateWeights(
                relevance=0.25,
                groundedness=0.45,
                completeness=0.30,
            ),
        ),
    )


def test_apply_retrieval_thresholds_filters_weak_dense_hits(monkeypatch):
    monkeypatch.setattr(
        kb_retrieval.config_registry,
        "get_rag_config",
        lambda: _rag_config(),
    )
    rows = [
        {"document_id": 1, "chunk_index": 0, "distance": 0.41},
        {"document_id": 2, "chunk_index": 0, "distance": 0.62},
    ]

    filtered = kb_retrieval._apply_retrieval_thresholds(
        rows,
        iteration=0,
        rerank_enabled=False,
    )

    assert [row["document_id"] for row in filtered] == [1]


def test_apply_retrieval_thresholds_enforces_rerank_threshold_when_available(monkeypatch):
    monkeypatch.setattr(
        kb_retrieval.config_registry,
        "get_rag_config",
        lambda: _rag_config(rerank_threshold=0.35),
    )
    rows = [
        {"document_id": 1, "chunk_index": 0, "distance": 0.32, "rerank_score": 0.51},
        {"document_id": 2, "chunk_index": 0, "distance": 0.28, "rerank_score": 0.22},
    ]

    filtered = kb_retrieval._apply_retrieval_thresholds(
        rows,
        iteration=0,
        rerank_enabled=True,
    )

    assert [row["document_id"] for row in filtered] == [1]


def test_apply_retrieval_thresholds_keeps_lexical_only_hits_with_good_rerank(monkeypatch):
    monkeypatch.setattr(
        kb_retrieval.config_registry,
        "get_rag_config",
        lambda: _rag_config(rerank_threshold=0.35),
    )
    rows = [
        {
            "document_id": 3,
            "chunk_index": 0,
            "distance": None,
            "lexical_rank": 1.7,
            "rerank_score": 0.44,
        }
    ]

    filtered = kb_retrieval._apply_retrieval_thresholds(
        rows,
        iteration=0,
        rerank_enabled=True,
    )

    assert [row["document_id"] for row in filtered] == [3]


def test_expand_results_with_parent_context_skips_missing_parent_windows(monkeypatch):
    class DummySession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeChunkRepository:
        def __init__(self, db):
            pass

        async def expand_parent_windows(self, *, child_chunk_ids):
            return {
                11: SimpleNamespace(
                    child_chunk_id=11,
                    parent_chunk_id=101,
                    content="parent window",
                    parent_content="parent window",
                    window_child_ids=[11, 12],
                )
            }

    monkeypatch.setattr(kb_retrieval, "AsyncSessionLocal", lambda: DummySession())
    monkeypatch.setattr(kb_retrieval, "DocumentChunkRepository", FakeChunkRepository)

    expanded = asyncio.run(
        kb_retrieval._expand_results_with_parent_context(
            [
                {
                    "document_id": 1,
                    "document_chunk_id": 11,
                    "chunk_text": "hit one",
                    "metadata": {},
                },
                {
                    "document_id": 1,
                    "document_chunk_id": 99,
                    "chunk_text": "hit two",
                    "metadata": {},
                },
            ]
        )
    )

    assert len(expanded) == 1
    assert expanded[0]["metadata"]["parent_chunk_id"] == 101
    assert expanded[0]["metadata"]["merged_child_chunk_ids"] == [11, 12]
