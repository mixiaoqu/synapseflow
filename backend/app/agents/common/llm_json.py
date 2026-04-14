"""Common JSON parsing helpers for LLM responses."""

from __future__ import annotations

from typing import Any

from app.utils import extract_json_from_llm_response


def parse_llm_json_object(content: str) -> dict[str, Any]:
    """Safely parse a JSON object from an LLM response."""

    return extract_json_from_llm_response(content)
