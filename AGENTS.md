# AGENTS.md

This file provides guidance to Codex when working with this repository. It is generated from the current code layout and should be kept aligned with real files, routes, and workflows.

## Project rules

- ??????????? UTF-8 ???????????????????? PowerShell ??????????????????????

- 不需要跑构建，除非用户明确要求。
- 遇见需求不清楚、实现路径有歧义、代码现状与需求冲突，或发现文档和代码不一致时，先向用户确认，不要直接按假设执行。
- 中文日志、中文注释、中文文档使用 UTF-8 编写；如果发现现有中文乱码，先说明编码问题，不要盲目批量重写。
- 当前仓库以代码为准，文档只作为线索；不要把代码中不存在的功能写成已实现功能。
- 后端使用 `uv` 管理依赖和运行命令。
- 前端使用 `pnpm`，不要改用 `npm` 或生成 `package-lock.json`。
- 只在用户明确要求时运行数据库迁移、Docker 部署、构建、批量重建索引、批量删除或发布相关命令。
- 修改后端 API、SSE 事件、LangGraph 工作流时，同时检查前端调用方和 `frontend/lib/stream/sse.ts` 的兼容性。

## Common commands

### Backend

- Install backend dependencies: `cd backend && uv sync --all-extras`
- Run the API locally: `cd backend && uv run uvicorn app.main:app --reload`
- Apply migrations: `cd backend && uv run alembic upgrade head`
- Run all backend tests: `cd backend && uv run pytest`
- Run one test file: `cd backend && uv run pytest tests/unit/test_agent_runtime.py -q`
- Run one test case: `cd backend && uv run pytest tests/unit/test_agent_runtime.py::test_name -q`
- Lint backend code: `cd backend && uv run ruff check app tests`
- Format backend code: `cd backend && uv run black app tests`
- Type-check backend code: `cd backend && uv run mypy app`

### Frontend

- Install frontend dependencies: `cd frontend && pnpm install`
- Run the frontend locally: `cd frontend && pnpm dev`
- Lint the frontend: `cd frontend && pnpm lint`
- Build command exists as `cd frontend && pnpm build`, but do not run it unless the user explicitly asks.

The root `Makefile` mirrors some commands, but it currently uses `npm` for frontend commands. Prefer `pnpm` inside `frontend/` because the repo has `pnpm-lock.yaml` and Docker frontend builds use pnpm.

### Docker / infrastructure

- Start the stack: `docker-compose up -d`
- Stop the stack: `docker-compose down`
- Compose services currently include PostgreSQL with pgvector, Redis, reranker, backend API, backend worker, and frontend.
- Production compose also includes nginx.

## Repository layout

This is a two-app monorepo:

- `backend/`: FastAPI backend with LangGraph, SQLAlchemy, PostgreSQL/pgvector, Redis/Dramatiq background indexing, document parsing, retrieval, and assistant chat services.
- `frontend/`: Next.js 15 App Router frontend with admin, end-user ask, and embedded assistant surfaces.
- `docker/`: Dockerfiles for backend, frontend, and reranker.
- `deploy/`: deployment/nginx support files.
- `scripts/`: setup scripts.

## Backend architecture

Backend entry points:

- `backend/app/main.py`: creates the FastAPI app, configures CORS, mounts `/preview`, registers API v1 routes, and exposes root health endpoints.
- `backend/app/api/v1/router.py`: aggregates versioned routers.
- `backend/app/db/models.py`: SQLAlchemy models.
- `backend/app/db/migrations/versions/`: Alembic migrations.
- `backend/app/core/config/`: YAML/settings loading and config schemas.
- `backend/config/*.yaml`: app, model, embedding, rerank, logging, and embed page configuration.

Current API router prefixes:

- `/api/v1/auth`: registration, login, current user.
- `/api/v1/ask`: user knowledge-base chat, chat sessions, feedback.
- `/api/v1/admin/qa`: admin QA preview, logs, and review operations.
- `/api/v1/embed`: embedded assistant session bootstrap/chat APIs.
- `/api/v1/assistants`: assistant profile CRUD, reorder, bulk action, preview, invoke, stream, and model options.
- `/api/v1/documents`: upload/import, list/detail, content update, versions, indexing, review, publish/unpublish, and delete operations.
- `/api/v1/document-categories`: document category CRUD.
- `/api/v1/teams`: team and team member CRUD.
- `/api/v1/projects`: project/app CRUD and embed preview.
- `/api/v1/users`: admin user management.
- `/api/v1/sensitive-words`: sensitive word settings, CRUD, import, and check.
- `/api/v1/knowledge-bases`: knowledge-base CRUD.
- health routes are registered without a versioned prefix tag in the router and also exist on the root app.

Application/service layer anchors:

- `backend/app/application/kb_chat_service.py`: orchestrates user/admin/embed assistant chat, sensitive-word checks, memory persistence, logs, and SSE streaming.
- `backend/app/application/assistant_service.py`: assistant profile operations and assistant preview support.
- `backend/app/application/document_service.py`: document lifecycle, content/version operations, review/publish transitions, and indexing triggers.
- `backend/app/application/indexing_service.py`: indexing job orchestration.
- `backend/app/application/project_service.py`: project and project app operations.
- `backend/app/application/agent_service.py`: base agent context/state helpers.
- `backend/app/application/stream_events.py`: SSE event envelope helpers.
- `backend/app/application/workflow_meta.py`: node labels and workflow metadata for streamed UI.

