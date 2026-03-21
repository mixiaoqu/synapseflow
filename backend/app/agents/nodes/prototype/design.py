"""组件设计节点"""
import json
from typing import Dict, Any

from app.agents.states.prototype_state import DocToPrototypeState
from app.core.llm import get_llm_for_planner

from app.agents.nodes.prototype.utils import parse_json_safely


def _normalize_colors(colors: dict) -> dict:
    """将嵌套的 colors（如 primary: {500: "#3B82F6"}）展平为单层 hex 字符串"""
    result = {}
    for key, val in (colors or {}).items():
        if isinstance(val, str) and val.startswith("#"):
            result[key] = val
        elif isinstance(val, dict):
            # 优先取 500，否则取第一个 hex 值
            pick = val.get("500") or val.get("DEFAULT") or next(
                (v for v in val.values() if isinstance(v, str) and v.startswith("#")),
                "#3B82F6",
            )
            result[key] = pick if isinstance(pick, str) else "#3B82F6"
        else:
            result[key] = "#3B82F6"
    return result


def _normalize_design_system(design_system: dict) -> dict:
    """规范化 design_system 结构，确保 colors 等字段格式正确"""
    result = dict(design_system or {})
    if "colors" in result:
        result["colors"] = _normalize_colors(result["colors"])
    return result


async def design_components_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """
    组件设计节点：设计HTML组件架构和设计系统
    使用：planner - 规划任务模型
    """
    llm = get_llm_for_planner()
    requirements = state["extracted_requirements"]

    prompt = f"""
基于需求设计HTML组件结构和设计系统：

需求信息：
{json.dumps(requirements, ensure_ascii=False)}

请设计，严格按以下 JSON 结构返回：

{{
    "components": [
        {{
            "tag": "header",
            "classes": ["sticky", "top-0"],
            "children": []
        }}
    ],
    "design_system": {{
        "colors": {{
            "primary": "#3B82F6",
            "secondary": "#8B5CF6",
            "background": "#FFFFFF"
        }},
        "typography": {{
            "font_family": "'Inter', sans-serif",
            "font_size": {{"base": "1rem", "lg": "1.125rem"}}
        }},
        "spacing": {{"base": "0.25rem", "scale": [0, 4, 8, 16, 24, 32, 48, 64]}}
    }}
}}

**重要约束：**
1. colors：每个 key 的值必须是单个 hex 字符串（如 "#3B82F6"），禁止使用嵌套对象（如 primary:{{50:"#...",500:"#..."}}）
2. typography.font_size：仅使用简单 key-value（如 base:"1rem"），不要嵌套对象
3. 直接返回 JSON，不要用 markdown 包裹
"""

    response = await llm.ainvoke(prompt)
    design = parse_json_safely(response.content)

    if not design:
        design = {"components": [], "design_system": {}}

    components = design.get("components") or design.get("ui_components") or []
    design_system = design.get("design_system") or {}
    design_system = _normalize_design_system(design_system)

    if not components:
        functional_modules = requirements.get("functional_modules", [])
        for m in functional_modules[:8]:
            comp = {
                "tag": "section",
                "classes": [m.get("id", "section").replace(" ", "_")],
                "children": [],
                "name": m.get("name", "")
            }
            components.append(comp)

    if not design_system:
        design_system = {"colors": {"primary": "#3B82F6"}, "typography": {"font_family": "Inter, sans-serif"}}

    return {"ui_components": components, "design_system": design_system}
