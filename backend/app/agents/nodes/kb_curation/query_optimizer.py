"""提问优化节点：优化/拆解问题，适配知识库约束。"""

import json
import re
from typing import Any, Dict

from app.agents.states import KbCurationState
from app.core.llm import get_llm_for_analysis


MAX_QUESTION_BYTES = 1000


def _strip_book_guillemets_for_retrieval(text: str) -> str:
    """
    检索问句一律去掉《…》篇名片段。
    向量检索按语义匹配正文，不按文件名。
    """
    t = re.sub(r"《[^》]+》", "", text)
    t = re.sub(r"\s*(?:和|或|与|、)\s*", " ", t)
    t = re.sub(r"(?:请(?:参考|检索|提供)|建议检索|尝试检索)\s*", "", t)
    t = re.sub(r"\s*中关于\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"^[，,、；;\s]+", "", t)
    t = re.sub(r"[，,、；;\s]+$", "", t)
    return t.strip()


def _merge_short_fallback(original: str, stripped: str, min_len: int = 24) -> str:
    """删篇名后若过短，回退为原始用户问题，避免空问句。"""
    s = (stripped or "").strip()
    if len(s) >= min_len:
        return s
    return (original or "").strip() or s


async def query_optimizer_node(state: KbCurationState) -> Dict[str, Any]:
    """
    提问优化节点：
    - 第 1 轮：若问题超长则拆解为核心子问题；否则直接透传
    - 第 2 轮及之后：根据评估节点反馈改写为下一轮检索用问句
    """
    query = state.get("query", "")
    iteration = state.get("iteration", 0)
    last_feedback = state.get("last_evaluation_feedback")

    if not query.strip():
        return {"optimized_query": query}

    if iteration == 0:
        if len(query.encode("utf-8")) <= MAX_QUESTION_BYTES:
            return {"optimized_query": query.strip()}

        llm = get_llm_for_analysis()
        prompt = f"""
用户的问题过长（超过 {MAX_QUESTION_BYTES} 字节），需要精简为适合知识库检索的核心问题。

原始问题：
{query}

要求：
1. 提取一个最核心、最直接的问题（控制在 300 字以内）
2. 保留关键术语，便于向量检索
3. 只返回优化后的问题文本，不要其他解释

优化后的问题：
"""
        response = await llm.ainvoke(prompt)
        optimized = (response.content or query).strip()
        return {"optimized_query": optimized or query}

    if not last_feedback:
        return {"optimized_query": query}

    llm = get_llm_for_analysis()
    feedback_str = json.dumps(last_feedback, ensure_ascii=False)
    known_lines: list[str] = []
    for doc in state.get("retrieved_docs") or []:
        meta = doc.get("metadata") or {}
        title = (meta.get("document_title") or "").strip()
        if title and title != "未知文档":
            known_lines.append(title)
    titles_block = (
        "\n".join(f"- {title}" for title in sorted(set(known_lines)))
        if known_lines
        else "（本轮尚未召回到带标题的文档；仍禁止书写任何《××手册》《××指南》类篇名。）"
    )

    prompt = f"""
你是“检索问题改写”助手。上一轮评估已结合知识库片段与答案生成反馈。
请以 reason 和 suggestion 中的检索意图与关键词为准，但输出必须符合下方硬规则。

【用户原始问题】
{query}

【当前召回所涉真实文档标题（仅供参考；检索不靠篇名匹配）】
{titles_block}

【上一轮评估反馈（JSON）】
{feedback_str}

硬规则（必须遵守）：
1. 输出一条用于向量检索的短问句或关键词串
2. 禁止出现任何《…》书名号及其中内容
3. 把 suggestion 里的意图改写成纯主题词，可与用户原问合并为一句自然问句
4. 中文 300 字以内

优化后的问题（不得含《》）：
"""

    response = await llm.ainvoke(prompt)
    optimized = (response.content or query).strip()
    optimized = _strip_book_guillemets_for_retrieval(optimized)
    optimized = _merge_short_fallback(query, optimized)
    return {"optimized_query": optimized or query}
