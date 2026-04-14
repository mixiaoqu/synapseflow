"""需求文档分块：超长时按 Markdown/伪标题切章，章内再按字数上限细分。"""
import re
from typing import Any, Dict, List

# 全文超过该字符数则启用「多章切分 + 并行抽取 + 合并」
PROTOTYPE_DOC_SPLIT_THRESHOLD = 12_000
# 单块最大字符（避免单章仍过长）
PROTOTYPE_SECTION_MAX_CHARS = 8_000
# 并行抽取章节时的最大并发数
PROTOTYPE_CHUNK_EXTRACT_CONCURRENCY = 4


def extract_section_title(text: str) -> str:
    """从块首行提取 Markdown 标题（#～####）。"""
    first_line = text.strip().split("\n")[0] if text else ""
    m = re.match(r"^#{1,4}\s+(.+)$", first_line.strip())
    return m.group(1).strip() if m else ""


def split_doc_into_section_texts(doc: str, max_chars: int) -> List[tuple[str, str]]:
    """
    将文档切成多个文本块（优先在 #～#### 标题处合并/断开，单块不超过 max_chars）。
    返回 [(chunk_text, section_title), ...]，title 可能为空。
    """
    doc = doc.strip()
    if not doc:
        return []
    if len(doc) <= max_chars:
        return [(doc, extract_section_title(doc))]

    chunks_raw: List[str] = []
    parts = re.split(r"(?=^#{1,4}\s+)", doc, flags=re.MULTILINE)
    if len(parts) == 1 and parts[0] == doc:
        parts = re.split(r"(\n\n+)", doc)
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
                subparts = re.split(r"(?<=[。\n])", p)
                sub_current = ""
                for sp in subparts:
                    sp = sp.strip()
                    if not sp:
                        continue
                    while len(sp) > max_chars:
                        if sub_current:
                            chunks_raw.append(sub_current)
                            sub_current = ""
                        chunks_raw.append(sp[:max_chars])
                        sp = sp[max_chars:].lstrip()
                    if len(sub_current) + len(sp) + 2 <= max_chars:
                        sub_current = (sub_current + "\n\n" + sp).strip() if sub_current else sp
                    else:
                        if sub_current:
                            chunks_raw.append(sub_current)
                        sub_current = sp
                current = sub_current
    if current:
        chunks_raw.append(current)

    return [(c, extract_section_title(c)) for c in chunks_raw]


def build_requirements_chunks(
    doc: str,
    split_threshold: int = PROTOTYPE_DOC_SPLIT_THRESHOLD,
    max_section_chars: int = PROTOTYPE_SECTION_MAX_CHARS,
) -> List[Dict[str, Any]]:
    """
    构造写入 state.requirements_chunks 的列表。
    未超阈值：单块（全文）；超过阈值：按章节/字数切多块。
    """
    doc = doc or ""
    if not doc.strip():
        return []

    if len(doc) <= split_threshold:
        return [
            {
                "id": "c0",
                "order": 0,
                "title": extract_section_title(doc) or "",
                "text": doc,
            }
        ]

    pairs = split_doc_into_section_texts(doc, max_section_chars)
    return [
        {
            "id": "c%s" % i,
            "order": i,
            "title": title or "",
            "text": text,
        }
        for i, (text, title) in enumerate(pairs)
    ]
