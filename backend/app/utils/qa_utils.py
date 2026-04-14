"""问答模块工具函数"""
import re
from typing import Dict, Any, List


# 答案中是否包含知识库缺漏相关表述
GAP_PHRASES = re.compile(
    r"知识库中没有|无法确定|未提及|未找到相关|暂无相关|无相关|缺乏.*信息|没有.*信息"
)


def answer_mentions_gap(answer: str) -> bool:
    """答案中是否包含知识库缺漏相关表述"""
    return bool(answer and GAP_PHRASES.search(answer))


def build_document_modification_suggestions(result: Dict[str, Any]) -> str:
    """
    基于 iteration_history + document_issues 生成可复制的文档修改建议文本
    """
    lines: List[str] = []
    lines.append("【文档修改建议】")

    original_query = result.get("query", "")
    iteration_history = result.get("iteration_history") or []
    document_issues = result.get("document_issues") or []
    answer = result.get("answer", "")
    confidence_score = result.get("confidence_score", 0)
    retrieved_docs = result.get("retrieved_docs") or []

    lines.append(f"问题：{original_query}")
    lines.append(f"置信度：{(confidence_score * 100):.0f}%")
    lines.append(f"检索结果：{len(retrieved_docs)} 条")
    lines.append("")

    # 未通过轮次：reason、suggestion、document_issues
    failed = [r for r in iteration_history if not r.get("passed")]
    for r in failed:
        lines.append(f"--- 第 {r.get('round', 0)} 轮（未达标）---")
        q = r.get("question", "")
        orig = r.get("original_question", "")
        if orig and orig != q:
            lines.append(f"原始提问：{orig}")
            lines.append(f"优化后：{q}")
        else:
            lines.append(f"提问：{q}")
        if r.get("reason"):
            lines.append(f"未通过原因：{r['reason']}")
        if r.get("suggestion"):
            lines.append(f"修改建议：{r['suggestion']}")
        # 该轮 document_issues（从 round_record 或全局累积中匹配）
        round_issues = [
            i for i in document_issues if i.get("round") == r.get("round")
        ] or r.get("document_issues", [])
        for issue in round_issues:
            if isinstance(issue, dict):
                doc_title = issue.get("document_title", "")
                desc = issue.get("description", "")
                mod = issue.get("modification_suggestion", "")
                if desc or mod:
                    prefix = f"[{doc_title}] " if doc_title else ""
                    lines.append(f"{prefix}文档问题：{desc}" + (f" 建议：{mod}" if mod else ""))
        lines.append("")

    # 从全局 document_issues 补充（可能没有 round 字段的旧格式）
    if document_issues and not any(
        i.get("round") for i in document_issues if isinstance(i, dict)
    ):
        lines.append("--- 文档层面问题 ---")
        for issue in document_issues:
            if isinstance(issue, dict):
                doc_title = issue.get("document_title", "")
                desc = issue.get("description", "")
                mod = issue.get("modification_suggestion", "")
                if desc or mod:
                    prefix = f"[{doc_title}] " if doc_title else ""
                    lines.append(f"- {prefix}{desc}" + (f" 建议：{mod}" if mod else ""))
        lines.append("")

    # 答案中含知识库缺漏表述时纳入
    if answer_mentions_gap(answer):
        lines.append("--- 答案中的文档缺漏反馈 ---")
        lines.append(answer)

    return "\n".join(lines).strip()
