import asyncio

import httpx

from app.services import reranker


class FailingAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.ConnectError("All connection attempts failed")


def test_rerank_connection_error_falls_back_without_exception_log(monkeypatch):
    chunks = [
        {"chunk_text": "快捷回复用于配置常见问题回复。", "document_id": 1, "chunk_index": 0},
        {"chunk_text": "门店入库用于记录入库单。", "document_id": 2, "chunk_index": 0},
    ]
    warnings: list[str] = []

    monkeypatch.setattr(reranker.httpx, "AsyncClient", FailingAsyncClient)
    monkeypatch.setattr(
        reranker.logger,
        "exception",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("connection errors should not log tracebacks")
        ),
    )
    monkeypatch.setattr(
        reranker.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(message.format(*args)),
    )

    result = asyncio.run(reranker.rerank("快捷回复相关问题", chunks, top_k=1))

    assert result == chunks[:1]
    assert warnings
