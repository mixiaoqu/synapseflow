"""验证和预览节点"""
import os
import hashlib
from typing import Dict, Any

from loguru import logger

from app.agents.states.prototype_state import DocToPrototypeState
from app.core.config import settings


async def validate_and_preview_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """
    验证和预览节点：HTML已是完整页面，直接保存
    """
    full_html = state["generated_html"]

    if "<!DOCTYPE" not in full_html and "<html" not in full_html:
        page_title = state["extracted_requirements"].get("page_info", {}).get("title", "原型预览")
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
</head>
<body>
{full_html}
</body>
</html>"""

    validation_errors = []
    if not state["generated_html"]:
        validation_errors.append("HTML生成失败")

    file_hash = hashlib.md5(full_html.encode()).hexdigest()[:12]
    preview_dir = settings.PREVIEW_DIR
    os.makedirs(preview_dir, exist_ok=True)

    preview_path = os.path.join(preview_dir, f"{file_hash}.html")
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    preview_url = f"/preview/{file_hash}.html"
    logger.info("节点完成: validate_preview，预览={}，有效={}", preview_url, len(validation_errors) == 0)

    return {
        "generated_html": full_html,
        "validation_errors": validation_errors,
        "is_valid": len(validation_errors) == 0,
        "preview_url": preview_url,
        "metadata": {"file_hash": file_hash, "file_path": preview_path}
    }
