# AGENTS.md

This file provides guidance to Codex when working with this repository. It is generated from the current code layout and should be kept aligned with real files, routes, and workflows.

## Project rules

- 当前项目阶段优先追求简洁、正确、统一的实现，不默认为了兼容性保留旧逻辑。
- 对自然语言中大量可变、可由模型结合上下文推理的语义，优先向模型提供可信上下文、明确规则、少量示例和结构化输出要求，代码侧只保留通用校验；不要用持续扩张的关键词、正则或条件分支模拟语义理解。安全、权限、金额口径、协议约束及其他必须确定执行的规则仍由代码负责。
- 修改代码时，应基于当前代码事实直接收敛到最终方案，避免无依据的 fallback、双路径、弱回退、模糊兜底或“过渡性兼容”写法。
- 只有在以下情况才考虑兼容处理：
  - 用户明确要求兼容旧行为；
  - 能从当前代码、数据或调用链中证明兼容约束真实存在；
  - 外部调用方已经明确依赖旧逻辑。
- 如果某种状态按当前实现本不应出现，应优先显式暴露问题，而不是静默兼容。
- 小范围文案、提示词、规则收口等不涉及行为变化的修改，不需要每次都额外编写测试脚本；只有重大改造、行为变化、数据流改动或回归风险较高时才补测试。

- 中文日志、中文注释、中文文档使用 UTF-8 编写；PowerShell 读取和写入中文文件时也要显式使用 UTF-8。

- 不需要跑构建，除非用户明确要求。
- 遇见需求不清楚、实现路径有歧义、代码现状与需求冲突，或发现文档和代码不一致时，先向用户确认，不要直接按假设执行。
- 中文日志、中文注释、中文文档使用 UTF-8 编写；如果发现现有中文乱码，先说明编码问题，不要盲目批量重写。
- 当前仓库以代码为准，文档只作为线索；不要把代码中不存在的功能写成已实现功能。
- 后端使用 `uv` 管理依赖和运行命令。
- 前端使用 `pnpm`，不要改用 `npm` 或生成 `package-lock.json`。
- 只在用户明确要求时运行数据库迁移、Docker 部署、构建、批量重建索引、批量删除或发布相关命令。
- 修改后端 API、SSE 事件、LangGraph 工作流时，同时检查前端调用方和 `frontend/src/shared/lib/stream/sse.ts` 的兼容性。

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

The root `Makefile` mirrors some commands and uses `pnpm` for frontend commands.

### Docker / infrastructure

- Start the stack: `docker-compose up -d`
- Stop the stack: `docker-compose down`
- Compose services currently include PostgreSQL with pgvector, Redis, reranker, backend API, backend worker, and frontend.
- Production compose also includes nginx.

## Repository layout

This is a two-app monorepo:

- `backend/`: FastAPI backend with LangGraph, SQLAlchemy, PostgreSQL/pgvector, Redis/Dramatiq background indexing, document parsing, retrieval, and assistant chat services.
- `frontend/`: Vue 3 + Vite admin frontend with embedded assistant surface.
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
- `/api/v1/admin/qa`: admin QA preview, logs, and review operations.
- `/api/v1/integration/bootstrap`: business-backend credential exchange for Agent Loader bootstrap.
- `/api/v1/widget`: token-protected Web Component bootstrap, chat, history, and feedback APIs.
- `/api/v1/assistants`: assistant profile CRUD, reorder, bulk action, preview, and model options.
- `/api/v1/documents`: upload/import, list/detail, content update, versions, indexing, review, publish/unpublish, and delete operations.
- `/api/v1/document-categories`: document category CRUD.
- `/api/v1/teams`: team and team member CRUD.
- `/api/v1/products`: product CRUD.
- `/api/v1/projects`: project and project-app CRUD.
- `/api/v1/users`: admin user management.
- `/api/v1/content-risk`: content-risk rule library CRUD, rule CRUD, and test check.
- `/api/v1/knowledge-bases`: knowledge-base CRUD.
- `/api/v1/evaluations`: evaluation dataset, case, run, and report management.
- `/mcp`: remote Streamable HTTP MCP endpoint exposing the app-scoped `agent_chat` tool.
- `/api/v1/agent-integrations`: tool provider management, tool synchronization/publishing, per-app grants, invocation audit, and project-app access credentials.
- health routes are registered without a versioned prefix tag in the router and also exist on the root app.

