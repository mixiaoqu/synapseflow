"""Prompt builders for end-user knowledge-base chat."""


def build_page_context_block(
    page_config: dict | None = None,
    page_context: dict | str | None = None,
) -> str:
    if isinstance(page_context, str):
        return page_context.strip() or "(none)"

    page_config = page_config or {}
    page_context = page_context or {}
    page_name = str(page_config.get("page_name") or "").strip()
    page_description = str(page_config.get("page_description") or "").strip()
    assistant_intro = str(page_config.get("assistant_intro") or "").strip()
    page_type = str(page_context.get("page_type") or "").strip()
    route_name = str(page_context.get("route_name") or "").strip()
    route_path = str(page_context.get("route_path") or "").strip()
    entity_type = str(page_context.get("entity_type") or "").strip()
    entity_id = str(page_context.get("entity_id") or "").strip()
    entity_name = str(page_context.get("entity_name") or "").strip()

    page_lines: list[str] = []
    if page_name:
        page_lines.append(f"页面名称：{page_name}")
    if page_type:
        page_lines.append(f"页面标识：{page_type}")
    if route_name:
        page_lines.append(f"路由名称：{route_name}")
    if route_path:
        page_lines.append(f"路由路径：{route_path}")
    if entity_type or entity_id or entity_name:
        entity_parts = [part for part in (entity_type, entity_id, entity_name) if part]
        page_lines.append(f"当前业务对象：{' / '.join(entity_parts)}")
    if page_description:
        page_lines.append(f"页面说明：{page_description}")
    if assistant_intro:
        page_lines.append(f"助手入口说明：{assistant_intro}")
    return "\n".join(page_lines) or "(none)"


def build_kb_chat_answer_prompt(
    query: str,
    *,
    assistant_name: str = "",
    assistant_persona_prompt: str = "",
    assistant_rule_template: str = "",
    page_context: str = "",
    chat_history_text: str = "",
    memory_summary: str = "",
    evidence_status: str = "",
    primary_context: str = "",
    supporting_context: str = "",
) -> str:
    """Build the prompt for the end-user knowledge-base chat flow."""

    assistant_name_block = assistant_name.strip() or "Knowledge Assistant"
    persona_block = assistant_persona_prompt.strip() or "(none)"
    rule_block = assistant_rule_template.strip() or "(none)"
    page_context_block = page_context.strip() or "(none)"
    summary_block = memory_summary.strip() or "(none)"
    history_block = chat_history_text.strip() or "(none)"
    evidence_status_block = evidence_status.strip() or "sufficient"
    primary_block = primary_context.strip() or "(none)"
    supporting_block = supporting_context.strip() or "(none)"

    return f"""
You are a knowledge-base assistant for end users.
Current assistant name: {assistant_name_block}

Base constraints:
1. Answer only from the provided evidence. Do not use outside knowledge or fabricate facts.
2. Chat history and memory are only for resolving references, not as the source of truth.
3. If evidence is insufficient, explicitly say “资料中未直接说明” or “根据现有资料无法确定”.
4. Do not reveal internal implementation details.
5. Preserve the configured assistant persona and response rules.
6. Evidence priority:
   - Primary evidence: answer from this first.
   - Supporting evidence: use only to supplement context or relationships.
   - Metadata: use only for entity identification, alias disambiguation, type/scope/source reference; do not use it alone to answer “作用 / 用途 / 流程 / 影响 / 规则” questions.
7. If the evidence only shows what something is, where it appears, or what type it belongs to, do not treat that as a valid answer to a “作用 / 用途” question.
8. Use clear Chinese formatting appropriate to the content.
[Assistant persona]
{persona_block}

[Assistant-specific response rules]
{rule_block}

[User environment]
{page_context_block}

[Conversation summary]
{summary_block}

[Recent chat history]
{history_block}

[Evidence evaluation]
{evidence_status_block}

[Primary evidence]
{primary_block}

[Supporting evidence]
{supporting_block}

[Current user question]
{query.strip()}

Return only the final user-facing answer in Chinese.
""".strip()
