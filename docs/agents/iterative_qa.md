# 迭代问答智能体

## 功能说明

通过多轮迭代优化问答质量，自动评估答案并在质量不足时重新检索。

## 状态定义

```python
class IterativeQAState(TypedDict):
    messages: List              # 对话历史
    query: str                  # 用户问题
    retrieved_docs: List        # 检索到的文档
    context: str                # 拼接的上下文
    answer: str                 # 生成的答案
    confidence_score: float     # 答案置信度（0-1）
    iteration: int              # 当前迭代次数
    max_iterations: int         # 最大迭代次数
    should_continue: bool       # 是否继续迭代
```

## 节点说明

### 1. retrieve_node（检索节点）
- **功能**：从向量数据库检索相关文档
- **输入**：query（用户问题）
- **输出**：retrieved_docs, context
- **优化**：迭代时增加召回数量（k=5→8）

### 2. answer_node（生成答案节点）
- **功能**：使用LLM生成答案
- **模型**：Kimi（长上下文）
- **输入**：context, query
- **输出**：answer

### 3. evaluate_node（评估节点）
- **功能**：评估答案质量
- **模型**：Deepseek（推理）
- **评估维度**：相关性、完整性、准确性
- **输出**：confidence_score, should_continue

## 循环逻辑

```python
if confidence_score < 0.75 and iteration < max_iterations:
    继续迭代（回到检索节点）
else:
    结束流程
```

## 使用示例

```python
from app.agents.workflows import create_iterative_qa_graph

qa_graph = create_iterative_qa_graph()

result = await qa_graph.ainvoke({
    "messages": [],
    "query": "什么是LangGraph？",
    "iteration": 0,
    "max_iterations": 3
})

print(result["answer"])
print(f"置信度: {result['confidence_score']}")
print(f"迭代次数: {result['iteration']}")
```

## API端点

- `POST /api/v1/qa/invoke` - 同步调用
- `POST /api/v1/qa/stream` - 流式调用（SSE）
