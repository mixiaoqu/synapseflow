"""Prompt 共用工具。"""

import re

_TECH_ROUTE_IN_PARENS = re.compile(
    r"\s*[（(]\s*[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)+(?:\?[A-Za-z0-9_=&-]+)?\s*[）)]"
)


def sanitize_user_kb_context(context: str) -> str:
    """移除普通用户回答中不应复述的技术路径标记，如“(refund/list)”之类内容。"""
    return _TECH_ROUTE_IN_PARENS.sub("", context or "")
