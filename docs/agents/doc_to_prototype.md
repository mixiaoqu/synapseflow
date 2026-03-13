# 文档转原型智能体

## 功能说明

将任意格式的需求文档自动转换为可交互的HTML原型，支持口语化、无格式文档。

## 状态定义

```python
class DocToPrototypeState(TypedDict):
    requirements_doc: str           # 需求文档
    extracted_requirements: dict    # 提取的结构化需求
    ui_components: List[dict]       # UI组件树
    design_system: dict             # 设计系统
    generated_html: str             # HTML代码
    generated_css: str              # CSS代码
    generated_js: str               # JavaScript代码
    validation_errors: List[str]    # 验证错误
    preview_url: str                # 预览链接
    is_valid: bool                  # 是否有效
    metadata: dict                  # 元数据
```

## 节点说明

### 1. extract_requirements_node（需求提取）
- **功能**：从任意格式文档中提取UI需求
- **模型**：Kimi（长上下文）
- **特点**：适应无格式文档，智能推断
- **输出**：page_info, functional_modules, interactions, data_model, visual_style

### 2. design_components_node（组件设计）
- **功能**：设计HTML组件架构和设计系统
- **模型**：Deepseek
- **输出**：ui_components, design_system

### 3. generate_html_node（HTML生成）
- **功能**：生成语义化HTML5代码
- **模型**：Deepseek
- **使用**：Tailwind CSS类名
- **输出**：generated_html

### 4. generate_css_node（CSS生成）
- **功能**：生成自定义样式
- **模型**：Deepseek
- **输出**：generated_css（CSS变量、动画、响应式）

### 5. generate_js_node（JS生成）
- **功能**：生成交互逻辑
- **模型**：Deepseek
- **输出**：generated_js（事件处理、表单验证）

### 6. validate_and_preview_node（验证预览）
- **功能**：验证代码并生成预览
- **验证**：HTML标签闭合、语法检查
- **输出**：preview_url, is_valid

## 流程特点

**顺序执行（流水线）**：无循环，一次性生成

## 支持的文档格式

✅ 规范Markdown（有标题和列表）
✅ 纯文本（口语化描述）
✅ 混乱笔记（跳跃性思维）
✅ 部分结构化

**示例输入：**
```
我想做个网站 上面要有个导航栏 然后下面写个大标题
再放几个产品介绍 最后要有联系表单 颜色用蓝色 要现代感
```

**LLM会理解并提取：**
- navbar（导航栏）
- hero（标题区域）
- features（产品介绍）
- contact form（联系表单）
- visual_style: modern + blue

## 使用示例

```python
from app.agents.workflows import create_doc_to_prototype_graph

prototype_graph = create_doc_to_prototype_graph()

result = await prototype_graph.ainvoke({
    "requirements_doc": "需求文档内容..."
})

print(f"预览: {result['preview_url']}")
print(f"有效: {result['is_valid']}")
```

## API端点

- `POST /api/v1/prototype/generate` - 同步生成
- `POST /api/v1/prototype/generate/stream` - 流式生成（SSE）
