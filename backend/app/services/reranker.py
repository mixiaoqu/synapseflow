"""
Rerank 服务：通过远程 API 对 (query, chunks) 重排
支持 bailian（阿里云百炼）和 vllm（自建 vLLM）
"""
from typing import List

import httpx
from loguru import logger

from app.core.config import settings
from app.core.config.registry import config_registry

BAILIAN_RERANK_URL = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"


def _get_url_and_headers():
    """根据 provider 返回请求 URL 和 headers"""
    rerank_cfg = config_registry.get_rerank_config()
    if rerank_cfg.provider == "bailian":
        api_key = settings.DASHSCOPE_API_KEY
        if not api_key:
            raise ValueError("RERANK_PROVIDER=bailian 时需配置 DASHSCOPE_API_KEY")
        return BAILIAN_RERANK_URL, {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    # vllm
    url = rerank_cfg.api_url.rstrip("/")
    if "/rerank" not in url:
        url = f"{url}/v1/rerank"
    headers = {"Content-Type": "application/json"}
    if settings.RERANK_API_KEY:
        headers["Authorization"] = f"Bearer {settings.RERANK_API_KEY}"
    return url, headers


def _coerce_rerank_index(idx_raw, n_chunks: int) -> int | None:
    """将 API 返回的 index 转为 0-based；兼容部分服务使用 1-based。"""
    if idx_raw is None:
        return None
    try:
        idx = int(idx_raw)
    except (TypeError, ValueError):
        return None
    if 0 <= idx < n_chunks:
        return idx
    if 1 <= idx <= n_chunks:
        return idx - 1
    return None


def _build_payload(query: str, documents: list[str], top_n: int):
    """构建请求体"""
    rerank_cfg = config_registry.get_rerank_config()
    payload = {
        "model": rerank_cfg.model,
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents)),
    }
    if rerank_cfg.provider == "bailian" and rerank_cfg.instruct:
        payload["instruct"] = rerank_cfg.instruct
    return payload


def _parse_response(data: dict, chunks: list[dict], top_k: int) -> list[dict]:
    """解析 API 响应，bailian 为 output.results，vllm 为 results 或 data"""
    if config_registry.get_rerank_config().provider == "bailian":
        output = data.get("output") or {}
        raw = output.get("results") or []
        # 兼容 compatible-api 可能返回的 data.results 或顶层 results
        if not raw:
            raw = data.get("results") or data.get("data") or []
        if raw:
            logger.debug("精排 响应首条字段 {}", list(raw[0].keys()) if raw else [])
    else:
        raw = data.get("results") or data.get("data") or []

    if not raw:
        logger.warning("精排 无 results，顶层 keys={}", list(data.keys()))
        return chunks[:top_k]

    out: list[dict] = []
    seen: set[int] = set()
    for r in raw:
        if len(out) >= top_k:
            break
        idx_raw = r.get("index", r.get("idx"))
        idx = _coerce_rerank_index(idx_raw, len(chunks))
        if idx is None:
            if idx_raw is not None:
                logger.warning("精排 无效下标 index={}（共 {} 条）", idx_raw, len(chunks))
            continue
        if idx in seen:
            continue
        seen.add(idx)
        score = r.get("relevance_score", r.get("score", r.get("relevance", 0.0)))
        chunk = dict(chunks[idx])
        chunk["rerank_score"] = float(score)
        out.append(chunk)

    if not out and chunks:
        logger.warning(
            "精排 解析为空 raw={} 条，回退向量序 top={}",
            len(raw),
            top_k,
        )
        return chunks[:top_k]
    if out:
        logger.debug(
            "精排 首条 index={} score={}",
            raw[0].get("index"),
            raw[0].get("relevance_score", raw[0].get("score")),
        )
    return out


async def rerank(query: str, chunks: List[dict], top_k: int | None = None) -> List[dict]:
    """
    调用远程 Rerank API，对 chunks 按与 query 的相关度重排

    chunks: [{"chunk_text": str, "document_id": int, "chunk_index": int, "distance": float}, ...]
    返回: 按 rerank 分数排序后的子集，每项增加 "rerank_score"
    """
    if not chunks:
        logger.debug("精排 跳过（无输入）")
        return []

    top_k = top_k or config_registry.get_rag_config().retrieval.final_top_k
    documents = [c.get("search_text") or c["chunk_text"] for c in chunks]

    try:
        url, headers = _get_url_and_headers()
        logger.debug("精排 请求 {}", url.split("?")[0])
    except ValueError as e:
        logger.error("精排 配置错误: {}", e)
        return chunks[:top_k]

    payload = _build_payload(query, documents, top_k)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        body = e.response.text
        if len(body) > 120:
            body = body[:120] + "…"
        logger.error("精排 HTTP {} {}", e.response.status_code, body)
        return chunks[:top_k]
    except Exception as e:
        logger.exception("精排 请求异常: {}", e)
        return chunks[:top_k]

    # 检查百炼的错误响应
    if "code" in data and data.get("code"):
        logger.error("精排 API 错误 code={} {}", data.get("code"), data.get("message", ""))
        return chunks[:top_k]

    out = _parse_response(data, chunks, top_k)
    scores = [round(r.get("rerank_score", 0), 4) for r in out]
    if scores:
        logger.info(
            "精排 完成 {} 条 | 分 {:.3f}~{:.3f}",
            len(out),
            min(scores),
            max(scores),
        )
    else:
        logger.info("精排 完成 {} 条", len(out))
    if out and all(s == 0 for s in scores):
        raw = (data.get("output") or {}).get("results") or data.get("results") or data.get("data") or []
        sample = raw[0] if raw else {}
        logger.warning(
            "精排 全为 0 分，样例字段 {}",
            {k: v for k, v in sample.items() if k != "document"},
        )
    return out
