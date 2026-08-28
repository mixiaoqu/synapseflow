FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PYTORCH_CPU_FIND_LINKS=https://mirrors.aliyun.com/pytorch-wheels/cpu/
ARG TORCH_VERSION=2.11.0+cpu

ENV HF_HOME=/models/huggingface
ENV HF_HUB_DOWNLOAD_TIMEOUT=600
ENV HF_HUB_ETAG_TIMEOUT=60
ENV PYTHONUNBUFFERED=1
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_DEFAULT_TIMEOUT=600
ENV RERANK_MODEL=BAAI/bge-reranker-v2-m3
ENV RERANK_USE_FP16=false
ENV RERANK_MODEL_LOAD_RETRIES=10
ENV RERANK_MODEL_LOAD_RETRY_DELAY=15

RUN pip install --no-cache-dir \
    -i ${PIP_INDEX_URL} \
    --find-links ${PYTORCH_CPU_FIND_LINKS} \
    torch==${TORCH_VERSION}

RUN pip install --no-cache-dir \
    -i ${PIP_INDEX_URL} \
    fastapi \
    "uvicorn[standard]" \
    FlagEmbedding==1.3.5 \
    "transformers>=4.36,<5" \
    sentencepiece

COPY app.py /app/app.py

EXPOSE 8012

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8012"]
