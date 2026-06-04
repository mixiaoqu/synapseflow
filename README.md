# LangChain RAG 知识库

当前仓库收口为两个主要应用：

- `backend/`：FastAPI + LangGraph 后端服务。
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

## 仓库结构

```text
langchain-rag-kb/
├─ backend/    FastAPI + LangGraph 服务
├─ frontend/   Vue 3 管理后台
├─ docker/     Docker 构建配置
└─ README.md
```

## 当前模块边界

### 前端保留模块

- 登录与鉴权守卫：`frontend/src/modules/auth`、`frontend/src/app/guards`
- 后台壳层与导航：`frontend/src/app/layouts`、`frontend/src/app/navigation`
- 知识库、项目、助手、团队、用户管理：`frontend/src/modules/*`
- 内容风控中心：`frontend/src/modules/content-risk`
- API 封装：`frontend/src/shared/api`

### 后端保留能力

- 鉴权与用户体系：`/api/v1/auth`
- 问答接口：`/api/v1/ask`
- 后台问答质检：`/api/v1/admin/qa`
- 文档管理：`/api/v1/documents`
- 文档分类：`/api/v1/document-categories`
- 知识库管理：`/api/v1/knowledge-bases`
- 助手配置：`/api/v1/assistants`
- 团队、用户管理：`/api/v1/teams`、`/api/v1/users`
- 内容风控规则库：`/api/v1/content-risk`

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

- `POST /api/v1/ask/invoke`
- `POST /api/v1/ask/stream`
- `GET /api/v1/ask/sessions`
- `GET /api/v1/ask/sessions/{session_id}`
- `DELETE /api/v1/ask/sessions/{session_id}`
- `POST /api/v1/admin/qa/preview`
- `GET /api/v1/admin/qa/logs`
- `GET /api/v1/admin/qa/logs/{log_id}`
- `POST /api/v1/admin/qa/logs/{log_id}/review`
- `GET|POST|PATCH|DELETE /api/v1/content-risk/*`
- `POST /api/v1/documents/*`
- `GET|POST|PATCH|DELETE /api/v1/knowledge-bases/*`

完整接口以 `http://localhost:8000/api/v1/docs` 为准。

## 开发建议

- 前端统一在 `frontend/` 下开发。
- 前端依赖和脚本统一使用 `pnpm`。
- 业务实现优先放在现有模块目录或服务层，避免新增重复入口。
