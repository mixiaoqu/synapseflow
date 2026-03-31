# SynapseFlow

基于LangGraph 0.6.0的智能体协同系统

## 🚀 项目简介

SynapseFlow是一个智能体协作平台，实现三大核心场景：

1. **迭代问答**：多轮知识库问答，自动优化答案质量
2. **递归修订**：自动检测文档遗漏，智能补充完善
3. **文档转原型**：需求文档自动生成可交互的HTML原型

## 🛠️ 技术栈

### 后端
- **框架**：Python 3.11 + FastAPI
- **智能体**：LangGraph 0.6.0
- **LLM**：Deepseek + Kimi
- **数据库**：PostgreSQL + pgvector
- **包管理**：uv

### 前端
- **框架**：Next.js 15 + React 19
- **样式**：Tailwind CSS + shadcn/ui
- **语言**：TypeScript

## 📦 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- uv（Python包管理器）

### 1. 克隆项目

```bash
cd d:\SynapseFlow
```

### 2. 配置环境变量

**后端：**
```bash
cd backend
cp .env.example .env
# 编辑.env文件，填入API密钥
```

**前端：**
```bash
cd frontend
cp .env.local.example .env.local
```

### 3. 启动数据库

```bash
docker-compose up -d postgres
```

### 4. 安装后端依赖

```bash
cd backend

# 安装uv（如果还没安装）
# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 安装依赖
uv sync

# 运行数据库迁移
uv run alembic upgrade head
```

### 5. 启动后端服务

```bash
cd backend
uv run uvicorn app.main:app --reload
```

后端将在 http://localhost:8000 启动

API文档：http://localhost:8000/api/v1/docs

### 6. 安装前端依赖

```bash
cd frontend
pnpm install
```

### 7. 启动前端服务

```bash
cd frontend
pnpm dev
```

前端将在 http://localhost:3000 启动

## 🐳 使用Docker（推荐）

```bash
# 一键启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 📚 项目结构

```
SynapseFlow/
├── backend/              # Python后端
│   ├── app/
│   │   ├── agents/      # LangGraph智能体
│   │   ├── api/         # FastAPI路由
│   │   ├── core/        # 核心配置
│   │   └── models/      # 数据模型
│   └── pyproject.toml
├── frontend/            # Next.js前端
│   ├── app/            # App Router
│   └── components/     # React组件
├── docker/             # Docker配置
└── docker-compose.yml
```

## 🎯 API端点

### 迭代问答
- `POST /api/v1/kb-curation/invoke` - 同步知识库治理问答
- `POST /api/v1/kb-curation/stream` - 流式知识库治理问答
- `POST /api/v1/kb-chat/invoke` - 同步知识库问答
- `POST /api/v1/kb-chat/stream` - 流式知识库问答

### 文档修订
- `POST /api/v1/revision/suggest` - 用户建议驱动修订（文档 + 建议 → 修订稿 + 遗漏提示）

### 文档转原型
- `POST /api/v1/prototype/generate` - 生成原型
- `POST /api/v1/prototype/generate/stream` - 流式生成

## 🧪 运行测试

```bash
cd backend
uv run pytest
```

## 📖 文档

详细文档请查看 `docs/` 目录：

- [架构设计](docs/architecture.md)
- [智能体文档](docs/agents/)
- [API文档](docs/api/)

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License
