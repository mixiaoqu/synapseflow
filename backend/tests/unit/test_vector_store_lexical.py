import asyncio

from app.services import vector_store


def _row(
    document_id: int,
    chunk_index: int,
    title: str,
    *,
    distance: float | None = None,
) -> dict:
    return {
        "chunk_text": f"chunk-{document_id}-{chunk_index}",
        "search_text": f"search-{document_id}-{chunk_index}",
        "document_id": document_id,
        "chunk_index": chunk_index,
        "document_chunk_id": document_id * 100 + chunk_index,
        "metadata": {},
        "distance": distance,
        "document_title": title,
    }


def test_search_lexical_fuses_fts_and_trgm_for_query(monkeypatch):
    async def fake_fts(*args, **kwargs):
        return [_row(1, 0, "Doc A"), _row(2, 0, "Doc B")]

    async def fake_trgm(*args, **kwargs):
        return [_row(2, 0, "Doc B"), _row(3, 0, "Doc C")]

    monkeypatch.setattr(vector_store, "_search_lexical_fts", fake_fts)
    monkeypatch.setattr(vector_store, "_search_lexical_trgm", fake_trgm)

    rows = asyncio.run(vector_store.search_lexical(object(), "refund policy", k=3))

    assert rows[0]["document_id"] == 2
    assert {row["document_id"] for row in rows} == {1, 2, 3}


def test_search_lexical_runs_fts_and_trgm_sequentially(monkeypatch):
    order: list[str] = []

    async def fake_fts(*args, **kwargs):
        order.append("fts:start")
        await asyncio.sleep(0)
        order.append("fts:end")
        return [_row(1, 0, "Doc A")]

    async def fake_trgm(*args, **kwargs):
        order.append("trgm:start")
        await asyncio.sleep(0)
        order.append("trgm:end")
        return [_row(2, 0, "Doc B")]

    monkeypatch.setattr(vector_store, "_search_lexical_fts", fake_fts)
    monkeypatch.setattr(vector_store, "_search_lexical_trgm", fake_trgm)

    rows = asyncio.run(vector_store.search_lexical(object(), "refund policy", k=3))

    assert order == ["fts:start", "fts:end", "trgm:start", "trgm:end"]
    assert {row["document_id"] for row in rows} == {1, 2}


def test_search_hybrid_rrf_runs_dense_then_lexical_on_same_session(monkeypatch):
    order: list[str] = []

    async def fake_dense(*args, **kwargs):
        order.append("dense:start")
        await asyncio.sleep(0)
        order.append("dense:end")
        return [_row(1, 0, "Dense Doc", distance=0.12)]

    async def fake_lexical(*args, **kwargs):
        order.append("lexical:start")
        await asyncio.sleep(0)
        order.append("lexical:end")
        return [_row(2, 0, "Lexical Doc")]

    monkeypatch.setattr(vector_store, "search", fake_dense)
    monkeypatch.setattr(vector_store, "search_lexical", fake_lexical)

    rows = asyncio.run(
        vector_store.search_hybrid_rrf(
            object(),
            query_text="refund policy",
            query_embedding=[0.1, 0.2],
            k_dense=4,
            k_lexical=4,
            user_id=1,
            knowledge_base_id=2,
            category_id=3,
            rrf_k=60,
            pool_limit=4,
        )
    )

    assert order == ["dense:start", "dense:end", "lexical:start", "lexical:end"]
    assert {row["document_id"] for row in rows} == {1, 2}
