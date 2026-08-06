# SynapseFlow 知识库与嵌入助手平台

当前仓库收口为三个主要应用/工具：

- `backend/`：FastAPI + LangGraph 后端服务，同时提供面向编辑器/客户端的远程 Streamable HTTP MCP 入口。
- `frontend/`：Vue 3 + Vite 管理后台前端。

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
├─ frontend/     Vue 3 管理后台、Agent Loader 与 Widget
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
- 业务端 Agent Widget：`frontend/src/widget`
- CDN 接入 Loader：`frontend/src/agent-loader`
- API 封装：`frontend/src/shared/api`

### 后端保留能力

- 鉴权与用户体系：`/api/v1/auth`
- 后台问答质检：`/api/v1/admin/qa`
- 业务端 Agent Widget：`/api/v1/widget`
- 文档管理：`/api/v1/documents`
- 文档分类：`/api/v1/document-categories`
- 知识库管理：`/api/v1/knowledge-bases`
- 助手配置：`/api/v1/assistants`
- 团队、用户、产品、项目/应用管理：`/api/v1/teams`、`/api/v1/users`、`/api/v1/products`、`/api/v1/projects`
- 内容风控规则库、规则测试和判定日志：`/api/v1/content-risk`
- 远程 MCP Agent 入口：`/mcp`

### MCP 工具边界

远程 MCP 使用 Streamable HTTP，仅注册一个 `agent_chat(message)` 工具。请求使用
`ProjectAppAccessCredential` 生成的 Bearer 凭据，服务端根据凭证解析当前 `ProjectApp`，第一版仅通过其绑定的知识库调用 `knowledge_qa`。

TRAE 配置示例：

```json
{
  "mcpServers": {
    "synapseflow-agent": {
      "url": "https://your-domain.example/mcp",
      "headers": {
        "Authorization": "Bearer <client_id>.<client_secret>"
      }
    }
  }
}
```

### 产品 / 项目 / 应用关系

- `Product` 属于一个团队，是业务产品容器。
- `Project` 属于一个 `Product`。
- `ProjectApp` 属于一个 `Project`，并绑定一个知识库、可选文档分类和可选默认助手。
- 嵌入助手、MCP、问答日志和风控日志会在可用时携带 `product_id`、`project_id`、`project_app_id` 上下文。

### 当前图谱能力

`backend/langgraph.json` 当前暴露顶层 `agent` 与 `knowledge_qa`。注册位置是 `backend/app/agents/runtime/factory.py`。

```text
agent: route -> respond
       route -> plan -> execute -> aggregate -> respond

knowledge_qa: plan_query -> plan_retrieval -> retrieve_knowledge -> compose_result
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

## 当前公开 API 组

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/widget/bootstrap`
- `POST /api/v1/widget/stream`
- `GET /api/v1/widget/sessions`
- `GET /api/v1/widget/sessions/{session_id}`
- `DELETE /api/v1/widget/sessions/{session_id}`
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
- `POST|GET|DELETE /mcp`

完整接口以 `http://localhost:8000/api/v1/docs` 为准。

## 开发建议

- 前端统一在 `frontend/` 下开发。
- 前端依赖和脚本统一使用 `pnpm`。
- 后端依赖和命令统一使用 `uv`。
- 业务实现优先放在现有模块目录或服务层，避免新增重复入口。
