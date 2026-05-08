"""Embedded assistant page configuration helpers."""

from __future__ import annotations

import functools
from typing import Any

from pydantic import BaseModel, Field

from app.core.config.loader import load_embed_app_pages_raw


class EmbedPageConfig(BaseModel):
    page_type: str
    page_name: str = "当前页面"
    page_description: str = ""
    assistant_intro: str = ""
    suggested_questions: list[str] = Field(default_factory=list)


def _normalize_key(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


@functools.lru_cache(maxsize=128)
def _load_embed_page_config_data(product_code: str, project_code: str, app_code: str) -> dict[str, Any]:
    data = load_embed_app_pages_raw(product_code, project_code, app_code)
    return data if isinstance(data, dict) else {}


def get_embed_page_config(
    product_code: str | None,
    project_code: str | None,
    app_code: str | None,
    page_type: str | None,
) -> EmbedPageConfig | None:
    product_key = _normalize_key(product_code)
    project_key = _normalize_key(project_code)
    app_key = _normalize_key(app_code)
    page_key = _normalize_key(page_type)
    if not product_key or not project_key or not app_key or not page_key:
        return None

    data = _load_embed_page_config_data(product_key, project_key, app_key)
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, dict):
        return None

    raw_page = pages.get(page_key)
    if not isinstance(raw_page, dict):
        return None

    return EmbedPageConfig(
        page_type=page_key,
        page_name=str(raw_page.get("page_name") or "当前页面"),
        page_description=str(raw_page.get("page_description") or ""),
        assistant_intro=str(raw_page.get("assistant_intro") or ""),
        suggested_questions=_coerce_string_list(
            raw_page.get("suggested_questions")
        ),
    )
