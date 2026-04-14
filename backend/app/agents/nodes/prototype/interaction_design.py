"""交互设计层：补全可点击原型的交互契约，并写回 extracted_requirements.interactions。"""
import copy
import json
import time
from typing import Any, Dict, List

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.core.llm import get_llm_for_planner
from app.agents.nodes.prototype.utils import parse_json_safely, normalize_requirements


def _empty_interaction() -> Dict[str, Any]:
    return {
        "click": "",
        "form_submit": "",
        "navigation": "",
        "state_change": "",
    }


def _merge_interactions(
    extracted: Dict[str, Any],
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    out = copy.deepcopy(extracted) if extracted else {}
    base: List[Dict[str, Any]] = list(out.get("interactions") or [])
    keys = ("click", "form_submit", "navigation", "state_change")
    for k in keys:
        val = spec.get(k)
        if isinstance(val, str) and val.strip():
            base.append(
                {
                    "id": "ix_%s" % k,
                    "trigger": k,
                    "action": val.strip(),
                    "target": "",
                    "event_type": "click" if k == "click" else ("submit" if k == "form_submit" else "nav"),
                }
            )
    out["interactions"] = base
    return normalize_requirements(out)


async def interaction_design_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """基于 product_spec 与 normalized_spec 生成 interaction_spec。"""
    product = state.get("product_spec") or {}
    normalized = state.get("normalized_spec") or {}
    extracted = state.get("extracted_requirements") or {}

    llm = get_llm_for_planner()
    prompt = f"""你是交互设计师。根据产品与业务规格，用**简短规则句**描述原型中需要体现的交互（不要求写代码）。

# 产品规格
{json.dumps(product, ensure_ascii=False)}

# 归一化业务规格（摘录）
{json.dumps({k: normalized.get(k) for k in ("features", "business_flows", "data_objects")}, ensure_ascii=False)}

---

输出严格 JSON：
{{
  "click": "主要点击行为说明（列表、按钮、行操作等）",
  "form_submit": "表单提交与校验示意说明",
  "navigation": "页面间跳转与返回说明，须与页面 id / hash 路由一致",
  "state_change": "列表筛选、Tab、展开收起等状态变化说明"
}}

若无某类交互，对应字段可写空字符串。
仅返回 JSON。"""

    t0 = time.perf_counter()
    try:
        resp = await llm.ainvoke(prompt)
        spec = parse_json_safely(resp.content)
        if not isinstance(spec, dict):
            spec = _empty_interaction()
        for k in ("click", "form_submit", "navigation", "state_change"):
            if k not in spec:
                spec[k] = ""
            elif not isinstance(spec[k], str):
                spec[k] = str(spec[k])
        merged = _merge_interactions(extracted, spec)
        logger.info(
            "[交互设计] 完成，补充交互 %s 条，耗时 %.1fs",
            len(merged.get("interactions") or []),
            time.perf_counter() - t0,
        )
        return {
            "interaction_spec": spec,
            "extracted_requirements": merged,
        }
    except Exception as e:
        logger.error("[交互设计] 失败: %s", e, exc_info=True)
        spec = _empty_interaction()
        return {
            "interaction_spec": spec,
            "extracted_requirements": _merge_interactions(extracted, spec),
        }
