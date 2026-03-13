# Python Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装uv
RUN pip install uv

# 复制依赖文件
COPY pyproject.toml ./

# 安装依赖
RUN uv pip install --system -r pyproject.toml

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令（由docker-compose覆盖）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
