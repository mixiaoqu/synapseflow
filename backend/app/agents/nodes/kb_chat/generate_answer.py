"""用户知识库：面向最终用户的回答生成（语气与要求与管理员迭代 QA 不同）"""
from typing import Any, Dict, Optional

from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt
from app.agents.states import KbChatState
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


async def user_kb_generate_answer_node(state: KbChatState) -> Dict[str, Any]:
    fixed = should_skip_kb_llm(state)
    if fixed:
        return {
            "answer": fixed,
            "messages": [{"role": "assistant", "content": fixed}],
        }
    llm = get_llm_for_generation()
    prompt = build_kb_chat_answer_prompt(
        state.get("query", ""),
        state.get("context", ""),
    )
    response = await llm.ainvoke(prompt)
    text = response.content if isinstance(response.content, str) else str(response.content)
    return {
        "answer": text,
        "messages": [{"role": "assistant", "content": text}],
    }
