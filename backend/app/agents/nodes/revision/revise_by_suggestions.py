"""基于用户建议执行修订的节点"""
import re
from typing import Dict, Any, List, Set, Tuple

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.chunk_utils import (
    split_document_into_chunks,
    CHUNK_CHAR_LIMIT,
)
from app.core.llm import get_llm_for_content_gen


# 小文档可直接整篇修订，超过此长度则分段
SMALL_DOC_CHAR_LIMIT = 2500

# 块元数据：(text, section_title, index)
ChunkWithMeta = Tuple[str, str, int]


def _get_chunks_meta(state: UserDrivenRevisionState) -> List[ChunkWithMeta]:
    """
    从 state 获取 chunks_meta；若未预先分块则现场计算（向后兼容）。
    """
    chunks = state.get("chunks_meta") or []
    if chunks:
        return chunks
    doc = state.get("current_doc", "") or ""
    return split_document_into_chunks(doc, max_chars=CHUNK_CHAR_LIMIT)


def _parse_chinese_number(s: str) -> int:
    """解析中文数字，如 三→3, 十→10, 十二→12, 二十→20"""
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
            return 10 + b  # 十一～十九
        if s[1] == "十":
            return a * 10  # 二十～九十
        return 0
    if len(s) == 3 and s[1] == "十":
        return num_map.get(s[0], 0) * 10 + num_map.get(s[2], 0)  # 二十一～九十九
    return 0


def _map_targets_to_chunks(tasks: List[Dict[str, Any]], chunks_meta: List[ChunkWithMeta]) -> Set[int]:
    """
    将 parsed_tasks 中的 target 映射到受影响的 chunk 索引集合。
    无法精确定位时返回全部索引（保守策略）。
    """
    n = len(chunks_meta)
    if n == 0:
        return set()

    affected: Set[int] = set()

    # 全文/整体 类 target → 所有块
    full_doc_keywords = ("全文", "整体", "全部", "整篇", "全文档", "整个文档")

    # 开头类 → chunk 0
    start_keywords = ("开头", "开头部分", "首段", "第一段", "引言", "前言", "开篇")

    # 结尾类 → 最后一块
    end_keywords = ("结尾", "末尾", "最后", "最后一段", "总结", "结语")

    for t in tasks:
        target = (t.get("target") or "").strip()
        if not target:
            affected.update(range(n))
            continue

        matched = False

        # 全文
        for kw in full_doc_keywords:
            if kw in target:
                affected.update(range(n))
                matched = True
                break
        if matched:
            continue

        # 开头
        for kw in start_keywords:
            if kw in target:
                affected.add(0)
                matched = True
                break
        if matched:
            continue

        # 结尾
        for kw in end_keywords:
            if kw in target:
                affected.add(n - 1)
                matched = True
                break
        if matched:
            continue

        # 第 X 章/节/段：尝试匹配 section_title 或块内容
        for i, (text, section_title, _) in enumerate(chunks_meta):
            # 去掉 target 中常见修饰，如「的」「部分」等
            t_clean = target.replace("的", "").replace("部分", "").strip()
            if t_clean in section_title or target in section_title:
                affected.add(i)
                matched = True
                break
            # 块开头 200 字符内匹配（章节号可能出现在首句）
            preview = (section_title + text[:200])
            if target in preview or t_clean in preview:
                affected.add(i)
                matched = True
                break
            # 数字匹配：第三章、第十二节 → 匹配章节序号
            chapter_num = re.search(r"第([一二三四五六七八九十\d]+)[章节目段]", target)
            if chapter_num:
                num_str = chapter_num.group(1)
                idx = int(num_str) if num_str.isdigit() else _parse_chinese_number(num_str)
                if 1 <= idx <= n:
                    affected.add(idx - 1)
                    matched = True
                    break

        if not matched:
            # 无法定位时保守处理：纳入所有块
            affected.update(range(n))

    return affected if affected else set(range(n))


