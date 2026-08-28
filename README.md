# SynapseFlow 知识库与嵌入助手平台

当前仓库收口为三个主要应用/工具：

- `backend/`：FastAPI + LangGraph 后端服务，同时提供面向编辑器/客户端的远程 Streamable HTTP MCP 入口。
- `frontend/`：Vue 3 + Vite 管理后台前端。

学习与开发入口：[项目分层与依赖速查](ARCHITECTURE.md)。

## 联网搜索（Tavily）

内置 `search_web` 与知识库、业务查询能力并列，由主 Agent 按目标选择。搜索和正文提取是内部步骤，无需在「Agent 集成」创建工具提供方，也无需逐应用授权。

本地在 `backend/.env` 中设置以下配置并重启后端；开发 Compose 挂载该文件。生产 Compose 则在部署所用的环境文件中设置同名变量，重新创建 backend 和 backend-worker：

```dotenv
WEB_SEARCH_ENABLED=true
TAVILY_API_KEY=你的Tavily密钥
```

- 开关默认关闭，或 Key 为空时工具不可见；开启后所有应用（含预览、评测与远程 MCP 主 Agent）均可调用。Key 仅保留在后端。
- 采用 [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search) 和 [Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract) REST 接口，复用现有 `httpx`，无新增依赖或数据库迁移。
- 每次最多搜索 5 条、按返回顺序选择最多 3 个去重后的公开 URL；每页最多返回 8000 字符正文节选。固定 basic 深度；不采用 Tavily 生成的答案，不自动重试付费请求。
- 每个 HTTP 请求总时限 30 秒、响应上限 1 MiB；搜索及批量提取各计 1 次内部操作，另加顶层能力调用 1 次，计入现有 Agent 总预算。不是跨用户费用总额限制，账户额度须在 Tavily 控制台设置。
- 仅自动发送搜索目标与所选 URL，不附带身份、完整对话、页面或业务工具结果。模型生成的搜索词仍可能包含敏感信息，开启前应评估数据出境与使用范围；这不是自动脱敏保障。
- 网页保留真实 URL、标题、抓取时间和可获得的发布日期；抓取时间不代表发布日期。抓取失败的摘要仅作检索线索，不能当作已核验正文，页面也不会写入知识库。
- 联网能力不等于医疗知识库。药品用法用量必须核对具体名称、厂家、剂型、规格和权威说明书；当前实现没有药品专用来源库或临床准确性保证。

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
`ProjectAppAccessCredential` 生成的 Bearer 凭据，服务端根据凭证解析当前 `ProjectApp`，通过顶层 `agent` 使用该应用绑定的知识库及已授权的只读业务能力。内置能力工具不作为独立 MCP 入口暴露。

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
agent: decide -> respond
       decide -> execute -> decide（根据结果继续或结束）

knowledge_qa: plan_query -> plan_retrieval -> retrieve_knowledge -> compose_result
```

主 Agent 通过内置工具 `search_knowledge` 和 `query_business_data` 调用现有知识与业务子图。
工具定义集中维护能力契约，主提示词使用通用决策规则；独立调用并行执行，后续调用可引用已完成结果。
生产入口准备当前应用的授权能力摘要，原有服务继续负责权限校验和审计。
规划模型须支持原生工具调用及 JSON 对象输出模式。默认限制为 6 次模型决策、8 次顶层调用、24 个执行操作、3 路并发、单次能力调用 90 秒及执行阶段 240 秒；内部检索批次和业务接口调用计入执行操作预算，最终回复另有 60 秒超时。 最终交付 JSON 校验失败时，每次决策最多纠正两次；每次模型调用均计入上述轮次和时间预算。纠正耗尽后保留已有结果，明确返回部分完成或失败。

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
