"""Readable Chinese logging helpers for workflow nodes."""

from __future__ import annotations

import json
from typing import Any, Mapping

from loguru import logger


def _clip_text(value: Any, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return _clip_text(value)
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        sample = value[:5]
        suffix = f"（共 {len(value)} 项）" if len(value) > len(sample) else ""
        return f"{json.dumps(sample, ensure_ascii=False, default=str)}{suffix}"
    if isinstance(value, Mapping):
        return json.dumps(dict(value), ensure_ascii=False, default=str)
    return _clip_text(value)


def log_node_info(
    *,
    workflow_id: str,
    node_id: str,
    node_name: str,
    details: Mapping[str, Any],
    elapsed_ms: int | None = None,
) -> None:
    """Print one readable Chinese log block for a workflow node."""

    lines = [
        "",
        f"[工作流节点] {workflow_id}.{node_id} - {node_name}",
    ]
    for key, value in details.items():
        lines.append(f"- {key}: {_format_value(value)}")
    if elapsed_ms is not None:
        lines.append(f"- 节点耗时毫秒: {elapsed_ms}")
    logger.bind(agent_node_log=True).info("\n".join(lines))
