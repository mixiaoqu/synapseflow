import asyncio

from app.services import vector_store


def _row(document_id: int, chunk_index: int, title: str, *, distance: float = 2.0) -> dict:
    return {
        "chunk_text": f"chunk-{document_id}-{chunk_index}",
        "search_text": f"search-{document_id}-{chunk_index}",
        "document_id": document_id,
        "chunk_index": chunk_index,
        "metadata": {},
        "distance": distance,
        "document_title": title,
    }


def test_search_lexical_fuses_fts_and_trgm_for_cjk_query(monkeypatch):
    async def fake_fts(*args, **kwargs):
        return [_row(1, 0, "Doc A"), _row(2, 0, "Doc B")]

    async def fake_trgm(*args, **kwargs):
        return [_row(2, 0, "Doc B"), _row(3, 0, "Doc C")]

    monkeypatch.setattr(vector_store, "_search_lexical_fts", fake_fts)
    monkeypatch.setattr(vector_store, "_search_lexical_trgm", fake_trgm)

    rows = asyncio.run(vector_store.search_lexical(object(), "退款规则", k=3))

    assert rows[0]["document_id"] == 2
    assert {row["document_id"] for row in rows} == {1, 2, 3}


def test_search_hybrid_rrf_runs_dense_and_lexical_in_parallel(monkeypatch):
    dense_started = asyncio.Event()
    lexical_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_dense(*args, **kwargs):
        dense_started.set()
        await release.wait()
        return [_row(1, 0, "Dense Doc", distance=0.12)]

    async def fake_lexical(*args, **kwargs):
        lexical_started.set()
        await release.wait()
        return [_row(2, 0, "Lexical Doc")]

    monkeypatch.setattr(vector_store, "search", fake_dense)
    monkeypatch.setattr(vector_store, "search_lexical", fake_lexical)

    async def runner():
        task = asyncio.create_task(
            vector_store.search_hybrid_rrf(
                object(),
                query_text="退款规则",
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
        await asyncio.wait_for(dense_started.wait(), timeout=0.2)
        await asyncio.wait_for(lexical_started.wait(), timeout=0.2)
        release.set()
        return await asyncio.wait_for(task, timeout=0.2)

    rows = asyncio.run(runner())

    assert dense_started.is_set()
    assert lexical_started.is_set()
    assert {row["document_id"] for row in rows} == {1, 2}
