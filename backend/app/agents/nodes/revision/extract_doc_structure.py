"""解析文档结构节点：将长文档拆成章节树结构"""
import re
from typing import Dict, Any, List

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState


def _parse_headings(doc: str) -> List[Dict[str, Any]]:
    """
    解析文档中所有 Markdown 标题，返回 [(level, title, start_pos), ...]
    level: ##=1, ###=2, ####=3...
    """
    headings: List[Dict[str, Any]] = []
    for m in re.finditer(r'^(#{1,6})\s+(.+)$', doc, flags=re.MULTILINE):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.start()
        headings.append({"level": level, "title": title, "start": start})
    return headings


def _build_section_tree(headings: List[Dict[str, Any]], doc_len: int) -> List[Dict[str, Any]]:
    """
    根据标题列表构建章节树。
    每个节点: {level, title, start, end, children}
    """
    if not headings:
        return []

    tree: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = []  # (node, depth) for building tree

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

        # 弹栈直到找到合适的父节点（level 比当前小）
        while stack and stack[-1]["level"] >= level:
            stack.pop()

        if not stack:
            tree.append(node)
        else:
            stack[-1]["children"].append(node)

        stack.append(node)

    return tree


def _log_structure_tree(nodes: List[Dict[str, Any]], indent: int = 0) -> None:
    """递归打印章节树"""
    for n in nodes:
        prefix = "  " * indent
        logger.info(
            "{}{} {} (pos {}-{})",
            prefix,
            "#" * n["level"],
            n["title"],
            n["start"],
            n["end"],
        )
        if n.get("children"):
            _log_structure_tree(n["children"], indent + 1)


async def extract_doc_structure_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    解析文档结构，将长文档拆成章节树结构。

    输入：current_doc
    输出：doc_structure = [
        {
            "level": 1,
            "title": "第一章 引言",
            "start": 0,
            "end": 500,
            "children": [
                {"level": 2, "title": "1.1 背景", "start": 100, "end": 400, "children": []}
            ]
        },
        ...
    ]
    """
    doc = state.get("current_doc", "") or ""

    if not doc.strip():
        logger.info("文档为空，无结构可解析")
        return {"doc_structure": []}

    headings = _parse_headings(doc)
    doc_len = len(doc)

    if not headings:
        logger.info("文档无 Markdown 标题，结构为空树")
        return {"doc_structure": []}

    tree = _build_section_tree(headings, doc_len)

    logger.info("解析文档结构 (doc_structure) 共 {} 个顶层章节:", len(tree))
    _log_structure_tree(tree)

    return {"doc_structure": tree}
