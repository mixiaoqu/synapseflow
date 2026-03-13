# Graphs目录

## 用途

存放LangGraph工作流图的构建逻辑。

## 设计原则

- **只定义图结构**：节点连接、边、条件路由
- **不实现节点逻辑**：节点函数从`nodes/`目录导入
- **不定义状态**：状态从`states/`目录导入

## 文件命名规范

- `qa_graph.py` - 问答图
- `revision_graph.py` - 修订图
- `prototype_graph.py` - 原型图
- `<场景名>_graph.py` - 其他场景图

## 示例代码结构

```python
# graphs/qa_graph.py
from langgraph.graph import StateGraph, END
from app.agents.states.qa_state import QAState
from app.agents.nodes.retrieval import retrieve_node
from app.agents.nodes.generation import answer_node
from app.agents.nodes.evaluation import evaluate_node


def create_qa_graph():
    """构建问答图"""
    workflow = StateGraph(QAState)
    
    # 添加节点（从nodes导入）
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("evaluate", evaluate_node)
    
    # 定义图结构
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "answer")
    workflow.add_edge("answer", "evaluate")
    
    # 条件路由
    workflow.add_conditional_edges(
        "evaluate",
        route_function,
        {"continue": "retrieve", "end": END}
    )
    
    return workflow.compile()
```

## 当前状态

目前图定义在 `workflows/` 目录中，未来可以迁移到此目录实现更清晰的分离。
