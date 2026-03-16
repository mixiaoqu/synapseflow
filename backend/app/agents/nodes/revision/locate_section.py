"""定位到具体段落/章节，为每块生成修订提示"""
from typing import Dict, Any, List

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState


def _build_section_hints(
    tasks: List[Dict[str, Any]],
    affected_indices: List[int],
    chunks_meta: List[tuple],
) -> Dict[int, str]:
    """
    为每个受影响的 chunk 生成定位提示，便于 LLM 更精准修订。
    当 target 较具体（如「第二段」「第三章」）时，附加提示。
    """
    hints: Dict[int, str] = {}
    for idx in affected_indices:
        chunk_tasks = []
        for t in tasks:
            target = (t.get("target") or "").strip()
            action = t.get("action", "modify")
            req = t.get("content_requirement", "")
            if target and req:
                chunk_tasks.append(f"目标「{target}」: {action} - {req}")
        if chunk_tasks:
            hints[idx] = "本块相关任务: " + "; ".join(chunk_tasks)
    return hints


async def locate_section_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    在块内定位到具体段落，为受影响的块生成修订提示。

    输入：parsed_tasks, affected_chunk_indices, chunks_meta
    输出：section_hints = {chunk_idx: "本块相关任务: ..."}
    """
    tasks = state.get("parsed_tasks", [])
    affected_indices = state.get("affected_chunk_indices", [])
    chunks_meta = state.get("chunks_meta", [])

    if not tasks or not affected_indices:
        return {"section_hints": {}}

    section_hints = _build_section_hints(tasks, affected_indices, chunks_meta)

    if section_hints:
        logger.info(
            "段落定位 (locate_section): 为 {} 个块生成修订提示",
            len(section_hints),
        )
        for idx, hint in section_hints.items():
            logger.debug("  块 {}: {}", idx + 1, hint[:80] + "…" if len(hint) > 80 else hint)

    return {"section_hints": section_hints}
