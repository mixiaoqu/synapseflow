# LangChain RAG 知识库 Backend

当前后端只对两类前端界面提供支撑：

- `/ask` 用户问答界面
- `/admin` 后台管理界面

## 开发命令

### 安装依赖

```bash
uv sync --all-extras
```

### 启动服务

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### 代码检查

```bash
uv run ruff check app tests
uv run black app tests
uv run mypy app
```

### 运行测试

```bash
uv run pytest
```

## 当前公开路由

- `health`
- `auth`
- `ask`
- `admin/qa`
- `assistants`
- `documents`
- `document-categories`
- `knowledge-bases`
- `teams`
- `users`
- `content-risk`

## 关键代码位置

- 应用入口：[app/main.py](app/main.py)
- API 路由汇总：[app/api/v1/router.py](app/api/v1/router.py)
- 问答接口：[app/api/v1/endpoints/ask.py](app/api/v1/endpoints/ask.py)
- Agent 对话编排服务：[app/application/agent_chat_service.py](app/application/agent_chat_service.py)
- 文档管理接口：[app/api/v1/endpoints/documents.py](app/api/v1/endpoints/documents.py)
- 文档索引服务：[app/services/document_indexer.py](app/services/document_indexer.py)
- 知识库文本检索服务：[app/services/kb_text_retrieval.py](app/services/kb_text_retrieval.py)
- 内容风控规则库接口：[app/api/v1/endpoints/content_risk_libraries.py](app/api/v1/endpoints/content_risk_libraries.py)
- 内容风控检测服务：[app/services/content_risk_detection_service.py](app/services/content_risk_detection_service.py)

## 请求流转

### 问答链路
`/api/v1/ask/*` → `agent_chat_service.py` → 顶层 Agent 路由与执行 → SSE 或同步响应

### 管理链路
`/api/v1/admin/qa/*` → 问答日志仓储与预览调用 → 后台质检界面

### 文档链路
`/api/v1/documents/*` → 文档生命周期/索引服务 → PostgreSQL + pgvector

## 维护约束

- 新增后端能力前，先确认是否真的需要新的公开路由组。
- 如果只是后台内部能力，优先复用现有 `ask`、`admin/qa`、`documents`、`knowledge-bases` 体系。
- 任何流式接口变更都要保持与 `frontend/src/shared/lib/stream/sse.ts` 兼容。
