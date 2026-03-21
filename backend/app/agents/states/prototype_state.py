"""文档转原型状态定义"""
from typing import TypedDict, List, Dict, Any


class DocToPrototypeState(TypedDict):
    """文档转原型状态"""
    requirements_doc: str # 需求文档
    extracted_requirements: Dict[str, Any] # 提取的需求
    ui_components: List[Dict[str, Any]] # UI组件
    design_system: Dict[str, Any] # 设计系统
    generated_html: str # 生成的HTML
    validation_errors: List[str] # 验证错误
    preview_url: str # 预览URL
    is_valid: bool # 是否有效
    metadata: Dict[str, Any] # 元数据
