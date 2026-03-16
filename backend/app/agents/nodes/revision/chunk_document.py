"""将文档切成小块节点"""
from typing import Dict, Any

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.chunk_utils import (
    split_document_into_chunks,
    compute_chunk_positions,
    CHUNK_CHAR_LIMIT,
)


async def chunk_document_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    将文档切成小块，便于后续定位与修订。

    输入：current_doc
    输出：chunks_meta = [(chunk_text, section_title, index), ...]
    """
    doc = state.get("current_doc", "") or ""

    if not doc.strip():
        logger.info("文档为空，无块可切")
        return {"chunks_meta": [], "chunks_positions": []}

    chunks_meta = split_document_into_chunks(doc, max_chars=CHUNK_CHAR_LIMIT)
    chunks_positions = compute_chunk_positions(doc, chunks_meta)

    logger.info(
        "文档分块完成 (chunks_meta): 共 {} 块, 单块上限 {} 字, 总长 {} 字",
        len(chunks_meta),
        CHUNK_CHAR_LIMIT,
        len(doc),
    )
    for i, (text, title, _) in enumerate(chunks_meta):
        preview = (text[:50] + "…") if len(text) > 50 else text
        logger.info("  块 {}: title={} | {} 字 | 预览: {}", i + 1, title or "(无)", len(text), preview.replace("\n", " "))

    return {"chunks_meta": chunks_meta, "chunks_positions": chunks_positions}
