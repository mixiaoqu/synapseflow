# SynapseFlow 知识库与嵌入助手平台

当前仓库收口为三个主要应用/工具：

- `backend/`：FastAPI + LangGraph 后端服务。
- `frontend/`：Vue 3 + Vite 管理后台前端。
- `mcp_server/`：面向编辑器/客户端的只读 MCP stdio 工具服务。

## 技术栈

### Backend

- Python 3.11
- FastAPI
- LangGraph
- PostgreSQL + pgvector
- uv

### Frontend

- Vue 3
- Vue Router 4
- Pinia
- Element Plus
- Tailwind CSS
- Vite
- pnpm

### MCP Server

- TypeScript
- Model Context Protocol SDK
- zod
- pnpm

## 仓库结构

```text
synapseflow/
├─ backend/      FastAPI + LangGraph 服务
├─ frontend/     Vue 3 管理后台与嵌入助手页面
├─ mcp_server/   MCP stdio 工具服务
├─ docker/       Docker 构建配置
├─ deploy/       部署与 nginx 配置
└─ README.md
```

## 当前模块边界

### 前端保留模块

- 登录与鉴权守卫：`frontend/src/modules/auth`、`frontend/src/app/guards`
- 后台壳层与导航：`frontend/src/app/layouts`、`frontend/src/app/navigation`
- 知识库、应用接入、助手、团队、用户管理：`frontend/src/modules/*`
- 问答日志：`frontend/src/modules/qa-logs`
- 内容风控中心：`frontend/src/modules/content-risk`
- 嵌入助手页面：`frontend/src/modules/embed`
- API 封装：`frontend/src/shared/api`

### 后端保留能力

- 鉴权与用户体系：`/api/v1/auth`
- 问答接口：`/api/v1/ask`
- 后台问答质检：`/api/v1/admin/qa`
- 嵌入助手会话与问答：`/api/v1/embed`
- 文档管理：`/api/v1/documents`
- 文档分类：`/api/v1/document-categories`
- 知识库管理：`/api/v1/knowledge-bases`
- 助手配置：`/api/v1/assistants`
- 团队、用户、产品、项目/应用管理：`/api/v1/teams`、`/api/v1/users`、`/api/v1/products`、`/api/v1/projects`
- 内容风控规则库、规则测试和判定日志：`/api/v1/content-risk`
- MCP 只读知识访问：`/api/v1/mcp`

### MCP 工具边界

`mcp_server/` 通过 stdio 注册 3 个工具：

- `resolve_scope`：根据 `product_code`、`project_code`、`app_code` 解析产品/项目/应用范围。
- `search_knowledge`：在已绑定的单个知识库范围内检索片段。
- `answer_knowledge`：复用后端 KB chat 预览能力返回答案和检索证据。

后端 `/api/v1/mcp/bootstrap` 用企业服务 token 换取 MCP scope token；`/scope/resolve`、`/search`、`/answer` 是只读访问入口。

### 产品 / 项目 / 应用关系

- `Product` 属于一个团队，是业务产品容器。
- `Project` 属于一个 `Product`。
- `ProjectApp` 属于一个 `Project`，并绑定一个知识库、可选文档分类和可选默认助手。
- 嵌入助手、MCP、问答日志和风控日志会在可用时携带 `product_id`、`project_id`、`project_app_id` 上下文。

### 当前图谱能力

`backend/langgraph.json` 当前只暴露 `kb_chat`。注册位置是 `backend/app/agents/runtime/factory.py`，实际图谱路径为：

```text
analyze -> rewrite_query -> retrieve -> evaluate -> answer
```

## 快速开始

### 1. 启动基础依赖

```bash
docker compose up -d postgres redis reranker
```

### 2. 启动后端

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

后端默认地址：`http://localhost:8000`

### 3. 启动 worker

```bash
cd backend
uv run dramatiq app.workers.indexing_tasks --processes 1 --threads 1
```

### 4. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端默认地址：`http://localhost:5173`

### 5. 启动 MCP server

```bash
cd mcp_server
pnpm install
pnpm dev
```

MCP server 使用 stdio transport，通常由编辑器或 MCP 客户端拉起；Windows 安装脚本在 `mcp_server/installer/windows/` 下。

## 当前公开 API 组

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/ask/invoke`
- `POST /api/v1/ask/stream`
- `GET /api/v1/ask/sessions`
- `GET /api/v1/ask/sessions/{session_id}`
- `DELETE /api/v1/ask/sessions/{session_id}`
- `POST /api/v1/embed/session`
- `GET /api/v1/embed/assistant/bootstrap`
- `POST /api/v1/embed/assistant/invoke`
- `POST /api/v1/embed/assistant/stream`
- `POST /api/v1/admin/qa/preview`
- `GET /api/v1/admin/qa/logs`
- `GET /api/v1/admin/qa/logs/{log_id}`
- `POST /api/v1/admin/qa/logs/{log_id}/review`
- `GET|POST|PUT|DELETE /api/v1/products/*`
- `GET|POST|PUT|DELETE /api/v1/projects/*`
- `GET|POST|PUT|DELETE /api/v1/projects/{project_id}/apps/*`
- `GET|POST|PUT|DELETE /api/v1/assistants/*`
- `GET|POST|PUT|DELETE /api/v1/documents/*`
- `GET|POST|PUT|DELETE /api/v1/document-categories/*`
- `GET|POST|PUT|DELETE /api/v1/teams/*`
- `GET|POST|PUT|DELETE /api/v1/users/*`
- `GET|POST|PATCH|DELETE /api/v1/content-risk/*`
- `POST /api/v1/documents/*`
- `GET|POST|PATCH|DELETE /api/v1/knowledge-bases/*`
- `POST /api/v1/mcp/bootstrap`
- `POST /api/v1/mcp/scope/resolve`
- `POST /api/v1/mcp/search`
- `POST /api/v1/mcp/answer`

完整接口以 `http://localhost:8000/api/v1/docs` 为准。

## 开发建议

- 前端统一在 `frontend/` 下开发。
- 前端依赖和脚本统一使用 `pnpm`。
- 后端依赖和命令统一使用 `uv`。
- MCP server 依赖和脚本统一使用 `pnpm`。
- 业务实现优先放在现有模块目录或服务层，避免新增重复入口。
