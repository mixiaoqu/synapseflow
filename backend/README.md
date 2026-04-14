# SynapseFlow Backend

基于FastAPI和LangGraph的后端服务

## 开发指南

### 安装依赖

```bash
# 使用uv安装
uv sync

# 安装开发依赖
uv sync --all-extras
```

### 启动服务

```bash
# 开发模式
uv run uvicorn app.main:app --reload

# 生产模式
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/unit/test_agents/

# 生成覆盖率报告
uv run pytest --cov=app --cov-report=html
```

### 代码格式化

```bash
# Black格式化
uv run black app/

# Ruff检查
uv run ruff check app/

# 类型检查
uv run mypy app/
```

### 数据库迁移

```bash
# 创建迁移
uv run alembic revision --autogenerate -m "描述"

# 应用迁移
uv run alembic upgrade head

# 回滚迁移
uv run alembic downgrade -1
```

## 项目结构

```
app/
├── agents/          # LangGraph智能体
│   ├── nodes/      # 节点函数
│   ├── workflows/  # 工作流定义
│   └── utils/      # 工具函数
├── api/            # API路由
│   └── v1/         # API版本1
├── core/           # 核心配置
│   └── llm/        # LLM管理
├── models/         # 数据模型
│   ├── domain/     # 领域模型
│   └── schemas/    # Pydantic Schema
├── db/             # 数据库
│   ├── models/     # ORM模型
│   └── repositories/
├── services/       # 业务逻辑
└── main.py         # 应用入口
```

## 三大智能体场景

### 1. 迭代问答（Iterative Q&A）
- 文件：`app/agents/workflows/iterative_qa.py`
- 端点：`POST /api/v1/kb-curation/invoke`
- 流程：检索 → 生成答案 → 评估质量 → 循环优化

### 2. 文档修订（Suggest Revision）
- 文件：`app/agents/graphs/suggest_revision_graph.py`
- 端点：`POST /api/v1/revision/suggest`
- 流程：解析建议 → 执行修订 → 判断遗漏

### 3. 文档转原型（Doc-to-Prototype）
- 文件：`app/agents/workflows/doc_to_prototype.py`
- 端点：`POST /api/v1/prototype/generate`
- 流程：提取需求 → 设计组件 → 生成代码 → 验证预览

## 环境变量

参考 `.env.example` 文件配置必需的环境变量：

- `DEEPSEEK_API_KEY` - Deepseek API密钥
- `KIMI_API_KEY` - Kimi API密钥
- `DATABASE_URL` - 数据库连接字符串
- `SECRET_KEY` - JWT密钥

## API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
