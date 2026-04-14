"""Prompt builders for admin-facing knowledge-base curation."""

from typing import Any

from app.agents.prompts.common import sanitize_user_kb_context
from app.core.config.schemas import RagEvaluateWeights


def build_kb_curation_answer_prompt(
    *,
    query: str,
    context: str,
    iteration: int = 0,
    last_feedback: dict[str, Any] | None = None,
) -> str:
    """Build the answer-generation prompt for a curation round."""
    clean_context = sanitize_user_kb_context(context)
    prompt = f"""
基于以下知识库内容回答用户问题。
知识库内容：
{clean_context}

用户问题：{query}

要求：
1. 答案必须基于知识库内容。
2. 如果知识库中没有相关信息，明确说明。
3. 答案要详细、准确、结构化。
4. 如果知识库里出现类似“refund/list”“xxx/index”这种技术路径或路由标记，不要原样输出给用户，应改写成自然语言页面名称。
"""

    if iteration > 0 and last_feedback:
        prompt += f"""

【上一轮反馈】上一轮答案未通过评估，请针对以下反馈改进：
- 未通过原因：{last_feedback.get('reason', '')}
- 修改建议：{last_feedback.get('suggestion', '')}

请避免重复上一轮的无效回答方式，有针对性地补充或修正，生成符合要求的答案。
"""

    return prompt.strip() + "\n\n回答：\n"


def build_kb_curation_evaluation_prompt(
    *,
    query: str,
    context: str,
    answer: str,
    pass_threshold: float,
    weights: RagEvaluateWeights,
) -> str:
    """Build the evaluation prompt for an admin curation round."""
    wr, wg, wc = weights.relevance, weights.groundedness, weights.completeness
    return f"""
你是 RAG 答案质量评估员。请只依据【知识库内容】判断【答案】是否准确、有据、答全用户问题。最终分数由三个 0~1 的分项经系统加权得到（权重：相关性 {wr}、可溯源性 {wg}、完整性 {wc}），你必须逐项打分，禁止仅凭感觉给一个总分。
【知识库内容】（检索片段，用于核对答案依据）：
{context}

【用户问题】：{query}

【答案】：{answer}

—— 分项定义（每项 0.0~1.0，与答案准确性直接挂钩）——
1) relevance（相关性）：答案是否直接针对用户问题意图。答非所问、只答边角，低分。
2) groundedness（可溯源性）：答案中的关键断言是否可由【知识库内容】支持。明显编造或与片段矛盾，低分。
3) completeness（完整性）：用户为解决问题所需的信息，是否已从知识库中直接获得或通过片段完整覆盖。若只是说明库内缺失，则完整性应偏低。

分项参考刻度：
- 0.85~1.0：该维度几乎无问题
- 0.70~0.84：小问题或可接受瑕疵
- 0.50~0.69：明显不足，影响可用性
- 0.35~0.49：严重问题
- 0.0~0.34：该维度基本失败

硬性对齐（打分前自检）：
- 若【知识库内容】为空、或仅为“未检索到”类占位，groundedness ≤ 0.35，且三项不可虚高。
- 若答案整段拒答、拒不基于知识库作答，而非如实说明库内缺失，relevance 与 completeness 均应 ≤ 0.45。
- 若答案核心断言明显不在片段中且无法合理概括自片段，groundedness ≤ 0.35。
- 若知识库未覆盖用户核心诉求，即使答案写得好，completeness 也通常不应高于 0.55。

通过线：加权总分 ≥ {pass_threshold} 且各维度通常应 ≥ 0.65。若 completeness ≤ 0.55，一般视为未通过。

当不通过时，如果存在文档层面的缺失，请在 document_issues 中输出，类型为 knowledge_gap / document_incomplete / low_relevance 之一。
重要：每个 document_issue 必须包含 document_title。
- 若知识库内容中有【文档：xxx】标记，从中提取文档名；
- 若知识库完全为空或需新增文档，document_title 填“需新增文档”。

suggestion 字段面向下一轮检索：写关键词、同义扩展、检索方向即可。不要在 suggestion 中臆造文档名。

返回 JSON（不要其他内容），必须包含 relevance、groundedness、completeness：
{{
    "relevance": 0.75,
    "groundedness": 0.80,
    "completeness": 0.70,
    "reason": "未达标原因简述（达标可简短或省略）",
    "suggestion": "面向下一轮检索的具体指示（未达标时必填）",
    "document_issues": [
        {{
            "type": "knowledge_gap",
            "document_title": "文档A.pdf",
            "description": "该文档缺少关于 xxx 的说明",
            "modification_suggestion": "建议在文档中增加 xxx 相关章节"
        }}
    ]
}}

document_issues 仅在不通过且存在文档问题时填写，可为空数组 []。document_title 必填。
可选：同时给出 "score" 供对照；系统会以 relevance/groundedness/completeness 加权重算为准。
""".strip()
