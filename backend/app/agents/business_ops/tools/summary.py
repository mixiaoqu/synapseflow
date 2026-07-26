"""Bound tool results before passing them back to the business planner."""

from __future__ import annotations

from typing import Any

MAX_SUMMARY_ITEMS = 10
MAX_SUMMARY_TEXT = 500


def summarize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_SUMMARY_TEXT]
    if isinstance(value, list):
        return [summarize_value(item) for item in value[:MAX_SUMMARY_ITEMS]]
    if isinstance(value, dict):
        return {str(key): summarize_value(item) for key, item in value.items()}
    return value
