# States目录

## 用途

存放LangGraph工作流的状态定义。

## 设计原则

- 每个工作流一个状态文件
- 使用`TypedDict`定义状态结构
- 包含详细的字段注释
- 使用类型注解

## 文件命名规范

- `qa_state.py` - 问答状态
- `revision_state.py` - 修订状态
- `prototype_state.py` - 原型状态

## 示例代码

```python
# states/qa_state.py
from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages


class QAState(TypedDict):
    """迭代问答的状态定义"""
    
    # 对话相关
    messages: Annotated[List, add_messages]  # 对话历史
    query: str                               # 用户问题
    
    # 检索相关
    retrieved_docs: List[dict]               # 检索到的文档
    context: str                             # 拼接的上下文
    
    # 生成相关
    answer: str                              # 生成的答案
    confidence_score: float                  # 答案置信度(0-1)
    
    # 迭代控制
    iteration: int                           # 当前迭代次数
    max_iterations: int                      # 最大迭代次数
    should_continue: bool                    # 是否继续迭代
```

## 当前状态

目前状态定义在 `utils/state.py` 中，未来可以拆分到独立文件。
