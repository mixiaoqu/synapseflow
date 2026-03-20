"""提问优化节点：优化/拆解问题，适配知识库约束"""
import json
import re
from typing import Any, Dict

from app.agents.states import IterativeQAState
from app.core.llm import get_llm_for_analysis


# 知识库约束：单次问题长度建议
MAX_QUESTION_BYTES = 1000


def _strip_book_guillemets_for_retrieval(text: str) -> str:
    """
    检索问句**一律去掉**《…》篇名片段：向量检索按语义匹配正文，不按文件名；
    评估模型会不断臆造新手册/指南名（不限于某一两个例子），白名单无法穷举。
    """
    t = re.sub(r"《[^》]+》", "", text)
    # 去掉因删篇名产生的残缺连接词与套话
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


async def query_optimizer_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    提问优化节点：
    - 第1轮：若问题超长则拆解为核心子问题；否则直接透传
    - 第2+轮：以评估节点给出的 reason + suggestion 为准，改写为下一轮检索用问句（单一统一 prompt，不按类型分支）
    """
    query = state.get("query", "")
    iteration = state.get("iteration", 0)
    last_feedback = state.get("last_evaluation_feedback")

    if not query.strip():
        return {"optimized_query": query}

    # 第1轮：仅做长度检查，超长时提取核心问题
    if iteration == 0:
        if len(query.encode("utf-8")) <= MAX_QUESTION_BYTES:
            return {"optimized_query": query.strip()}
        # 超长：用 LLM 提取一个最核心的子问题
        llm = get_llm_for_analysis()
        prompt = f"""
用户的问题过长（超过{MAX_QUESTION_BYTES}字节），需要精简为适合知识库检索的核心问题。

原始问题：
{query}

要求：
1. 提取一个最核心、最直接的问题（控制在300字以内）
2. 保留关键术语，便于向量检索
3. 只返回优化后的问题文本，不要其他解释

优化后的问题：
"""
        response = await llm.ainvoke(prompt)
        optimized = (response.content or query).strip()
        return {"optimized_query": optimized or query}

    # 第2+轮：严格依据评估节点给出的 reason + suggestion（已结合检索片段与答案）改写检索问题
    if not last_feedback:
        return {"optimized_query": query}

    llm = get_llm_for_analysis()
    feedback_str = json.dumps(last_feedback, ensure_ascii=False)
    known_lines: list[str] = []
    for doc in state.get("retrieved_docs") or []:
        meta = doc.get("metadata") or {}
        t = (meta.get("document_title") or "").strip()
        if t and t != "未知文档":
            known_lines.append(t)
    titles_block = (
        "\n".join(f"- {t}" for t in sorted(set(known_lines)))
        if known_lines
        else "（本轮尚未召回到带标题的文档；仍禁止书写任何《××手册》《××指南》类篇名。）"
    )

    prompt = f"""
你是「检索问题改写」助手。上一轮评估已结合知识库片段与答案生成反馈——以「reason」「suggestion」中的**检索意图与关键词**为准，但输出必须符合下方硬规则。

【用户原始问题】
{query}

【当前召回所涉真实文档标题（仅供参考；检索不靠篇名匹配）】
{titles_block}

【上一轮评估反馈（JSON）】
{feedback_str}

硬规则（必须遵守，不依赖具体业务举例）：
1. 输出**一条**用于向量检索的短问句或关键词串；**不要**写「请参考《…》」「请检索《…》全文」「《A》和《B》中关于…」——系统**无法**按臆造篇名打开文档。
2. **禁止**出现任何《…》书名号及其中内容；禁止出现「××操作手册」「××指南」「××规范」等**具体文件名**（除非与上方列表中某标题**完全一致**且确有必要，一般不要写篇名）。
3. 把 suggestion 里的意图改写成**纯主题词**：如 账号注销、销户、账户删除、用户设置、退出登录、永久关闭账户 等，可与用户原问合并为一句自然问句。
4. 中文 300 字以内。

优化后的问题（不得含《》）：
"""

    response = await llm.ainvoke(prompt)
    optimized = (response.content or query).strip()
    optimized = _strip_book_guillemets_for_retrieval(optimized)
    optimized = _merge_short_fallback(query, optimized)
    return {"optimized_query": optimized or query}
