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
    if settings.RERANK_PROVIDER == "bailian":
        api_key = settings.DASHSCOPE_API_KEY
        if not api_key:
            raise ValueError("RERANK_PROVIDER=bailian 时需配置 DASHSCOPE_API_KEY")
        return BAILIAN_RERANK_URL, {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    # vllm
    url = settings.RERANK_API_URL.rstrip("/")
    if "/rerank" not in url:
        url = f"{url}/v1/rerank"
    headers = {"Content-Type": "application/json"}
    if settings.RERANK_API_KEY:
        headers["Authorization"] = f"Bearer {settings.RERANK_API_KEY}"
    return url, headers


def _build_payload(query: str, documents: list[str], top_n: int):
    """构建请求体"""
    payload = {
        "model": settings.RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents)),
    }
    if settings.RERANK_PROVIDER == "bailian" and settings.RERANK_INSTRUCT:
        payload["instruct"] = settings.RERANK_INSTRUCT
    return payload


def _parse_response(data: dict, chunks: list[dict], top_k: int) -> list[dict]:
    """解析 API 响应，bailian 为 output.results，vllm 为 results 或 data"""
    if settings.RERANK_PROVIDER == "bailian":
        output = data.get("output") or {}
        raw = output.get("results") or []
        # 兼容 compatible-api 可能返回的 data.results 或顶层 results
        if not raw:
            raw = data.get("results") or data.get("data") or []
        if raw:
            logger.debug("[Rerank] 响应结构 output.results 首项 keys={}", list(raw[0].keys()) if raw else [])
    else:
        raw = data.get("results") or data.get("data") or []

    if not raw:
        logger.warning("[Rerank] 响应无 results，data keys={}", list(data.keys()))
        return chunks[:top_k]

    out = []
    for r in raw[:top_k]:
        idx = r.get("index", r.get("idx", len(out)))
        score = r.get("relevance_score", r.get("score", r.get("relevance", 0.0)))
        if 0 <= idx < len(chunks):
            chunk = dict(chunks[idx])
            chunk["rerank_score"] = float(score)
            out.append(chunk)
        else:
            logger.warning("[Rerank] 无效 index={} 超出 chunks 长度 {}", idx, len(chunks))
    if out:
        logger.debug("[Rerank] 解析首项 index={} score={} raw_keys={}", raw[0].get("index"), raw[0].get("relevance_score", raw[0].get("score")), list(raw[0].keys()))
    return out


async def rerank(query: str, chunks: List[dict], top_k: int | None = None) -> List[dict]:
    """
    调用远程 Rerank API，对 chunks 按与 query 的相关度重排

    chunks: [{"chunk_text": str, "document_id": int, "chunk_index": int, "distance": float}, ...]
    返回: 按 rerank 分数排序后的子集，每项增加 "rerank_score"
    """
    if not chunks:
        logger.debug("[Rerank] 输入为空，跳过")
        return []

    top_k = top_k or config_registry.get_rag_config()["retrieval"]["final_top_k"]
    documents = [c["chunk_text"] for c in chunks]

    try:
        url, headers = _get_url_and_headers()
        logger.debug("[Rerank] 请求 URL={}", url.split("?")[0])
    except ValueError as e:
        logger.error("[Rerank] 配置错误: {}", e)
        return chunks[:top_k]

    payload = _build_payload(query, documents, top_k)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("[Rerank] API 请求失败 status={} body={}", e.response.status_code, e.response.text[:200])
        return chunks[:top_k]
    except Exception as e:
        logger.exception("[Rerank] API 调用异常: {}", e)
        return chunks[:top_k]

    # 检查百炼的错误响应
    if "code" in data and data.get("code"):
        logger.error("[Rerank] API 返回错误 code={} message={}", data.get("code"), data.get("message", ""))
        return chunks[:top_k]

    out = _parse_response(data, chunks, top_k)
    scores = [round(r.get("rerank_score", 0), 4) for r in out]
    logger.info("[Rerank] 完成 返回{}条 rerank_score={}", len(out), scores)
    if out and all(s == 0 for s in scores):
        # 全 0 时打印原始响应结构便于排查
        raw = (data.get("output") or {}).get("results") or data.get("results") or data.get("data") or []
        sample = raw[0] if raw else {}
        logger.warning("[Rerank] 所有 score 为 0，请检查 API 响应 首项示例={}", {k: v for k, v in sample.items() if k != "document"})
    return out