Application/service layer anchors:

- `backend/app/application/agent/input_builder.py`: defines the transport-neutral run request and prepares trusted graph input.
- `backend/app/application/agent/runner.py`: isolates LangGraph invoke/stream execution from product use cases.
- `backend/app/application/agent/run_service.py`: orchestrates one Agent run, including safety and persistence.
- `backend/app/application/agent/run_recorder.py`: persists completed turns and refreshes conversation summaries.
- `backend/app/application/agent/run_trace.py`: builds structured run diagnostics and retrieval review logs without persistence.
- `backend/app/application/agent/conversation_service.py`: queries and deletes persisted Agent conversations.
- `backend/app/application/agent/embedded_service.py`: orchestrates the production embedded-agent use case.
- `backend/app/application/assistant_service.py`: assistant profile operations and assistant preview support.
- `backend/app/application/document_service.py`: document lifecycle, content/version operations, review/publish transitions, and indexing triggers.
- `backend/app/application/indexing_service.py`: indexing job orchestration.
- `backend/app/application/project_service.py`: project and project app operations.
- `backend/app/application/integration_bootstrap_service.py`: validates app credentials and issues Loader bootstrap payloads.
- `backend/app/application/product_service.py`: product CRUD and team-scoped product listing.
- `backend/app/application/remote_mcp_service.py`: validates ProjectApp credentials, resolves the bound application context, maps MCP sessions, and invokes the main Agent.
- `backend/app/application/business_operations/*`: whitelisted business data operation boundary for agent-triggered business data queries or actions. The current implementation exposes product search through a controlled registry/service/mock gateway.
- `backend/app/application/agent_tool_catalog_service.py`: tool provider management, discovery, synchronization, publishing, grants, and invocation queries.
- `backend/app/application/agent_tool_execution_service.py`: governed tool validation, provider execution, and redacted invocation audit.
- `backend/app/application/agent/sse_events.py`: SSE event envelope helpers.
- `backend/app/application/agent/workflow_meta.py`: backend-authoritative node labels and display stage metadata for streamed UI.

Domain services and repositories:

- `backend/app/services/kb_text_retrieval.py`: text retrieval orchestration, reranking integration, empty/no-hit handling, and context assembly.
- `backend/app/services/document_indexer.py`: document chunking, embedding, and index writes.
- `backend/app/services/semantic_chunk.py`: semantic chunking.
- `backend/app/services/vector_store.py`: pgvector/vector search access.
- `backend/app/services/reranker.py`: reranker integration.
- `backend/app/services/chat_memory.py`: chat session/message persistence.
- `backend/app/services/content_risk_detection_service.py`: content-risk rule matching for query and answer interception.
- `backend/app/services/tool_providers/*`: protocol-neutral provider gateway plus business HTTP and MCP HTTP adapters.
- `backend/app/services/kb_graph_retrieval.py` and related graph services: graph-based retrieval, summary, indexing, and cleanup helpers.
- `backend/app/repositories/*`: database access layer for users, teams, documents, knowledge bases, projects, assistants, chat logs, index jobs, categories, and content-risk rules.

Core data models currently include:

- `User`, `Team`, `TeamMember`
- `KnowledgeBase`, `KnowledgeBaseMember`
- `DocumentCategory`, `Document`, `DocumentChunk`, `Embedding`
- `IndexJob`, `IndexJobDocument`
- `AssistantProfile`
- `Product`, `Project`, `ProjectApp`
- `ToolProvider`, `AgentTool`, `AgentAppToolGrant`, `AgentToolInvocation`
- `ChatSession`, `ChatMessage`, `KbChatLog`, `ContentRiskLog`
- `ContentRiskLibrary`, `ContentRiskRule`

## Agent workflow system

The current graph registry is `backend/app/agents/runtime/factory.py`.

Registered workflows:

