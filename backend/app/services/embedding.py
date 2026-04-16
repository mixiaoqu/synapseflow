"""SentenceTransformer-based embedding service."""

import os
import threading

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

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
    logger.info(
        "Warming up embedding model model={} device={}",
        embedding_cfg.model,
        embedding_cfg.device,
    )
    _get_embedder()
    logger.info("Embedding model warmup complete model={}", embedding_cfg.model)


def embed_query(text: str) -> list[float]:
    """Embed one query string."""
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

    embedding_cfg = config_registry.get_embedding_config()
    vecs = _get_embedder().encode(
        texts,
        batch_size=embedding_cfg.batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vecs]
