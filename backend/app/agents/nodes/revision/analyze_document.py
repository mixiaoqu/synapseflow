"""分析文档节点：解析结构并分块"""
import re
from typing import Dict, Any, List

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.chunk_utils import (
    split_document_into_chunks,
    compute_chunk_positions,
    CHUNK_CHAR_LIMIT,
)


def _parse_headings(doc: str) -> List[Dict[str, Any]]:
    """解析文档中所有 Markdown 标题，返回 [(level, title, start_pos), ...]"""
    headings: List[Dict[str, Any]] = []
    for m in re.finditer(r"^(#{1,6})\s+(.+)$", doc, flags=re.MULTILINE):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.start()
        headings.append({"level": level, "title": title, "start": start})
    return headings


def _build_section_tree(headings: List[Dict[str, Any]], doc_len: int) -> List[Dict[str, Any]]:
    """根据标题列表构建章节树，每个节点: {level, title, start, end, children}"""
    if not headings:
        return []

    tree: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = []

    for i, h in enumerate(headings):
        level = h["level"]
        title = h["title"]
        start = h["start"]
        end = doc_len
        if i + 1 < len(headings):
            end = headings[i + 1]["start"] - 1

        node: Dict[str, Any] = {
            "level": level,
            "title": title,
            "start": start,
            "end": end,
            "children": [],
        }

        while stack and stack[-1]["level"] >= level:
            stack.pop()

        if not stack:
            tree.append(node)
        else:
            stack[-1]["children"].append(node)

        stack.append(node)

    return tree


async def analyze_document_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    解析文档结构并分块。

    输入：current_doc
    输出：doc_structure, chunks_meta, chunks_positions
    """
    doc = (state.get("current_doc") or "").strip()

    if not doc:
        logger.info("[修订 2/4] analyze_document 完成 - 文档为空")
        return {
            "doc_structure": [],
            "chunks_meta": [],
            "chunks_positions": [],
        }

    headings = _parse_headings(doc)
    doc_len = len(doc)
    doc_structure = _build_section_tree(headings, doc_len) if headings else []
    chunks_meta = split_document_into_chunks(doc, max_chars=CHUNK_CHAR_LIMIT)
    chunks_positions = compute_chunk_positions(doc, chunks_meta)

    logger.info(
        "[修订 2/4] analyze_document 完成 - 章节 {} 个, 分块 {} 个, 总长 {} 字",
        len(headings),
        len(chunks_meta),
        doc_len,
    )

    return {
        "doc_structure": doc_structure,
        "chunks_meta": chunks_meta,
        "chunks_positions": chunks_positions,
    }
