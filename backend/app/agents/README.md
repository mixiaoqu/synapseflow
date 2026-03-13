# Agents目录结构说明

## 📁 目录组织

```
agents/
├── graphs/              # 图定义（只包含图结构）⭐
│   ├── __init__.py
│   ├── README.md
│   ├── qa_graph.py                 # 待创建
│   ├── revision_graph.py           # 待创建
│   └── prototype_graph.py          # 待创建
│
├── states/              # 状态定义（TypedDict）⭐
│   ├── __init__.py
│   ├── README.md
│   ├── qa_state.py                 # 待创建
│   ├── revision_state.py           # 待创建
│   └── prototype_state.py          # 待创建
│
├── nodes/               # 节点函数（按功能分类）⭐
│   ├── __init__.py
│   ├── README.md
│   ├── retrieval/                  # 检索节点
│   │   ├── __init__.py
│   │   ├── vector_search.py        # 待创建
│   │   └── query_rewrite.py        # 待创建
│   ├── generation/                 # 生成节点
│   │   ├── __init__.py
│   │   ├── answer_gen.py           # 待创建
│   │   ├── content_gen.py          # 待创建
│   │   └── code_gen.py             # 待创建
│   ├── evaluation/                 # 评估节点
│   │   ├── __init__.py
│   │   ├── quality_eval.py         # 待创建
│   │   └── completeness_eval.py    # 待创建
│   └── validation/                 # 验证节点
│       ├── __init__.py
│       ├── html_validator.py       # 待创建
│       └── syntax_validator.py     # 待创建
│
├── workflows/           # 完整工作流（当前实现）✅
│   ├── __init__.py
│   ├── iterative_qa.py             # 场景1：迭代问答
│   ├── recursive_revision.py       # 场景2：递归修订
│   └── doc_to_prototype.py         # 场景3：文档转原型
│
├── tools/               # 智能体工具（ReAct模式）⭐
│   ├── __init__.py
│   ├── search_tool.py              # 待创建
│   ├── calculator_tool.py          # 待创建
│   └── web_tool.py                 # 待创建
│
├── prompts/             # 提示词模板⭐
│   ├── __init__.py
│   ├── qa_prompts.py               # 待创建
│   ├── revision_prompts.py         # 待创建
│   └── prototype_prompts.py        # 待创建
│
└── utils/               # 辅助工具函数✅
    ├── __init__.py
    └── state.py                    # 临时：状态定义（未来迁移到states/）
```

## 🎯 两种开发模式

### 模式A：当前实现（workflows/）✅

**特点：一体化**
- 图定义、节点、状态都在一个文件中
- 适合快速开发和原型验证
- 当前三大场景都采用此模式

**文件示例：**
```python
# workflows/iterative_qa.py
# 包含：状态定义 + 节点函数 + 图构建
class IterativeQAState(TypedDict): ...
async def retrieve_node(state): ...
async def answer_node(state): ...
def create_iterative_qa_graph(): ...
```

### 模式B：分离式（graphs/ + nodes/ + states/）⭐

**特点：模块化**
- 图、节点、状态分离存放
- 节点可跨图复用
- 适合大型项目和团队协作

**文件示例：**
```python
# states/qa_state.py
class QAState(TypedDict): ...

# nodes/retrieval/vector_search.py
async def retrieve_node(state: QAState): ...

# nodes/generation/answer_gen.py
async def answer_node(state: QAState): ...

# graphs/qa_graph.py
from app.agents.states.qa_state import QAState
from app.agents.nodes.retrieval import retrieve_node
from app.agents.nodes.generation import answer_node

def create_qa_graph():
    workflow = StateGraph(QAState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("answer", answer_node)
    ...
```

## 🔄 迁移路径

**当前状态：** 使用 `workflows/` 一体化模式

**未来可选：** 逐步迁移到分离式
1. 将状态定义移到 `states/`
2. 将节点函数移到 `nodes/` 分类子目录
3. 在 `graphs/` 中重新组织图定义
4. 保持 `workflows/` 向后兼容

## 📝 最佳实践

### 何时使用workflows/
- ✅ 快速开发原型
- ✅ 场景简单（3-5个节点）
- ✅ 节点不需要复用

### 何时使用graphs/ + nodes/
- ✅ 项目成熟期
- ✅ 节点需要跨图复用
- ✅ 团队协作开发
- ✅ 需要单独测试节点

## 🎓 学习资源

- 查看 `graphs/README.md` 了解图定义规范
- 查看 `states/README.md` 了解状态定义规范
- 查看 `nodes/README.md` 了解节点函数规范
- 查看 `workflows/*.py` 学习当前实现
