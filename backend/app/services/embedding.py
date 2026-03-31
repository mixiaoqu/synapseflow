"""
BGE 中文嵌入服务 进行文本向量化
直接使用 SentenceTransformer，优先加载 safetensors，避免重复下载 pytorch_model.bin
"""
import os
from typing import List

# 在导入 huggingface 相关库之前设置，抑制 symlinks 警告
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from sentence_transformers import SentenceTransformer

from app.core.config import config_registry

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    """懒加载嵌入模型"""
    global _embedder
    if _embedder is None:
        embedding_cfg = config_registry.get_embedding_config()
        _embedder = SentenceTransformer(
            embedding_cfg.model,
            device="cpu",
        )
    return _embedder


def embed_query(text: str) -> List[float]:
    """单条文本嵌入"""
    vec = _get_embedder().encode(
        text,
        normalize_embeddings=True,
    )
    return vec.tolist()


def embed_documents(texts: List[str]) -> List[List[float]]:
    """批量文本嵌入"""
    if not texts:
        return []
    vecs = _get_embedder().encode(
        texts,
        normalize_embeddings=True,
    )
    return [v.tolist() for v in vecs]
