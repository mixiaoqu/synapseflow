"""文档转原型节点使用的工具函数"""
import json
from typing import Dict, Any


def parse_json_safely(content: str) -> Dict[str, Any]:
    """安全解析JSON"""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    try:
        return json.loads(content.strip())
    except Exception:
        return {}


def auto_complete_requirements(doc: str, partial: Dict[str, Any]) -> Dict[str, Any]:
    """智能补全需求（规则兜底），当LLM提取失败或不完整时使用"""
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

    color_map = {"blue": "#3B82F6", "purple": "#8B5CF6", "green": "#10B981", "red": "#EF4444"}
    result = {
        "page_info": partial.get("page_info", {
            "title": "自动生成页面", "type": page_type, "description": "根据需求文档自动生成"
        }),
        "functional_modules": partial.get("functional_modules", [{
            "id": "main_content", "name": "主内容区", "description": "页面主要内容",
            "position": "main", "components": ["Content"], "priority": "high"
        }]),
        "interactions": partial.get("interactions", []),
        "data_model": partial.get("data_model", []),
        "visual_style": {
            "theme": "modern", "color_scheme": color_scheme,
            "primary_color": color_map[color_scheme], "layout": "single_column",
            "font_family": "Inter", "responsive": True, **partial.get("visual_style", {})
        }
    }
    return result


def normalize_requirements(data: Dict[str, Any]) -> Dict[str, Any]:
    """规范化提取的需求数据，确保所有必需字段都存在且格式正确"""
    if "page_info" not in data:
        data["page_info"] = {"title": "自动生成页面", "type": "landing_page", "description": ""}
    for field in ["functional_modules", "interactions", "data_model"]:
        if field not in data or not isinstance(data[field], list):
            data[field] = []
    if "visual_style" not in data:
        data["visual_style"] = {
            "theme": "modern", "color_scheme": "blue", "primary_color": "#3B82F6",
            "layout": "single_column", "responsive": True
        }
    for i, module in enumerate(data.get("functional_modules", [])):
        if "id" not in module:
            module["id"] = f"module_{i}"
        if "components" not in module:
            module["components"] = []
    return data
