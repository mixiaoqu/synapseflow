"""需求提取节点"""
import json
from typing import Dict, Any

from app.agents.states.prototype_state import DocToPrototypeState
from app.core.llm import get_llm_for_long_text

from app.agents.nodes.prototype.utils import (
    parse_json_safely,
    auto_complete_requirements,
    normalize_requirements,
)


async def extract_requirements_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """
    需求提取节点：理解任意格式的需求文档
    使用：long_text_understanding - Kimi长文本理解（temperature=0.4）
    """
    print("\n" + "="*80)
    print("[节点开始] extract_requirements_node 开始执行")
    print(f"[节点开始] 需求文档长度: {len(state['requirements_doc'])}")
    print("="*80)

    llm = get_llm_for_long_text()
    print(f"[节点] 获取LLM实例: {llm.__class__.__name__}")

    prompt = f"""你是一个资深的产品设计师和前端架构师，擅长从各种格式的需求文档中提取UI设计需求。

# 需求文档
{state["requirements_doc"]}

---

# 你的任务
从上述文档中提取完整的UI设计需求，包括：页面结构、功能模块、交互行为、数据模型、视觉风格。

## 提取规则

### 1. 页面类型识别
- **落地页**：包含Hero区、特性展示、CTA按钮 → `landing_page`
- **仪表盘**：包含数据图表、统计卡片、侧边栏 → `dashboard`
- **表单页**：主要是输入字段和提交 → `form`
- **内容页**：文章、博客、文档展示 → `content`
- **电商**：产品列表、购物车、结账 → `ecommerce`

### 2. 功能模块拆解
从描述中识别关键模块：
- "顶部导航" / "菜单" / "Header" → Navbar模块
- "大标题" / "主视觉区" / "Hero" → Hero模块
- "联系表单" / "反馈" → ContactForm模块
- "产品特性" / "优势展示" → Features模块
- "底部" / "Footer" / "版权信息" → Footer模块

### 3. 交互行为推断
- 明确的交互：从动词识别（点击、提交、滚动、悬停）
- 隐含的交互：
  - 表单 → 自动添加"验证"和"提交"交互
  - 导航菜单 → 自动添加"展开/收起"交互
  - 模态框 → 自动添加"打开/关闭"交互

### 4. 数据模型提取
- 从表单字段描述推断类型：
  - "邮箱" → type: "email", validation: "email格式"
  - "密码" → type: "password", minLength: 6
  - "姓名" → type: "text", required: true
- 从数据展示推断：
  - "用户列表" → 需要User数据模型
  - "产品卡片" → 需要Product数据模型

### 5. 视觉风格识别
- **主题关键词**：
  - "现代" / "简约" → modern
  - "暗色" / "深色" → dark
  - "扁平" → flat
  - "渐变" / "炫彩" → gradient
- **配色关键词**：
  - "蓝色系" → blue (#3B82F6)
  - "紫色系" → purple (#8B5CF6)
  - "绿色系" → green (#10B981)
  - 未指定 → 默认蓝色
- **布局关键词**：
  - "单栏" → single_column
  - "两栏" / "分栏" → two_column
  - "网格" / "卡片式" → grid

---

## 输出格式（严格JSON）

```json
{{
    "page_info": {{
        "title": "提取的页面标题",
        "type": "landing_page",
        "description": "页面用途简述"
    }},
    "functional_modules": [
        {{
            "id": "navbar",
            "name": "导航栏",
            "description": "顶部导航，包含Logo和菜单",
            "position": "top",
            "components": ["Logo", "NavMenu", "CTAButton"],
            "priority": "high"
        }},
        {{
            "id": "hero",
            "name": "Hero区域",
            "description": "主视觉区，包含标题和行动号召",
            "position": "main",
            "components": ["Heading", "Subheading", "CTAButtons"],
            "priority": "high"
        }}
    ],
    "interactions": [
        {{
            "id": "nav_toggle",
            "trigger": "点击菜单按钮",
            "action": "展开/收起导航菜单",
            "target": "mobile_menu",
            "event_type": "click"
        }},
        {{
            "id": "cta_click",
            "trigger": "点击CTA按钮",
            "action": "跳转到注册页面或显示表单",
            "target": "signup_form",
            "event_type": "click"
        }}
    ],
    "data_model": [
        {{
            "entity": "ContactForm",
            "fields": [
                {{
                    "name": "name",
                    "label": "姓名",
                    "type": "text",
                    "required": true,
                    "validation": "非空"
                }},
                {{
                    "name": "email",
                    "label": "邮箱",
                    "type": "email",
                    "required": true,
                    "validation": "邮箱格式"
                }}
            ]
        }}
    ],
    "visual_style": {{
        "theme": "modern",
        "color_scheme": "blue",
        "primary_color": "#3B82F6",
        "layout": "single_column",
        "font_family": "Inter",
        "responsive": true
    }}
}}
```

---

## 重要提示
1. **必须返回有效的JSON**（用```json包裹）
2. **如果信息不完整，智能补全**（如：只说"登录页"→自动添加用户名、密码字段）
3. **优先识别核心功能**，次要细节可以默认值
4. **交互尽可能详细**，这决定了JS代码质量

现在开始提取！
"""

    try:
        print(f"[节点] 准备调用LLM，prompt长度: {len(prompt)}")
        response = await llm.ainvoke(prompt)
        print(f"[节点] LLM调用完成，响应长度: {len(response.content)}")
        extracted = parse_json_safely(response.content)
        print(f"[节点] JSON解析完成")

        if not extracted or "page_info" not in extracted:
            print(f"[警告] LLM返回格式不正确，使用智能补全")
            extracted = auto_complete_requirements(state["requirements_doc"], extracted)

        extracted = normalize_requirements(extracted)

        print("\n" + "="*80)
        print(f"[节点完成] 提取需求 (extract_requirements)")
        print("="*80)
        page_info = extracted.get('page_info', {})
        print(f"[页面信息]")
        print(f"   标题: {page_info.get('title', 'N/A')}")
        print(f"   类型: {page_info.get('type', 'N/A')}")
        print(f"   描述: {page_info.get('description', 'N/A')}")
        modules = extracted.get('functional_modules', [])
        print(f"\n[功能模块]: {len(modules)} 个")
        for i, module in enumerate(modules[:5], 1):
            print(f"   {i}. {module.get('name', '')} - {module.get('description', '')}")
        if len(modules) > 5:
            print(f"   ... 还有 {len(modules) - 5} 个模块")
        print("="*80 + "\n")

        return {"extracted_requirements": extracted}

    except Exception as e:
        print(f"[错误] 需求提取失败: {e}")
        return {
            "extracted_requirements": auto_complete_requirements(
                state["requirements_doc"],
                {}
            )
        }
