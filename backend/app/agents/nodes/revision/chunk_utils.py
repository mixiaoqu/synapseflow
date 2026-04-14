"""共享分块逻辑：将文档切成小块"""
import re
from typing import List, Tuple

# 单块字符上限，规避 API 输出截断
CHUNK_CHAR_LIMIT = 1500

ChunkWithMeta = Tuple[str, str, int]


def extract_section_title(text: str) -> str:
    """从块首行提取标题（#～###### 开头的 Markdown 标题）"""
    first_line = text.strip().split("\n")[0] if text else ""
    m = re.match(r'^#{1,6}\s+(.+)$', first_line.strip())
    return m.group(1).strip() if m else ""


def split_document_into_chunks(
    doc: str,
    max_chars: int = CHUNK_CHAR_LIMIT,
) -> List[ChunkWithMeta]:
    """
    将文档按自然段落分块，优先在 #～###### 标题处断开。
    单块不超过 max_chars 字符。
    返回 [(chunk_text, section_title, index), ...]
    """
    if not doc.strip():
        return []
    if len(doc) <= max_chars:
        return [(doc, extract_section_title(doc), 0)]

    chunks_raw: List[str] = []
    parts = re.split(r'(?=^#{1,6}\s+)', doc, flags=re.MULTILINE)
    if len(parts) == 1 and parts[0] == doc:
        parts = re.split(r'(\n\n+)', doc)
        parts = [p for p in parts if p.strip()]

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
                subparts = re.split(r'(?<=[。\n])', p)
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

    return [(c, extract_section_title(c), i) for i, c in enumerate(chunks_raw)]


def compute_chunk_positions(doc: str, chunks_meta: List[ChunkWithMeta]) -> List[Tuple[int, int]]:
    """
    计算每个 chunk 在原文中的 (start, end) 字符偏移。
    用于 doc_structure 的 section [start,end] 与 chunk 位置重叠判断。
    """
    if not doc or not chunks_meta:
        return []
    positions: List[Tuple[int, int]] = []
    search_start = 0
    for text, _, _ in chunks_meta:
        idx = doc.find(text, search_start)
        if idx >= 0:
            positions.append((idx, idx + len(text)))
            search_start = idx + len(text)
        else:
            positions.append((search_start, search_start + len(text)))
            search_start += len(text)
    return positions
