# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Common commands

### Backend
- Install backend dependencies for development: `cd backend && uv sync --all-extras`
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
- Build the frontend: `cd frontend && pnpm build`
- Lint the frontend: `cd frontend && pnpm lint`

### Docker / infrastructure
- Start PostgreSQL only: `docker-compose up -d postgres`
- Start the full stack: `docker-compose up -d`
- Stop the stack: `docker-compose down`

The root `Makefile` mirrors some of this, but it uses `npm` for frontend commands. Prefer `pnpm` when working in `frontend/` because the repo uses `pnpm-lock.yaml` and the Docker setup also runs `pnpm`.

## Architecture overview

This is a two-app monorepo:
- `backend/`: FastAPI + LangGraph + PostgreSQL/pgvector
- `frontend/`: Next.js 15 App Router dashboard

### Backend request flow
Backend requests generally flow like this:

`app/api/v1/endpoints/*` -> `app/application/*_service.py` -> LangGraph workflow in `app/agents/graphs/*` -> feature nodes in `app/agents/nodes/*` -> shared retrieval/indexing/domain services in `app/services/*`

Important anchors:
- `backend/app/main.py` boots FastAPI, CORS, `/preview` static files, and the versioned API router.
- `backend/app/api/v1/router.py` registers auth, kb-chat, kb-curation, revision, prototype, documents, teams, and knowledge-bases endpoints.
- `backend/app/application/agent_service.py` builds the shared workflow context/state used by the application services.

### Workflow system
All major agent workflows are registered centrally in `backend/app/agents/runtime/factory.py`.

Current workflow IDs and shapes:
- `kb_chat`: `retrieve -> answer`
- `kb_curation`: `query_optimizer -> retrieve -> answer -> evaluate`, looping back to `query_optimizer` until the answer passes evaluation or `max_iterations` is reached
- `suggest_revision`: `parse_suggestions -> analyze_document -> locate_edits -> revise`
- `doc_to_prototype`: a linear seven-step pipeline from chunk preparation to prototype generation

Shared runtime pieces:
- `backend/app/agents/runtime/context.py`: base workflow context (`user_id`, `team_id`, `knowledge_base_id`, `request_id`, `run_id`, `metadata`, `messages`)
- `backend/app/agents/runtime/events.py`: canonical SSE envelope for streaming workflows
- `backend/app/application/stream_events.py`: helper emitters used by streaming services
- `backend/app/application/workflow_meta.py`: user-facing node labels and model metadata for streamed UIs

When changing a streaming workflow, keep the backend SSE envelope compatible with the frontend parser in `frontend/lib/stream/sse.ts`.

### Retrieval and knowledge-base pipeline
Knowledge-base chat and curation share the same retrieval/indexing backbone:
- `backend/app/services/kb_retrieval.py`: vector/hybrid retrieval, optional reranking, empty-KB/no-hit detection, and prompt context budget trimming
- `backend/app/services/document_indexer.py`: semantic chunking, embedding generation, batch indexing, and reindexing
- `backend/app/db/models.py`: core relational model (`KnowledgeBase`, `Document`, `Embedding`, plus team/user membership tables)

The main mental model is:

`knowledge base -> documents -> chunk embeddings -> retrieval context -> answer/evaluation`

### KB curation specifics
`kb_curation` is an admin workflow, not just a chat variant.

Its state in `backend/app/agents/states/kb_curation_state.py` carries:
- the original and optimized query
- retrieved docs and assembled prompt context
- answer and confidence score
- iteration count / max iterations
- `iteration_history`
- `last_evaluation_feedback`
- accumulated `document_issues`

`backend/app/agents/nodes/kb_curation/evaluate.py` already extracts structured `document_issues` and produces actionable `suggestion` text for the next optimization round. `backend/app/application/kb_curation_service.py` maps this state to the API response and streaming summaries.

### Frontend structure
The frontend is an authenticated dashboard app.

Important anchors:
- `frontend/app/(dashboard)/layout.tsx`: authenticated shell and left navigation for the main product surfaces
- `frontend/lib/api/client.ts`: fetch wrapper with bearer auth, JSON helpers, multipart upload, and `postStream`
- `frontend/lib/stream/sse.ts`: manual SSE parsing over `fetch` streams (the app does not use `EventSource`)

Pattern:
- pages in `frontend/app/(dashboard)/*/page.tsx` are mostly composition layers
- feature logic lives in `frontend/hooks/*`
- HTTP integrations live in `frontend/lib/api/*`
- prototype generation keeps client-side workflow state in a Zustand store

Current integration notes:
- KB chat uses streaming.
- KB curation exposes both `/invoke` and `/stream`, but the current hook `frontend/hooks/useKbCuration.ts` uses the synchronous `invoke` path.
- Prototype generation streams multipart upload results from `/api/v1/prototype/generate/stream/file`.

## Repo-specific notes

- The READMEs are useful for setup, but some backend structure references are stale. Prefer the current code layout under `backend/app/agents/graphs`, `backend/app/application`, and `backend/app/agents/runtime`.
- `frontend/package.json` does not define a test script; the backend test suite is the main automated test surface currently present in the repo.
