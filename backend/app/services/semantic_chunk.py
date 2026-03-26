"""
向量索引用分块：仅在 # / ## / ### 处切段（不把 #### 及以下当边界），
段内按空行段落合并，单块总长度不超过 max_chars；超长块再用 RecursiveCharacterTextSplitter 细分。
每块写入向量前增加「[模块路径] 父 > 子」前缀（与正文一并 embedding）。
"""
import re
from typing import List, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter


def _format_module_prefix(crumb: str, max_chars: int) -> str:
    if not crumb:
        return ""
    head, tail = "[模块路径] ", "\n\n"
    reserve_body = 48
    max_crumb = max_chars - len(head) - len(tail) - reserve_body
    if max_crumb < 4:
        return ""
    c = crumb if len(crumb) <= max_crumb else crumb[: max_crumb - 1] + "…"
    return head + c + tail


def _body_budget(max_chars: int, prefix: str) -> int:
    """正文允许的最大长度，使 len(prefix) + body <= max_chars（极端情况至少保留 1）。"""
    return max(1, max_chars - len(prefix))


def _parse_heading_line(line: str) -> Tuple[int, str] | None:
    m = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
    if not m:
        return None
    return len(m.group(1)), m.group(2).strip()


def _sections_with_breadcrumbs(doc: str) -> List[Tuple[str, str]]:
    """按 #～### 切段顺序扫描，为每段生成 (面包屑, 段原文)。"""
    parts = re.split(r"(?=^#{1,3}\s+)", doc, flags=re.MULTILINE)
    stack: List[Tuple[int, str]] = []
    out: List[Tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        first = part.split("\n", 1)[0].strip()
        parsed = _parse_heading_line(first)
        if parsed:
            level, title = parsed
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            crumb = " > ".join(t for _, t in stack)
        else:
            crumb = ""
        out.append((crumb, part))
    return out


def _pack_paragraphs(parts: List[str], max_chars: int) -> List[str]:
    """将段落列表按 max_chars 合并为若干块。"""
    chunks_raw: List[str] = []
    current = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(current) + len(p) + 2 <= max_chars:
            current = (current + "\n\n" + p).strip() if current else p
        else:
            if current:
                chunks_raw.append(current)
            if len(p) <= max_chars:
                current = p
            else:
                subparts = re.split(r"(?<=[。\n])", p)
                current = ""
                for sp in subparts:
                    sp = sp.strip()
                    if not sp:
                        continue
                    while len(sp) > max_chars:
                        if current:
                            chunks_raw.append(current)
                            current = ""
                        chunks_raw.append(sp[:max_chars])
                        sp = sp[max_chars:].lstrip()
                    if len(current) + len(sp) + 2 <= max_chars:
                        current = (current + "\n\n" + sp).strip() if current else sp
                    else:
                        if current:
                            chunks_raw.append(current)
                        current = sp
    if current:
        chunks_raw.append(current)
    return chunks_raw


def _split_oversized_with_splitter(
    text: str, body_max: int, overlap: int
) -> List[str]:
    if len(text) <= body_max:
        return [text] if text.strip() else []
    ov = min(overlap, max(0, body_max - 1))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=body_max,
        chunk_overlap=ov,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )
    return [x.strip() for x in splitter.split_text(text) if x.strip()]


def split_for_vector_index(text: str, max_chars: int, overlap: int) -> List[str]:
    """
    :param text: 全文
    :param max_chars: 单块最大字符数（含「模块路径」前缀，来自 embedding.yaml chunk.size）
    :param overlap: 仅在对超长正文做字符级切分时使用（chunk.overlap）
    """
    if not text.strip():
        return []
    doc = text.strip()
    sections = _sections_with_breadcrumbs(doc)
    out: List[str] = []

    for crumb, section in sections:
        prefix = _format_module_prefix(crumb, max_chars)
        body_max = _body_budget(max_chars, prefix)

        if len(section) <= body_max:
            piece = (prefix + section).strip() if prefix else section
            if piece:
                out.append(piece)
            continue

        inner = [p.strip() for p in re.split(r"\n\s*\n+", section) if p.strip()]
        raw_chunks = _pack_paragraphs(inner, body_max)
        for c in raw_chunks:
            c = c.strip()
            if not c:
                continue
            if len(c) <= body_max:
                piece = (prefix + c).strip() if prefix else c
                out.append(piece)
            else:
                for sub in _split_oversized_with_splitter(c, body_max, overlap):
                    piece = (prefix + sub).strip() if prefix else sub
                    out.append(piece)

    return [x for x in out if x]
