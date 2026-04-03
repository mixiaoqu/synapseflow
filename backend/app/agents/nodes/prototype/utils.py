"""Utility helpers used by prototype workflow nodes."""

from typing import Any, Dict

from app.agents.common.llm_json import parse_llm_json_object


def parse_json_safely(content: str) -> Dict[str, Any]:
    """Safely parse JSON returned by an LLM."""

    return parse_llm_json_object(content)


def auto_complete_requirements(doc: str, partial: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback requirements completion when extraction is incomplete."""

    doc_lower = doc.lower()
    page_type = "landing_page"
    if any(word in doc_lower for word in ["登录", "login", "注册", "signup"]):
        page_type = "form"
    elif any(word in doc_lower for word in ["仪表盘", "dashboard", "后台"]):
        page_type = "dashboard"
    elif any(word in doc_lower for word in ["产品", "商品", "购物", "电商"]):
        page_type = "ecommerce"

    color_scheme = "blue"
    if any(word in doc_lower for word in ["紫色", "purple", "violet"]):
        color_scheme = "purple"
    elif any(word in doc_lower for word in ["绿色", "green"]):
        color_scheme = "green"
    elif any(word in doc_lower for word in ["红色", "red"]):
        color_scheme = "red"

    color_map = {
        "blue": "#3B82F6",
        "purple": "#8B5CF6",
        "green": "#10B981",
        "red": "#EF4444",
    }
    result = {
        "page_info": partial.get(
            "page_info",
            {
                "title": "自动生成页面",
                "type": page_type,
                "description": "根据需求文档自动生成",
            },
        ),
        "functional_modules": partial.get(
            "functional_modules",
            [
                {
                    "id": "main_content",
                    "name": "主内容区",
                    "description": "页面主要内容",
                    "position": "main",
                    "components": ["Content"],
                    "priority": "high",
                }
            ],
        ),
        "interactions": partial.get("interactions", []),
        "data_model": partial.get("data_model", []),
        "visual_style": {
            "theme": "modern",
            "color_scheme": color_scheme,
            "primary_color": color_map[color_scheme],
            "layout": "single_column",
            "font_family": "Inter",
            "responsive": True,
            **partial.get("visual_style", {}),
        },
    }
    return result


def normalize_requirements(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize extracted requirements into a stable shape."""

    if "page_info" not in data:
        data["page_info"] = {
            "title": "自动生成页面",
            "type": "landing_page",
            "description": "",
        }
    for field in ["functional_modules", "interactions", "data_model"]:
        if field not in data or not isinstance(data[field], list):
            data[field] = []
    if "visual_style" not in data:
        data["visual_style"] = {
            "theme": "modern",
            "color_scheme": "blue",
            "primary_color": "#3B82F6",
            "layout": "single_column",
            "responsive": True,
        }
    for index, module in enumerate(data.get("functional_modules", [])):
        if "id" not in module:
            module["id"] = f"module_{index}"
        if "components" not in module:
            module["components"] = []
    return data