- `agent`: top-level workflow defined by `backend/app/agents/main/graph.py`; path is `route -> respond` for direct responses, or `route -> plan -> execute -> aggregate -> respond` for delegated execution.
- `knowledge_qa`: reusable single-goal knowledge-base QA subgraph defined by `backend/app/agents/knowledge_qa/graph.py`; the top-level `agent` plan owns multi-goal decomposition and may execute up to three independent `knowledge_qa` steps in parallel. Each subgraph follows `plan_query -> plan_retrieval -> retrieve_knowledge -> compose_result`, generates multiple retrieval expressions for only its assigned goal, and allows at most one feedback-driven query rewrite when evidence auditing misses the goal. If that retry produces no executable new query, `plan_query` exits directly to `compose_result`.
- `business_ops`: controlled read-only business data operation subgraph defined by `backend/app/agents/business_ops/graph.py`; it performs up to three sequential tool calls, loops from `execute_operation` back to `analyze_request` only when another call is required, and retains one optional parameter-correction retry per call.
- `backend/langgraph.json` currently exposes `agent` and `knowledge_qa` for LangGraph tooling. `business_ops` is registered in the runtime factory and executed as a subgraph through `agent`.

`backend/tests/unit/test_workflow_registry_consistency.py` guards workflow documentation metadata: every compiled graph node must match its `GraphDefinition.node_ids` entry and `application/agent/workflow_meta.py` metadata, while every `backend/langgraph.json` graph entry must point to the registered factory. Update these declarations together whenever a graph node changes.

<!-- workflow-node-ids:start -->
- `agent` nodes: `route`, `plan`, `execute`, `aggregate`, `respond`
- `knowledge_qa` nodes: `plan_query`, `plan_retrieval`, `retrieve_knowledge`, `compose_result`
- `business_ops` nodes: `analyze_request`, `match_operation`, `execute_operation`, `replan_operation_params`, `compose_result`
<!-- workflow-node-ids:end -->

Important workflow files:

- `backend/app/agents/main/state.py`: top-level Agent input and state contracts.
- `backend/app/agents/main/nodes/*`: top-level routing, planning, execution, aggregation, and response nodes.
- `backend/app/agents/knowledge_qa/state.py`: knowledge QA subgraph state contract.
- `backend/app/agents/business_ops/state.py`: business data operation subgraph state contract.
- `backend/app/agents/business_ops/decision.py`: tool-candidate serialization, LLM decisions, normalization, and parameter correction.
- `backend/app/agents/business_ops/nodes.py`: business operation node implementations and routing decisions.
- `backend/app/agents/main/intent.py`: top-level intent classification and fallback rules.
- `backend/app/agents/knowledge_qa/query_plan.py`: single-goal structured query planning that preserves the assigned goal and generates up to three semantic queries plus three exact lexical phrases.
- `backend/app/agents/knowledge_qa/nodes/plan_retrieval.py`: knowledge retrieval planning.
- `backend/app/agents/knowledge_qa/nodes/retrieve.py`: single-goal text retrieval, accumulated evidence auditing, one optional rewrite retry, and compact retrieval result assembly. Child-chunk RRF/reranking and parent-window expansion are owned by `backend/app/services/kb_text_retrieval.py`.
- `backend/app/agents/main/nodes/respond.py`: top-level final answer generation and streamed token output.
- `backend/app/agents/main/prompt.py`: top-level page-context prompt formatting.
- `backend/app/agents/common/*`: shared retrieval, JSON LLM, document analysis, and streaming helpers.

The chat application service always uses the top-level `agent` workflow. Do not reintroduce a configurable workflow selector unless there is a verified runtime need and a tested caller contract.

Workflow display metadata is backend-authoritative. Backend SSE events should provide `display_stages`, `display_stage`, `display_title`, `activity_text`, `workflow_id`, `node_id`, and `node_name` through `backend/app/application/agent/workflow_meta.py` and node activity events; frontend code should consume those fields instead of maintaining local workflow or node label maps.

When changing streamed chat behavior, keep backend events compatible with the frontend SSE parser in `frontend/src/shared/lib/stream/sse.ts` and reducer in `frontend/src/shared/lib/stream/workflowRun.ts`.

## Retrieval and document pipeline

The implemented knowledge pipeline is:

