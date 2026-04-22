from __future__ import annotations

import os
import threading
import time
from typing import Any

from fastapi import FastAPI
from FlagEmbedding import FlagReranker
from pydantic import BaseModel, Field

MODEL_NAME = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
MODEL_LOAD_RETRIES = int(os.getenv("RERANK_MODEL_LOAD_RETRIES", "10"))
MODEL_LOAD_RETRY_DELAY = float(os.getenv("RERANK_MODEL_LOAD_RETRY_DELAY", "15"))
USE_FP16 = os.getenv("RERANK_USE_FP16", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(title="SynapseFlow Reranker")
_rerank_lock = threading.Lock()


def _load_reranker() -> FlagReranker:
    last_error: Exception | None = None
    for attempt in range(1, MODEL_LOAD_RETRIES + 1):
        try:
            print(
                f"Loading reranker model {MODEL_NAME} "
                f"(attempt {attempt}/{MODEL_LOAD_RETRIES})",
                flush=True,
            )
            return FlagReranker(MODEL_NAME, use_fp16=USE_FP16)
        except Exception as exc:
            last_error = exc
            if attempt >= MODEL_LOAD_RETRIES:
                break
            print(
                f"Failed to load reranker model: {exc!r}. "
                f"Retrying in {MODEL_LOAD_RETRY_DELAY:g}s...",
                flush=True,
            )
            time.sleep(MODEL_LOAD_RETRY_DELAY)
    raise RuntimeError(f"Failed to load reranker model after {MODEL_LOAD_RETRIES} attempts") from last_error


_reranker = _load_reranker()


class RerankRequest(BaseModel):
    model: str | None = None
    query: str = Field(..., min_length=1)
    documents: list[str] = Field(default_factory=list)
    top_n: int | None = Field(default=None, ge=1)


def _as_scores(raw_scores: Any) -> list[float]:
    if isinstance(raw_scores, (float, int)):
        return [float(raw_scores)]
    if hasattr(raw_scores, "tolist"):
        raw_scores = raw_scores.tolist()
    return [float(score) for score in list(raw_scores)]


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "use_fp16": USE_FP16,
    }


@app.post("/v1/rerank")
def rerank(body: RerankRequest) -> dict[str, list[dict[str, float | int]]]:
    indexed_documents = [
        (index, doc)
        for index, doc in enumerate(body.documents)
        if doc.strip()
    ]
    if not indexed_documents:
        return {"results": []}

    pairs = [[body.query, doc] for _, doc in indexed_documents]
    with _rerank_lock:
        scores = _as_scores(_reranker.compute_score(pairs))

    ranked = sorted(
        enumerate(scores),
        key=lambda item: item[1],
        reverse=True,
    )
    top_n = min(body.top_n or len(ranked), len(ranked))
    return {
        "results": [
            {
                "index": indexed_documents[local_index][0],
                "relevance_score": score,
            }
            for local_index, score in ranked[:top_n]
        ]
    }
