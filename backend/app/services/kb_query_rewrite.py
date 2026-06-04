"""Retrieval query rewrite helpers for KB chat."""

from __future__ import annotations

import re
from typing import Any, Callable

from loguru import logger

from app.core.llm import get_llm_for_analysis
from app.utils import extract_json_from_llm_response

_FALLBACK_RETRIEVAL_QUERY_LIMIT = 4
_MAX_QUERY_LENGTH = 160
_MAX_HYDE_DOCUMENT_LENGTH = 400

_CODE_TOKEN_PATTERN = re.compile(
    r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'|《([^》]+)》|([A-Za-z0-9_./:-]{3,})"
)
_RUNTIME_REFERENCE_PATTERN = re.compile(
    r"(当前页面|这个页面|该页面|本页面|当前页|这个页|本页|这里)"
)


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _normalize_query(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:_MAX_QUERY_LENGTH].strip()


def _normalize_hyde_document(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:_MAX_HYDE_DOCUMENT_LENGTH].strip()


def _dedupe_keep_order(items: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_query(item)
        key = normalized.casefold()
        if len(normalized) < 2 or key in seen:
            continue
        out.append(normalized)
        seen.add(key)
        if len(out) >= limit:
            break
    return out


def _dedupe_all_keep_order(items: list[str]) -> list[str]:
    return _dedupe_keep_order(items, limit=max(len(items), 1))


def _split_lexical_terms(items: list[str]) -> list[str]:
    terms: list[str] = []
    for item in items:
        terms.extend(str(item or "").split())
    return _dedupe_all_keep_order(terms)


def _is_unquoted_protected_token(token: str) -> bool:
    if re.search(r"[0-9_./:-]", token):
        return True
    if token.isupper() and len(token) > 1:
        return True
    return any(char.isupper() for char in token[1:])


def _extract_protected_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _CODE_TOKEN_PATTERN.finditer(text or ""):
        token = next((group for group in match.groups() if group), "")
        cleaned = _normalize_query(token.strip("`\"'"))
        if len(cleaned) < 2:
            continue
        if match.group(5) and not _is_unquoted_protected_token(cleaned):
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        tokens.append(cleaned)
        seen.add(key)
    return tokens


def _format_runtime_context(runtime_context: dict[str, Any] | None) -> str:
    if not isinstance(runtime_context, dict):
        return "(none)"

    page_name = _normalize_query(str(runtime_context.get("page_name") or ""))
    page_type = _normalize_query(str(runtime_context.get("page_type") or ""))
    page_description = _normalize_query(str(runtime_context.get("page_description") or ""))
    lines = []
    if page_name:
        lines.append(f"Page name: {page_name}")
    if page_type:
        lines.append(f"Page type: {page_type}")
    if page_description:
        lines.append(f"Page description: {page_description}")
    return "\n".join(lines) or "(none)"


def _runtime_contextual_query(query: str, runtime_context: dict[str, Any] | None) -> str:
    if not _RUNTIME_REFERENCE_PATTERN.search(query):
        return ""

    page_name = ""
    if isinstance(runtime_context, dict):
        page_name = _normalize_query(str(runtime_context.get("page_name") or ""))
    if not page_name or page_name in query:
        return ""
    return _normalize_query(f"{page_name} {query}")


def _recent_user_context(chat_history: list[dict[str, str]] | None, *, limit: int = 2) -> str:
    recent = [
        _normalize_query(str(item.get("content") or ""))
        for item in list(chat_history or [])
        if str(item.get("role") or "").strip().lower() == "user"
    ]
    recent = [item for item in recent if item]
    return " | ".join(recent[-limit:])


def _build_fallback_queries(
    query: str,
    *,
    chat_history: list[dict[str, str]] | None,
    memory_summary: str | None,
    runtime_context: dict[str, Any] | None,
    limit: int,
) -> list[str]:
    original = _normalize_query(query)
    if not original:
        return []

    candidates = [original]
    runtime_query = _runtime_contextual_query(original, runtime_context)
    if runtime_query:
        candidates.insert(0, runtime_query)

    recent_user_context = _recent_user_context(chat_history)
    summary = _normalize_query(memory_summary or "")
    if recent_user_context:
        candidates.append(_normalize_query(f"{recent_user_context} {original}"))
    if summary:
        candidates.append(_normalize_query(f"{summary} {original}"))
    return _dedupe_keep_order(candidates, limit=limit)


def _build_rewrite_prompt(
    query: str,
    *,
    question_type: str,
    retrieval_label: str,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    protected_tokens: list[str] | None = None,
) -> str:
    history_lines = []
    for item in list(chat_history or [])[-4:]:
        role = str(item.get("role") or "").strip().lower() or "assistant"
        content = _normalize_query(str(item.get("content") or ""))
        if not content:
            continue
        history_lines.append(f"{role.title()}: {content}")

    protected = ", ".join(protected_tokens or []) or "(none)"
    summary_text = _normalize_query(memory_summary or "") or "(none)"
    context_text = "\n".join(history_lines) or "(none)"
    runtime_context_text = _format_runtime_context(runtime_context)
    return f"""
你是知识库检索查询翻译器，需要把用户问题翻译成适合检索系统使用的查询。

目标：
把口语化、模糊、依赖上下文的用户问题，翻译成完整、无歧义、关键词密集的检索查询。

只返回 JSON：
{{
  "semantic_queries": ["完整语义查询，给向量检索"],
  "lexical_terms": ["关键词或短语，给关键词检索"],
  "candidate_entities": ["实体 1", "实体 2"]
}}

规则：
- 不要回答问题。
- 不要编造事实。
- semantic_queries 用于向量检索，必须完整、无歧义、保留问题语义。
- lexical_terms 用于关键词检索，只放单个关键词或不可拆短语，不要放一整句。
- candidate_entities 用于图谱检索，只放可作为实体匹配的对象名。
- 第一条 semantic_queries 必须是最适合作为独立向量检索输入的主查询。
- 每条 lexical_terms 都应短、准、面向命中，不要保留聊天式表达。
- 能从最近对话、会话摘要、用户环境中确定指代时，要补全代词、省略主语和模糊引用。
- 尽量包含明确的实体、模块、产品、功能名、流程名、属性、错误名、标识符和约束条件。
- 去掉“怎么”“这个”“那个”“帮我看看”“是什么意思”等口语填充词，除非它们属于真实术语。
- 根据问题需要返回有效查询，不要为了凑数量生成重复或空泛查询。
- 相关时必须原样保留这些受保护 token：{protected}
- question_type 用于决定改写策略。
- retrieval_label 用于决定检索宽度：fast 表示最小扩展，standard 表示均衡，broad 表示更宽召回。
- followup_lookup 必须尽量根据最近对话补全短指代。
- procedural_lookup 应偏向流程、步骤、配置、处理方式等词。
- relationship_lookup 应偏向关系、依赖、归属、连接等词。
- compare_lookup 应偏向对比类查询。
- summary_lookup 可以包含多方面概览查询。
- candidate_entities 应包含问题或改写查询中的主要实体、模块、产品、流程名或对象。
- 如果没有明确内容，返回空数组。

问题类型：{question_type}
检索宽度：{retrieval_label}

会话摘要：
{summary_text}

最近对话：
{context_text}

用户环境：
{runtime_context_text}

用户问题：
{query}
""".strip()


def _build_hyde_prompt(
    query: str,
    *,
    question_type: str,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    protected_tokens: list[str] | None = None,
) -> str:
    history_lines = []
    for item in list(chat_history or [])[-4:]:
        role = str(item.get("role") or "").strip().lower() or "assistant"
        content = _normalize_query(str(item.get("content") or ""))
        if not content:
            continue
        history_lines.append(f"{role.title()}: {content}")

    protected = ", ".join(protected_tokens or []) or "(none)"
    summary_text = _normalize_query(memory_summary or "") or "(none)"
    context_text = "\n".join(history_lines) or "(none)"
    runtime_context_text = _format_runtime_context(runtime_context)
    return f"""
你是知识库检索增强器，需要为用户问题生成一段用于向量检索的“假设答案文档”（HyDE）。

目标：
- 写一段看起来像知识库文档片段的短文本，帮助向量检索更容易命中相关内容。
- 这不是给用户的最终答案，只是检索用的语义扩展文本。

输出要求：
- 只输出纯文本，不要输出 JSON、标题、列表标记或解释。
- 长度控制在 1 段内，尽量 60 到 180 个中文字符。
- 保留用户问题里的关键实体、属性、约束、场景和受保护 token。
- 可以合理补全可能出现在知识库中的相关表达，但不要编造具体事实、数字、结论或引用来源。
- 如果问题是比较/关系类，优先覆盖对比维度、关系对象和判断标准。
- 如果问题是属性/定义类，优先覆盖对象、属性、适用范围、限制条件和常见表述。
- 相关时必须原样保留这些受保护 token：{protected}

问题类型：{question_type}

会话摘要：
{summary_text}

最近对话：
{context_text}

用户环境：
{runtime_context_text}

用户问题：
{query}
""".strip()


async def generate_hyde_document(
    query: str,
    *,
    llm: Any,
    question_type: str,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    protected_tokens: list[str] | None = None,
) -> str:
    response = await llm.ainvoke(
        _build_hyde_prompt(
            query,
            question_type=question_type,
            chat_history=chat_history,
            memory_summary=memory_summary,
            runtime_context=runtime_context,
            protected_tokens=protected_tokens,
        )
    )
    return _normalize_hyde_document(_coerce_text(getattr(response, "content", response)))


def _append_hyde_query(semantic_queries: list[str], hyde_document: str) -> list[str]:
    normalized_hyde = _normalize_hyde_document(hyde_document)
    if not normalized_hyde:
        return semantic_queries

    merged: list[str] = []
    seen: set[str] = set()
    for item in [*semantic_queries, normalized_hyde]:
        normalized = _normalize_hyde_document(item)
        if len(normalized) < 2:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        merged.append(normalized)
        seen.add(key)
    return merged


def _validate_queries(
    *,
    original: str,
    queries: list[str],
    protected_tokens: list[str],
) -> list[str]:
    normalized = _dedupe_keep_order(queries, limit=max(len(queries), 1))
    if not normalized:
        normalized = _dedupe_keep_order([original], limit=1)
    if not normalized:
        return []

    if protected_tokens:
        joined = " || ".join(normalized)
        for token in protected_tokens[:8]:
            if token not in joined and token.casefold() in original.casefold():
                raise ValueError(f"protected token missing from rewrite result: {token}")
    return normalized


async def build_kb_chat_retrieval_queries(
    query: str,
    *,
    chat_history: list[dict[str, str]] | None = None,
    memory_summary: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
    question_type: str = "entity_lookup",
    retrieval_label: str = "standard",
) -> dict[str, Any]:
    """Build retrieval-focused queries for single-round KB chat."""

    original = _normalize_query(query)
    if not original:
        return {
            "semantic_queries": [],
            "lexical_terms": [],
            "candidate_entities": [],
            "relation_pairs": [],
            "relation_queries": [],
            "target_attributes": [],
            "entity_constraints": {},
        }

    protected_tokens = _extract_protected_tokens(original)
    fallback = _build_fallback_queries(
        original,
        chat_history=chat_history,
        memory_summary=memory_summary,
        runtime_context=runtime_context,
        limit=_FALLBACK_RETRIEVAL_QUERY_LIMIT,
    )

    try:
        resolved_factory = llm_factory or get_llm_for_analysis
        llm = resolved_factory()
        response = await llm.ainvoke(
            _build_rewrite_prompt(
                original,
                question_type=question_type,
                retrieval_label=retrieval_label,
                chat_history=chat_history,
                memory_summary=memory_summary,
                runtime_context=runtime_context,
                protected_tokens=protected_tokens,
            )
        )
        parsed = extract_json_from_llm_response(_coerce_text(getattr(response, "content", response)))
        raw_semantic_queries = parsed.get("semantic_queries") or []
        llm_semantic_queries = [item for item in raw_semantic_queries if isinstance(item, str)]
        raw_lexical_terms = parsed.get("lexical_terms") or []
        llm_lexical_terms = [item for item in raw_lexical_terms if isinstance(item, str)]
        raw_entities = parsed.get("candidate_entities") or []
        llm_entities = [
            _normalize_query(item)
            for item in raw_entities
            if isinstance(item, str) and _normalize_query(item)
        ]
        semantic_queries = _validate_queries(
            original=original,
            queries=llm_semantic_queries,
            protected_tokens=protected_tokens,
        )
        try:
            hyde_document = await generate_hyde_document(
                original,
                llm=llm,
                question_type=question_type,
                chat_history=chat_history,
                memory_summary=memory_summary,
                runtime_context=runtime_context,
                protected_tokens=protected_tokens,
            )
            semantic_queries = _append_hyde_query(semantic_queries, hyde_document)
        except Exception as exc:
            logger.warning("KB chat HyDE generation failed, continue without HyDE: {}", exc)
        lexical_terms = _split_lexical_terms(llm_lexical_terms)
        return {
            "semantic_queries": semantic_queries or fallback or [original],
            "lexical_terms": lexical_terms,
            "candidate_entities": _dedupe_keep_order(llm_entities, limit=8),
            "relation_pairs": list(parsed.get("relation_pairs") or []),
            "relation_queries": list(parsed.get("relation_queries") or []),
            "target_attributes": [
                _normalize_query(item)
                for item in list(parsed.get("target_attributes") or [])
                if isinstance(item, str) and _normalize_query(item)
            ],
            "entity_constraints": (
                dict(parsed.get("entity_constraints") or {})
                if isinstance(parsed.get("entity_constraints"), dict)
                else {}
            ),
        }
    except Exception as exc:
        logger.warning("KB chat query rewrite failed, fallback to backup queries: {}", exc)
        return {
            "semantic_queries": fallback or [original],
            "lexical_terms": [],
            "candidate_entities": [],
            "relation_pairs": [],
            "relation_queries": [],
            "target_attributes": [],
            "entity_constraints": {},
        }
