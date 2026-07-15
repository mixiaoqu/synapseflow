"""Compatibility names for the legacy embedded assistant page."""

from app.core.config.assistant_pages import (
    AssistantPageConfig as EmbedPageConfig,
    get_assistant_page_config as get_embed_page_config,
)

__all__ = ["EmbedPageConfig", "get_embed_page_config"]
