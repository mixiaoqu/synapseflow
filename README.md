# LangChain RAG 知识库

当前仓库已经收口为两个实际产品入口：

- `/ask`：用户问答界面
- `/admin`：后台管理界面

## 技术栈

### Backend
- Python 3.11
- FastAPI
- LangGraph
- PostgreSQL + pgvector
- uv

### Frontend
- Next.js 15 App Router
- React 19
- TypeScript
- Tailwind CSS + shadcn/ui

## 仓库结构

```text
langchain-rag-kb/
├─ backend/    FastAPI + LangGraph 服务
├─ frontend/   Next.js 前端
├─ docker/     Docker 构建配置
└─ README.md
```

## 当前模块边界

### 前端保留模块
- 问答工作台：`frontend/app/page.tsx`、`frontend/app/(user)/ask/*`
- 后台管理：`frontend/app/(admin)/admin/*`
- 文档与知识库管理：`frontend/features/documents/*`
- API 封装：`frontend/lib/api/*`

### 后端保留能力
- 鉴权与用户体系：`/api/v1/auth`
- 问答接口：`/api/v1/ask`
- 后台问答质检：`/api/v1/admin/qa`
- 文档管理：`/api/v1/documents`
- 文档分类：`/api/v1/document-categories`
- 知识库管理：`/api/v1/knowledge-bases`
- 助手配置：`/api/v1/assistants`
- 团队、用户、敏感词：`/api/v1/teams`、`/api/v1/users`、`/api/v1/sensitive-words`

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

前端默认地址：`http://localhost:3000`

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
- `POST /api/v1/documents/*`
- `GET|POST|PATCH|DELETE /api/v1/knowledge-bases/*`

完整接口以 `http://localhost:8000/api/v1/docs` 为准。

## 开发建议

- 页面入口只围绕 `/ask` 与 `/admin` 组织。
- 业务实现优先放在特性目录或服务层。
