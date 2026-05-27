from types import SimpleNamespace

import httpx

from app.services import embedding


class FakeEmbeddingResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ]
        }


class FakeEmbeddingClient:
    requests: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def post(self, url, json, headers):
        self.requests.append({"url": url, "json": json, "headers": headers})
        return FakeEmbeddingResponse()


def test_embed_documents_calls_siliconflow_embeddings_api(monkeypatch):
    FakeEmbeddingClient.requests = []
    monkeypatch.setattr(
        embedding.config_registry,
        "get_embedding_config",
        lambda: SimpleNamespace(
            provider="siliconflow",
            api_url="https://api.siliconflow.cn/v1/embeddings",
            api_key="sf-key",
            model="BAAI/bge-m3",
            dim=2,
            dimensions=2,
            batch_size=8,
            device="cpu",
        ),
    )
    monkeypatch.setattr(embedding.httpx, "Client", FakeEmbeddingClient, raising=False)

    vectors = embedding.embed_documents(["第一段", "第二段"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert FakeEmbeddingClient.requests == [
        {
            "url": "https://api.siliconflow.cn/v1/embeddings",
            "json": {
                "model": "BAAI/bge-m3",
                "input": ["第一段", "第二段"],
                "encoding_format": "float",
                "dimensions": 2,
            },
            "headers": {
                "Content-Type": "application/json",
                "Authorization": "Bearer sf-key",
            },
        }
    ]


def test_embed_documents_requires_siliconflow_api_key(monkeypatch):
    monkeypatch.setattr(
        embedding.config_registry,
        "get_embedding_config",
        lambda: SimpleNamespace(
            provider="siliconflow",
            api_url="https://api.siliconflow.cn/v1/embeddings",
            api_key="",
            model="BAAI/bge-m3",
            dim=2,
            dimensions=2,
            batch_size=8,
            device="cpu",
        ),
    )

    try:
        embedding.embed_documents(["第一段"])
    except ValueError as exc:
        assert "SILICONFLOW_API_KEY" in str(exc)
    else:
        raise AssertionError("missing SiliconFlow API key should fail fast")

