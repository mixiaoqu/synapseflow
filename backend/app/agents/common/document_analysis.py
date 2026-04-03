"""Shared document structure analysis helpers."""

from __future__ import annotations

import re
from typing import Any


def parse_markdown_headings(document: str) -> list[dict[str, Any]]:
    """Extract markdown headings with their level and offsets."""

    headings: list[dict[str, Any]] = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", document, flags=re.MULTILINE):
        headings.append(
            {
                "level": len(match.group(1)),
                "title": match.group(2).strip(),
                "start": match.start(),
            }
        )
    return headings


def build_markdown_section_tree(
    headings: list[dict[str, Any]],
    *,
    document_length: int,
) -> list[dict[str, Any]]:
    """Build a nested section tree from parsed markdown headings."""

    if not headings:
        return []

    tree: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []
    for index, heading in enumerate(headings):
        level = heading["level"]
        end = document_length
        if index + 1 < len(headings):
            end = headings[index + 1]["start"] - 1

        node = {
            "level": level,
            "title": heading["title"],
            "start": heading["start"],
            "end": end,
            "children": [],
        }

        while stack and stack[-1]["level"] >= level:
            stack.pop()

        if stack:
            stack[-1]["children"].append(node)
        else:
            tree.append(node)

        stack.append(node)

    return tree
