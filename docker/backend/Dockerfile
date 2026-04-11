# syntax=docker/dockerfile:1
# BuildKit 缓存：export DOCKER_BUILDKIT=1 或 Docker 24+ 默认开启
#
# 国内构建慢时可在项目根 .env 设 UV_INDEX_URL 后 compose build，或：
# docker build --build-arg UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple ...
FROM python:3.11-slim-bookworm

WORKDIR /app

ARG UV_INDEX_URL=https://pypi.org/simple
ENV UV_INDEX_URL=${UV_INDEX_URL}

RUN python -m pip install --no-cache-dir --index-url "${UV_INDEX_URL}" "uv>=0.7,<1"

ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_CONCURRENT_DOWNLOADS=2 \
    UV_CONCURRENT_BUILDS=1

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
