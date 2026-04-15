ARG UV_VERSION=0.10.9
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin

FROM python:3.11-slim-bookworm AS builder

ARG UV_INDEX_URL=https://pypi.org/simple

COPY --from=uv-bin /uv /uvx /bin/

WORKDIR /app

ENV UV_INDEX_URL=${UV_INDEX_URL} \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_HTTP_TIMEOUT=600 \
    HF_HOME=/root/.cache/huggingface

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv,id=synapseflow-uv-cache \
    uv sync --frozen --no-install-project --no-dev --index "${UV_INDEX_URL}"

COPY . ./

RUN --mount=type=cache,target=/root/.cache/uv,id=synapseflow-uv-cache \
    uv sync --frozen --no-dev --index "${UV_INDEX_URL}"

FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/app/.cache/huggingface

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
