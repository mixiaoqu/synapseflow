"""Prompt exports."""

from __future__ import annotations

from typing import Any

__all__ = [
    "sanitize_user_kb_context",
    "build_kb_chat_answer_prompt",
]


def __getattr__(name: str) -> Any:
    if name == "sanitize_user_kb_context":
        from app.agents.prompts.common import sanitize_user_kb_context

        return sanitize_user_kb_context
    if name == "build_kb_chat_answer_prompt":
        from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt

        return build_kb_chat_answer_prompt
    raise AttributeError(name)
