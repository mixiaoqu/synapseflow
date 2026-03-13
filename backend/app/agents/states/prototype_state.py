"""文档转原型状态定义"""
from typing import TypedDict, List, Dict, Any


class DocToPrototypeState(TypedDict):
    """文档转原型状态"""
    requirements_doc: str
    extracted_requirements: Dict[str, Any]
    ui_components: List[Dict[str, Any]]
    design_system: Dict[str, Any]
    generated_html: str
    generated_css: str
    generated_js: str
    validation_errors: List[str]
    preview_url: str
    is_valid: bool
    metadata: Dict[str, Any]
