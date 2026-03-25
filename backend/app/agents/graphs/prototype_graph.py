"""文档转原型图：文档理解 → 结构抽取 → 产品/交互设计 → 单次生成 HTML 原型。"""
from __future__ import annotations

from typing import Any, Dict, List

from langgraph.graph import StateGraph, END

from app.agents.states.prototype import DocToPrototypeState
from app.agents.nodes.prototype import (
    prepare_requirement_chunks_node,
    chunk_understanding_node,
    structure_extraction_node,
    normalize_spec_node,
    product_design_node,
    interaction_design_node,
    generate_prototype_from_spec_node,
)


def create_doc_to_prototype_graph():
    """创建文档转原型图。不在图内解析文件；入图请用 prototype_state（图外可先 parse_uploaded_document）。"""
    workflow = StateGraph(DocToPrototypeState)
    workflow.add_node("prepare_requirement_chunks", prepare_requirement_chunks_node)
    workflow.add_node("chunk_understanding", chunk_understanding_node)
    workflow.add_node("structure_extraction", structure_extraction_node)
    workflow.add_node("normalize_spec", normalize_spec_node)
    workflow.add_node("product_design", product_design_node)
    workflow.add_node("interaction_design", interaction_design_node)
    workflow.add_node("generate_prototype_from_spec", generate_prototype_from_spec_node)

    workflow.set_entry_point("prepare_requirement_chunks")
    workflow.add_edge("prepare_requirement_chunks", "chunk_understanding")
    workflow.add_edge("chunk_understanding", "structure_extraction")
    workflow.add_edge("structure_extraction", "normalize_spec")
    workflow.add_edge("normalize_spec", "product_design")
    workflow.add_edge("product_design", "interaction_design")
    workflow.add_edge("interaction_design", "generate_prototype_from_spec")
    workflow.add_edge("generate_prototype_from_spec", END)

    return workflow.compile()


def get_doc_to_prototype_pipeline_node_ids(compiled: Any = None) -> tuple[str, ...]:
    """从已编译图的边推导用户节点顺序（不含 __start__ / __end__），供进度条「已完成/总数」。

    沿 __start__ 向 __end__ 走主链；若某节点有多条出边，目标按 id 字典序取第一条（线性图无影响）。
    """
    if compiled is None:
        compiled = create_doc_to_prototype_graph()
    gr = compiled.get_graph()
    adj: Dict[str, List[str]] = {}
    for e in gr.edges:
        adj.setdefault(e.source, []).append(e.target)
    for targets in adj.values():
        targets.sort()
    out: list[str] = []
    cur = "__start__"
    for _ in range(len(gr.nodes) + 8):
        if cur == "__end__":
            break
        nbrs = adj.get(cur, [])
        if not nbrs:
            break
        nxt = nbrs[0]
        if nxt == "__end__":
            break
        if nxt not in ("__start__", "__end__"):
            out.append(nxt)
        cur = nxt
    return tuple(out)
