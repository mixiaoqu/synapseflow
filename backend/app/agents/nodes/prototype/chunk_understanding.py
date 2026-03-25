"""分块业务语义理解：每块输出 summary / intent / entities / features / page_hints（不提 UI 实现）。"""
import asyncio
import time
from typing import Any, Dict, List

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.core.llm import get_llm_for_analysis
from app.agents.nodes.prototype.chunking import PROTOTYPE_CHUNK_EXTRACT_CONCURRENCY
from app.agents.nodes.prototype.utils import parse_json_safely


def _ordered_chunks(state: DocToPrototypeState) -> List[Dict[str, Any]]:
    raw = state.get("requirements_chunks") or []
    return sorted(raw, key=lambda c: c.get("order", 0))


def _prompt_one(chunk: Dict[str, Any], order: int, total: int) -> str:
    title = (chunk.get("title") or "").strip() or "（无标题）"
    text = chunk.get("text") or ""
    cid = chunk.get("id") or ("c%s" % order)
    return f"""你是业务需求分析师。以下为同一份需求文档的第 {order + 1}/{total} 块，chunk_id={cid}。

# 块标题
{title}

# 块正文
{text}

---

只输出严格 JSON（可用 ```json 包裹），结构如下：
{{
  "chunk_id": "{cid}",
  "chunk_order": {order},
  "summary": "用 2～4 句概括本块在业务上的含义",
  "intent": "本块要达成的业务目标或要解决的问题",
  "entities": ["业务实体或对象名，如 订单、客户"],
  "features": ["业务能力或功能点，动词短语，如 导出报表、审批请假"],
  "page_hints": ["信息场景或主题域，如 报表中心、审批待办；不要写具体组件名"]
}}

硬性约束：
1. 不要描述界面：禁止出现 按钮、弹窗、路由、组件、表格样式、像素、颜色 等 UI 实现词汇（除非原文仅作为业务词出现）。
2. 不要编造本块未出现的业务内容；信息不足则数组留空、summary 如实说「未明确」。
3. features / page_hints 用中文短语，简短清晰。

开始分析。"""


def _empty_summary(chunk: Dict[str, Any], order: int) -> Dict[str, Any]:
    cid = chunk.get("id") or ("c%s" % order)
    return {
        "chunk_id": cid,
        "chunk_order": order,
        "summary": "",
        "intent": "",
        "entities": [],
        "features": [],
        "page_hints": [],
    }


async def _understand_one(
    llm: Any,
    chunk: Dict[str, Any],
    order: int,
    total: int,
) -> Dict[str, Any]:
    prompt = _prompt_one(chunk, order, total)
    response = await llm.ainvoke(prompt)
    parsed = parse_json_safely(response.content)
    if not isinstance(parsed, dict):
        return _empty_summary(chunk, order)
    cid = chunk.get("id") or ("c%s" % order)
    parsed.setdefault("chunk_id", cid)
    parsed.setdefault("chunk_order", order)
    parsed.setdefault("summary", "")
    parsed.setdefault("intent", "")
    parsed.setdefault("entities", [])
    parsed.setdefault("features", [])
    parsed.setdefault("page_hints", [])
    for key in ("entities", "features", "page_hints"):
        if not isinstance(parsed[key], list):
            parsed[key] = []
    return parsed


async def chunk_understanding_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """并行理解各块，写入 chunk_summaries。"""
    chunks = _ordered_chunks(state)
    if not chunks:
        return {"chunk_summaries": []}

    llm = get_llm_for_analysis()
    total = len(chunks)
    if total == 1:
        t0 = time.perf_counter()
        try:
            one = await _understand_one(llm, chunks[0], 0, 1)

            return {"chunk_summaries": [one]}
        except Exception as e:
            return {"chunk_summaries": [_empty_summary(chunks[0], 0)]}

    sem = asyncio.Semaphore(PROTOTYPE_CHUNK_EXTRACT_CONCURRENCY)

    async def _run(i: int, ch: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            try:
                return await _understand_one(llm, ch, i, total)
            except Exception as e:
                return _empty_summary(ch, i)

    t0 = time.perf_counter()
    results = await asyncio.gather(*[_run(i, ch) for i, ch in enumerate(chunks)])
    ordered = sorted(results, key=lambda x: x.get("chunk_order", 0))
    return {"chunk_summaries": ordered}