Domain services and repositories:

- `backend/app/services/kb_retrieval.py`: vector/hybrid retrieval, reranking integration, empty/no-hit handling, and context assembly.
- `backend/app/services/document_indexer.py`: document chunking, embedding, and index writes.
- `backend/app/services/semantic_chunk.py`: semantic chunking.
- `backend/app/services/vector_store.py`: pgvector/vector search access.
- `backend/app/services/reranker.py`: reranker integration.
- `backend/app/services/chat_memory.py`: chat session/message persistence.
- `backend/app/services/sensitive_word_service.py`: sensitive word checks.
- `backend/app/repositories/*`: database access layer for users, teams, documents, knowledge bases, projects, assistants, chat logs, index jobs, categories, and sensitive words.

Core data models currently include:

- `User`, `Team`, `TeamMember`
- `KnowledgeBase`, `KnowledgeBaseMember`
- `DocumentCategory`, `Document`, `DocumentChunk`, `Embedding`
- `IndexJob`, `IndexJobDocument`
- `AssistantProfile`
- `Project`, `ProjectApp`
- `ChatSession`, `ChatMessage`, `KbChatLog`
- `SensitiveWordSetting`, `SensitiveWord`

## Agent workflow system

The current graph registry is `backend/app/agents/runtime/factory.py`.

Registered workflow:

- `kb_chat`: defined by `backend/app/agents/graphs/kb_chat_graph.py`
- Actual graph path: `plan_query -> rewrite_query -> retrieve -> answer`
- `backend/langgraph.json` exposes only `kb_chat`.

Important workflow files:

- `backend/app/agents/states/kb_chat_state.py`: KB chat state shape.
- `backend/app/agents/nodes/kb_chat/plan_query.py`: retrieval planning.
- `backend/app/agents/nodes/kb_chat/rewrite_query.py`: query rewriting.
- `backend/app/agents/nodes/kb_chat/retrieve.py`: retrieval node.
- `backend/app/agents/nodes/kb_chat/generate_answer.py`: answer generation and streamed token output.
- `backend/app/agents/prompts/kb_chat.py`: KB chat prompts.
- `backend/app/agents/common/*`: shared retrieval, JSON LLM, document analysis, and streaming helpers.

When changing streamed chat behavior, keep backend events compatible with the frontend SSE parser in `frontend/lib/stream/sse.ts`.

## Retrieval and document pipeline

The implemented knowledge pipeline is:

`knowledge base -> document/category/version/status -> document chunks -> embeddings -> retrieval context -> KB chat answer/log`

Relevant pieces:

- Document APIs upload/import/update/version/review/publish/unpublish content.
- Index jobs are persisted through `IndexJob` / `IndexJobDocument`.
- Background indexing uses `backend/app/workers/indexing_tasks.py` and `backend/app/workers/broker.py`.
- Retrieval respects visible ask document statuses and live/current document version behavior from `backend/app/services/document_lifecycle.py`.
- Sensitive-word checks are applied to chat queries and document content paths.

## Frontend architecture

Frontend entry points:

- `frontend/app/layout.tsx`: root layout.
- `frontend/app/page.tsx`: root page.
- `frontend/app/(auth)/login/page.tsx`: login page.
- `frontend/app/(user)/layout.tsx`: authenticated user shell.
- `frontend/app/(user)/ask/page.tsx`: end-user assistant/knowledge-base ask page.
- `frontend/app/(admin)/admin/layout.tsx`: authenticated admin shell.
- `frontend/app/embed/assistant/page.tsx`: embedded assistant page.

Admin pages currently present:

- `/admin`: admin workbench.
- `/admin/projects`: project management.
- `/admin/projects/[id]`: project details and app/embed configuration.
- `/admin/documents`: knowledge-base/document management.
- `/admin/documents/[knowledgeBaseId]`: knowledge-base detail/document list.
- `/admin/assistants`: assistant management.
- `/admin/assistants/new`: create assistant.
- `/admin/assistants/[assistantId]/edit`: edit assistant.
- `/admin/teams`: team management.
- `/admin/users`: user management.
- `/admin/review`: document review/publishing queue.
- `/admin/qa-quality`: QA quality/log review.
- `/admin/sensitive-words`: sensitive word management.

Frontend integration anchors:

- `frontend/lib/api/client.ts`: fetch wrapper, bearer auth, JSON, multipart form upload, and `postStream`.
- `frontend/lib/api/endpoints/ask.ts`: end-user ask/session APIs.
- `frontend/lib/api/endpoints/embed.ts`: embedded assistant APIs.
- `frontend/lib/api/assistants.ts`: assistant profile and assistant chat APIs.
- `frontend/lib/api/documents.ts`: document APIs.
- `frontend/lib/api/knowledgeBases.ts`: knowledge-base APIs.
- `frontend/lib/api/teams.ts`, `users.ts`, `sensitiveWords.ts`: admin APIs.
- `frontend/hooks/useAssistantChat.ts`: streamed assistant chat state for the user ask page.
- `frontend/features/embed/hooks/useEmbeddedAssistant.ts`: embedded assistant chat state.
- `frontend/lib/stream/sse.ts`: manual SSE parsing over fetch streams; the app does not use `EventSource`.

