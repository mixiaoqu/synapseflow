FROM python:3.11-slim-bookworm

WORKDIR /app

ARG UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG UV_VERSION=0.7.13

ENV UV_INDEX_URL=${UV_INDEX_URL}

RUN --mount=type=cache,target=/root/.cache/pip,id=synapseflow-pip-cache \
    python -m pip install \
    --disable-pip-version-check \
    --index-url "${UV_INDEX_URL}" \
    "uv==${UV_VERSION}"

ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_CONCURRENT_DOWNLOADS=2 \
    UV_CONCURRENT_BUILDS=1 \
    UV_HTTP_TIMEOUT=180

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv,id=synapseflow-uv-cache \
    uv sync --frozen --no-install-project --no-dev --index "${UV_INDEX_URL}"

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv,id=synapseflow-uv-cache \
    uv sync --frozen --no-dev --index "${UV_INDEX_URL}"

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]