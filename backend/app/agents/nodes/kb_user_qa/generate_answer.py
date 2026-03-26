"""用户知识库：面向最终用户的回答生成（语气与要求与管理员迭代 QA 不同）"""
from typing import Any, Dict, Optional

from app.agents.states.kb_user_qa_state import KbUserQAState
from app.core.llm import get_llm_for_generation

KB_EMPTY_COLLECTION_REPLY = (
    "当前选择的集合下还没有可检索的文档，请先在「文档库」中上传文档并完成索引。"
)
KB_NO_HITS_REPLY = (
    "没有在知识库中检索到与问题直接相关的资料。可以换个说法或关键词，或将检索范围设为「全部知识库」后再试。"
)


def should_skip_kb_llm(state: Dict[str, Any]) -> Optional[str]:
    """无可用摘录时返回固定答复，跳过大模型；否则返回 None。"""
    status = state.get("kb_retrieval_status")
    if status == "empty_collection":
        return KB_EMPTY_COLLECTION_REPLY
    if status == "no_hits":
        return KB_NO_HITS_REPLY
    if status == "ok":
        return None
    if not (state.get("retrieved_docs") or []):
        return KB_NO_HITS_REPLY
    return None


def build_user_kb_answer_prompt(query: str, context: str) -> str:
    """
    用户向提示：易懂、直接、不暴露内部流程用语。
    供图内节点与 /kb-qa/stream 流式接口共用，保证与 invoke 一致。
    """
    return (
        """你正在帮助普通用户，根据其问题从「知识库摘录」中找答案。

【知识库摘录】
%s

【用户问题】
%s

请遵守：
1. 只用摘录里有的信息作答；摘录里没有或不足以回答时，直接说明「资料里没有提到」或「根据现有资料无法确定」，不要猜测或编造。
2. 用语口语、简洁，避免「迭代」「评估」「管理员」「上一轮」等内部词。
3. 结构清楚：可先给简短结论，再分点说明；必要时用小节标题。
4. 摘录中的【文档：标题】表示出处；若用户问题适合，可在回答末尾用一行列出参考过的文档标题（无则省略）。

请直接输出给用户看的内容（不要写「好的」「作为 AI」等套话开头）：
"""
        % (context.strip(), query.strip())
    ).strip()


async def user_kb_generate_answer_node(state: KbUserQAState) -> Dict[str, Any]:
    fixed = should_skip_kb_llm(state)
    if fixed:
        return {
            "answer": fixed,
            "messages": [{"role": "assistant", "content": fixed}],
        }
    llm = get_llm_for_generation()
    prompt = build_user_kb_answer_prompt(
        state.get("query", ""),
        state.get("context", ""),
    )
    response = await llm.ainvoke(prompt)
    text = response.content if isinstance(response.content, str) else str(response.content)
    return {
        "answer": text,
        "messages": [{"role": "assistant", "content": text}],
    }