Auth and role helpers:

- `frontend/hooks/useAuthSession.ts`: restores/checks current auth session.
- `frontend/lib/auth/session.ts`: token/session storage helpers.
- `frontend/lib/auth/roles.ts`: admin access and role utilities.
- `frontend/components/team-scope/*` and `frontend/components/teams/TeamScopeSwitcher.tsx`: team scope context and switching.

## Current product surfaces

Only describe these as existing product surfaces unless code changes add more:

- User login and session restoration.
- End-user knowledge-base/assistant ask experience with streaming responses and chat history.
- Embedded assistant experience for project apps.
- Admin project and project-app management.
- Admin knowledge-base, document, category, version, indexing, review, and publish management.
- Admin assistant profile management and assistant preview/testing.
- Admin team, member, user, and role management.
- Admin QA log review and feedback flow.
- Sensitive-word configuration, import, checking, and enforcement.

Do not describe `kb_curation`, `suggest_revision`, or `doc_to_prototype` as implemented features unless corresponding code is added back to the repository. They are not registered in the current graph registry or API router.

## Testing notes

- Backend tests are under `backend/tests`.
- There is no frontend test script in `frontend/package.json`.
- Because project instructions say no build is needed, prefer targeted inspection, lint, or backend tests only when they are directly relevant and the user has not forbidden them.

## Documentation maintenance

When updating this file:

- Verify route claims against `backend/app/api/v1/router.py` and endpoint files.
- Verify workflow claims against `backend/app/agents/runtime/factory.py` and `backend/langgraph.json`.
- Verify frontend route claims against `frontend/app`.
- Keep commands consistent with `backend/pyproject.toml`, `frontend/package.json`, `docker-compose.yml`, and the lockfiles.

## 代码风格统一规则

- 本仓库采用“AGENTS.md 定底线，`docs/development/code-style.md` 定细则”的双文档方式统一多人和多 AI 的代码风格。
- 在修改代码前，先阅读与改动范围直接相关的现有实现，优先延续当前文件和当前层级已经存在的风格，不要自行发明新模式。

### 命名

- Python 文件、函数、变量统一使用 `snake_case`；类、Schema、Service、Repository 使用 `PascalCase`；常量使用全大写下划线。
- TypeScript/React 组件、类型、接口、枚举使用 `PascalCase`；函数、变量、hook 使用 `camelCase`；hook 必须以 `use` 开头。
- 布尔命名必须体现判断语义，优先使用 `is_`、`has_`、`can_`、`should_` 或 `is`、`has`、`can`、`should` 前缀。
- 命名优先表达业务含义，避免新增含糊命名和随意缩写；已有核心缩写如 `kb` 可以沿用，但不要继续扩散新的自定义缩写。

### 分层

- 后端遵循 `api -> application -> services -> repositories` 分层：`api` 只处理请求响应，`application` 负责编排用例流程，`services` 提供可复用领域能力，`repositories` 只负责数据访问。
- 前端遵循 `app / components / hooks / lib/api / features` 分层：页面负责装配，组件负责展示，hook 负责状态与交互编排，接口请求统一收敛到 `lib/api`。
- 新代码优先放入现有层级，不要为单次需求随意新增目录类别。
- 如果一个文件同时承担接口编排、领域能力和数据访问三种职责，应优先拆分，而不是继续叠加。

### 注释

- 注释只解释原因、约束、兼容性和边界，不解释表面动作。
- 默认少注释；中文注释必须使用 UTF-8，并与代码保持同步。
- 禁止新增“设置变量”“发送请求”之类的废话注释，也不要保留“先这样，后面再改”这类无结论注释。

### 前端写法

- 页面文件和业务组件不要直接散落裸 `fetch`；接口调用统一通过 `frontend/lib/api` 封装。
- 展示组件优先保持“输入 props，输出 UI”，复杂交互和流程状态优先下沉到 hook。
- 不要新增“万能组件”或没有拆分计划的巨型 hook；当组件同时承担请求、复杂状态、数据转换和渲染职责时，应主动拆分。

### 后端写法

- 路由层保持薄，避免在 endpoint 中直接写主业务流程、复杂查询拼装或跨服务编排。
- `application service` 面向一个用例组织流程，`domain service` 面向一种能力提供复用，不要混用职责。
- `repository` 不承载业务决策；如果代码在“编排一次流程”和“提供一种能力”之间摇摆，前者放 `application`，后者放 `services`。

### 自检

- 新增或修改代码前，先判断这段代码属于哪一层、是否沿用了该层现有模式、命名是否体现业务含义。
- 如需细则、正反例和拆分建议，查看 [docs/development/code-style.md](docs/development/code-style.md)。
