# 递归修订智能体

## 功能说明

自动检测文档中的遗漏内容，并通过递归循环不断补充完善。

## 状态定义

```python
class RecursiveRevisionState(TypedDict):
    original_doc: str           # 原始文档
    current_doc: str            # 当前修订版本
    document_structure: dict    # 文档结构分析
    missing_items: List[dict]   # 检测到的遗漏项
    revision_history: List      # 修订历史
    current_revision: str       # 当前修订内容
    validation_result: dict     # 验证结果
    iteration: int              # 迭代次数
    max_iterations: int         # 最大迭代次数
    is_complete: bool           # 是否完成
    confidence: float           # 完整性置信度
```

## 节点说明

### 1. analyze_structure_node（结构分析）
- **功能**：提取文档大纲和预期框架
- **模型**：Kimi（长文本）
- **输出**：sections, main_arguments, document_type

### 2. detect_missing_node（遗漏检测）
- **功能**：识别逻辑上缺失的内容
- **方法**：基于文档结构的逻辑推理
- **输出**：missing_items, is_complete

### 3. revise_node（生成修订）
- **功能**：为每个遗漏项生成补充内容
- **模型**：Kimi
- **输出**：current_doc, revision_history

### 4. validate_node（验证）
- **功能**：验证修订后的完整性
- **模型**：Deepseek
- **输出**：is_complete, confidence

## 递归逻辑

```python
if is_complete or iteration >= max_iterations:
    结束流程
else:
    继续检测遗漏
```

## 使用示例

```python
from app.agents.workflows import create_recursive_revision_graph

revision_graph = create_recursive_revision_graph()

result = await revision_graph.ainvoke({
    "original_doc": "...",
    "current_doc": "...",
    "iteration": 0,
    "max_iterations": 5
})

print(result["current_doc"])
print(f"置信度: {result['confidence']}")
print(f"修订次数: {len(result['revision_history'])}")
```

## API端点

- `POST /api/v1/revision/invoke` - 同步调用
- `POST /api/v1/revision/stream` - 流式调用（SSE）
