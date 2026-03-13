"""
BGE 中文嵌入服务
使用 HuggingFaceEmbeddings 进行文本向量化（本地 BGE-small-zh，512 维）
"""
from typing import List

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings

_embedder: HuggingFaceEmbeddings | None = None


def _get_embedder() -> HuggingFaceEmbeddings:
    """懒加载嵌入模型"""
    global _embedder
    if _embedder is None:
        model_name = settings.EMBEDDING_MODEL
        _embedder = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embedder


def embed_query(text: str) -> List[float]:
    """单条文本嵌入，返回 512 维向量"""
    return _get_embedder().embed_query(text)


def embed_documents(texts: List[str]) -> List[List[float]]:
    """批量文本嵌入"""
    return _get_embedder().embed_documents(texts)
