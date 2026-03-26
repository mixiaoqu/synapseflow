.PHONY: help install dev-backend dev-frontend dev test clean docker-up docker-down docker-build-lowmem

help:
	@echo "SynapseFlow - 可用命令："
	@echo "  make install       - 安装所有依赖"
	@echo "  make dev-backend   - 启动后端开发服务器"
	@echo "  make dev-frontend  - 启动前端开发服务器"
	@echo "  make dev          - 同时启动前后端"
	@echo "  make test         - 运行测试"
	@echo "  make docker-up    - 启动Docker服务"
	@echo "  make docker-down  - 停止Docker服务"
	@echo "  make docker-build-lowmem - 分步构建镜像（2核2G 等小内存机器，避免并行 OOM）"
	@echo "  make clean        - 清理临时文件"

install:
	@echo "安装后端依赖..."
	cd backend && uv sync
	@echo "安装前端依赖..."
	cd frontend && npm install
	@echo "✅ 依赖安装完成"

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build-lowmem:
	docker compose build backend
	docker compose build frontend

clean:
	@echo "清理临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf backend/previews/*
	rm -rf backend/uploads/*
	@echo "✅ 清理完成"
