"""Prompt builders for end-user knowledge-base chat."""

from app.agents.prompts.common import sanitize_user_kb_context


def build_kb_chat_answer_prompt(
    query: str,
    context: str,
    *,
    chat_history_text: str = "",
    memory_summary: str = "",
    assistant_name: str = "",
    assistant_welcome_message: str = "",
    assistant_placeholder_text: str = "",
    assistant_persona_prompt: str = "",
    assistant_rule_template: str = "",
    assistant_suggested_prompts: list[str] | None = None,
    page_config: dict | None = None,
    page_context: dict | None = None,
    evidence_status: str = "",
) -> str:
    """Build the prompt for the end-user knowledge-base chat flow."""

    clean_context = sanitize_user_kb_context(context)
    summary_block = memory_summary.strip() or "(none)"
    history_block = chat_history_text.strip() or "(none)"
    assistant_name_block = assistant_name.strip() or "Knowledge Assistant"
    welcome_block = assistant_welcome_message.strip() or "(none)"
    placeholder_block = assistant_placeholder_text.strip() or "(none)"
    persona_block = assistant_persona_prompt.strip() or "(none)"
    rule_block = assistant_rule_template.strip() or "(none)"
    evidence_status_block = evidence_status.strip() or "sufficient"
    suggested_prompt_lines = [
        f"- {item.strip()}"
        for item in (assistant_suggested_prompts or [])
        if str(item).strip()
    ]
    suggested_prompts_block = "\n".join(suggested_prompt_lines) or "(none)"
    page_config = page_config or {}
    page_context = page_context or {}
    page_name = str(page_config.get("page_name") or "").strip()
    page_description = str(page_config.get("page_description") or "").strip()
    assistant_intro = str(page_config.get("assistant_intro") or "").strip()
    page_type = str(page_context.get("page_type") or "").strip()
    page_lines = []
    if page_name:
        page_lines.append(f"页面名称：{page_name}")
    if page_type:
        page_lines.append(f"页面标识：{page_type}")
    if page_description:
        page_lines.append(f"页面说明：{page_description}")
    if assistant_intro:
        page_lines.append(f"助手入口说明：{assistant_intro}")
    if page_lines:
        page_lines.append("以上信息描述用户提问时所在的业务环境，用于理解“当前页面、这个页面、这里”等指代。")
    page_context_block = "\n".join(page_lines) or "(none)"

    return f"""
You are a knowledge-base assistant for end users.
Current assistant name: {assistant_name_block}

Base constraints:
1. Answer from the knowledge-base context first. Do not fabricate facts that are not supported.
2. Chat history and memory are only for resolving references like "that step" or "the previous page". They are not a source of truth.
3. If the available material is insufficient, explicitly say the资料中没有提到 or 根据现有资料无法确定.
4. Do not reveal internal implementation details such as API routes, field names, variable names, or database tables.
5. If the answer is procedural, organize it into clear, user-facing steps.
6. Always preserve the configured assistant persona and response rules, even when the knowledge base is insufficient.
7. If evidence status is not "sufficient", do not invent facts. Give a helpful answer in Chinese that clearly states the limitation while still following the configured assistant style.
8. 按内容选择清晰的排版：对比、价格、权限、状态、字段说明优先用 Markdown 表格；操作流程、设置步骤用编号步骤；注意事项、限制条件用简短项目符号；信息少于 2 项时不强行使用表格。
[Assistant persona]
{persona_block}

[Configured welcome message]
{welcome_block}

[Configured input placeholder]
{placeholder_block}

[Assistant-specific response rules]
{rule_block}

[Configured suggested prompts]
{suggested_prompts_block}

[User environment]
{page_context_block}

[Conversation summary]
{summary_block}

[Recent chat history]
{history_block}

[Evidence evaluation]
{evidence_status_block}

[Knowledge-base context]
{clean_context.strip()}

[Current user question]
{query.strip()}

Return only the final user-facing answer in Chinese.
""".strip()
