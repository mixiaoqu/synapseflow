# Nodes目录

## 用途

存放LangGraph工作流的节点函数实现。

## 目录组织

按功能类型分类：

- **`retrieval/`** - 检索相关节点（从向量数据库、搜索引擎检索）
- **`generation/`** - 生成相关节点（LLM生成内容、代码、文档）
- **`evaluation/`** - 评估相关节点（质量评估、打分、判断）
- **`validation/`** - 验证相关节点（格式验证、语法检查）

## 设计原则

1. **单一职责**：每个节点函数只做一件事
2. **可复用**：节点可以被多个图使用
3. **无状态**：节点函数本身无状态，只接收state并返回更新
4. **纯函数**：尽可能保持纯函数特性
5. **类型注解**：使用完整的类型提示

## 节点函数规范

```python
# nodes/retrieval/vector_search.py
from typing import Dict, Any


async def retrieve_from_vector_db(state: dict) -> Dict[str, Any]:
    """
    从向量数据库检索相关文档
    
    Args:
        state: 包含query字段的状态
        
    Returns:
        包含retrieved_docs和context的字典
    """
    query = state["query"]
    
    # 检索逻辑
    docs = await vectorstore.search(query, k=5)
    
    # 只返回状态更新
    return {
        "retrieved_docs": docs,
        "context": "\n".join([d.content for d in docs])
    }
```

## 节点命名规范

- 使用动词开头：`retrieve_`, `generate_`, `evaluate_`, `validate_`
- 描述性名称：`retrieve_from_vector_db` 而不是 `retrieve`
- 一致的后缀：`_node` 可选

## 当前状态

节点函数目前在 `workflows/` 文件中实现，未来可以按功能分类迁移到此目录。