`knowledge base -> document/category/version/status -> document chunks -> embeddings -> retrieval context -> KB chat answer/log`

Relevant pieces:

- Document APIs upload/import/update/version/review/publish/unpublish content.
- Index jobs are persisted through `IndexJob` / `IndexJobDocument`.
- Background indexing uses `backend/app/workers/indexing_tasks.py` and `backend/app/workers/broker.py`.
- Retrieval respects visible ask document statuses and live/current document version behavior from `backend/app/services/document_lifecycle.py`.
- Content-risk checks are applied to chat queries and generated answers.

## Frontend architecture

Frontend entry points:

- `frontend/src/main.ts`: Vue app bootstrap.
- `frontend/src/router/index.ts`: route definitions and auth guard registration.
- `frontend/src/app/layouts/AdminLayout.vue`: authenticated admin shell.
- `frontend/src/app/layouts/AuthLayout.vue`: login shell.
- `frontend/src/agent-loader/loader.ts`: fixed CDN Loader and the public `EnterpriseAgent` lifecycle API.
- `frontend/src/widget/`: CDN-delivered Web Component chat runtime.
- `frontend/vite.loader.config.ts` and `frontend/vite.widget.config.ts`: immutable Loader and exact-version Widget asset builds.

Admin pages currently present:

- `/dashboard`: admin dashboard placeholder.
- `/projects`: product/project management entry.
- `/projects/:projectId/apps`: project app list.
- `/projects/:projectId/apps/new`: create project app.
- `/projects/:projectId/apps/:appId`: project app detail.
- `/knowledge-bases`: knowledge-base management.
- `/knowledge-bases/:knowledgeBaseId`: knowledge-base detail/document list.
- `/knowledge-bases/:knowledgeBaseId/documents/:documentId`: document detail.
- `/assistants`: assistant management.
- `/assistants/new`: create assistant.
- `/assistants/:assistantId`: assistant detail.
- `/qa-logs`: question-answer log review.
- `/organizations`: team management.
- `/users`: user management.
- `/content-risk/libraries`: global content-risk rule library.
- `/content-risk/logs`: content-risk decision logs.

Frontend integration anchors:

- `frontend/src/shared/api/http.ts`: Axios wrapper, bearer auth, and normalized API errors.
- `frontend/src/shared/api/*`: admin API integrations.
- `frontend/src/shared/lib/stream/sse.ts`: manual SSE parsing over fetch streams; the app does not use `EventSource`.
- `frontend/src/shared/lib/stream/workflowRun.ts`: workflow progress reducer; display names and stage plans should come from backend SSE metadata.

Auth and role helpers:

- `frontend/src/stores/auth.ts`: restores/checks current auth session.
- `frontend/src/shared/auth/session.ts`: token/session storage helpers.
- `frontend/src/shared/auth/roles.ts`: admin access and role utilities.

## Current product surfaces

Only describe these as existing product surfaces unless code changes add more:

- User login and session restoration.
- CDN Loader and Web Component Widget integration with business-owned identity and final authorization.
- Assistant-routed business data operations through governed, published, per-app Agent tools supplied by registered tool providers.
- Admin tool provider management, synchronization, publishing, per-app tool grants, and invocation audit APIs.
- Admin product, project, and project-app management.
- Admin knowledge-base, document, category, version, indexing, review, and publish management.
- Admin assistant profile management and preview/testing.
- Admin team, member, user, and role management.
- Admin QA log review and feedback flow.
- Content-risk rule library management, rule testing, and query/answer interception.
- Remote Streamable HTTP MCP access through `/mcp`; the only exposed tool is the app-scoped `agent_chat` entrypoint.

## Product / project / app relation

- `Product` is the team-scoped top-level business container.
- `Project` belongs to one `Product`.
- `ProjectApp` belongs to one `Project` and binds one knowledge base, an optional document category, and an optional default assistant.
- Chat sessions, KB chat logs, and content-risk logs persist the `product_id` / `project_id` / `project_app_id` context when that scope exists.

Do not describe `kb_curation`, `suggest_revision`, or `doc_to_prototype` as implemented features unless corresponding code is added back to the repository. They are not registered in the current graph registry or API router.

