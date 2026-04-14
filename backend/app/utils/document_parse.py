"""
多格式上传文档 → 纯文本（Markdown 友好）。

供 HTTP 入口、图外组装状态等调用。
Cursor Skill「document-parse」描述与本模块保持同步。
"""
from __future__ import annotations

from io import BytesIO
from typing import Tuple

# 支持的文件类型（扩展名小写，带点）
SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx"})
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def normalize_requirements_plaintext(text: str) -> str:
    """
    图外规范化：统一换行与首尾空白。
    文件解析成功后在 parse_uploaded_document 内调用；JSON 直传需求在调用 prototype_state 前应调用本函数。
    """
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def parse_uploaded_document(filename: str, content: bytes) -> Tuple[str, str | None]:
    """
    从上传文件名与二进制内容解析为纯文本。

    Returns:
        (text, error_message)；成功时 error_message 为 None。
    """
    if len(content) > MAX_FILE_SIZE:
        return "", "文件大小超过限制（最大 %sMB）" % (MAX_FILE_SIZE // 1024 // 1024)

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        return "", "不支持的文件格式: %s，支持 %s" % (
            ext,
            ", ".join(sorted(SUPPORTED_EXTENSIONS)),
        )

    try:
        if ext in (".txt", ".md"):
            raw = _parse_text(content)
        elif ext == ".pdf":
            raw = _parse_pdf(content)
        elif ext == ".docx":
            raw = _parse_docx(content)
        else:
            return "", "未实现的解析器: %s" % ext
        return normalize_requirements_plaintext(raw), None
    except Exception as e:
        return "", "文件解析失败: %s" % str(e)


def _parse_text(content: bytes) -> str:
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码")


def _parse_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ImportError("请安装 pypdf: pip install pypdf") from e

    reader = PdfReader(BytesIO(content))
    texts = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(texts).strip()


def _paragraph_to_line(p) -> str | None:
    text = p.text.strip()
    if not text:
        return None
    style = ((p.style and p.style.name) or "").lower()
    if (
        "heading 1" in style
        or style == "title"
        or style.startswith("标题 1")
        or style.startswith("标题1")
    ):
        return "# %s" % text
    if "heading 2" in style or style.startswith("标题 2") or style.startswith("标题2"):
        return "## %s" % text
    if "heading 3" in style or style.startswith("标题 3") or style.startswith("标题3"):
        return "### %s" % text
    if "heading 4" in style or style.startswith("标题 4") or style.startswith("标题4"):
        return "#### %s" % text
    return text


def _iter_block_items(parent):
    from docx.document import Document as DocxDocument
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph

    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        parent_elm = getattr(parent, "_element", None)
        if parent_elm is None:
            return

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _table_to_text(table) -> str:
    from docx.text.paragraph import Paragraph

    rows_out: list[str] = []
    for row in table.rows:
        cells_out: list[str] = []
        for cell in row.cells:
            parts: list[str] = []
            for block in _iter_block_items(cell):
                if isinstance(block, Paragraph):
                    t = block.text.strip()
                    if t:
                        parts.append(t)
                else:
                    inner = _table_to_text(block).strip()
                    if inner:
                        parts.append(inner.replace("\n", " "))
            cells_out.append(" ".join(parts))
        rows_out.append(" | ".join(cells_out))
    return "\n".join(rows_out)


def _blocks_to_lines(doc) -> list[str]:
    from docx.document import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    lines: list[str] = []
    if not isinstance(doc, DocxDocument):
        return lines

    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            line = _paragraph_to_line(block)
            if line:
                lines.append(line)
        elif isinstance(block, Table):
            t = _table_to_text(block).strip()
            if t:
                lines.append(t)
    return lines


def _header_footer_extra(doc) -> list[str]:
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    extra: list[str] = []
    for section in doc.sections:
        for label, part in (("页眉", section.header), ("页脚", section.footer)):
            el = part._element
            for child in el.iterchildren():
                if isinstance(child, CT_P):
                    t = Paragraph(child, part).text.strip()
                    if t:
                        extra.append("[%s] %s" % (label, t))
                elif isinstance(child, CT_Tbl):
                    t = _table_to_text(Table(child, part)).strip()
                    if t:
                        extra.append("[%s]\n%s" % (label, t))
    return extra


def _parse_docx(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as e:
        raise ImportError("请安装 python-docx: pip install python-docx") from e

    doc = Document(BytesIO(content))
    lines = _blocks_to_lines(doc)
    hf = _header_footer_extra(doc)
    if hf:
        lines.extend(hf)
    return "\n\n".join(lines).strip()
