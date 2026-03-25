"""归一化规格：去重、合并、消歧（如同一能力多种说法）。"""
import json
import time
from typing import Any, Dict

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.core.llm import get_llm_for_analysis
from app.agents.nodes.prototype.utils import parse_json_safely


def _fallback_normalize(structured: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "roles": list(structured.get("roles") or []),
        "features": list(structured.get("features") or []),
        "business_flows": list(structured.get("business_flows") or []),
        "data_objects": list(structured.get("data_objects") or []),
        "aliases": [],
        "notes": "",
    }


async def normalize_spec_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """LLM 归一化 structured_spec → normalized_spec。"""
    structured = state.get("structured_spec") or {}
    if not structured:
        logger.warning("[规格归一] structured_spec 为空，输出空归一化结果")
        return {"normalized_spec": _fallback_normalize({})}

    llm = get_llm_for_analysis()
    prompt = f"""你是需求治理专家。对下列结构化需求做归一化：合并同义功能、消歧、去掉重复项。

# 输入 JSON
{json.dumps(structured, ensure_ascii=False)}

---

输出严格 JSON，结构：
{{
  "roles": [{{ "name": "", "description": "" }}],
  "features": [{{ "name": "", "description": "", "priority": "high|medium|low" }}],
  "business_flows": [{{ "name": "", "steps": [] }}],
  "data_objects": [{{ "name": "", "attributes": [], "notes": "" }}],
  "aliases": [{{ "canonical": "规范名", "variants": ["别称1", "别称2"] }}],
  "notes": "归并时做的假设（简短）"
}}

规则：
1. 「用户登录」与「账号登录」等应合并为一条 feature，aliases 记录别称。
2. 保持业务语义，仍不要写 UI 实现细节。
3. 仅返回 JSON。"""

    t0 = time.perf_counter()
    try:
        resp = await llm.ainvoke(prompt)
        data = parse_json_safely(resp.content)
        if not isinstance(data, dict):
            data = _fallback_normalize(structured)
        for k in ("roles", "features", "business_flows", "data_objects", "aliases"):
            if k not in data or not isinstance(data[k], list):
                data[k] = []
        if "notes" not in data or not isinstance(data["notes"], str):
            data["notes"] = ""
        logger.info(
            "[规格归一] 完成，features=%s，耗时 %.1fs",
            len(data.get("features") or []),
            time.perf_counter() - t0,
        )
        return {"normalized_spec": data}
    except Exception as e:
        logger.error("[规格归一] 失败，回退拷贝: %s", e, exc_info=True)
        return {"normalized_spec": _fallback_normalize(structured)}
