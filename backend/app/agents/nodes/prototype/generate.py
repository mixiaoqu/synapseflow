"""HTML/CSS/JS生成节点"""
import json
from typing import Dict, Any

from app.agents.states.prototype_state import DocToPrototypeState
from app.core.llm import get_llm_for_code_gen


def _truncate_for_prompt(obj: Any, max_chars: int = 6000) -> str:
    """避免 prompt 过长导致 API 限制"""
    s = json.dumps(obj, ensure_ascii=False)
    return s[:max_chars] + "..." if len(s) > max_chars else s


async def generate_html_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """
    HTML生成节点：生成完整的独立HTML页面（内联CSS+JS）
    使用：code_generation 
    """
    llm = get_llm_for_code_gen()

    req = state["extracted_requirements"]
    page_info = req.get("page_info", {})
    modules = req.get("functional_modules", [])[:6]
    style = req.get("visual_style", {})
    req_summary = {"page_info": page_info, "functional_modules": modules, "visual_style": style}

    prompt = f"""你是一个专业的前端工程师，请生成一个完整的、可独立运行的HTML页面。

组件结构：{_truncate_for_prompt(state["ui_components"], 2000)}
需求概要：{_truncate_for_prompt(req_summary)}
设计系统：{_truncate_for_prompt(state.get("design_system", {}), 1000)}

要求：
1. 生成完整的 <!DOCTYPE html> 页面，包含 <head> 和 <body>
2. CSS 写在 <style> 标签内（不要外链）
3. JavaScript 写在 <script> 标签内（不要外链，可使用 CDN 如 Tailwind/Alpine.js）
4. 响应式设计，支持移动端
5. 页面美观现代，符合设计系统配色
6. 直接输出 HTML 代码，不要任何解释。控制在 800 行以内以保持简洁。

生成完整HTML页面：
"""

    try:
        response = await llm.ainvoke(prompt)
    except Exception as e:
        err_msg = str(e)
        if "buffer overflow" in err_msg.lower() or "overflow" in err_msg.lower():
            raise RuntimeError(
                f"LLM 输出超限，请尝试更简化的需求描述。原始错误: {err_msg}"
            ) from e
        raise
    content = response.content
    if "```html" in content:
        content = content.split("```html")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    html_code = content.strip()

    print("\n" + "="*80)
    print(f"[节点完成] 生成HTML (generate_html)")
    print("="*80)
    print(f"[HTML代码]: {len(html_code.split(chr(10)))} 行")
    for i, line in enumerate(html_code.split('\n')[:10], 1):
        print(f"{i:3d} | {line[:75]}")
    print("="*80 + "\n")

    return {"generated_html": html_code}


async def generate_css_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """CSS已内联到HTML，此节点直接跳过"""
    print("[节点跳过] generate_css - CSS已内联到HTML中")
    return {"generated_css": ""}


async def generate_js_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """JS已内联到HTML，此节点直接跳过"""
    print("[节点跳过] generate_js - JS已内联到HTML中")
    return {"generated_js": ""}
