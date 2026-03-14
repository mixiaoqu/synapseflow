"""文件解析工具：从上传文件中提取文本内容"""
from typing import Tuple

# 支持的文件类型
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def extract_text_from_file(filename: str, content: bytes) -> Tuple[str, str | None]:
    """
    从文件内容中提取文本

    Args:
        filename: 文件名（用于判断类型）
        content: 文件二进制内容

    Returns:
        (提取的文本内容, 错误信息)
        成功时错误信息为 None
    """
    if len(content) > MAX_FILE_SIZE:
        return "", f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）"

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        return "", f"不支持的文件格式: {ext}，支持 {', '.join(SUPPORTED_EXTENSIONS)}"

    try:
        if ext in (".txt", ".md"):
            return _parse_text(content), None
        elif ext == ".pdf":
            return _parse_pdf(content), None
        elif ext == ".docx":
            return _parse_docx(content), None
        else:
            return "", f"未实现的解析器: {ext}"
    except Exception as e:
        return "", f"文件解析失败: {str(e)}"


def _parse_text(content: bytes) -> str:
    """解析纯文本和 Markdown"""
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码")


def _parse_pdf(content: bytes) -> str:
    """解析 PDF"""
    try:
        from pypdf import PdfReader
        from io import BytesIO
    except ImportError:
        raise ImportError("请安装 pypdf: pip install pypdf")

    reader = PdfReader(BytesIO(content))
    texts = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
    return "\n\n".join(texts).strip()


def _parse_docx(content: bytes) -> str:
    """解析 Word 文档"""
    try:
        from docx import Document
        from io import BytesIO
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")

    doc = Document(BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs).strip()
