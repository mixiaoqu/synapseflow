"""结构抽取层：从 chunk_summaries 汇总为 roles / features / business_flows / data_objects。"""
import json
import time
from typing import Any, Dict

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.core.llm import get_llm_for_analysis
from app.agents.nodes.prototype.utils import parse_json_safely


def _empty_structured() -> Dict[str, Any]:
    return {
        "roles": [],
        "features": [],
        "business_flows": [],
        "data_objects": [],
    }


async def structure_extraction_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """将分块业务语义合并为统一结构（类似产品经理整理需求）。"""
    summaries = state.get("chunk_summaries") or []
    doc = (state.get("requirements_doc") or "").strip()
    if not summaries and not doc:
        logger.warning("[结构抽取] 无 chunk_summaries 与正文，输出空结构")
        return {"structured_spec": _empty_structured()}

    payload = json.dumps(summaries, ensure_ascii=False) if summaries else "[]"
    doc_head = doc[:6000] if doc else ""

    llm = get_llm_for_analysis()
    prompt = f"""你是资深产品经理。根据下列「分块业务语义」与需求正文摘录，整理为统一需求结构。

# 分块摘要（JSON）
{payload}


---

输出严格 JSON（勿 markdown 代码块），结构：
{{
  "roles": [{{ "name": "角色名", "description": "职责简述" }}],
  "features": [{{ "name": "功能名", "description": "说明", "priority": "high|medium|low" }}],
  "business_flows": [{{ "name": "流程名", "steps": ["步骤1", "步骤2"] }}],
  "data_objects": [{{ "name": "对象名", "attributes": ["字段或属性"], "notes": "" }}]
}}

规则：
1. 去重合并各块重复的 feature / 实体；冲突时在 description 中兼容表述。
2. 仍不要写 UI 组件名；写业务流程与业务数据。
3. 信息不足时数组可为空，不要编造。

仅返回 JSON。"""

    t0 = time.perf_counter()
    try:
        resp = await llm.ainvoke(prompt)
        data = parse_json_safely(resp.content)
        if not isinstance(data, dict):
            data = _empty_structured()
        for k in ("roles", "features", "business_flows", "data_objects"):
            if k not in data or not isinstance(data[k], list):
                data[k] = []
        logger.info(
            "[结构抽取] 完成，features=%s flows=%s，耗时 %.1fs",
            len(data.get("features") or []),
            len(data.get("business_flows") or []),
            time.perf_counter() - t0,
        )
        return {"structured_spec": data}
    except Exception as e:
        logger.error("[结构抽取] 失败: %s", e, exc_info=True)
        return {"structured_spec": _empty_structured()}
