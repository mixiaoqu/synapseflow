FROM python:3.11-slim-bookworm

WORKDIR /app

RUN python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uv==0.10.9

ENV UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
ENV PATH="/app/.venv/bin:$PATH" \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_HTTP_TIMEOUT=600 \
    HF_HOME=/app/.cache/huggingface

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
