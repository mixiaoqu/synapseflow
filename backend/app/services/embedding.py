"""Embedding service with local and SiliconFlow online providers."""

import os
import threading

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import httpx
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.core.config import config_registry

_embedder: SentenceTransformer | None = None
_embedder_lock = threading.Lock()


def _validate_embedding_dim(embedder: SentenceTransformer) -> None:
    """Fail fast when the configured vector dimension does not match the model."""
    configured_dim = config_registry.get_embedding_config().dim
    model_dim = embedder.get_sentence_embedding_dimension()
    if model_dim is None or model_dim == configured_dim:
        return
    raise ValueError(
        "Embedding dimension mismatch: "
        f"config={configured_dim}, model={model_dim}. "
        "Update config/embedding.yaml and database vector schema together."
    )


def _get_embedder() -> SentenceTransformer:
    """Lazily create a shared embedder instance."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                embedding_cfg = config_registry.get_embedding_config()
                logger.info(
                    "Loading embedding model model={} device={}",
                    embedding_cfg.model,
                    embedding_cfg.device,
                )
                embedder = SentenceTransformer(
                    embedding_cfg.model,
                    device=embedding_cfg.device,
                )
                _validate_embedding_dim(embedder)
                _embedder = embedder
    return _embedder


def warmup_embedding_model() -> None:
    """Load the shared embedder eagerly during process startup."""
    embedding_cfg = config_registry.get_embedding_config()
    provider = (embedding_cfg.provider or "local").strip().lower()
    if provider == "siliconflow":
        logger.info("Skipping local embedding warmup for online provider={}", provider)
        return
    logger.info(
        "Warming up embedding model model={} device={}",
        embedding_cfg.model,
        embedding_cfg.device,
    )
    _get_embedder()
    logger.info("Embedding model warmup complete model={}", embedding_cfg.model)


def _siliconflow_url() -> str:
    embedding_cfg = config_registry.get_embedding_config()
    url = (embedding_cfg.api_url or "").strip().rstrip("/")
    if not url:
        raise ValueError("SiliconFlow embedding API URL is not configured")
    return url


def _siliconflow_headers() -> dict[str, str]:
    embedding_cfg = config_registry.get_embedding_config()
    if not embedding_cfg.api_key:
        raise ValueError("SILICONFLOW_API_KEY is required for SiliconFlow embeddings")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {embedding_cfg.api_key}",
    }


def _build_siliconflow_payload(texts: list[str]) -> dict:
    embedding_cfg = config_registry.get_embedding_config()
    payload = {
        "model": embedding_cfg.model,
        "input": texts,
        "encoding_format": "float",
    }
    if embedding_cfg.dimensions is not None:
        payload["dimensions"] = int(embedding_cfg.dimensions)
    return payload


def _parse_siliconflow_embeddings(data: dict, expected_count: int) -> list[list[float]]:
    raw_items = data.get("data") or []
    if len(raw_items) != expected_count:
        raise ValueError(
            "SiliconFlow embedding response count mismatch: "
            f"expected={expected_count}, actual={len(raw_items)}"
        )
    ordered_items = sorted(raw_items, key=lambda item: int(item.get("index", 0)))
    vectors: list[list[float]] = []
    configured_dim = config_registry.get_embedding_config().dim
    for item in ordered_items:
        vector = item.get("embedding")
        if not isinstance(vector, list):
            raise ValueError("SiliconFlow embedding response is missing embedding vector")
        if len(vector) != configured_dim:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"config={configured_dim}, response={len(vector)}. "
                "Update config/embedding.yaml and database vector schema together."
            )
        vectors.append([float(value) for value in vector])
    return vectors


def _embed_documents_siliconflow(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embedding_cfg = config_registry.get_embedding_config()
    vectors: list[list[float]] = []
    headers = _siliconflow_headers()
    url = _siliconflow_url()
    batch_size = max(1, int(embedding_cfg.batch_size))
    with httpx.Client(timeout=60.0) as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = client.post(url, json=_build_siliconflow_payload(batch), headers=headers)
            response.raise_for_status()
            vectors.extend(_parse_siliconflow_embeddings(response.json(), len(batch)))
    return vectors


def _embedding_provider() -> str:
    return (config_registry.get_embedding_config().provider or "local").strip().lower()


def embed_query(text: str) -> list[float]:
    """Embed one query string."""
    if _embedding_provider() == "siliconflow":
        vectors = _embed_documents_siliconflow([text])
        return vectors[0] if vectors else []
    vec = _get_embedder().encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vec.tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document chunks."""
    if not texts:
        return []

    if _embedding_provider() == "siliconflow":
        return _embed_documents_siliconflow(texts)

    embedding_cfg = config_registry.get_embedding_config()
    vecs = _get_embedder().encode(
        texts,
        batch_size=embedding_cfg.batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vecs]
