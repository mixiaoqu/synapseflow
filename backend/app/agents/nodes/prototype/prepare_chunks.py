"""需求文档分块节点：仅切分并写入 requirements_chunks，供提取节点并行解析。"""
from typing import Any, Dict

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.agents.nodes.prototype.chunking import (
    build_requirements_chunks,
    PROTOTYPE_DOC_SPLIT_THRESHOLD,
    PROTOTYPE_SECTION_MAX_CHARS,
)


async def prepare_requirement_chunks_node(state: DocToPrototypeState) -> Dict[str, Any]:
    doc = state.get("requirements_doc") or ""
    chunks = build_requirements_chunks(doc)
    logger.info(
        "[需求分块] 完成，共 %s 块（阈值 %s 字，单块上限 %s 字）",
        len(chunks),
        PROTOTYPE_DOC_SPLIT_THRESHOLD,
        PROTOTYPE_SECTION_MAX_CHARS,
    )
    return {"requirements_chunks": chunks}
