"""文档转原型节点（与 create_doc_to_prototype_graph 一致）"""
from app.agents.nodes.prototype.prepare_chunks import prepare_requirement_chunks_node
from app.agents.nodes.prototype.chunk_understanding import chunk_understanding_node
from app.agents.nodes.prototype.structure_extraction import structure_extraction_node
from app.agents.nodes.prototype.normalize_spec import normalize_spec_node
from app.agents.nodes.prototype.product_design import product_design_node
from app.agents.nodes.prototype.interaction_design import interaction_design_node
from app.agents.nodes.prototype.generate_from_spec import (
    generate_prototype_from_spec_node,
)

__all__ = [
    "prepare_requirement_chunks_node",
    "chunk_understanding_node",
    "structure_extraction_node",
    "normalize_spec_node",
    "product_design_node",
    "interaction_design_node",
    "generate_prototype_from_spec_node",
]
