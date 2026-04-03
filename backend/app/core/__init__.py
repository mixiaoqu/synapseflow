"""Core module."""

from __future__ import annotations

from typing import Any

__all__ = ["settings", "config_registry"]


def __getattr__(name: str) -> Any:
    if name in {"settings", "config_registry"}:
        from app.core.config import config_registry, settings

        return {
            "settings": settings,
            "config_registry": config_registry,
        }[name]
    raise AttributeError(name)
