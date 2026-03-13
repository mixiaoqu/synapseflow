"""文档转原型图"""
from langgraph.graph import StateGraph, END

from app.agents.states.prototype_state import DocToPrototypeState
from app.agents.nodes.prototype import (
    extract_requirements_node,
    design_components_node,
    generate_html_node,
    generate_css_node,
    generate_js_node,
    validate_and_preview_node,
)


def create_doc_to_prototype_graph():
    """创建文档转原型图"""
    workflow = StateGraph(DocToPrototypeState)

    workflow.add_node("extract_requirements", extract_requirements_node)
    workflow.add_node("design_components", design_components_node)
    workflow.add_node("generate_html", generate_html_node)
    workflow.add_node("generate_css", generate_css_node)
    workflow.add_node("generate_js", generate_js_node)
    workflow.add_node("validate_preview", validate_and_preview_node)

    workflow.set_entry_point("extract_requirements")

    workflow.add_edge("extract_requirements", "design_components")
    workflow.add_edge("design_components", "generate_html")
    workflow.add_edge("generate_html", "generate_css")
    workflow.add_edge("generate_css", "generate_js")
    workflow.add_edge("generate_js", "validate_preview")
    workflow.add_edge("validate_preview", END)

    return workflow.compile()
