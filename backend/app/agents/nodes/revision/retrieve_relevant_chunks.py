"""根据 parsed_tasks 的 target 检索受影响的 chunk 索引"""
import re
from typing import Dict, Any, List, Set

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.chunk_utils import ChunkWithMeta


def _parse_chinese_number(s: str) -> int:
    """解析中文数字"""
    if not s:
        return 0
    if s.isdigit():
        return int(s)
    num_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if len(s) == 1:
        return num_map.get(s, 0)
    if len(s) == 2:
        a, b = num_map.get(s[0], 0), num_map.get(s[1], 0)
        if s[0] == "十":
            return 10 + b
        if s[1] == "十":
            return a * 10
        return 0
    if len(s) == 3 and s[1] == "十":
        return num_map.get(s[0], 0) * 10 + num_map.get(s[2], 0)
    return 0


def _flatten_doc_structure(
    tree: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将章节树扁平化为 (level, title, start, end) 列表"""
    result: List[Dict[str, Any]] = []

    def _walk(nodes: List[Dict[str, Any]]) -> None:
        for n in nodes:
            result.append({
                "level": n["level"],
                "title": n["title"],
                "start": n["start"],
                "end": n["end"],
            })
            if n.get("children"):
                _walk(n["children"])

    _walk(tree)
    return result


def _chunks_overlap_section(
    chunk_start: int,
    chunk_end: int,
    section_start: int,
    section_end: int,
) -> bool:
    """判断 chunk [start, end) 与 section [start, end] 是否重叠"""
    return chunk_start < section_end and chunk_end > section_start


def _map_targets_to_chunks(
    tasks: List[Dict[str, Any]],
    chunks_meta: List[ChunkWithMeta],
    chunks_positions: List[tuple],
    doc_structure: List[Dict[str, Any]],
) -> Set[int]:
    """
    将 target 映射到受影响的 chunk 索引。
    优先使用 doc_structure 的区间重叠做精确定位。
    """
    n = len(chunks_meta)
    if n == 0:
        return set()

    flat_sections = _flatten_doc_structure(doc_structure) if doc_structure else []
    use_positions = len(chunks_positions) == n and n > 0

    affected: Set[int] = set()

    full_doc_keywords = ("全文", "整体", "全部", "整篇", "全文档", "整个文档")
    start_keywords = ("开头", "开头部分", "首段", "第一段", "引言", "前言", "开篇")
    end_keywords = ("结尾", "末尾", "最后", "最后一段", "总结", "结语")

    for t in tasks:
        target = (t.get("target") or "").strip()
        if not target:
            affected.update(range(n))
            continue

        matched = False

        for kw in full_doc_keywords:
            if kw in target:
                affected.update(range(n))
                matched = True
                break
        if matched:
            continue

        for kw in start_keywords:
            if kw in target:
                affected.add(0)
                matched = True
                break
        if matched:
            continue

        for kw in end_keywords:
            if kw in target:
                affected.add(n - 1)
                matched = True
                break
        if matched:
            continue

        t_clean = target.replace("的", "").replace("部分", "").strip()

        if use_positions and flat_sections:
            for sec in flat_sections:
                if t_clean in sec["title"] or target in sec["title"]:
                    section_start, section_end = sec["start"], sec["end"]
                    for i, (cs, ce) in enumerate(chunks_positions):
                        if _chunks_overlap_section(cs, ce, section_start, section_end):
                            affected.add(i)
                    matched = True
                    break

            if not matched:
                chapter_num = re.search(r"第([一二三四五六七八九十\d]+)[章节目段]", target)
                if chapter_num:
                    num_str = chapter_num.group(1)
                    idx = int(num_str) if num_str.isdigit() else _parse_chinese_number(num_str)
                    if 1 <= idx <= len(flat_sections):
                        sec = flat_sections[idx - 1]
                        section_start, section_end = sec["start"], sec["end"]
                        for i, (cs, ce) in enumerate(chunks_positions):
                            if _chunks_overlap_section(cs, ce, section_start, section_end):
                                affected.add(i)
                        matched = True

        if not matched:
            for i, (text, section_title, _) in enumerate(chunks_meta):
                if t_clean in section_title or target in section_title:
                    affected.add(i)
                    matched = True
                    break
                preview = section_title + text[:200]
                if target in preview or t_clean in preview:
                    affected.add(i)
                    matched = True
                    break
                chapter_num = re.search(r"第([一二三四五六七八九十\d]+)[章节目段]", target)
                if chapter_num:
                    num_str = chapter_num.group(1)
                    idx = int(num_str) if num_str.isdigit() else _parse_chinese_number(num_str)
                    if 1 <= idx <= n:
                        affected.add(idx - 1)
                        matched = True
                        break

        if not matched:
            affected.update(range(n))

    return affected if affected else set(range(n))


async def retrieve_relevant_chunks_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    根据 parsed_tasks 的 target 检索受影响的 chunk 索引。
    优先使用 doc_structure + chunks_positions 做区间重叠精确定位。

    输入：parsed_tasks, chunks_meta, chunks_positions, doc_structure
    输出：affected_chunk_indices
    """
    tasks = state.get("parsed_tasks", [])
    chunks_meta = state.get("chunks_meta", [])
    chunks_positions = state.get("chunks_positions", [])
    doc_structure = state.get("doc_structure", [])

    if not tasks:
        logger.info("无 parsed_tasks，受影响块为空")
        return {"affected_chunk_indices": []}

    affected = _map_targets_to_chunks(
        tasks,
        chunks_meta,
        chunks_positions,
        doc_structure,
    )
    affected_list = sorted(affected)

    logger.info(
        "检索相关块 (retrieve_relevant_chunks): 共 {} 块, 受影响 {} 块 -> {}",
        len(chunks_meta),
        len(affected_list),
        affected_list,
    )

    return {"affected_chunk_indices": affected_list}
