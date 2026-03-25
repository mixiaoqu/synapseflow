"""文档转原型状态定义（分块理解 → 结构抽取 → 规格归一 → 产品/交互设计 → 单次 HTML 生成）。"""
from typing import TypedDict, List, Dict, Any


class DocToPrototypeState(TypedDict):
    """LangGraph 文档转原型状态；多页场景下空列表/空字典表示尚未写入。"""

    # 需求正文：图外已规范化的纯文本（parse_uploaded_document 或 normalize_requirements_plaintext）
    requirements_doc: str
    # 从文档中抽取的结构化需求（与下游生成兼容：由产品层回写）
    extracted_requirements: Dict[str, Any]
    # 界面组件树或组件清单（设计节点产出）
    ui_components: List[Dict[str, Any]]
    # 设计系统（色板、字体、间距等）
    design_system: Dict[str, Any]
    # 最终合并后的完整 HTML（单页即整页；多页由 assembler 写入）
    generated_html: str
    # 校验错误信息列表
    validation_errors: List[str]
    # 后端保存预览文件后的访问路径（相对或绝对 URL）
    preview_url: str
    # 校验是否通过
    is_valid: bool
    # 扩展信息（耗时、模型名等）
    metadata: Dict[str, Any]

    # 文档切块，每块含 id、text、order 等
    requirements_chunks: List[Dict[str, Any]]
    # 每块业务语义摘要（不直接描述 UI 组件）
    chunk_summaries: List[Dict[str, Any]]
    # 结构抽取：角色、功能、流程、数据对象
    structured_spec: Dict[str, Any]
    # 归一化规格：去重合并后
    normalized_spec: Dict[str, Any]
    # 产品模型：页面、导航、用户流程
    product_spec: Dict[str, Any]
    # 交互设计：点击、表单、导航、状态
    interaction_spec: Dict[str, Any]

    # 站点地图 / 菜单项，供导航与按页生成
    site_map: List[Dict[str, Any]]
    # 各页 HTML 片段：键为页面 id（多页生成后再合并）
    page_html: Dict[str, str]
    # 生成策略：single 走单页；multi 按 site_map 分批生成
    generation_mode: str

    # 预留：历史校验重试回路字段（当前图为线性流程，未使用）
    prototype_revision_used: int
    prototype_revision_target: str


def prototype_state(requirements_doc: str) -> DocToPrototypeState:
    """
    构造 ainvoke/astream 的完整初始状态。
    requirements_doc 须在图外已规范化（上传走 parse_uploaded_document；字符串走 normalize_requirements_plaintext）。
    """
    return {
        "requirements_doc": requirements_doc,
        "extracted_requirements": {},
        "ui_components": [],
        "design_system": {},
        "generated_html": "",
        "validation_errors": [],
        "preview_url": "",
        "is_valid": False,
        "metadata": {},
        "requirements_chunks": [],
        "chunk_summaries": [],
        "structured_spec": {},
        "normalized_spec": {},
        "product_spec": {},
        "interaction_spec": {},
        "site_map": [],
        "page_html": {},
        "generation_mode": "single",
        "prototype_revision_used": 0,
        "prototype_revision_target": "",
    }
