"""根据 product_design、interaction_design 两步结果，单次调用生成 HTML 原型。"""
import asyncio
import hashlib
import html as html_lib
import json
import os
import time
from typing import Any, Dict

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.core.config import settings
from app.core.llm import get_llm_for_generation


def _json(state: Dict[str, Any], key: str) -> str:
    return json.dumps(state.get(key) or {}, ensure_ascii=False, indent=2)


def _strip_code_fence(content: str) -> str:
    if "```html" in content:
        return content.split("```html")[1].split("```")[0].strip()
    if "```" in content:
        return content.split("```")[1].split("```")[0].strip()
    return content.strip()


def _write_preview_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _navigation_layout_rules(state: DocToPrototypeState) -> str:
    ps = state.get("product_spec") or {}
    nav = ps.get("navigation") if isinstance(ps.get("navigation"), dict) else {}
    nt = (nav.get("type") or "").strip().lower()
    if nt not in ("top", "sidebar", "tab"):
        vs = ((state.get("extracted_requirements") or {}).get("visual_style") or {})
        nt = (vs.get("navigation_type") or "top").strip().lower()
    if nt not in ("top", "sidebar", "tab"):
        nt = "top"
    if nt == "sidebar":
        return (
            "- **全局导航（必须）**：`navigation.type` 为 **sidebar**。"
            " 使用**左侧固定竖向导航栏**（桌面宽度约 w-56～w-64），**右侧**为可滚动主内容区；"
            "主导航链接放在侧栏，**不要用顶栏横向菜单代替侧栏主导航**（顶栏仅可放标题/用户区等辅助信息）。"
        )
    if nt == "tab":
        return (
            "- **全局导航（必须）**：`navigation.type` 为 **tab**。"
            " 在**主内容区顶部**使用横向 **Tab** 切换不同区块或 hash 视图，"
            "不要用完整顶栏水平站点多页导航替代 Tab 结构（除非需求明确要求）。"
        )
    return (
        "- **全局导航（必须）**：`navigation.type` 为 **top**。"
        " 使用**页面顶部横向导航栏**放置主要入口，内容在下方主区域展开。"
    )


def _wrap_if_fragment(html: str, state: DocToPrototypeState) -> str:
    full = html.strip()
    if "<!DOCTYPE" in full or "<html" in full.lower():
        return full
    title = (
        (state.get("extracted_requirements") or {}).get("page_info") or {}
    ).get("title", "原型预览")
    title_esc = html_lib.escape(str(title))
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        "  <title>%s</title>\n  <script src=\"https://cdn.tailwindcss.com\"></script>\n"
        "</head>\n<body class=\"bg-slate-50 text-slate-900\">\n%s\n</body>\n</html>"
        % (title_esc, full)
    )


async def generate_prototype_from_spec_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """
    根据 product_spec 与 interaction_spec 生成 HTML 原型。
    """
    prompt = f"""你是前端工程师。下面 JSON 来自流水线中**产品设计**与**交互设计**两个节点的输出，请据此生成**可运行的 HTML 原型**。

# 产品设计（product_spec）
{_json(state, "product_spec")}

# 交互设计（interaction_spec）
{_json(state, "interaction_spec")}

# 需求摘要（extracted_requirements）
{_json(state, "extracted_requirements")}

要求：
- 中文界面，页面美观现代
- **系统模块**：若 `product_spec.system_modules` 非空，信息架构与页内区块须与之对齐（模块/子模块在界面中有对应体现，勿与文档层级矛盾）。
- 严格遵循 `product_spec.navigation`：`type` 与 `links` 必须与页面 `id`、hash 路由一致。
{_navigation_layout_rules(state)}
- 只输出 HTML 源码，不要 Markdown 解释。
- 确保交互功能都正常运行。

请直接生成 HTML：
"""

    llm = get_llm_for_generation()
    t0 = time.perf_counter()
    try:
        response = await llm.ainvoke(prompt)
    except Exception as e:
        logger.error("[规格生成原型] LLM 调用失败: %s", e, exc_info=True)
        return {
            "generated_html": "",
            "preview_url": "",
            "is_valid": False,
            "validation_errors": ["生成失败: %s" % str(e)],
            "metadata": {"error": str(e)},
        }

    raw = _strip_code_fence(response.content)
    full_html = _wrap_if_fragment(raw, state)
    elapsed = time.perf_counter() - t0
    logger.info(
        "[规格生成原型] 完成，耗时 %.1fs，HTML 长度 %s",
        elapsed,
        len(full_html),
    )

    if not full_html.strip():
        return {
            "generated_html": "",
            "preview_url": "",
            "is_valid": False,
            "validation_errors": ["HTML 为空"],
            "metadata": {},
        }

    file_hash = hashlib.md5(full_html.encode()).hexdigest()[:12]
    preview_dir = settings.PREVIEW_DIR
    preview_path = os.path.join(preview_dir, "%s.html" % file_hash)
    await asyncio.to_thread(os.makedirs, preview_dir, exist_ok=True)
    await asyncio.to_thread(_write_preview_file, preview_path, full_html)
    preview_url = "/preview/%s.html" % file_hash

    return {
        "generated_html": full_html,
        "preview_url": preview_url,
        "is_valid": True,
        "validation_errors": [],
        "metadata": {"file_hash": file_hash, "file_path": preview_path},
    }
