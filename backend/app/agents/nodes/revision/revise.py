"""执行修订：逐块调用 LLM 并拼接"""
import asyncio
from typing import Dict, Any, List

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.agents.nodes.revision.chunk_utils import split_document_into_chunks, CHUNK_CHAR_LIMIT
from app.core.llm import get_llm_for_generation

SMALL_DOC_CHAR_LIMIT = 2500
MAX_CONCURRENT_LLM_CALLS = 5  # 最大并发 LLM 请求数


def _get_chunks_meta(state: UserDrivenRevisionState) -> List[tuple]:
    """从 state 获取 chunks_meta；若未预先分块则现场计算"""
    chunks = state.get("chunks_meta") or []
    if chunks:
        return chunks
    doc = state.get("current_doc", "") or ""
    return split_document_into_chunks(doc, max_chars=CHUNK_CHAR_LIMIT)


async def _revise_single_chunk(
    chunk: str,
    chunk_idx: int,
    total_chunks: int,
    task_desc: str,
    llm,
    semaphore: asyncio.Semaphore = None,
) -> str:
    """修订单个文档块（支持并发控制）"""
    async def _do_revise():
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
        tasks_str = task_desc.lower()
        if len(chunk) > 300 and len(revised) < len(chunk) * 0.35:
            if "delete" not in tasks_str and "删除" not in tasks_str and "简化" not in tasks_str:
                logger.warning(
                    "块 {} 输出过短(原文{}字->{}字)，疑似截断，保留原文",
                    chunk_idx + 1,
                    len(chunk),
                    len(revised),
                )
                return chunk
        return revised
    
    if semaphore:
        async with semaphore:
            return await _do_revise()
    else:
        return await _do_revise()


async def revise_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    根据 parsed_tasks 执行修订。
    小文档：整篇一次性修订；大文档：仅修订 affected chunks。
    """
    current_doc = state.get("current_doc", "") or ""
    tasks = state.get("parsed_tasks", [])

    if not tasks:
        logger.info("[修订 4/4] revise 完成 - 无任务，保留原文")
        return {"revised_document": current_doc, "current_doc": current_doc}

    task_desc = "\n".join(
        f"- {i + 1}. [{t.get('action', 'modify')}] {t.get('target', '')}: {t.get('content_requirement', '')}"
        for i, t in enumerate(tasks)
    )
    llm = get_llm_for_generation()

    if len(current_doc) <= SMALL_DOC_CHAR_LIMIT:
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
        logger.info("[修订 4/4] revise 完成 - 小文档整篇修订, 输出 {} 字", len(revised))
    else:
        chunks_meta = _get_chunks_meta(state)
        affected_list = state.get("affected_chunk_indices") or []
        affected_indices = set(affected_list) if affected_list else set(range(len(chunks_meta)))
        section_hints = state.get("section_hints") or {}

        total_affected = len(affected_indices)
        logger.info(
            "[修订 4/4] revise 分段执行: 共 {} 段, 修订 {} 段, 原文 {} 字",
            len(chunks_meta),
            total_affected,
            len(current_doc),
        )

        # 并发修订优化：使用 asyncio.gather + Semaphore
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
        
        # 准备并发任务
        tasks_to_run = []
        chunk_index_map = []  # 记录每个任务对应的原始索引
        
        for i, (chunk_text, _, _) in enumerate(chunks_meta):
            if i in affected_indices:
                chunk_task_desc = task_desc
                if i in section_hints:
                    chunk_task_desc = task_desc + "\n\n" + section_hints[i]
                
                task = _revise_single_chunk(
                    chunk_text, i, len(chunks_meta), chunk_task_desc, llm, semaphore
                )
                tasks_to_run.append(task)
                chunk_index_map.append(i)
        
        revised_results = await asyncio.gather(*tasks_to_run)
        
        # 按原始顺序组装结果
        result_dict = dict(zip(chunk_index_map, revised_results))
        revised_chunks: List[str] = []
        for i, (chunk_text, _, _) in enumerate(chunks_meta):
            if i in result_dict:
                revised_chunks.append(result_dict[i])
            else:
                revised_chunks.append(chunk_text)

        revised = "\n\n".join(revised_chunks)
        logger.info("[修订 4/4] revise 完成 - 大文档分段修订, 输出 {} 字", len(revised))

    return {"revised_document": revised, "current_doc": revised}
