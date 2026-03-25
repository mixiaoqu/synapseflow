"""
向量索引用分块：优先按 Markdown 标题（#～######）切段，段内按空行段落合并，
单块不超过 max_chars；超长块再用 RecursiveCharacterTextSplitter（带 overlap）细分。
"""
import re
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


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


def split_for_vector_index(text: str, max_chars: int, overlap: int) -> List[str]:
    """
    :param text: 全文
    :param max_chars: 单块最大字符数（来自 embedding.yaml chunk.size）
    :param overlap: 仅在对超长块做字符级切分时使用（chunk.overlap）
    """
    if not text.strip():
        return []
    doc = text.strip()
    if len(doc) <= max_chars:
        return [doc]

    parts = re.split(r"(?=^#{1,6}\s+)", doc, flags=re.MULTILINE)
    chunks_raw: List[str] = []

    if len(parts) == 1 and parts[0] == doc:
        para_parts = [p.strip() for p in re.split(r"\n\s*\n+", doc) if p.strip()]
        chunks_raw = _pack_paragraphs(para_parts, max_chars)
    else:
        for section in parts:
            section = section.strip()
            if not section:
                continue
            if len(section) <= max_chars:
                chunks_raw.append(section)
                continue
            inner = [p.strip() for p in re.split(r"\n\s*\n+", section) if p.strip()]
            chunks_raw.extend(_pack_paragraphs(inner, max_chars))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )
    out: List[str] = []
    for c in chunks_raw:
        c = c.strip()
        if not c:
            continue
        if len(c) <= max_chars:
            out.append(c)
        else:
            out.extend(splitter.split_text(c))
    return [x.strip() for x in out if x.strip()]
