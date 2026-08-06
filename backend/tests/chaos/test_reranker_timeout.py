import asyncio

import httpx

from app.services import reranker


class TimeoutAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        request = httpx.Request("POST", "http://reranker.test/v1/rerank")
        raise httpx.ReadTimeout("reranker read timeout", request=request)


def test_reranker_timeout_falls_back_to_original_order(monkeypatch):
    chunks = [
        {"chunk_text": "退款规则说明。", "document_id": 1, "chunk_index": 0},
        {"chunk_text": "发货规则说明。", "document_id": 2, "chunk_index": 0},
    ]
    warnings: list[str] = []

    monkeypatch.setattr(reranker.httpx, "AsyncClient", TimeoutAsyncClient)
    monkeypatch.setattr(
        reranker.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(message.format(*args)),
    )

    result = asyncio.run(reranker.rerank("如何退款？", chunks, top_k=1))

    assert result == chunks[:1]
    assert any("回退原始排序" in warning for warning in warnings)