async def _revise_single_chunk(
    chunk: str,
    chunk_idx: int,
    total_chunks: int,
    task_desc: str,
    llm,
) -> str:
    """修订单个文档块，仅输出该块内容"""
    prompt = f"""你是文档修订助手。下面是文档的第 {chunk_idx + 1}/{total_chunks} 段。

# 本段原文
{chunk}

# 修订任务（仅修改与本段相关的部分，无关则保持不变）
{task_desc}

# 要求
1. 若任务不涉及本段，直接输出本段原文，不要改动
2. 若需修改，保持风格一致，与上下文衔接
3. **只输出本段修订结果**，不要输出解释、序号或其他段落
4. **必须完整输出本段全部内容**，不可截断或遗漏，输出长度应与原文相当（除非任务要求删除）
"""
    response = await llm.ainvoke(prompt)
    revised = (response.content or "").strip()
    if not revised:
        return chunk
    # 截断检测：输出异常短且非删除任务时，可能被 API 截断，回退到原文
    tasks_str = task_desc.lower()
    if len(chunk) > 300 and len(revised) < len(chunk) * 0.35:
        if "delete" not in tasks_str and "删除" not in tasks_str and "简化" not in tasks_str:
            logger.warning("块 {} 输出过短(原文{}字->{}字)，疑似截断，保留原文", chunk_idx + 1, len(chunk), len(revised))
            return chunk
    return revised


async def revise_by_suggestions_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    根据 parsed_tasks 逐条执行修订
    大文档采用分段修订，规避 API 的 4K 输出限制
    """
    current_doc = state.get("current_doc", "") or ""
    tasks = state.get("parsed_tasks", [])

    if not tasks:
        return {"revised_document": current_doc}

    task_desc = "\n".join(
        f"- {i + 1}. [{t.get('action', 'modify')}] {t.get('target', '')}: {t.get('content_requirement', '')}"
        for i, t in enumerate(tasks)
    )

    llm = get_llm_for_content_gen(max_tokens=4096)

    if len(current_doc) <= SMALL_DOC_CHAR_LIMIT:
        # 小文档：整篇一次性修订
        prompt = f"""你是一个专业的文档修订助手。请根据以下修订任务，对文档进行修改。

# 原始文档
{current_doc}

# 修订任务（请逐条执行）
{task_desc}

# 要求
1. 保持文档原有风格和语气
2. 修改后的内容需与上下文自然衔接
3. 直接输出**完整修订后的文档**，不要输出解释或任务清单
4. 若某任务无法准确定位，请根据语义在合理位置完成

请输出修订后的完整文档：
"""
        response = await llm.ainvoke(prompt)
        revised = (response.content or "").strip()
        revised = revised if revised else current_doc
    else:
        # 大文档：优先使用 retrieve_relevant_chunks 的 affected_chunk_indices
        chunks_meta = _get_chunks_meta(state)
        affected_list = state.get("affected_chunk_indices") or []
        affected_indices = set(affected_list) if affected_list else _map_targets_to_chunks(tasks, chunks_meta)
        section_hints = state.get("section_hints") or {}

        logger.info(
            "文档分段修订: 共 {} 段, 受影响 {} 段, 总长 {} 字",
            len(chunks_meta),
            len(affected_indices),
            len(current_doc),
        )

        revised_chunks: List[str] = []
        for i, (chunk_text, _, _) in enumerate(chunks_meta):
            if i in affected_indices:
                chunk_task_desc = task_desc
                if i in section_hints:
                    chunk_task_desc = task_desc + "\n\n" + section_hints[i]
                rev = await _revise_single_chunk(
                    chunk_text, i, len(chunks_meta), chunk_task_desc, llm
                )
                revised_chunks.append(rev)
            else:
                revised_chunks.append(chunk_text)

        revised = "\n\n".join(revised_chunks)

    return {"revised_document": revised, "current_doc": revised}
