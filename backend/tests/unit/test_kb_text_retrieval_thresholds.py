import asyncio
from types import SimpleNamespace

from app.core.config.schemas import (
    RagChunkConfig,
    RagConfig,
    RagRetrievalConfig,
    RagRetrievalProfileConfig,
)
from app.services import kb_text_retrieval
from app.services import vector_store


def _rag_config(
    *,
    rerank_threshold: float | None = 0.35,
    rrf_score_threshold: float | None = None,
) -> RagConfig:
    return RagConfig(
        chunk=RagChunkConfig(
            size=700,
            overlap=100,
            parent_target_min=1200,
            parent_target_max=2500,
            child_target_min=400,
            child_target_max=900,
            split_overlap_units=1,
            parent_window_max_chars=1800,
            parent_window_neighbor_span=1,
        ),
        retrieval=RagRetrievalConfig(
            k_first=32,
            distance_threshold=0.5,
            rrf_score_threshold=rrf_score_threshold,
            rerank_threshold=rerank_threshold,
            final_top_k=10,
            llm_reference_top_k=10,
            hybrid_enabled=True,
            lexical_k=32,
            rrf_k=60,
            hybrid_pool_limit=64,
            kb_context_max_chars=12000,
            profiles={
                "standard": RagRetrievalProfileConfig(
                    recall_k=32,
                    lexical_k=24,
                    graph_limit=10,
                    final_top_k=10,
                    llm_reference_top_k=10,
                    context_budget=12000,
                    rerank_enabled=False,
                )
            },
        ),
    )


def test_apply_retrieval_thresholds_filters_weak_dense_hits(monkeypatch):
    monkeypatch.setattr(
        kb_text_retrieval.config_registry,
        "get_rag_config",
        lambda: _rag_config(),
    )
    rows = [
        {"document_id": 1, "chunk_index": 0, "distance": 0.41},
        {"document_id": 2, "chunk_index": 0, "distance": 0.62},
    ]

    filtered = kb_text_retrieval._apply_retrieval_thresholds(
        rows,
        rerank_enabled=False,
    )

    assert [row["document_id"] for row in filtered] == [1]


def test_apply_retrieval_thresholds_enforces_rerank_threshold_when_available(monkeypatch):
    monkeypatch.setattr(
        kb_text_retrieval.config_registry,
        "get_rag_config",
        lambda: _rag_config(rerank_threshold=0.35),
    )
    rows = [
        {"document_id": 1, "chunk_index": 0, "distance": 0.32, "rerank_score": 0.51},
        {"document_id": 2, "chunk_index": 0, "distance": 0.28, "rerank_score": 0.22},
    ]

    filtered = kb_text_retrieval._apply_retrieval_thresholds(
        rows,
        rerank_enabled=True,
    )

    assert [row["document_id"] for row in filtered] == [1]


def test_apply_retrieval_thresholds_keeps_lexical_only_hits_with_good_rerank(monkeypatch):
    monkeypatch.setattr(
        kb_text_retrieval.config_registry,
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

    filtered = kb_text_retrieval._apply_retrieval_thresholds(
        rows,
        rerank_enabled=True,
    )

    assert [row["document_id"] for row in filtered] == [3]


def test_apply_retrieval_thresholds_filters_low_rrf_score(monkeypatch):
    monkeypatch.setattr(
        kb_text_retrieval.config_registry,
        "get_rag_config",
        lambda: _rag_config(rrf_score_threshold=0.02),
    )
    rows = [
        {
            "document_id": 1,
            "chunk_index": 0,
            "distance": 0.28,
            "rrf_score": 0.031,
        },
        {
            "document_id": 2,
            "chunk_index": 0,
            "distance": 0.24,
            "rrf_score": 0.012,
        },
        {
            "document_id": 3,
            "chunk_index": 0,
            "distance": None,
            "lexical_rank": 1.2,
            "rrf_score": 0.018,
        },
    ]

    filtered = kb_text_retrieval._apply_retrieval_thresholds(
        rows,
        rerank_enabled=False,
    )

    assert [row["document_id"] for row in filtered] == [1]


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
                    expansion_mode="structured_focus",
                )
            }

    monkeypatch.setattr(kb_text_retrieval, "AsyncSessionLocal", lambda: DummySession())
    monkeypatch.setattr(kb_text_retrieval, "DocumentChunkRepository", FakeChunkRepository)

    expanded = asyncio.run(
        kb_text_retrieval._expand_results_with_parent_context(
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
    assert expanded[0]["metadata"]["expansion_mode"] == "structured_focus"
    assert expanded[0]["metadata"]["merged_child_chunk_ids"] == [11, 12]


def test_retrieval_document_version_condition_does_not_filter_versions():
    assert vector_store._document_version_sql_condition("live") == "TRUE"
    assert vector_store._document_version_sql_condition("current") == "TRUE"
    assert vector_store._document_version_sql_condition(None) == "TRUE"
