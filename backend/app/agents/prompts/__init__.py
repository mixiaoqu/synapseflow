"""Prompt exports."""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_kb_chat_answer_prompt",
]


def __getattr__(name: str) -> Any:
    if name == "build_kb_chat_answer_prompt":
        from app.agents.prompts.kb_chat import build_kb_chat_answer_prompt

        return build_kb_chat_answer_prompt
    raise AttributeError(name)