## Testing notes

- Backend tests are under `backend/tests`.
- There is no frontend test script in `frontend/package.json`.
- Because project instructions say no build is needed, prefer targeted inspection, lint, or backend tests only when they are directly relevant and the user has not forbidden them.

## Git change log summaries

When the user asks to write logs, summarize the Git change area, or convert current changes into log mode:

- First inspect `git status --short`, `git diff --stat`, and `git diff --cached --stat`.
- Distinguish staged, unstaged, and untracked changes when they differ.
- Read relevant diffs or current files before describing the purpose of a change.
- Output a numbered list.
- Each item must use the format `1. 工作项名称：作用描述`.
- The work item name should summarize the change theme.
- The description must explain the effect or purpose of the change, not only list filenames.
- Prefer grouping by feature or workflow instead of listing every changed file.
- Include verification as a numbered item when tests, lint, or build commands were run.
- If no verification was run, explicitly include that no verification was run.
- Do not claim unverified behavior as completed.
- Do not attribute existing user changes to Codex unless the conversation clearly shows Codex made them.

## Documentation maintenance

When updating this file:

- Verify route claims against `backend/app/api/v1/router.py` and endpoint files.
- Verify workflow claims against `backend/app/agents/runtime/factory.py` and `backend/langgraph.json`.
- Verify frontend route claims against `frontend/src/router/index.ts`.
- Keep commands consistent with `backend/pyproject.toml`, `frontend/package.json`, `docker-compose.yml`, and the lockfiles.


### 命名

- Python 文件、函数、变量统一使用 `snake_case`；类、Schema、Service、Repository 使用 `PascalCase`；常量使用全大写下划线。
- TypeScript/React 组件、类型、接口、枚举使用 `PascalCase`；函数、变量、hook 使用 `camelCase`；hook 必须以 `use` 开头。
- 布尔命名必须体现判断语义，优先使用 `is_`、`has_`、`can_`、`should_` 或 `is`、`has`、`can`、`should` 前缀。
- 命名优先表达业务含义，避免新增含糊命名和随意缩写；已有核心缩写如 `kb` 可以沿用，但不要继续扩散新的自定义缩写。

### 分层

- 后端遵循 `api -> application -> services -> repositories` 分层：`api` 只处理请求响应，`application` 负责编排用例流程，`services` 提供可复用领域能力，`repositories` 只负责数据访问。
- 前端遵循 `src/app / src/modules / src/shared / src/stores` 分层：页面负责装配，组件负责展示，组合式函数负责状态与交互编排，接口请求统一收敛到 `src/shared/api`。
- 新代码优先放入现有层级，不要为单次需求随意新增目录类别。
- 如果一个文件同时承担接口编排、领域能力和数据访问三种职责，应优先拆分，而不是继续叠加。


### 注释

- 注释只解释原因、约束、兼容性和边界，不解释表面动作。
- 默认少注释；中文注释必须使用 UTF-8，并与代码保持同步。
- 禁止新增“设置变量”“发送请求”之类的废话注释，也不要保留“先这样，后面再改”这类无结论注释。

### 前端写法

- 页面文件和业务组件不要直接散落裸 `fetch`；接口调用统一通过 `frontend/src/shared/api` 封装。
- 展示组件优先保持“输入 props，输出 UI”，复杂交互和流程状态优先下沉到 composable 或 store。
- 不要新增“万能组件”或没有拆分计划的巨型 composable；当组件同时承担请求、复杂状态、数据转换和渲染职责时，应主动拆分。

### 后端写法

- 路由层保持薄，避免在 endpoint 中直接写主业务流程、复杂查询拼装或跨服务编排。
- `application service` 面向一个用例组织流程，`domain service` 面向一种能力提供复用，不要混用职责。
- `repository` 不承载业务决策；如果代码在“编排一次流程”和“提供一种能力”之间摇摆，前者放 `application`，后者放 `services`。
- 不需要写测试。

### 自检

- 新增或修改代码前，先判断这段代码属于哪一层、是否沿用了该层现有模式、命名是否体现业务含义。
- 如果发现当前的方案不合理，或者有更好更合理的方案，可以提出来由用户确认。
